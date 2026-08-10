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
demo, not a stand-in for a real user-facing upload -- see
`digitax_invoice_phase1_upload_demo.json` below for the real-upload,
operator-facing counterpart.

**2026-08-10 capability-field fix:** PR #6 replaced the old flat
`structuredFormats["factur-x"].xsdVersion`/`.legacyBaseline` fields with a
per-level `xsdBaselines` map (each recognized profile is genuinely on its
own XSD baseline now). The `Check Factur-X Version` node read the old
fields and silently printed `"Using validator baseline: XSD undefined."`
against the merged API -- reproduced against real `n8nio/n8n:2.33.7`, then
fixed to read `xsdBaselines.en16931.version`/`.legacyBaseline` and to also
surface `schematron.status`/`.artifactVersion`/`.engine`.

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

## digitax_invoice_phase1_upload_demo.json

The operator-facing counterpart to the structured regression demo above:
accepts a **real** binary invoice upload and calls the same Phase 1 API.
The upload form offers two fictional contexts: Unternehmen X selects the
starter profile, while Unternehmen Y selects the operating profile with the
additional approved-supplier control `ORG-002`. The workflow itself remains
organization-neutral and forwards the selected `organizationId` dynamically.

```
Webhook: Invoice Upload (POST multipart/form-data)
  -> Build Run Context           -- correlation ID before any API call,
                                     filename/MIME type, organizationId
                                     (explicit, or the fictional default
                                     only under demoMode=true)
  -> Validate Upload Request     -- missing file / missing org context:
       -> [invalid] Build Invalid Upload Payload     never retried, no API call made
       -> [valid]   GET /capabilities
  -> Evaluate Capability Gate    -- EN16931 processable? Schematron implemented?
       -> [absent]  Build Capability Gate Failure Payload   routes safely to technical_review
       -> [present] POST /v1/invoices/process
  -> Classify Process Response   -- 2xx success / 4xx-5xx "not retried" failure
  -> Build Browser Response      -- single convergence point: renders full HTML
                                     (invoice identity, parties, totals, profile,
                                     XSD/Schematron version, control table)
  -> Respond to Webhook (HTML)
  -> Status Routing (Switch, 4 explicit outputs)
       -> Human Review - Standard
       -> Human Review - Prioritized
       -> Human Review - Technical      (explicit route, not a fallthrough)
       -> Human Review - Unknown (fallback)
```

Every failure and success path (`Build Invalid Upload Payload`, both
`Build Technical Failure Payload (...)` nodes, `Build Capability Gate
Failure Payload`, `Classify Process Response`) feeds the *same* `Build
Browser Response` node, which feeds the *same* `Respond to Webhook` and
`Status Routing` -- no duplicated response-building or routing logic.

### Why a Webhook, not a Form Trigger

