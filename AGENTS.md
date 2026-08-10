# Agent Working Agreement

## Scope

This repository owns Factur-X/ZUGFeRD generation, extraction, and validation.
The current development slice also defines the boundary to the DigiTax n8n
invoice intake workflow. Keep orchestration in n8n and format-specific invoice
logic in an API or dedicated validator.

## Phase 1 Rules

- Phase 1 ends with a control report and one of four routing statuses:
  `unauffaellig`, `hinweis`, `klaerung_erforderlich`, or `nicht_pruefbar`.
- Phase 1 may extract, normalize, validate, compare, calculate, and suggest.
- Phase 1 must not approve, reject, book, pay, contact a supplier, or make the
  final tax judgment.
- Factur-X/ZUGFeRD input uses embedded XML as the authoritative machine input.
- Plain PDF input uses OCR/LLM extraction but must converge on the same
  canonical invoice contract and selected deterministic control profile.
- `docs/invoice_phase1/control_catalog.md` is a candidate catalog, not a claim
  that every control is universally applicable or already implemented.
- Every run identifies the catalog and profile version. Add controls
  incrementally without changing Phase 1 into final tax approval.
- Low-confidence or incomplete PDF extraction must route to human review. It
  must never be silently treated as a valid structured invoice.
- Reqeli is an optional analysis service after a control finding, not the
  invoice validator and not the decision maker.
- Do not describe XSD validity, Schematron validity, BPMN validity, or an LLM
  result as proof of legal or tax compliance.

## Standards Baseline

- Target current ZUGFeRD 2.5 / Factur-X 1.09 artifacts for new work while
  retaining explicitly tested backwards compatibility where required.
- Use XSD plus the official Schematron/business rules for structured invoices.
- Treat XRechnung as a separate validation capability. Do not claim that the
  existing Factur-X endpoints provide complete XRechnung validation.

## Quality Gate

- Add synthetic fixtures only; do not commit real invoices or organization
  data.
- Test success, invalid, incomplete, unsupported, and low-confidence paths.
- Keep API errors machine-readable and distinguish invalid input from server
  failure.
- Preserve source document hashes and rule/evidence references in the control
  report.
