# n8n integration examples

## Naming, versioning, and visual structure (2026-08-10 final-demo-ui round)

n8n's native **Folders** feature (and creating additional **Projects**
beyond the default personal one) are gated behind an Enterprise license in
this n8n version (`feat:folders`, `feat:projectRole:admin` -- confirmed by
reading the running container's own `dist/controllers/folder.controller.js`
and `dist/license.js` directly, not assumed). No license key is configured
or available, so this project does not attempt to unlock or bypass that
gate. Instead, workflow organization is achieved entirely through a
**consistent naming convention**, which needs no license and groups
workflows the same way in n8n's flat list:

```
DigiTax | Invoice Phase 1 | Flow 1a | <Workflow> | v<major>.<minor>.<patch>
DigiTax | Invoice Phase 1 | Flow 1b | <Workflow> | v<major>.<minor>.<patch>
```

| Display name | Export filename | Workflow id (stable) | Status |
|---|---|---|---|
| `DigiTax \| Invoice Phase 1 \| Flow 1a \| Structured Regression \| v1.0.0` | `digitax_invoice_phase1_flow1a_structured_regression_v1_0_0.json` | `digitax-invoice-phase1-structured-demo` | helper (inactive, CI/regression only) |
| `DigiTax \| Invoice Phase 1 \| Flow 1a \| Upload Demo \| v1.0.0` | `digitax_invoice_phase1_flow1a_upload_v1_0_0.json` | `digitax-invoice-phase1-upload-demo` | demo-ready (active) |
| `DigiTax \| Invoice Phase 1 \| Flow 1a \| Batch Demo \| v1.0.0` | n/a -- browser page `facturx/phase1/static/batch_demo.html`, not an n8n workflow | n/a | demo-ready (served whenever `FACTURX_ENABLE_DEMO_ENDPOINTS=true`) |
| `DigiTax \| Invoice Phase 1 \| Flow 1a \| Batch Item \| v1.0.0` | `digitax_invoice_phase1_flow1a_batch_item_v1_0_0.json` | `digitax-invoice-phase1-batch-item` | demo-ready (active, subworkflow for Batch Demo) |
| `DigiTax \| Invoice Phase 1 \| Flow 1b \| PDF OCR/LLM Concept \| v0.2.0` | `digitax_invoice_phase1_flow1b_pdf_ocr_concept_v0_2_0.json` | `digitax-invoice-phase1-flow1b-pdf-ocr` | concept (inactive, credentials pending) |
| `DigiTax \| Invoice Phase 1 \| Shared \| Assemble ActivityExecution \| v1.0.0` | `digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json` | `digitax-invoice-phase1-shared-assemble-activity-execution` | demo-ready (active/published -- no webhook, never externally reachable, but n8n 2.33.7's WorkflowPublicationService refuses to let Execute Workflow invoke an unpublished target at all) |

Workflow **ids are deterministic and never change** across a rename --
`n8n import:workflow` upserts by id, so re-importing an updated export
always updates the existing workflow in place, never creates a duplicate
(verified: re-imported all four twice in a row, `n8n list:workflow` shows
exactly one entry per id both times). A patch/minor content change keeps
the same id and bumps the version in the display name; a future
incompatible major version would get a new id.

**Every workflow node** is renamed to a short, action-oriented name with a
stable two-digit phase prefix, and every workflow uses the *same* five
section names, marked with sticky notes on a left-to-right grid (no crossed
connections, no long diagonal edges):

1. `01 Input and context`
2. `02 Intake and normalization`
3. `03 DigiTax controls` (the real Phase-1 API boundary, or -- Flow 1b only
   -- the temporary concept mirror, explicitly labeled as such)
4. `04 Control report and routing`
5. `05 Human review handoff`

Each workflow also carries a **`## VERSION INFO`** sticky note near its
start with: display name + semantic version, status (`demo-ready` /
`helper` / `concept`), input/output boundary, the API/control-contract
version it targets (`catalogVersion`, control profile id/version, or --
Flow 1b -- which control it mirrors and its rule version), last-verified
date, and its own source export filename.

None of this changes topology or control logic -- it is a presentation and
organization pass only. Every functional detail documented below (fail-safe
retry, the missing-API-contract gap, confidence heuristics, etc.) is
unchanged from the prior rounds; only node/workflow names and layout moved.

## P2.1 Wave 1 A5 Stage 0/1: activity binding, ActivityExecution assembly, and evidence-schema vendoring

Implemented against `coordination/control-plane/runs/2026-08-12-p2-implementation-planning/A5/implementation-plan.md`
(A1-accepted `ACCEPTED_FOR_IMPLEMENTATION_PLANNING_BASELINE`) under H1's
Stage 0/1-only authorization
(`coordination/control-plane/runs/2026-08-13-p2-wave1-implementation/A5/human-decision.json`).
**Scope correction accepted for this implementation round:** only
`ActivityExecution` is generated and embedded. `HumanReviewDecision` is
vendored (so the P2.1 schema pair stays atomically hash-pinned) but
deliberately not compiled or embedded anywhere -- Flow 2 / active human
review is out of this implementation's authorized scope, unchanged from the
plan's own Stage 2/3 gating.

### Identity propagation (Flow 1a only)

`01.2 Build run context` (Upload Demo, Batch Item) / `01.3 Build run
context` (Structured Regression -- `01.2` is already the demo-fixture
loader in that workflow) generates two independent, secure identifiers
before any API call:

```javascript
if (typeof crypto === "undefined" || typeof crypto.randomUUID !== "function") {
  throw new Error("SECURE_UUID_UNAVAILABLE: refusing to mint a weak identifier ...");
}
const correlationId = crypto.randomUUID();
const processInstanceId = crypto.randomUUID();
```

No `Math.random()`/timestamp fallback exists anywhere in any of the three
workflows for either identifier -- a missing `crypto.randomUUID` fails
visibly rather than minting a low-entropy identity for evidence (the pinned
`n8nio/n8n:2.33.7` image always exposes it; this is a defensive guarantee,
not an expected runtime path). `correlationId` is sent to the real Phase 1
API as `X-Correlation-ID` on the `03.1 Run DigiTax controls` request;
`processInstanceId` is never sent to the API, only used for evidence.
Flow 1b is **unmodified by this change** -- explicitly out of scope, exactly
as the accepted plan requires.

A new one-line Code node (`02.6 Mark phase1 attempt start` / `01.3 Mark
phase1 attempt start` / `02.9 Mark phase1 attempt start`, named to avoid
each workflow's own existing numbering) captures
`phase1AttemptStartedAt = new Date().toISOString()` immediately before the
API call, and each pre-flight-rejection node captures its own
`gateDecisionAt` at rejection time -- both feed the `startedAt`/`completedAt`
mapping below rather than reusing `receivedAt`.

### Centralized `ActivityExecution` assembly

Every branch node in all three Flow-1a workflows (invalid upload,
capabilities-service failure, capability-gate failure, a 2xx report, a
4xx/5xx API response, and a genuine connection failure) emits only a small,
normalized **outcome envelope** (`outcome`, `report`, `httpErrorCode`,
`n8nErrorCode`, `phase1AttemptStartedAt`/`gateDecisionAt`, plus
Phase-1-business passthrough fields under `phase1Status`/`routing`/... --
deliberately not named `status`/`resultCode`, which are reserved for
`ActivityExecution`'s own fields). No branch node constructs a full
`ActivityExecution` object itself (no branch `jsCode` contains the literal
key `"executionId"`). Every path converges on a `Call Assemble
ActivityExecution` node (`n8n-nodes-base.executeWorkflow`, calling
`digitax-invoice-phase1-shared-assemble-activity-execution` by id), then a
`Merge ActivityExecution into outcome` Code node that reconciles the shared
subworkflow's minimal `{ activityExecution }` return with the branch's own
envelope, before finally reaching each workflow's existing control-report
builder -- which is otherwise **unedited**.

`digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json`
(`DigiTax | Invoice Phase 1 | Shared | Assemble ActivityExecution | v1.0.0`,
`active: true` -- its only trigger is `executeWorkflowTrigger`, so it has no
webhook and is never externally reachable; it must still be
active/published, confirmed against the real pinned n8n 2.33.7 image, whose
`WorkflowPublicationService` refuses to let an Execute Workflow node invoke
an unpublished target at all: `"Workflow is not active and cannot be
executed."`) is the one place this mapping exists:

| `outcome` | `status` | `resultCode` | `startedAt` | `completedAt` |
|---|---|---|---|---|
| `REPORT` (schema-valid `phase1ControlReport`) | `SUCCEEDED` | `report.status` | `report.startedAt` | `report.createdAt` |
| `HTTP_ERROR` (API responded, no report) | `FAILED` | the API's `error_code` (or `HTTP_<status>`) | `phase1AttemptStartedAt` | assembly time |
| `TRANSPORT_FAILURE` (connection failure, not a timeout) | `FAILED` | `INVOICE_PROCESSING_SERVICE_UNAVAILABLE` | `phase1AttemptStartedAt` | assembly time |
| `TIMEOUT` (`ETIMEDOUT`/`ECONNABORTED`, or message matches `/timeout/i`) | `TIMED_OUT` | `INVOICE_PROCESSING_SERVICE_TIMEOUT` | `phase1AttemptStartedAt` | assembly time |
| `PRE_FLIGHT_REJECTED` (the API was never invoked) | `NOT_EXECUTED` | the pre-flight error code | `gateDecisionAt` | `gateDecisionAt` (same instant) |

A 4xx/5xx without a control report is a real `FAILED` `ActivityExecution` --
never `SUCCEEDED` merely because the API responded (`tests/test_n8n_activity_execution_assembly.py::test_http_error_outcome_maps_to_failed_never_succeeded`
is the direct regression guard). `01.1 Assert activity binding published`
throws `ACTIVITY_BINDING_NOT_PUBLISHED` if its embedded binding literals
are null/placeholder or the caller's `workflowId` has no known binding;
`01.4 Validate against ActivityExecution shape` embeds the generated AJV
validator (below) verbatim and throws `ACTIVITY_EXECUTION_SCHEMA_INVALID`
before the object can reach any response or persistence node.

### Activity binding: `examples/n8n/activity_binding.invoice_intake.json`

A generated lockfile, **never hand-edited** -- only
`examples/n8n/scripts/Sync-ActivityBinding.ps1 -Regenerate` may write it, by
(1) reading A6's published `invoice-intake` activity-binding export
(`-SourcePath`/`-SourceUrl`), (2) hashing it, (3) overwriting the vendored
snapshot `examples/n8n/vendor/a6_activity_binding_export.json` with the
export verbatim, (4) deriving `processDefinition`/`activityDefinition`/
`executor` from that snapshot, and (5) filling `workflowBindings[]` by
reading each Flow-1a workflow file's own `id` and `"| vX.Y.Z"` name-suffix
literal directly -- never inventing a value. `provenance` carries **no
generation timestamp** (a fixed `generatorVersion` instead), so two
consecutive `-Regenerate` runs against unchanged inputs are byte-identical,
which is what `-CheckOnly` (regenerate into a temp path from the
*already-committed* vendored snapshot, diff, fail on drift) depends on --
`-CheckOnly` never reads the external A6/`verfahren-builder` source, so a
normal CI checkout of only this repository is sufficient.

**Today's real state:** Wave 1C (`C:\Agentic\verfahren-builder`,
`agent/p2-1-wave1c-invoice-binding-publication`,
`10849bdfaf985d27c751006089b87da8508196b4`) is H1-approved, A1-accepted, and
A7-reconciled, so the lockfile is committed already `PUBLISHED`
(`processId digitax.invoice-intake @ 1.1.1-draft`, `activityId
digitax.invoice-intake.phase1.structured-control @ 1.0.0`, executor
`digitax.invoice.phase1-controls @ 1.1.0`) -- not the accepted plan's
originally-assumed pre-Stage-0 `PENDING_A6_PUBLICATION` placeholder. The
fail-closed guard itself is still proven (via a synthetic "null literal"
fixture fed directly to `01.1`'s own code, in
`tests/test_n8n_activity_binding_manifest.py`), just not by shipping an
actually-unpublished repository state, since Wave 1C was already real
before this Stage 0/1 authorization -- the adaptation
`coordination/control-plane/runs/2026-08-13-p2-wave1-implementation/A5/request.md`
explicitly allows.

### P2.1 schema vendoring and the generated `ActivityExecution` validator

`examples/n8n/vendor/p2_1/` holds immutable, hash-pinned, checked-in copies
of both canonical P2.1 execution-evidence schemas
(`activity-execution.schema.json`, `human-review-decision.schema.json`,
`schema_provenance.json` -- no generation timestamp, `usage` field on each
entry). Only `examples/n8n/scripts/Sync-P2.1Schemas.ps1 -Regenerate` may
write them, copying from the local P2.1 research-workspace package
(`-CheckOnly` never reads that workspace -- CI has no access to it).

`examples/n8n/package.json` (`ajv` + `ajv-formats`, both build-time-only
`devDependencies`, never present in any n8n runtime container) +
`examples/n8n/scripts/generate-evidence-validators.mjs` compile
**only `activity-execution.schema.json`** into
`examples/n8n/generated/validate_activity_execution.generated.js` (plus
`validator_provenance.json`, hash-pinned to the vendored schema, no
timestamp) via AJV's standalone code generation, with `ajv-formats`
registered so `format: "date-time"` is actually enforced (AJV core alone
treats `format` as a no-op without a formats plugin --
`tests/test_n8n_generated_validators.py::test_generated_validator_enforces_date_time_format_via_ajv_formats`
proves it is not silently skipped). The generator also inlines AJV's own
small runtime helpers (`ucs2length`, used by `minLength`/`maxLength`) that
AJV's standalone output would otherwise `require()` at runtime -- the
committed generated file contains **no** `require`/`module`/`import`
anywhere, so it is safe to embed verbatim inside a sandboxed n8n Code node
with `NODE_FUNCTION_ALLOW_EXTERNAL` left unset. `human-review-decision.schema.json`
is vendored (so the schema pair stays atomically hash-pinned) but **no
validator is generated for it** -- `validator_provenance.json` marks its
entry `"status": "DEFERRED_NOT_GENERATED_FLOW_2_OUT_OF_SCOPE"` explicitly,
per this round's scope correction.

The generated validator source is embedded **verbatim** inside the shared
subworkflow's `01.4 Validate against ActivityExecution shape` node
(`tests/test_n8n_generated_validators.py::test_generated_validator_source_embedded_verbatim_in_shared_subworkflow`
catches a regeneration that was not followed by re-embedding).

### Regenerating

```powershell
cd examples/n8n
./scripts/Sync-P2.1Schemas.ps1 -Regenerate          # local, one-time-per-schema-change
npm install && node scripts/generate-evidence-validators.mjs
./scripts/Sync-ActivityBinding.ps1 -Regenerate -SourcePath <path-to-A6-export> -SourceRef <descriptive-ref>
```

Then re-embed the freshly generated `validate_activity_execution.generated.js`
source verbatim into the shared subworkflow's `01.4` node, and the (rarely
changing) binding literals into its `01.1`/`01.3` nodes if the binding
itself changed. CI only ever runs the `-CheckOnly` variants of both sync
scripts plus a regeneration-and-diff of the validator generator -- never
`-Regenerate`, and never a read of either external source
(`work/arbeitsbericht/research/...` or `verfahren-builder`).

## digitax_invoice_intake.json

A sanitized export of the current DigiTax invoice-intake draft (mailbox
intake, invoice classification, OCR/LLM extraction via Gemini, K1/K2 master
data and VAT-ID matching, Reqeli analysis, TCMS-Framework and Excel
reporting). It is a credential-free reference for the existing workflow
shape, not yet rewired to call this repository's `/v1/invoices/*` endpoints
-- that rewiring is tracked as follow-up work once the Phase 1 API
(`facturx/phase1/`) is in place; `invoice_phase1_node_plan.md` remains the
authoritative blueprint for that step. **This file is never renamed or
modified** by the naming/versioning round above -- it stays the untouched
historical source Flow 1b's OCR chain was extracted from (see below).

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

## digitax_invoice_phase1_flow1a_structured_regression_v1_0_0.json

`DigiTax | Invoice Phase 1 | Flow 1a | Structured Regression | v1.0.0` --
a credential-free, self-contained n8n workflow that runs the real Phase 1
API end to end for a structured EN16931 invoice:

```
01.1 Trigger: select invoice (Manual Trigger)
  -> 01.2 Load demo fixture             -- embedded synthetic EN16931 XML
  -> 01.3 Build run context             -- secure correlationId/processInstanceId
  -> 02.1 Read API capabilities
  -> 02.2 Check Factur-X profile        -- surfaces the legacy-baseline note
  -> 02.9 Mark phase1 attempt start
  -> 03.1 Run DigiTax controls          -- POST /v1/invoices/process, sends X-Correlation-ID
  -> 04.1 Build control report
  -> Call Assemble ActivityExecution -> Merge ActivityExecution into outcome
  -> 04.2 Route by review status        (Switch on routing)
       -> 05.1 Human review - standard        (unauffaellig)
       -> 05.2 Human review - prioritized     (klaerung_erforderlich / nicht_pruefbar
                                               content findings from the API itself)
       -> 05.3 Human review - unclassified    (any other routing value, including
                                               technical API failures, see below)
```

The embedded invoice is a synthetic, fictional fixture ("Unternehmen X") so
the workflow is fully reproducible via `n8n execute` with no filesystem
mounts and no real invoice data. It is a deterministic regression/CI
demo, not a stand-in for a real user-facing upload -- see the Upload Demo
workflow below for the real-upload, operator-facing counterpart.

**2026-08-10 capability-field fix:** PR #6 replaced the old flat
`structuredFormats["factur-x"].xsdVersion`/`.legacyBaseline` fields with a
per-level `xsdBaselines` map (each recognized profile is genuinely on its
own XSD baseline now). The capability-check node read the old fields and
silently printed `"Using validator baseline: XSD undefined."` against the
merged API -- reproduced against real `n8nio/n8n:2.33.7`, then fixed to
read `xsdBaselines.en16931.version`/`.legacyBaseline` and to also surface
`schematron.status`/`.artifactVersion`/`.engine`.

### Fail-safe API-error handling

Both HTTP nodes (`02.1 Read API capabilities`, `03.1 Run DigiTax controls`)
are configured with:

- `retryOnFail: true`, `maxTries: 3`, `waitBetweenTries: 1000` -- a bounded
  retry for transient service failures only. Deterministic validation
  failures already come back from the API as an ordinary `200` response with
  a `nicht_pruefbar`/`klaerung_erforderlich` report and are never retried.
- `onError: "continueErrorOutput"` -- once retries are exhausted, the node's
  error output (instead of failing the whole execution) feeds a dedicated
  Code node (`02.3 Handle capabilities failure` /
  `03.2 Handle controls-call failure`) that builds a safe human-review
  payload:
  - `status: "nicht_pruefbar"`
  - `routing: "technical_review"` (deliberately not `standard_review` or
    `prioritized_review`, so it falls through the existing status-routing
    switch's fallback output into the unclassified human-review node
    without duplicating that switch's logic)
  - `failedStep` -- which HTTP call failed
  - `errorCode` -- a stable code (`CAPABILITIES_SERVICE_UNAVAILABLE` /
    `INVOICE_PROCESSING_SERVICE_UNAVAILABLE`)
  - `correlationId` -- a fresh UUID (or a timestamp-based fallback if
    `crypto.randomUUID` isn't available) so a failed run can be traced
  - `explanation` -- a human-readable summary of the underlying error

The workflow never ends as an unhandled execution error: an unreachable API
still finishes at the unclassified human-review node with a `nicht_pruefbar`
payload, same as any other technical/unclassified outcome.

### Docker import and run

The local `n8n` CLI needs Node >=22.16; verify against the pinned
`n8nio/n8n:2.33.7` image instead, matching the version this project targets.
n8n blocks `$env.*` expression access by default
(`ExpressionError: access to env vars denied`) -- this workflow reads its API
base URL via `{{ $env.FACTURX_API_BASE_URL }}`, so that restriction must be
explicitly relaxed for the container, or the base URL must be moved to an
n8n Variable/credential instead (recommended for a real deployment; not done
here to keep the demo a single portable JSON file with no pre-seeded
instance state).

Import:

```
docker run --rm \
  -v "<path-to-repo>/examples/n8n/digitax_invoice_phase1_flow1a_structured_regression_v1_0_0.json:/data/workflow.json:ro" \
  n8nio/n8n:2.33.7 \
  import:workflow --input=/data/workflow.json
```

Run (against a Phase 1 API already listening on the host, e.g.
`python run.py` at `http://localhost:6969`):

```
docker run --rm \
  -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
  -e FACTURX_API_BASE_URL=http://host.docker.internal:6969 \
  -v "<path-to-repo>/examples/n8n/digitax_invoice_phase1_flow1a_structured_regression_v1_0_0.json:/data/workflow.json:ro" \
  n8nio/n8n:2.33.7 \
  sh -c "n8n import:workflow --input=/data/workflow.json && n8n execute --id=digitax-invoice-phase1-structured-demo"
```

`N8N_BLOCK_ENV_ACCESS_IN_NODE=false` is only needed because this demo reads
its base URL from `$env.*` directly; it is not required if you switch the
URL to an n8n Variable or credential.

**Import verification:** real, via the official `n8nio/n8n:2.33.7` Docker
image. `tests/test_n8n_structured_demo_workflow.py` is the CI structural
guard (JSON validity, no secrets/hardcoded hosts, graph integrity,
configurable API URL, bounded retry + error-branch wiring, both review
routes plus the technical-failure fallback all present); it is not a
substitute for the real import/execute evidence, which is recorded in
`coordination/claude-codex/handover-log.md`.

## digitax_invoice_phase1_flow1a_upload_v1_0_0.json

`DigiTax | Invoice Phase 1 | Flow 1a | Upload Demo | v1.0.0` -- the
operator-facing counterpart to the structured regression demo above:
accepts a **real** binary invoice upload and calls the same Phase 1 API.
The upload form offers two fictional contexts: Unternehmen X selects the
starter profile, while Unternehmen Y selects the operating profile with the
additional approved-supplier control `ORG-002`. The workflow itself remains
organization-neutral and forwards the selected `organizationId` dynamically.

```
01.1 Receive invoice upload (POST multipart/form-data)
  -> 01.2 Build run context      -- secure correlationId/processInstanceId before
                                     any API call, filename/MIME type, organizationId
                                     (explicit, or the fictional default
                                     only under demoMode=true)
  -> 01.3 Validate upload request -- missing file / missing org context:
  -> 01.4 Has valid upload?
       -> [invalid] 01.5 Handle invalid upload     never retried, no API call made
       -> [valid]   02.1 Read API capabilities
  -> 02.2 Evaluate capability gate    -- EN16931 processable? Schematron implemented?
  -> 02.4 Required capability present?
       -> [absent]  02.5 Handle capability gate failure   routes safely to technical_review
       -> [present] 02.6 Mark phase1 attempt start
                      -> 03.1 Run DigiTax controls    -- POST /v1/invoices/process,
                                                          sends X-Correlation-ID
  -> 03.2 Classify controls response   -- REPORT / HTTP_ERROR (2xx-with-report vs. not)
  -> 03.3 Handle controls-call failure -- TRANSPORT_FAILURE / TIMEOUT (connection level)
  -> Call Assemble ActivityExecution -> Merge ActivityExecution into outcome
  -> 04.1 Build control report         -- single convergence point: renders full HTML
                                           (invoice identity, parties, totals, profile,
                                           XSD/Schematron version, control table)
  -> 04.2 Respond to browser (HTML)
  -> 04.3 Route by review status (Switch, 4 explicit outputs)
       -> 05.1 Human review - standard
       -> 05.2 Human review - prioritized
       -> 05.3 Human review - technical      (explicit route, not a fallthrough)
       -> 05.4 Human review - unknown
```

Every failure and success path (`01.5 Handle invalid upload`, both
`Handle ... failure` nodes, `02.5 Handle capability gate failure`,
`03.2 Classify controls response`, `03.3 Handle controls-call failure`)
emits only a normalized outcome envelope and feeds the *same* `Call
Assemble ActivityExecution` -> `Merge ActivityExecution into outcome` pair,
which feeds the *same* `04.1 Build control report` node, the *same*
`04.2 Respond to browser`, and the *same* `04.3 Route by review status` --
no duplicated response-building, routing, or `ActivityExecution`-assembly
logic (see "P2.1 Wave 1 A5 Stage 0/1" above).

### Why a Webhook, not a Form Trigger

Both trigger types need the same production-activation step (the workflow
must be published/active for their real HTTP endpoint to work -- a test-mode
listen-once endpoint isn't scriptable). A Webhook is exercisable headlessly
with curl/PowerShell the same way this whole project's evidence has been
gathered throughout; a Form Trigger offers no advantage for that and adds
UI-only surface. The minimal static page `phase1_upload_demo_page.html`
(open directly in a browser, no server, no build step) gives the
human-browser demo experience by simply POSTing multipart form data to the
same webhook.

### Fail-safe design

- **Deterministic input errors never reach the API.** No file, or no
  `organizationId`/`demoMode`, is caught in `01.3 Validate upload request`
  and routed straight to `technical_review` -- confirmed by real timing
  evidence: this path returns in ~0.075s (no network call, obviously no
  retry).
- **A real 4xx/5xx from the API is never retried either.** Both
  `02.1 Read API capabilities` and `03.1 Run DigiTax controls` use
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
  `02.2 Evaluate capability gate` checks `processableLevels` contains
  `en16931` and `schematron.status === "implemented"` before ever calling
  `/v1/invoices/process`.
- **`technical_review` is an explicit Switch rule**, not a fallthrough to
  the unknown-value fallback (unlike the regression demo's deliberately
  simpler design) -- `05.3 Human review - technical` and
  `05.4 Human review - unknown` are two distinct terminal nodes.

### Isolated environment: docker-compose.phase1-upload-demo.yml

A separate, self-contained stack -- **never** the pre-existing, separately
managed n8n instance on port 5678 / volume `n8n_data`, which this tooling
never touches:

- `api`: builds the repository's own `Dockerfile`, host port `6970` (not
  `6969`, so it never collides with a manually-run `python run.py`),
  reachable from n8n via the compose network as `http://api:6969`. Runs
  with `FACTURX_ENABLE_DEMO_ENDPOINTS=true` so the batch dashboard and mock
  invoice endpoints are available.
- `n8n`: pinned `n8nio/n8n:2.33.7`, host port `5679`, named volume
  `digitax_n8n_phase1_data` (never `n8n_data`).
- Both services have real Docker healthchecks; nothing is imported or
  executed before both report healthy.

Manage it with `examples/n8n/scripts/Manage-Phase1UploadDemo.ps1`
(Windows PowerShell 5.1-compatible):

```powershell
# Build+start both services, wait for real health, import all four demo
# workflows idempotently, publish+restart so Upload/Batch Item webhooks go
# live, verify Structured Regression and Flow 1b stay inactive:
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
Upload Demo and Batch Item's production webhooks therefore need an explicit
`n8n update:workflow --id=... --active=true` after every import, and a
container restart for that activation to take effect on the already-running
process -- `Start` and any manual re-import both need this sequence; the
script handles it automatically for `Start`, and then explicitly re-verifies
the whole active-state policy (Upload + Batch Item active; Structured
Regression + Flow 1b inactive) rather than assuming it worked.

**Operational note on `n8n execute` against a running instance:** the
main `n8n start` process holds n8n's Task Runners broker on its default
port, which happens to collide with this stack's chosen host port (5679,
purely coincidental). A subsequent `docker exec ... n8n execute` therefore
needs `-e N8N_RUNNERS_BROKER_PORT=15679` (or any free port) to avoid `port
5679 is already in use` -- this didn't surface in earlier testing, which
only ever used one-shot `docker run --rm` containers with no already-running
main process to collide with.

### Real execution evidence (2026-08-10, n8n 2.33.7)

Via the isolated stack above, real multipart POSTs to
`http://localhost:5679/webhook/phase1-invoice-upload` (temporary fixtures
derived at test time from the already-accepted embedded XML in the
Structured Regression workflow, never committed separately):

| Scenario | Result | Notes |
|---|---|---|
| Valid EN16931 invoice | `unauffaellig` / `standard_review` | Full control table, XSD 1.09 EN16931, Schematron `implemented` |
| Faulty invoice (amount mismatch) | `klaerung_erforderlich` / `prioritized_review` | CAL-003 with formula/expected/actual/difference |
| No `organizationId`, no `demoMode` | `nicht_pruefbar` / `technical_review` | `ORGANIZATION_CONTEXT_REQUIRED`, ~0.075s, no API call |
| Unrecognized file content | `nicht_pruefbar` / `technical_review` | real API `415`, `UNSUPPORTED_CONTENT_TYPE`, ~0.091s, not retried |
| No file uploaded | `nicht_pruefbar` / `technical_review` | `MISSING_INVOICE_FILE` |
| API unreachable | `nicht_pruefbar` / `technical_review` | `CAPABILITIES_SERVICE_UNAVAILABLE`, ~14.8s (bounded retry), recovered immediately on API restart |
| Double import (all four workflows, twice) | no duplicates | `n8n list:workflow` shows exactly one entry per workflow id after re-importing all files twice |

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

Result (2026-08-10, n8n 2.33.7, against the renamed/restructured
`digitax_invoice_phase1_flow1a_batch_item_v1_0_0.json`): **all 7 generated
cases pass** -- `x_valid`, `x_missing_supplier_identifier`,
`x_incorrect_payable`, `x_shared_unapproved_supplier` (all
`inbound-starter-de-v1`), and `y_valid`, `y_unapproved_supplier`,
`y_multiple_mismatches` (all `inbound-operating-de-v1`).

`DigiTax | Invoice Phase 1 | Flow 1a | Batch Demo | v1.0.0` is the browser
dashboard served by the demo API at `http://localhost:6970/demo/batch` --
not an n8n workflow itself, so it has no export file or workflow id of its
own; it's documented here under the same naming scheme purely for
presentation consistency. Each selected file is sent through the separate
`digitax_invoice_phase1_flow1a_batch_item_v1_0_0.json`
(`phase1-invoice-batch-item` webhook, node chain
`01.1 Receive batch item -> 01.2 Build run context -> 01.3 Mark phase1
attempt start -> 03.1 Run DigiTax controls (sends X-Correlation-ID) ->
04.1 Build control report -> Call Assemble ActivityExecution -> Merge
ActivityExecution into outcome -> 04.2 Respond to batch caller`). The
caller-facing JSON shape (`{ok, statusCode, canonicalInvoice,
phase1ControlReport}` / `{ok: false, statusCode, errorCode, detail}`) is
unchanged; `activityExecution` is attached alongside it. The dashboard performs no invoice
checks itself; it only consolidates API reports and requests an XLSX
serialization for export -- routing/aggregation across the batch is the
caller's responsibility, not this subworkflow's.

Full detail in `coordination/claude-codex/handover-log.md` and
`output/bpmn/flowcharts/n8n/n8n_flow01_mapping.md`.
`tests/test_n8n_upload_demo_workflow.py` and `tests/test_n8n_batch_workflow.py`
are the CI structural guards; they are not a substitute for the real
evidence above.

## digitax_invoice_phase1_flow1b_pdf_ocr_concept_v0_2_0.json

`DigiTax | Invoice Phase 1 | Flow 1b | PDF OCR/LLM Concept | v0.2.0` --
processes a plain PDF invoice (no embedded structured XML) via OCR/LLM
extraction instead of XML parsing. `v0.2.0` (2026-08-11, dev-stack/
AI-selection round) adds an explicit local-vs-cloud AI execution choice in
front of the extraction step; `v0.1.0`'s single Gemini-only path is now the
*cloud* lane of two technically separate lanes that converge on one
canonical output. Three of the original four OCR nodes remain reused from
`digitax_invoice_intake.json` **unmodified** (the prompt-builder was
deliberately corrected in the prior round; the parser gained one addition
in this round -- see below):

```
01.1 Receive PDF upload (POST multipart/form-data, file field "data")
  -> 01.2 Build run context      -- correlation ID before any call,
                                     organizationId (explicit, or the
                                     fictional default only under demoMode=true),
                                     aiExecutionProfile (stable profile ID only)
  -> 01.3 Validate upload request
  -> 01.4 Has valid upload?
       -> [invalid] 01.5 Handle invalid upload    never retried, no call made
       -> [valid]   01.6 Resolve organization profile (concept)
  -> 01.7 Organization profile known?
       -> [unknown] 01.8 Handle unknown organization
       -> [known]   01.9 Resolve AI execution profile
  -> 01.10 Route by AI profile (Switch: local / cloud / unresolved)
       -> [unresolved]  01.11 Handle unresolved AI profile   unknown profile ID, or
                                                               local-default without a
                                                               configured endpoint --
                                                               never a cloud default
       -> [local]  02.1L Encode PDF for local OCR -> 02.2L Build local OCR/LLM request
                      -> 02.3L Run OCR/LLM extraction (local) (bounded retry, maxTries: 3)
                      -> 02.5L Parse local OCR/LLM output
       -> [cloud]  02.1 Encode PDF for OCR -> 02.2 Build OCR/LLM request
                      -> 02.3 Run OCR/LLM extraction (Gemini) (bounded retry, maxTries: 5)
                      -> 02.5 Parse OCR/LLM output
  -> 02.7 Normalize invoice (concept)      -- single shared node for both lanes
  -> 03.1 Run DigiTax controls (concept)     -- ORG-001 evaluation
  -> 04.1 Build control report      -- adds processingPath/aiExecutionProfile/
                                        aiProvider/modelId/modelVersion/
                                        processingLocation/promptVersion/fallbackUsed
  -> 04.2 Render control report      -- single convergence point, HTML, with an
                                         explicit "temporary implementation" notice
  -> 04.3 Respond to browser (HTML)
  -> 04.4 Route by review status (Switch, 4 explicit outputs)
       -> 05.1 / 05.2 / 05.3 / 05.4 Human review - standard / prioritized / technical / unknown
```

`digitax_invoice_intake.json` itself is **untouched** -- it remains the
historical, sanitized reference for the full mailbox-intake workflow this
chain was extracted from. Unrelated scope from that workflow (Outlook
mailbox intake, BZSt VAT lookup, Excel reporting, Reqeli analysis) is not
present here at all, per the task's explicit scope reduction.

### The reused OCR nodes: byte-for-byte, not just "similar" -- except two, changed on purpose

`02.1 Encode PDF for OCR` and `02.3 Run OCR/LLM extraction (Gemini)` carry
the *exact same* `jsCode`/parameters and node `id`s as
`digitax_invoice_intake.json`'s `fix base64` and
`File-Based OCR with Gemini 2.5` -- verified by
`tests/test_n8n_flow1b_workflow.py::test_ocr_nodes_reused_verbatim_from_intake_workflow`,
which diffs the two files directly rather than trusting a copy-paste by eye.

`02.5 Parse OCR/LLM output` (`Gemini Output Parser` in the historical
workflow) keeps its parsing/normalization logic byte-for-byte (markdown-
fence stripping, JSON parsing, the fixed 14-field shape -- verified by
`test_cloud_parser_extends_intake_logic_without_replacing_it`), with one
addition in this round: it now also emits `aiMeta` (provider/model/
processingLocation/promptVersion/fallbackUsed) so its output converges with
the local lane's `02.5L Parse local OCR/LLM output`, which parses an
OpenAI-compatible `choices[0].message.content` shape instead of Gemini's
`candidates[...]` shape but emits the exact same `{invoice_extracted,
aiMeta}` contract. Both feed the single, shared `02.7 Normalize invoice
(concept)` node -- there is one canonical invoice/`fieldEvidence` contract
regardless of which lane ran, per the AI-selection spec's convergence
requirement.

**`02.2 Build OCR/LLM request` (`Build Gemini Request` in the historical
workflow) is the one deliberate exception**, corrected in this round: the
original prompt hardcoded the expected buyer company name, its two approved
addresses, and its VAT ID directly into the extraction instructions --
telling the model the answer in advance, which would make the downstream
ORG-001 comparison against that same master data meaningless. The corrected
prompt extracts seller/buyer using only the document's own labels and
layout ("Rechnungssteller"/"Von" vs. "Rechnungsempfaenger"/"An"/"Bill To"),
with no organization name, address, VAT ID, or the words
"expected"/"approved" anywhere in it.
`tests/test_n8n_flow1b_workflow.py::test_build_gemini_request_prompt_has_no_master_data_leak`
asserts none of those values ever leak back in, and a companion test
(`test_intake_workflow_prompt_still_has_the_original_leak_unremediated`)
documents on purpose that the historical file still has the original,
uncorrected prompt -- it's the untouched source, not a second copy of the fix.

One consequence worth knowing: **the upload's binary field must be named
`data`**, not `invoiceFile` like the Flow 1a upload demo, because that's
the reused encode-node's hardcoded `binaryPropertyName`. This is a
deliberate, documented inconsistency across the workflow family, not an
oversight.

The one deliberate addition beyond verbatim reuse of the three unmodified
nodes: `02.5 Parse OCR/LLM output` gained `onError: "continueErrorOutput"`.
It throws by design on malformed LLM output (invalid JSON, unexpected
response shape), and the historical mailbox-intake workflow had no
fail-safe wrapping around that at all. This workflow must never end as an
unhandled execution error, so the thrown error is now routed to a proper
`nicht_pruefbar`/`technical_review` payload. This is error-handling wiring
only -- the parsing logic itself is untouched.

### AI execution profile selection (local vs. cloud)

Added 2026-08-11 (dev-stack/AI-selection round), per
`coordination/claude-codex/prompts/2026-08-11_ai_execution_selection_ui.md`.
The shared upload page
([`phase1_upload_demo_page.html`](phase1_upload_demo_page.html)) sends only
a stable profile ID -- never a provider URL, model name, or credential:

```json
{
  "processingPath": "structured" | "pdf_ocr",
  "aiExecutionProfile": null | "local-default" | "cloud-gemini",
  "organizationId": "unternehmen-x-demo"
}
```

`01.9 Resolve AI execution profile` resolves the ID entirely server-side
(reading `LOCAL_LLM_BASE_URL`/`LOCAL_LLM_MODEL` via `$env`, and hardcoding
`gemini-2.5-pro` for the cloud profile) and classifies the request as
`local`, `cloud`, `unknown` (unrecognized/missing ID), or
`local_unavailable` (`local-default` selected but no local endpoint is
configured). `01.10 Route by AI profile` sends `unknown` and
`local_unavailable` to the same explicit failure node,
`01.11 Handle unresolved AI profile`, which reports
`nicht_pruefbar`/`technical_review` with a distinct error code
(`AI_PROFILE_UNKNOWN` or `AI_LOCAL_PROVIDER_UNAVAILABLE`) -- **never** a
default to cloud. Security rules enforced by this design (all verified
live against the running dev stack, see "Verification" below):

- **No silent local-to-cloud fallback.** A configured-but-unreachable local
  endpoint fails the run; it does not retry against Gemini.
- **Unknown/missing profile ID aborts safely**, never defaults to cloud.
- **Cloud requires an explicit selection every time** -- the browser never
  remembers or defaults to `cloud-gemini`; see the upload page's disabled
  submit button until a PDF-path choice is made.
- **No secrets or internal URLs ever reach the browser or the control
  report.** The upload page's "provider/model status" text is static,
  descriptive copy (e.g. "Provider: local (configured server-side)"), never
  the actual `LOCAL_LLM_BASE_URL` value.

Both lanes converge on `02.7 Normalize invoice (concept)` with an identical
canonical invoice/`fieldEvidence` shape (see above), so `03.1 Run DigiTax
controls (concept)` and everything downstream is unaware of which lane ran.
`04.1 Build control report` adds eight audit fields to every response
(success or failure): `processingPath`, `aiExecutionProfile`, `aiProvider`,
`modelId`, `modelVersion`, `processingLocation` (`local`/`cloud`/`null`),
`promptVersion`, `fallbackUsed` (always `false` -- there is no fallback path
in this design to set it `true`).

The local lane (`02.1L`-`02.6L`) is a CONCEPT: it assumes a local,
OpenAI-compatible endpoint that accepts a base64 PDF as an `image_url`
content part (the convention several local inference servers use). No model
is bundled, downloaded, or run by this repository or by `compose.dev.yml`
-- see the root README's "Optional: local AI for Flow 1b" section. The
cloud lane is unchanged from `v0.1.0`'s Gemini path.

### Missing API contract -- this is a temporary implementation, not a shortcut

`POST /v1/invoices/process` only accepts a file upload, and the shipped
`MockPdfExtractionAdapter` (`facturx/phase1/normalize/pdf_adapter.py`) is
keyed by the SHA-256 of the uploaded bytes with **no seam for an external
caller to inject a real OCR/LLM extraction result**. There is also no API
endpoint exposing organization master data
(`facturx/phase1/organization_master_data.py`) to an external caller. So
Flow 1b **cannot** call the real API to evaluate ORG-001 against genuinely
OCR-extracted fields today -- and it does not pretend to. Instead:

- `01.6 Resolve organization profile (concept)` hand-mirrors only the
  `buyer` block of `organization_master_data.py`'s two fictional org
  contexts. This **must be kept in sync by hand** until a real endpoint or
  adapter seam exists -- a genuine, acknowledged maintenance burden, not a
  one-time cost.
- `03.1 Run DigiTax controls (concept)` replicates
  `evaluate_org_001()` and its `_check`/`_combine`/`_normalize_for_match`
  helpers from `facturx/phase1/controls/executor.py` line-for-line in
  JavaScript: same 5 buyer fields, same `0.70` confidence threshold, same
  case/whitespace-insensitive comparison, same severity/reason-code shape,
  same control id/title (`ORG-001` / `Stammdatenabgleich Rechnungsempfänger`
  -- never called a "ZUGFeRD gateway"). Verified with real execution
  (Node.js, not just read-through) in `tests/test_n8n_flow1b_workflow.py`.
- The rendered HTML result (`04.2 Render control report`) carries an
  explicit, prominent banner stating this is a temporary n8n-side
  implementation, so no viewer mistakes it for a real API-issued control
  report.

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

Imported as **inactive** by both the presentation demo stack
(`digitax-phase1-demo-n8n`) and the developer stack's `n8n-init`
(`digitax_devstack_n8n_data` volume) -- neither activates Flow 1b by
default. **No Gemini credential and no `LOCAL_LLM_BASE_URL` are configured
in either environment.** `02.3 Run OCR/LLM extraction (Gemini)` still
carries the same `REPLACE_WITH_YOUR_CREDENTIAL_ID` placeholder as the
historical workflow -- nothing was copied from any other n8n instance.
Before a real end-to-end run:

1. Open the n8n UI (`http://localhost:5679` for either stack).
2. Select **DigiTax | Invoice Phase 1 | Flow 1b | PDF OCR/LLM Concept | v0.2.0**.
3. For cloud AI: on the `02.3 Run OCR/LLM extraction (Gemini)` node, select
   or create a real **Google Gemini (PaLM) API** credential (Google AI
   Studio API key). For local AI: set `LOCAL_LLM_BASE_URL`/`LOCAL_LLM_MODEL`
   in `.env` (dev stack) before starting, pointing at an OpenAI-compatible
   endpoint you already run yourself.
4. Activate the workflow only after that -- it is deliberately left
   inactive on import.

Status is **imported, inactive, visually structured, credentials/API
convergence pending** -- not "working." No E2E claim is made without a
credential or a real local endpoint actually present.

### Verification

- `pytest`: full suite green (162 tests across all n8n workflow test
  files as of the dev-stack/AI-selection round), including
  `tests/test_n8n_flow1b_workflow.py` (structural checks plus real Node.js
  execution of the ORG-001 evaluator and status aggregator against
  synthetic inputs -- the actual reused JS logic, not a re-implementation
  assumption).
- Real `n8n import:workflow`/`update:workflow` against pinned
  `n8nio/n8n:2.33.7`, both in the presentation stack's persistent container
  and in a from-scratch `compose.dev.yml up --build` run (fresh volume,
  then a second startup without reset) -- 4 workflows, no duplicates,
  correct active state, both times.
- Live webhook evidence against the running dev stack: all 7 Unternehmen
  X/Y profile-matrix invoices through `phase1-invoice-upload` and one
  through `phase1-invoice-batch-item`, a faulty (missing-file) upload
  routed to `nicht_pruefbar`/`MISSING_INVOICE_FILE`, and -- with Flow 1b
  temporarily activated for this check only -- an unknown AI profile, a
  missing AI profile, and an unconfigured local provider each independently
  confirmed to route to `nicht_pruefbar`/`technical_review` rather than a
  cloud default or a silent fallback. The cloud lane itself fails at
  credential resolution in this environment (no real Gemini credential is
  configured anywhere in this repository or its containers), so it is
  reported as configured/importable but not E2E-verified, per the
  AI-selection spec's own instruction for that case.
- Full detail, exact commands, and evidence in
  `coordination/claude-codex/handover-log.md` and
  `output/bpmn/flowcharts/n8n/n8n_flow01_mapping.md`.

## General rule

Workflow exports must contain no credentials, API keys, real invoice data,
host-specific URLs, or organization secrets. Use environment variables or n8n
credentials for all endpoints.
