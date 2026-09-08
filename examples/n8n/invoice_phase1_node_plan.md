# n8n node plan: DigiTax invoice Phase 1

## Inputs

- binary invoice file
- `organizationId`
- approved organization master-data reference
- optional `correlationId`

**P2.1 Wave 1 A5 Stage 1 (implemented, Flow 1a only):** `correlationId` and
`processInstanceId` are always *generated* by the run-context node
(`crypto.randomUUID()`, no weak fallback) -- never accepted from the
caller. `correlationId` is sent to the Phase 1 API as `X-Correlation-ID`;
`processInstanceId` is evidence-only, never sent to the API.
**Flow 1b is explicitly unaffected by this or any other Stage 0/1
change** -- see `examples/n8n/README.md`'s "P2.1 Wave 1 A5 Stage 0/1"
section.

## Main path

1. **Trigger: invoice received** - webhook, mailbox, or manual test trigger.
2. **Create run context** - run ID, timestamp, filename, MIME type, SHA-256,
   plus (Stage 1) secure `correlationId`/`processInstanceId` generation.
3. **Validate envelope** - file limits, allowed MIME types, encryption state.
4. **Inspect document** - call `/v1/invoices/inspect`.
5. **Switch by detected source**:
   - `factur-x`: extract embedded XML, validate, normalize.
   - `xrechnung`: call the separate supported validator; otherwise return
     `UNSUPPORTED_XRECHNUNG_VALIDATOR` and `nicht_pruefbar`.
   - `pdf`: call OCR/LLM extraction adapter, then normalize.
   - `unknown`: return `nicht_pruefbar`.
6. **Validate canonical JSON** - fail closed on schema errors.
7. **Load organization master data** - versioned snapshot for this run.
8. **Load control profile** - resolve the versioned control selection for the
   organization and invoice context.
9. **Determine applicability** - mark each selected control as applicable or
   not applicable using explicit rules.
10. **Execute selected controls** - run deterministic controls and retain
   control/rule versions.
11. **Optional VAT-ID check** - only when applicable and configured; merge its
    result into the control results.
12. **Aggregate Phase 1 status** - use the four-value status contract.
13. **Optional Reqeli analysis** - disabled by default; invoke only for selected
    findings and retain its output as suggestions.
14. **Persist evidence package** - source hash/reference, canonical JSON,
    control report, rule versions, execution timestamps, and service responses.
15. **Return human-review payload** - status, findings, evidence, suggestions.

## Error workflow

- retry transient API failures with bounded exponential backoff
- never retry deterministic validation failures
- route exhausted service failures to `nicht_pruefbar`
- preserve the failed step, stable error code, and correlation ID
- do not continue to approval, booking, or payment

## Required environment/credentials

- `FACTURX_API_BASE_URL`
- `FACTURX_RISK_REVIEW_API_BASE_URL` -- base URL of the accepted DigiTax
  Risk Review service (`POST /v1/risk-review`), used only by Batch Item
  v1.1.0's gated advisory step (A6a synthetic TCMS demo); never called for a
  clean (`unauffaellig`) report. That service is a separate repository, not
  bundled or started by any compose file in this repository.
- `PDF_EXTRACTION_API_BASE_URL`
- organization master-data credential/reference
- optional VAT validation credential
- optional `REQELI_API_BASE_URL`
- evidence repository credential

The current `examples/n8n/digitax_invoice_intake.json` draft (not yet rewired
to the endpoints above) additionally requires, since sanitization replaced
its hardcoded values:

- `TCMS_FRAMEWORK_BASE_URL`, `TCMS_ORGANIZATION_ID`, `TCMS_PROCESS_ID` -- the
  TCMS-Framework webhook target (was `host.docker.internal:3000`)
- `REQELI_API_BASE_URL` -- the Reqeli analysis endpoint (was
  `host.docker.internal:8090`)
- `REQELI_ENABLED` -- must be the string `"true"` to allow Reqeli to run at
  all; disabled by default per AGENTS.md, ANDed with the workflow's own
  business-rule trigger

The Reqeli request body no longer carries database credentials of any kind
(an earlier sanitization pass replaced the hardcoded DSN with an
env-var-templated one, which still shipped a live DB password over HTTP on
every call -- caught in review). It now sends `connection_ref: "tcms-primary"`,
an opaque reference; Reqeli must resolve it against its own server-side
credential configuration, not receive a connection string from n8n at all.

## Output

The workflow returns `canonicalInvoice`, `phase1ControlReport`, and
`evidencePackageRef`. It never returns a final accounting approval.

**P2.1 Wave 1 A5 Stage 1 (implemented, Flow 1a only):** exactly one
schema-valid `ActivityExecution` object (P2.1
`activity-execution.schema.json` v1.0.0) is assembled and validated per
Phase-1 run, via the shared, versioned
`digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json`
subworkflow -- see `examples/n8n/README.md`. It is not yet persisted to any
Evidence Store (out of this implementation's authorized scope, blocked
until Stage 3).
