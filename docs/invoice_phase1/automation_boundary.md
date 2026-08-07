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
| Minimum controls | Run the shared controls C01-C08 below | deterministic service or n8n code node |
| Optional external checks | VAT-ID check when applicable and configured | n8n/API |
| Status aggregation | Produce one Phase 1 status and routing target | deterministic rules |
| Evidence | Persist source hash, extracted values, rule versions, findings, and timestamps | n8n/repository |
| Optional analysis | Invoke Reqeli only for configured findings | n8n + Reqeli |
| Handover | Display report and suggestions to the responsible human | n8n/application UI |

## Shared minimum control catalog

The PDF path must run the same content controls as the structured path after
normalization. It cannot claim the same source reliability: XML values come
from structured fields, while PDF values carry OCR/LLM confidence and evidence.

| ID | Minimum control | Machine outcome |
|---|---|---|
| C01 | Input readable, supported, and not encrypted | pass/fail/not_reliable |
| C02 | Structured document valid for detected version/profile | pass/fail/not_applicable |
| C03 | Invoice number and issue date present | pass/fail/not_reliable |
| C04 | Supplier and buyer name/address present | pass/fail/not_reliable |
| C05 | Supplier tax number or VAT ID present; buyer VAT ID where required | pass/fail/not_applicable/not_reliable |
| C06 | Supply description and delivery/service date or period present | pass/fail/not_reliable |
| C07 | Currency, net/tax/gross/payable totals present and arithmetically consistent | pass/fail/not_reliable |
| C08 | Buyer data match approved organization master data | pass/fail/not_reliable |

Additional controls such as duplicate detection, foreign VAT-ID confirmation,
reverse-charge indicators, exemptions, credit notes, and small-value invoices
may be enabled as configured extensions. They must use explicit applicability
conditions and may not be hidden inside an LLM prompt.

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