Both trigger types need the same production-activation step (the workflow
must be published/active for their real HTTP endpoint to work -- a test-mode
listen-once endpoint isn't scriptable). A Webhook is exercisable headlessly
with curl/PowerShell the same way this whole project's evidence has been
gathered throughout (see `digitax_invoice_phase1_structured_demo.json`'s
`n8n execute` verification and PR #5's real-execution evidence); a Form
Trigger offers no advantage for that and adds UI-only surface. The minimal
static page `phase1_upload_demo_page.html` (open directly in a browser, no
server, no build step) gives the human-browser demo experience by simply
POSTing multipart form data to the same webhook.

### Fail-safe design

- **Deterministic input errors never reach the API.** No file, or no
  `organizationId`/`demoMode`, is caught in `Validate Upload Request` and
  routed straight to `technical_review` -- confirmed by real timing
  evidence: this path returns in ~0.075s (no network call, obviously no
  retry).
- **A real 4xx/5xx from the API is never retried either.** Both
  `GET /capabilities` and `POST /v1/invoices/process` use
  `options.response.neverError: true` + `fullResponse: true`, so *any* HTTP
  response -- including 400/415/503 -- lands as normal node output with a
  `statusCode`, never as a thrown error. Only a genuine connection-level
  failure (`onError: "continueErrorOutput"`, `retryOnFail`, `maxTries: 3`,
  `waitBetweenTries: 1000`) is retried. Verified with real timing: a real
  API `415` rejection (garbage upload content) returns in ~0.09s; a real
  unreachable-service failure (API container stopped) takes ~14.8s,
  consistent with three bounded retries against a real DNS/connection
  failure -- proof the two cases are genuinely handled differently, not
  just labeled differently.
- **A missing required capability routes safely, not silently.**
  `Evaluate Capability Gate` checks `processableLevels` contains `en16931`
  and `schematron.status === "implemented"` before ever calling
  `/v1/invoices/process`.
- **`technical_review` is an explicit Switch rule**, not a fallthrough to
  the unknown-value fallback (unlike the regression demo's deliberately
  simpler design) -- `Human Review - Technical` and `Human Review - Unknown
  (fallback)` are two distinct terminal nodes.

### Isolated environment: docker-compose.phase1-upload-demo.yml

A separate, self-contained stack -- **never** the pre-existing, separately
managed n8n instance on port 5678 / volume `n8n_data`, which this tooling
never touches:

- `api`: builds the repository's own `Dockerfile`, host port `6970` (not
  `6969`, so it never collides with a manually-run `python run.py`),
  reachable from n8n via the compose network as `http://api:6969`.
- `n8n`: pinned `n8nio/n8n:2.33.7`, host port `5679`, named volume
  `digitax_n8n_phase1_data` (never `n8n_data`).
- Both services have real Docker healthchecks; nothing is imported or
  executed before both report healthy.

Manage it with `examples/n8n/scripts/Manage-Phase1UploadDemo.ps1`
(Windows PowerShell 5.1-compatible):

```powershell
# Build+start both services, wait for real health, import all demo workflows
# idempotently, publish+restart so the upload webhook goes live:
./scripts/Manage-Phase1UploadDemo.ps1 -Action Start

# Two real checks: CLI-execute the regression demo, and a real multipart
# POST to the live upload webhook. Evidence saved under
# output/bpmn/renders/versions/digitax_flow01_n8n/upload-automation/review_evidence/:
./scripts/Manage-Phase1UploadDemo.ps1 -Action SmokeTest

# Stop containers, keep the named volume (workflows/executions persist):
./scripts/Manage-Phase1UploadDemo.ps1 -Action Stop

# Destructive, explicit only -- deletes digitax_n8n_phase1_data after
# re-verifying the exact volume name. Refuses without -Confirm:
./scripts/Manage-Phase1UploadDemo.ps1 -Action Reset -Confirm
```

**Operational note on n8n's CLI:** `n8n import:workflow` always deactivates
the imported workflow, even when the source JSON has `"active": true`
(confirmed empirically -- every import prints `Deactivating workflow ...`).
The upload demo's production webhook therefore needs an explicit
`n8n update:workflow --id=... --active=true` after every import, and a
container restart for that activation to take effect on the already-running
process -- `Start` and any manual re-import both need this sequence; the
script handles it automatically for `Start`.

**Operational note on `n8n execute` against a running instance:** the
main `n8n start` process holds n8n's Task Runners broker on its default
port, which happens to collide with this stack's chosen host port (5679,
purely coincidental). A subsequent `docker exec ... n8n execute` therefore
needs `-e N8N_RUNNERS_BROKER_PORT=15679` (or any free port) to avoid `port
5679 is already in use` -- this didn't surface in PR #5's testing, which
only ever used one-shot `docker run --rm` containers with no already-running
main process to collide with.

### Real execution evidence (2026-08-10, n8n 2.33.7)

Via the isolated stack above, real multipart POSTs to
`http://localhost:5679/webhook/phase1-invoice-upload` (temporary fixtures
derived at test time from the already-accepted embedded XML in
`digitax_invoice_phase1_structured_demo.json`, never committed separately --
see the parallel-agent boundary in `NEXT_JOB_2026-08-10.md`):

| Scenario | Result | Notes |
|---|---|---|
| Valid EN16931 invoice | `unauffaellig` / `standard_review` | Full control table, XSD 1.09 EN16931, Schematron `implemented` |
| Faulty invoice (amount mismatch) | `klaerung_erforderlich` / `prioritized_review` | CAL-003 with formula/expected/actual/difference |
| No `organizationId`, no `demoMode` | `nicht_pruefbar` / `technical_review` | `ORGANIZATION_CONTEXT_REQUIRED`, ~0.075s, no API call |
| Unrecognized file content | `nicht_pruefbar` / `technical_review` | real API `415`, `UNSUPPORTED_CONTENT_TYPE`, ~0.091s, not retried |
| No file uploaded | `nicht_pruefbar` / `technical_review` | `MISSING_INVOICE_FILE` |
| API unreachable | `nicht_pruefbar` / `technical_review` | `CAPABILITIES_SERVICE_UNAVAILABLE`, ~14.8s (bounded retry), recovered immediately on API restart |
| Double import | no duplicates | `n8n list:workflow` shows exactly one entry per workflow id after re-importing both files |

### Batch and profile-comparison demo

Generate the upload-ready hybrid PDFs with:

```bash
python examples/demo/generate_demo_invoices.py --output-dir .demo-output
```

