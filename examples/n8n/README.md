# n8n integration examples

## digitax_invoice_intake.json

A sanitized export of the current DigiTax invoice-intake draft (mailbox
intake, invoice classification, OCR/LLM extraction via Gemini, K1/K2 master
data and VAT-ID matching, Reqeli analysis, TCMS-Framework and Excel
reporting). It is a credential-free reference for the existing workflow
shape, not yet rewired to call this repository's `/v1/invoices/*` endpoints
-- that rewiring is tracked as follow-up work once the Phase 1 API
(`facturx/phase1/`) is in place; `invoice_phase1_node_plan.md` remains the
authoritative blueprint for that step.

Sanitization removed, before this file was ever committed:
- a live-looking Postgres DSN with embedded credentials, sent to Reqeli on
  every request. This was **not** fixed by templating the DSN through
  environment variables -- that still ships a live DB password over HTTP on
  every call. Instead, Reqeli now receives an opaque
  `connection_ref: "tcms-primary"` and is expected to resolve its own DB
  credentials server-side; no connection string of any kind is transmitted.
- real Microsoft Outlook/Excel/Google credential references, a real
  SharePoint personal-folder URL, an Outlook mailbox deep link, and the
  n8n instance identifier
- the real organization name and two real-looking addresses (replaced with
  the repo's fictional "Unternehmen X" convention)
- hardcoded `host.docker.internal` service URLs (replaced with
  `{{ $env.* }}` expressions; required variables are documented in
  `invoice_phase1_node_plan.md`)

It also adds one behavior change beyond sanitization: the "Trigger Reqeli?"
node now additionally requires `$env.REQELI_ENABLED == "true"`, ANDed with
the existing business-rule trigger, so Reqeli is disabled by default per
`AGENTS.md`.

**Import verification:** real, not just structural. The local `n8n` CLI is
blocked in this environment (`n8n import:workflow` requires Node >=22.16;
this machine has 22.15.0), so verification instead used the official
`n8nio/n8n` Docker image (checked version 2.33.6):

```
docker run --rm -v "<path-to-file>:/data/workflow.json:ro" n8nio/n8n \
  import:workflow --input=/data/workflow.json
```

Result: `Successfully imported 1 workflow.`, confirmed listable afterward
(`list:workflow` returned `digitax-invoice-intake-phase1|DigiTax Invoice
Intake (Phase 1, sanitized)`). This confirms the file is valid,
importable n8n workflow JSON. It does not confirm the workflow runs
correctly end-to-end against live services (Outlook, Gemini, BZSt, Reqeli,
Excel) -- those credentials/URLs are placeholders by design and must be
supplied by whoever imports it. `tests/test_n8n_workflow_export.py` is a
structural regression guard (JSON validity, no re-introduced secrets, node
graph integrity, Reqeli gate present) that runs in CI; it is not a
substitute for the import test above.

## digitax_invoice_phase1_structured_demo.json

A credential-free, self-contained n8n workflow that runs the real Phase 1
API end to end for a structured EN16931 invoice:

```
Start (Manual Trigger)
  -> Select Invoice (Demo Fixture)      -- embedded synthetic EN16931 XML
  -> GET /capabilities
  -> Check Factur-X Version             -- surfaces the legacy-baseline note
  -> POST /v1/invoices/process
  -> Build Review Summary
  -> Status Routing (Switch on routing)
       -> Human Review - Standard        (unauffaellig)
       -> Human Review - Prioritized     (klaerung_erforderlich / nicht_pruefbar
                                          content findings from the API itself)
       -> Human Review - Unclassified    (any other routing value, including
          (fallback)                     technical API failures, see below)
```

The embedded invoice is a synthetic, fictional fixture ("Unternehmen X") so
the workflow is fully reproducible via `n8n execute` with no filesystem
mounts and no real invoice data. It is a deterministic regression/CI
demo, not a stand-in for a real user-facing upload -- a separate
operator-facing workflow with a real binary file input (Form Trigger or
similar) is tracked as follow-up work in `AGENT_PROMPT.md`.

### Fail-safe API-error handling

Both HTTP nodes (`GET /capabilities`, `POST /v1/invoices/process`) are
configured with:

- `retryOnFail: true`, `maxTries: 3`, `waitBetweenTries: 1000` -- a bounded
  retry for transient service failures only. Deterministic validation
  failures already come back from the API as an ordinary `200` response with
  a `nicht_pruefbar`/`klaerung_erforderlich` report and are never retried.
- `onError: "continueErrorOutput"` -- once retries are exhausted, the node's
  error output (instead of failing the whole execution) feeds a dedicated
  Code node (`API Failure - Capabilities` / `API Failure - Process Invoice`)
  that builds a safe human-review payload:
  - `status: "nicht_pruefbar"`
  - `routing: "technical_review"` (deliberately not `standard_review` or
    `prioritized_review`, so it falls through the existing Status Routing
    switch's fallback output into `Human Review - Unclassified (fallback)`
    without duplicating that switch's logic)
  - `failedStep` -- which HTTP call failed
  - `errorCode` -- a stable code (`CAPABILITIES_SERVICE_UNAVAILABLE` /
    `INVOICE_PROCESSING_SERVICE_UNAVAILABLE`)
  - `correlationId` -- a fresh UUID (or a timestamp-based fallback if
    `crypto.randomUUID` isn't available) so a failed run can be traced
  - `explanation` -- a human-readable summary of the underlying error

The workflow never ends as an unhandled execution error: an unreachable API
still finishes at `Human Review - Unclassified (fallback)` with a
`nicht_pruefbar` payload, same as any other technical/unclassified outcome.

### Docker import and run

The local `n8n` CLI needs Node >=22.16; verify against the pinned
`n8nio/n8n:2.33.6` image instead, matching the version this project targets.
n8n 2.33.6 blocks `$env.*` expression access by default
(`ExpressionError: access to env vars denied`) -- this workflow reads its API
base URL via `{{ $env.FACTURX_API_BASE_URL }}`, so that restriction must be
explicitly relaxed for the container, or the base URL must be moved to an
n8n Variable/credential instead (recommended for a real deployment; not done
here to keep the demo a single portable JSON file with no pre-seeded
instance state).

Import:

```
docker run --rm \
  -v "<path-to-repo>/examples/n8n/digitax_invoice_phase1_structured_demo.json:/data/workflow.json:ro" \
  n8nio/n8n:2.33.6 \
  import:workflow --input=/data/workflow.json
```

Run (against a Phase 1 API already listening on the host, e.g.
`python run.py` at `http://localhost:6969`):

```
docker run --rm \
  -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
  -e FACTURX_API_BASE_URL=http://host.docker.internal:6969 \
  -v "<path-to-repo>/examples/n8n/digitax_invoice_phase1_structured_demo.json:/data/workflow.json:ro" \
  n8nio/n8n:2.33.6 \
  sh -c "n8n import:workflow --input=/data/workflow.json && n8n execute --id=digitax-invoice-phase1-structured-demo"
```

`N8N_BLOCK_ENV_ACCESS_IN_NODE=false` is only needed because this demo reads
its base URL from `$env.*` directly; it is not required if you switch the
URL to an n8n Variable or credential.

**Import verification:** real, via the official `n8nio/n8n:2.33.6` Docker
image (checked version). `tests/test_n8n_structured_demo_workflow.py` is the
CI structural guard (JSON validity, no secrets/hardcoded hosts, graph
integrity, configurable API URL, bounded retry + error-branch wiring, both
review routes plus the technical-failure fallback all present); it is not a
substitute for the real import/execute evidence, which is recorded in
`coordination/claude-codex/handover-log.md`.

## General rule

Workflow exports must contain no credentials, API keys, real invoice data,
host-specific URLs, or organization secrets. Use environment variables or n8n
credentials for all endpoints.
