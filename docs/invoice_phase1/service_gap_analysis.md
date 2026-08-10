# Factur-X API gap analysis

## Current implementation

The repository currently exposes:

- `POST /facturx-pdfgen`
- `POST /facturx-pdfextractxml`
- `POST /facturx-xmlcheck`

The bundled schemas and code point to Factur-X 1.07.2, corresponding to
ZUGFeRD 2.3.2. Validation is primarily XSD-based. The optional detailed field
checks are hand-written XPath checks and must not be treated as a replacement
for official business rules.

## Required refinement order

1. **Implemented** (first Phase 1 vertical slice). `GET /health` and
   `GET /capabilities` report supported formats, versions, profiles, the
   XSD baseline (explicitly flagged `legacyBaseline: true`, see item 2), and
   Schematron status (`not_implemented`, see item 3).
2. **Not implemented; tracked separately.** The XSD baseline stays at
   Factur-X 1.07.2 / ZUGFeRD 2.3.2 for this slice -- upgrading means fetching
   and bundling a new official schema package with its own licensing check,
   which is intentionally kept out of this slice. See the follow-up issue
   referenced from the repository issue tracker (filed alongside issue #1)
   for the ZUGFeRD 2.5 / Factur-X 1.09 upgrade.
3. **Not implemented.** No official Schematron/business-rule artifacts are
   bundled or fetched. `STR-004` is defined in the control catalog but is
   deliberately excluded from the `inbound-starter-de-v1` starter profile
   rather than reported as passed or run -- see
   `facturx/phase1/controls/catalog.py`. XSD validation (the other half of
   this item) is implemented and returns findings with rule ID, severity,
   and message via `STR-003`.
4. **Implemented** for the new `/v1/invoices/*` endpoints
   (`facturx/phase1/api.py`): a stable JSON envelope
   (`{"canonicalInvoice": ..., "phase1ControlReport": ...}`), each part
   independently schema-validated. The legacy `/facturx-*` endpoints are
   unchanged and still mix response shapes -- migrating them is future work.
5. **Implemented.** `facturx/phase1/normalize/` produces
   `canonical_invoice.schema.json`-conformant output for both the structured
   (embedded/direct XML) and plain-PDF paths, retaining the source hash and
   per-field evidence; the original XML bytes are not discarded during
   normalization.
6. Change arbitrary embedded-XML extraction from a permissive default to an
   explicit compatibility option with content, size, and parser safeguards.
7. **Implemented** for the new endpoints: 400/422 for malformed requests
   (including missing/unrecognized organization context), 415 for content
   that isn't recognizable as PDF or XML at all, 200 with a classified
   `nicht_pruefbar` report for anticipated content issues (encrypted,
   unsupported detected format, low-confidence PDF extraction), and 5xx with
   a stable `error_code` only for genuinely unexpected technical failures.
   The legacy `/facturx-*` endpoints are unchanged.
8. **Partially implemented.** `tests/` covers the required FX-01, FX-04,
   PDF-01, PDF-02, PDF-03, and SYS-02 scenarios from
   `docs/invoice_phase1/test_matrix.md` end-to-end through the new
   endpoints; the legacy endpoints still have no automated tests.
9. Keep XRechnung validation separate until an official KoSIT-compatible
   validator and its current bundle are integrated and tested. (Unchanged:
   `detectedFormat` reports `xrechnung`/`unknown` as unsupported, routed to
   `nicht_pruefbar`, never validated.)

## Proposed API additions

All four are implemented in `facturx/phase1/api.py`.

- `POST /v1/invoices/inspect`: detect source type, format, profile, and version.
- `POST /v1/invoices/normalize`: extract/normalize structured or plain-PDF
  invoice data into `canonical_invoice`. No organization context required
  (it runs no controls).
- `POST /v1/invoices/validate`: return XSD findings as JSON for a structured
  document (`applicable: false` for a plain PDF, not an error). Schematron
  is reported as `"not_implemented"`, never silently omitted from the
  response.
- `POST /v1/invoices/process`: the full pipeline -- normalize, run the
  starter control profile, aggregate, return `canonicalInvoice` +
  `phase1ControlReport`.

Existing endpoints should remain during migration and be marked with their
supported versions.

## Standards baseline checked on 2026-08-07

- FeRD publishes ZUGFeRD 2.5 / Factur-X 1.09 as the current package and
  provides XSD and Schematron artifacts for all profiles:
  <https://www.ferd-net.de/en/downloads/publications/details/zugferd-25-deutsch>
- The official German e-invoice FAQ distinguishes structured e-invoices from
  other invoices such as plain PDFs. Technical validation supports processing
  but does not itself establish legal or tax correctness:
  <https://www.bundesfinanzministerium.de/Content/DE/FAQ/e-rechnung.html>
- XRechnung has its own current specification and validation bundle and must
  therefore not be advertised as a side effect of Factur-X validation:
  <https://xeinkauf.de/xrechnung/versionen-und-bundles/>
