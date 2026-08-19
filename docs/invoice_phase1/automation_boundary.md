# Phase 1 automation boundary

## What n8n should automate

| Step | Automated result | Component |
|---|---|---|
| Intake | Receive file and organization context; calculate SHA-256; create run ID | n8n |
| Safety checks | Check size, MIME type, encryption/password protection, duplicate file hash | n8n |
| Format detection | Distinguish hybrid PDF, plain PDF, direct XML, and unsupported input | n8n + format service |
| ZUGFeRD/Factur-X extraction | Extract embedded XML using `facturx_apis` | Factur-X API |
| Structured validation | Detect version/profile; run XSD and official Schematron/business rules | Factur-X API |
| PDF extraction | OCR/text extraction plus constrained LLM mapping | extraction service called by n8n |
| Normalization | Map both paths to `canonical_invoice.schema.json` | format adapter/service |
| Selected controls | Load a versioned organization/control profile and run its applicable controls | deterministic service, initially n8n code nodes where necessary |
| Optional external checks | VAT-ID check when applicable and configured | n8n/API |
| Status aggregation | Produce one Phase 1 status and routing target | deterministic rules |
| Evidence | Persist source hash, extracted values, rule versions, findings, and timestamps. **P2.1 Wave 1 A5 Stage 1 (Flow 1a only, implemented):** one schema-valid `ActivityExecution` object is assembled and validated per run via the shared `digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json` subworkflow, bound to the H1-approved, hash-pinned `examples/n8n/activity_binding.invoice_intake.json` lockfile -- not yet persisted to any Evidence Store (blocked until Stage 3). | n8n/repository |
| Optional analysis | Invoke Reqeli only for configured findings | n8n + Reqeli |
| Handover | Display report and suggestions to the responsible human | n8n/application UI |

## Example starter control profile

The following controls are an initial executable example, not the complete or
universally required catalog. The broader candidate list is maintained in
`control_catalog.md`. The PDF path must run the same selected content controls
as the structured path after normalization. It cannot claim the same source
reliability: XML values come from structured fields, while PDF values carry
OCR/LLM confidence and evidence.

| ID | Example control | Machine outcome |
|---|---|---|
| DOC-001 | Input readable, supported, and not encrypted | pass/fail/not_reliable |
| STR-003 | Structured document valid for detected XSD | pass/fail/not_applicable |
| STR-004 | Official structured business rules satisfied | pass/fail/not_applicable |
| FRM-004 | Issue date present | pass/fail/not_reliable |
| FRM-005 | Invoice number present | pass/fail/not_reliable |
| FRM-001 | Supplier and buyer names present | pass/fail/not_reliable |
| FRM-002 | Supplier and buyer addresses present | pass/fail/not_reliable |
| FRM-003 | Supplier tax number or VAT ID present | pass/fail/not_reliable |
| FRM-006 | Supply description present | pass/fail/not_reliable |
| FRM-007 | Delivery/service date or period present when applicable | pass/fail/not_applicable/not_reliable |
| CAL-001 | Line amounts arithmetically consistent | pass/fail/not_reliable |
| CAL-002 | Tax bases, rates, tax amounts, and rounding consistent | pass/fail/not_reliable |
| CAL-003 | Net, tax, gross, and payable totals reconcile | pass/fail/not_reliable |
| CAL-004 | Currency present and used consistently | pass/fail/not_reliable |
| ORG-001 | Buyer data match approved organization master data | pass/fail/not_reliable |

Further controls are enabled incrementally through explicit versioned profiles.
Applicability conditions may not be hidden inside an LLM prompt.

## Phase 1 status aggregation

- `nicht_pruefbar`: source cannot be read, schema is unsupported, required PDF
  extraction is unreliable, or the control execution failed technically.
- `klaerung_erforderlich`: a blocking content, arithmetic, master-data, or
  applicable external-validation finding exists.
- `hinweis`: only non-blocking findings remain.
- `unauffaellig`: all applicable automated controls passed.

Unknown values use the safe fallback `nicht_pruefbar`.

## Human Phase 2

The responsible person retains authenticity and business-context assessment,
verification that the supply was actually received, interpretation of unclear
tax cases, supplier communication, correction request, rejection, approval,
booking, payment release, and final tax responsibility.
