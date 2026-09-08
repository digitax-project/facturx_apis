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

## Execution traceability (`phase1_control_report` schema `1.1.0`)

`POST /v1/invoices/process` accepts an optional `X-Correlation-ID` request
header (1-200 characters, `[A-Za-z0-9._:-]`), validated before the
application-level bounded upload read (`_read_upload_bounded()`) and
before any Phase-1 pipeline processing. This is an application-level
ordering guarantee, not a transport-level one: FastAPI/Starlette has
already received and parsed the incoming multipart request before the
route handler runs, as it must for any endpoint; the header is validated
at the first opportunity the application code has, ahead of the
application's own upload-reading and processing steps. When supplied and
valid, it is echoed verbatim into the report's `correlationId` field, and
into the JSON error body of any later, pre-report rejection (e.g.
`ORGANIZATION_CONTEXT_REQUIRED`); when omitted, `correlationId` is
entirely absent from the report (never `null`). An invalid value is
rejected with `400 INVALID_CORRELATION_ID` before the bounded upload read
or any pipeline processing runs, and is never echoed back.

Every report also carries a required, server-generated `startedAt`
timestamp (the moment pipeline execution began), alongside the existing
`createdAt` (report construction time).

Process, activity, workflow, and orchestration identifiers
(`processId`/`processVersion`/`activityId`/`activityVersion`,
`workflowId`/`workflowVersion`/`nodeId`) are **deliberately not part of
this contract**. They are owned by the orchestration layer (n8n) and the
Process Generator that defines them, not by this deterministic control
API — adding them here would collapse the separation between "what was
defined," "what a deterministic service executed," and "what an
orchestrator's workflow instance did," which this API's contract is
designed to keep distinct.

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
