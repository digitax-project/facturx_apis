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

1. Add `GET /health` and `GET /capabilities` with supported formats, versions,
   profiles, XSD artifacts, and Schematron artifacts.
2. Upgrade the target baseline to ZUGFeRD 2.5 / Factur-X 1.09 and explicitly
   test any supported older versions.
3. Execute official XSD and Schematron/business-rule validation; return every
   finding with rule ID, severity, source location, and standard version.
4. Return a stable JSON envelope for extraction and validation instead of
   switching between raw XML, file responses, and loosely structured errors.
5. Add a normalization endpoint or library function that produces the canonical
   invoice contract without discarding the original XML or source hash.
6. Change arbitrary embedded-XML extraction from a permissive default to an
   explicit compatibility option with content, size, and parser safeguards.
7. Use 4xx responses for invalid/unsupported input and 5xx only for service
   failures. Include stable error codes for n8n routing.
8. Add synthetic fixtures and automated API tests for valid, invalid,
   unsupported, encrypted, malformed, and ambiguous inputs.
9. Keep XRechnung validation separate until an official KoSIT-compatible
   validator and its current bundle are integrated and tested.

## Proposed API additions

- `POST /v1/invoices/inspect`: detect source type, format, profile, and version.
- `POST /v1/invoices/normalize`: extract/normalize structured invoice data.
- `POST /v1/invoices/validate`: return XSD/Schematron findings as JSON.
- `POST /v1/invoices/process`: optional convenience endpoint combining the
  preceding steps while preserving their individual results.

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
