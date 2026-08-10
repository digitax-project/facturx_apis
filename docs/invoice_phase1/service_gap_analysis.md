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

1. **Implemented** (first Phase 1 vertical slice, extended in the Factur-X
   1.09/Schematron round). `GET /health` and `GET /capabilities` report
   supported formats, versions, profiles, the per-level XSD baseline
   (`structuredFormats["factur-x"].xsdBaselines`), and Schematron status
   (`"implemented"`, `scope: ["en16931"]`, see item 3).
2. **Implemented for EN16931; other profiles unchanged.** EN16931 now
   validates against the vendored, hash-verified Factur-X 1.09 XSD (see
   `facturx/phase1/resources/facturx-1.09-en16931/PROVENANCE.json` for full
   source/hash/license provenance -- vendor-copied from the pinned,
   PyPI-hash-verified `factur-x==6.6` wheel, per the reviewed Stage 1
   decision). `minimum`/`basicwl`/`basic`/`extended` remain on the legacy
   Factur-X 1.07.2 / ZUGFeRD 2.3.2 XSDs, since only EN16931 has reviewed
   content controls and a reviewed Schematron artifact so far. This is
   Factur-X **1.09**, not the true ZUGFeRD 2.5.2 / Factur-X 1.09.2
   corrigendum (published 2026-08-04, primarily affecting EXTENDED) --
   that official package is gated behind a personal-data registration form
   on ferd-net.de/fnfe-mpe.org with no direct download; acquiring the true
   1.09.2 artifacts (if they differ from 1.09 for EN16931 at all) remains a
   separate follow-up.
3. **Implemented for EN16931.** The official, vendored Factur-X 1.09 EN16931
   compiled Schematron business rules are executed offline via pinned
   `saxonche` (SaxonC-HE 13.0, no Java, no network at runtime) -- see
   `facturx/phase1/validate/schematron.py`. `STR-004` is now selected in the
   `inbound-starter-de-v1` starter profile (bumped to version `0.2.0`) and
   returns real rule IDs (`FX-SCH-A-nnnnnn`), the official BR-*/BR-CO-*
   text, and an XPath location per finding. It only runs once XSD validation
   (`STR-003`) has passed (Schematron's arithmetic assumes XSD-conformant
   types) and only for EN16931 (not yet reviewed for the other recognized
   profiles); a Saxon/resource failure, timeout, or unparseable output
   reports `not_reliable`, forcing `nicht_pruefbar`, never `passed`.
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
- `POST /v1/invoices/validate`: return XSD and (for EN16931) Schematron
  findings as JSON for a structured document (`applicable: false` for a
  plain PDF, not an error). The `schematron` field is always an object with
  a `status`, never silently omitted from the response.
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
