# Changelog

## v1.1.0 - 2026-08-13

- Added an optional `X-Correlation-ID` request header on
  `POST /v1/invoices/process`, validated before the application-level
  bounded upload read (`_read_upload_bounded()`) and before any Phase-1
  pipeline processing, and echoed verbatim into the report's
  `correlationId` when supplied; entirely absent (never `null`) when the
  caller omits it. An invalid value is rejected with `400
  INVALID_CORRELATION_ID` before that bounded read or any pipeline
  processing runs (FastAPI/Starlette has already parsed the incoming
  multipart request before the route handler runs, as it must for any
  endpoint; this header is validated at the first opportunity the
  application code has, ahead of the application's own upload-reading
  and processing steps); a valid one is also echoed in the JSON error
  body of a later pre-report rejection.
- Added a new required, server-generated `startedAt` timestamp to every
  `phase1_control_report`, captured as the first step of pipeline
  execution; existing `createdAt` is unchanged.
- Bumped `phase1_control_report`'s `schemaVersion` to `1.1.0` (both the
  docs and packaged schema copies, kept byte-identical) and the service
  release version (`API_VERSION`, `README.md`, `setup.py`) to `1.1.0` to
  match. `pyproject.toml`'s embedded `factur-x` library version (`3.6`)
  is unaffected, as it is independently versioned from the DigiTax Phase 1
  API.
- Deliberately does **not** add any process/activity/workflow identifier,
  AI provider/model field, or `HumanReviewDecision` field to this API or
  its report contract; those remain the responsibility of the
  orchestration layer around this service, not this API itself.

## v1.0.1 - 2026-08-10

- Corrected the unsupported documentation claim about a Factur-X 1.09.2 /
  ZUGFeRD 2.5.2 release. Official FeRD/FNFE-MPE sources checked on 2026-08-10
  identify Factur-X 1.09 / ZUGFeRD 2.5 as current.
- Added a dated official-standard baseline with source URLs and a mandatory
  update procedure.
- Added a generated inventory of all 427 contextual Schematron assertions,
  including 302 unique technical IDs, rule families, severity, messages,
  XPath expressions, source lines, and source hash.

## v1.0.0 - 2026-08-10

First stable DigiTax Phase 1 invoice-preprocessing release.

- Added secure invoice inspection, normalization, validation, and processing
  endpoints with canonical invoice and control-report contracts.
- Added Factur-X 1.09 EN16931 XSD validation and offline official Schematron
  execution with traceable rule findings.
- Added the versioned `inbound-starter-de-v1` control profile with document,
  structure, mandatory-field, arithmetic, currency, and organization checks.
- Added fail-safe status routing to standard, prioritized, or technical human
  review. The service does not approve, book, pay, or contact suppliers.
- Added reproducible valid and incorrect-payable hybrid Factur-X demo invoices.
- Added an isolated n8n 2.33.7 upload demo with browser-readable results and
  one-command start, smoke-test, status, stop, and reset operations.