The set contains valid and faulty invoices for both organizations. It covers
required information, arithmetic, buyer master data, supplier master data, and
multiple simultaneous mismatches. The exact sequence, expected findings, and
intended presentation message are documented in
`docs/invoice_phase1/demo_profile_matrix.md`.

Run all generated cases through the live n8n webhook and verify the returned status
and selected profile:

```powershell
./examples/n8n/scripts/Test-Phase1DemoMatrix.ps1
```

The browser dashboard is served by the demo API at
`http://localhost:6970/demo/batch`. Each selected file is sent through the
separate `phase1-invoice-batch-item` n8n webhook. The dashboard performs no
invoice checks itself; it only consolidates API reports and requests an XLSX
serialization for export.

Full detail in `coordination/claude-codex/handover-log.md` and
`output/bpmn/flowcharts/n8n/n8n_flow01_mapping.md`.
`tests/test_n8n_upload_demo_workflow.py` is the CI structural guard; it is
not a substitute for the real evidence above.

## digitax_invoice_phase1_flow1b_pdf_ocr.json

Flow 1b: processes a plain PDF invoice (no embedded structured XML) via
OCR/LLM extraction (Gemini) instead of XML parsing, reusing the four
proven OCR nodes from `digitax_invoice_intake.json` **unmodified**:

```
Webhook: PDF Invoice Upload (POST multipart/form-data, file field "data")
  -> Build Run Context           -- correlation ID before any call,
                                     organizationId (explicit, or the
                                     fictional default only under demoMode=true)
  -> Validate Upload Request     -- missing file / missing org context:
       -> [invalid] Build Invalid Upload Payload    never retried, no call made
       -> [valid]   Resolve Organization Profile (temporary mirror)
  -> Organization Profile Known?
       -> [unknown] Build Unknown Organization Payload
       -> [known]   fix base64 -> Build Gemini Request
                       -> File-Based OCR with Gemini 2.5 (bounded retry, maxTries: 5)
                       -> Gemini Output Parser
  -> Normalize OCR Fields to Canonical Buyer Shape (temporary)
  -> Evaluate ORG-001 (temporary mirror)
  -> Build Review Summary
  -> Build Browser Response      -- single convergence point, HTML, with an
                                     explicit "temporary implementation" notice
  -> Respond to Webhook (HTML)
  -> Status Routing (Switch, 4 explicit outputs)
       -> Human Review - Standard / Prioritized / Technical / Unknown (fallback)
```

`digitax_invoice_intake.json` itself is **untouched** -- it remains the
historical, sanitized reference for the full mailbox-intake workflow this
chain was extracted from. Unrelated scope from that workflow (Outlook
mailbox intake, BZSt VAT lookup, Excel reporting, Reqeli analysis) is not
present here at all, per the task's explicit scope reduction.

### The four reused OCR nodes: byte-for-byte, not just "similar"

`fix base64`, `Build Gemini Request`, `File-Based OCR with Gemini 2.5`, and
`Gemini Output Parser` carry the *exact same* `jsCode`/parameters and node
`id`s as `digitax_invoice_intake.json` -- verified by
`tests/test_n8n_flow1b_workflow.py::test_ocr_nodes_reused_verbatim_from_intake_workflow`,
which diffs the two files directly rather than trusting a copy-paste by eye.
Two consequences worth knowing, not fixed here because the task's explicit
instruction was to reuse this logic, not improve it:

- **The Gemini prompt hint is hardcoded to `Unternehmen X`** (name, two
  approved addresses, VAT ID). Using Flow 1b for a different
  `organizationId` (e.g. `unternehmen-y-demo`) will still work -- ORG-001 is
  evaluated independently downstream against whichever organization was
  actually selected -- but the extraction *guidance* quality may degrade
  for a genuinely different buyer, since the model isn't told to expect one.
- **The upload's binary field must be named `data`**, not `invoiceFile`
  like the Flow 1a upload demo, because that's `fix base64`'s hardcoded
  `binaryPropertyName`. This is a deliberate, documented inconsistency
  across the workflow family, not an oversight.

The one deliberate addition beyond verbatim reuse: `Gemini Output Parser`
gained `onError: "continueErrorOutput"`. It throws by design on malformed
LLM output (invalid JSON, unexpected response shape), and the historical
mailbox-intake workflow had no fail-safe wrapping around that at all. This
workflow must never end as an unhandled execution error, so the thrown
error is now routed to a proper `nicht_pruefbar`/`technical_review` payload.
This is error-handling wiring only -- the parsing logic itself is untouched.

### Missing API contract -- this is a temporary implementation, not a shortcut

