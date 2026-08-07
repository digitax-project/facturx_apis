# Implementation handover

## Objective

Implement the first DigiTax Phase 1 invoice-processing vertical slice in this
repository and provide an importable n8n workflow example.

Phase 1 means automated preprocessing of an incoming invoice. It is not TOGAF
ADM Phase A. The workflow ends at a documented control report for human review.

## Read first

1. `AGENTS.md`
2. `docs/invoice_phase1/automation_boundary.md`
3. `docs/invoice_phase1/control_catalog.md`
4. `docs/invoice_phase1/service_gap_analysis.md`
5. `docs/invoice_phase1/contracts/*.schema.json`
6. `examples/n8n/invoice_phase1_node_plan.md`

## Required first slice

- Inspect and normalize one current Factur-X/ZUGFeRD fixture.
- Normalize one plain-PDF fixture supplied through a mock extraction adapter.
- Define a small versioned starter profile from `control_catalog.md` and run the
  same selected content controls against both canonical invoices.
- Produce the same schema-valid Phase 1 control report for both paths.
- Return `nicht_pruefbar` for unreliable extraction or unsupported input.
- Keep Reqeli behind an optional disabled-by-default node.
- Add automated tests for FX-01, FX-04, PDF-01, PDF-02, PDF-03, and SYS-02.
- Export a credential-free n8n workflow JSON under `examples/n8n/` only after
  it imports successfully into the supported n8n version.

## Non-goals

- no approval, rejection, booking, payment, or supplier communication
- no claim of complete XRechnung support
- no replacement of official Schematron rules with LLM checks
- no real organization or invoice data

## Definition of done

- API and contract tests pass locally and in CI.
- n8n workflow imports without embedded credentials or environment secrets.
- structured and PDF fixtures converge before shared content controls run.
- every report identifies the catalog and control-profile version used.
- every report includes source, extraction, rule, result, evidence, and timing.
- README documents startup, supported versions, and known limitations.
