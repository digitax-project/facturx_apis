# n8n node plan: DigiTax invoice Phase 1

## Inputs

- binary invoice file
- `organizationId`
- approved organization master-data reference
- optional `correlationId`

## Main path

1. **Trigger: invoice received** - webhook, mailbox, or manual test trigger.
2. **Create run context** - run ID, timestamp, filename, MIME type, SHA-256.
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
8. **Execute C01-C08** - deterministic controls with explicit applicability.
9. **Aggregate Phase 1 status** - use the four-value status contract.
10. **Optional VAT-ID check** - only when applicable and configured; merge
    result into the report before final aggregation.
11. **Optional Reqeli analysis** - disabled by default; invoke only for selected
    findings and retain its output as suggestions.
12. **Persist evidence package** - source hash/reference, canonical JSON,
    control report, rule versions, execution timestamps, and service responses.
13. **Return human-review payload** - status, findings, evidence, suggestions.

## Error workflow

- retry transient API failures with bounded exponential backoff
- never retry deterministic validation failures
- route exhausted service failures to `nicht_pruefbar`
- preserve the failed step, stable error code, and correlation ID
- do not continue to approval, booking, or payment

## Required environment/credentials

- `FACTURX_API_BASE_URL`
- `PDF_EXTRACTION_API_BASE_URL`
- organization master-data credential/reference
- optional VAT validation credential
- optional `REQELI_API_BASE_URL`
- evidence repository credential

## Output

The workflow returns `canonicalInvoice`, `phase1ControlReport`, and
`evidencePackageRef`. It never returns a final accounting approval.