`POST /v1/invoices/process` only accepts a file upload, and the shipped
`MockPdfExtractionAdapter` (`facturx/phase1/normalize/pdf_adapter.py`) is
keyed by the SHA-256 of the uploaded bytes with **no seam for an external
caller to inject a real OCR/LLM extraction result**. There is also no API
endpoint exposing organization master data
(`facturx/phase1/organization_master_data.py`) to an external caller. So
Flow 1b **cannot** call the real API to evaluate ORG-001 against genuinely
OCR-extracted fields today -- and it does not pretend to. Instead:

- `Resolve Organization Profile (temporary mirror)` hand-mirrors only the
  `buyer` block of `organization_master_data.py`'s two fictional org
  contexts. This **must be kept in sync by hand** until a real endpoint or
  adapter seam exists -- a genuine, acknowledged maintenance burden, not a
  one-time cost.
- `Evaluate ORG-001 (temporary mirror)` replicates
  `evaluate_org_001()` and its `_check`/`_combine`/`_normalize_for_match`
  helpers from `facturx/phase1/controls/executor.py` line-for-line in
  JavaScript: same 5 buyer fields, same `0.70` confidence threshold, same
  case/whitespace-insensitive comparison, same severity/reason-code shape.
  Verified with real execution (Node.js, not just read-through) in
  `tests/test_n8n_flow1b_workflow.py`.
- The rendered HTML result carries an explicit, prominent banner stating
  this is a temporary n8n-side implementation, so no viewer mistakes it for
  a real API-issued control report.

**What real convergence with Flow 1a would require** (open decision, not
implemented): either (a) a real `PdfExtractionAdapter` the API's existing
dependency-injection seam can select, fed by this workflow's OCR chain, so
`/v1/invoices/process` can be called normally with the original PDF -- or
(b) a narrower endpoint/contract accepting pre-extracted canonical fields
plus their evidence directly. Recorded here and in
`output/bpmn/flowcharts/n8n/n8n_flow01_mapping.md` for Codex/the user to
decide, not silently chosen.

### Confidence: Gemini has no native per-field signal

Unlike the Flow 1a PDF path's `PdfExtractionAdapter` contract (which always
carries a real confidence per field), Gemini's structured-JSON output is
just five key/value pairs with no calibrated confidence at all. This
workflow uses a documented, conservative placeholder: `0.85` (just above
the `0.70` threshold used everywhere else in this project) for any field
Gemini returned a real value for, and `0.0`/`state: "not_extracted"` --
**not** `confirmed_missing` -- for anything Gemini reported as `"not
found"`. The `not_extracted` choice is deliberate: there's no calibrated
signal to trust an LLM's own absence claim as a confirmed business fact
yet, so a missing field always forces `not_reliable`/human review rather
than a confident `MISSING_FIELD` failure. This satisfies the project-wide
rule that low-confidence or missing OCR fields must never auto-pass --
verified with real Node.js execution, not just asserted.

### Import status: imported, credentials pending

Imported as **inactive** into the isolated `digitax-phase1-demo-n8n`
(`n8nio/n8n:2.33.7`) container, confirmed via
`n8n list:workflow --active=false`; re-imported a second time with no
duplicate created. **No Gemini credential is configured in that instance.**
`File-Based OCR with Gemini 2.5` still carries the same
`REPLACE_WITH_YOUR_CREDENTIAL_ID` placeholder as the historical workflow --
nothing was copied from the pre-existing, separately managed `n8n`
container (port 5678) or from anywhere else. Before a real end-to-end run:

1. Open the n8n UI at `http://localhost:5679`.
2. Select **DigiTax Flow 1b - PDF OCR/LLM**.
3. On the `File-Based OCR with Gemini 2.5` node, select or create a real
   **Google Gemini (PaLM) API** credential (Google AI Studio API key).
4. Activate the workflow only after that -- it is deliberately left
   inactive on import per the task's explicit instruction.

Status is **imported, credentials pending** -- not "working." No E2E claim
is made without a credential actually present.

### Verification

- `pytest`: full suite green, including
  `tests/test_n8n_flow1b_workflow.py` (structural checks plus real Node.js
  execution of the ORG-001 evaluator and status aggregator against
  synthetic inputs -- the actual reused JS logic, not a re-implementation
  assumption).
- Real `n8n import:workflow` against pinned `n8nio/n8n:2.33.7` in the
  running isolated container (not a one-shot `--rm` container -- the same
  persistent stack the Flow 1a upload demo already uses).
- Full detail, exact commands, and the "credentials pending" scope in
  `coordination/claude-codex/handover-log.md` and
  `output/bpmn/flowcharts/n8n/n8n_flow01_mapping.md`.

## General rule

Workflow exports must contain no credentials, API keys, real invoice data,
host-specific URLs, or organization secrets. Use environment variables or n8n
credentials for all endpoints.
