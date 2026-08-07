# DigiTax invoice intake: Phase 1 preparation

This package is the decision-complete handover for refining `facturx_apis` and
the DigiTax n8n invoice workflow.

## Goal

Produce the same canonical invoice data and the same Phase 1 control report for
two input paths:

1. Factur-X/ZUGFeRD: extract embedded XML, validate the detected version and
   profile, and normalize the structured data.
2. Plain PDF: extract data with OCR/LLM, record field-level evidence and
   confidence, and normalize it to the same contract.

Both paths then run the same selected deterministic control profile. The
candidate catalog is intentionally broader than the first implementation and
can be expanded control by control. Human oversight starts after Phase 1.

## Files

- `automation_boundary.md`: what n8n automates and what remains human.
- `control_catalog.md`: extensible candidate controls and implementation waves.
- `service_gap_analysis.md`: current Factur-X API gaps and implementation order.
- `test_matrix.md`: synthetic acceptance scenarios.
- `agent_handover.md`: paste-ready implementation assignment.
- `contracts/canonical_invoice.schema.json`: common normalized invoice input.
- `contracts/phase1_control_report.schema.json`: common control output.
- `examples/`: valid contract examples.
- `../../examples/n8n/invoice_phase1_node_plan.md`: n8n node-level blueprint.

## First implementation slice

Implement a vertical slice for one valid ZUGFeRD invoice, one valid plain PDF,
one missing-field PDF, and one invalid structured invoice. Select and document
a small starter control profile from the catalog; it is not necessary to
implement the complete catalog. Do not begin with Reqeli or booking integration.
The slice is complete when all four cases create a schema-valid canonical
invoice or a controlled `nicht_pruefbar` result and a schema-valid Phase 1
report.
