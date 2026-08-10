# Changelog

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
