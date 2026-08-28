"""Behavioral regression guard for
examples/n8n/digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json
("DigiTax | Invoice Phase 1 | Shared | Assemble ActivityExecution | v1.0.0").

Real execution of the four Code nodes via Node.js (the same
subprocess-harness technique test_n8n_flow1b_workflow.py already
established), not string-presence assertions: every outcome->status/
resultCode/timestamp mapping in accepted A5 plan section 3.2 is exercised
with a synthetic envelope fixture and the object produced is validated
against the real generated AJV validator.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
N8N_DIR = REPO_ROOT / "examples" / "n8n"
SHARED_SUBWORKFLOW_PATH = (
    N8N_DIR / "digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json"
)

NODE_AVAILABLE = shutil.which("node") is not None

CHAIN_NODE_NAMES = (
    "01.1 Assert activity binding published",
    "01.2 Compute status/resultCode/timestamps",
    "01.3 Assemble ActivityExecution object",
    "01.4 Validate against ActivityExecution shape",
)


def _load_workflow() -> dict:
    return json.loads(SHARED_SUBWORKFLOW_PATH.read_text(encoding="utf-8"))


def _nodes_by_name(data: dict) -> dict:
    return {n["name"]: n for n in data["nodes"]}


def _chain_code() -> list:
    nodes = _nodes_by_name(_load_workflow())
    return [nodes[name]["parameters"]["jsCode"] for name in CHAIN_NODE_NAMES]


def _run_chain(envelope: dict) -> dict:
    """Runs the full 01.1 -> 01.4 chain in a single Node.js subprocess,
    threading each node's output into the next exactly as n8n's
    Execute Workflow Trigger -> Code -> Code -> Code -> Code chain would."""
    chain = _chain_code()
    steps_js = "\n".join(
        f"""
data = (function() {{
  const $input = {{ first: () => ({{ json: data }}) }};
{code}
}})()[0].json;
"""
        for code in chain
    )
    harness = f"""
const $workflow = {{ id: {json.dumps(envelope.get("workflowId"))} }};
let data = {json.dumps(envelope)};
try {{
{steps_js}
  process.stdout.write(JSON.stringify({{ ok: true, result: data }}));
}} catch (e) {{
  process.stdout.write(JSON.stringify({{ ok: false, message: e.message }}));
}}
"""
    # Written to a temp .js file and run via `node <file>`, not `node -e` --
    # the ~33KB embedded generated validator source (inside 01.4's own code)
    # exceeds the Windows command-line length limit when passed as -e.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".mjs", delete=False, encoding="utf-8") as f:
        f.write(harness)
        script_path = f.name
    try:
        proc = subprocess.run(["node", script_path], capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0, f"node execution failed: {proc.stderr}\nharness:\n{harness}"
        return json.loads(proc.stdout)
    finally:
        Path(script_path).unlink(missing_ok=True)


BASE_ENVELOPE = {
    "processInstanceId": "PI-1",
    "correlationId": "CORR-1",
    "workflowId": "digitax-invoice-phase1-upload-demo",
    "receivedAt": "2026-08-14T10:00:00.000Z",
}


def test_workflow_file_exists_and_is_valid_json():
    assert SHARED_SUBWORKFLOW_PATH.exists()
    _load_workflow()


def test_workflow_id_and_active_state():
    """Published/active, even though it has no webhook and is never
    externally reachable: confirmed against the real pinned n8n 2.33.7
    image that its WorkflowPublicationService refuses to let an Execute
    Workflow node invoke an unpublished target at all ("Workflow is not
    active and cannot be executed."). Its only trigger node is
    executeWorkflowTrigger -- publishing it opens no live traffic surface."""
    data = _load_workflow()
    assert data["id"] == "digitax-invoice-phase1-shared-assemble-activity-execution"
    assert data["active"] is True
    trigger = next(n for n in data["nodes"] if n["type"] == "n8n-nodes-base.executeWorkflowTrigger")
    assert trigger is not None
    assert not any(n["type"] == "n8n-nodes-base.webhook" for n in data["nodes"])


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_flow1b_workflow_id_has_a_published_binding():
    """P2.1 Wave 1 A5 revision round 2: Flow 1b now calls the real Phase 1
    API (POST /v1/invoices/process-extracted) and must assemble exactly one
    validated ActivityExecution for the same activity Flow 1a uses, via the
    same published binding -- proven here the same way every Flow 1a
    workflowId already is, by running the real chain with Flow 1b's own
    workflowId and node name."""
    envelope = {
        **BASE_ENVELOPE,
        "workflowId": "digitax-invoice-phase1-flow1b-pdf-ocr",
        "outcome": "REPORT",
        "report": {
            "status": "unauffaellig", "routing": "standard_review",
            "startedAt": "2026-08-14T10:00:00.100Z", "createdAt": "2026-08-14T10:00:01.000Z",
            "runId": "RUN-1B", "reportId": "REP-1B", "sourceSha256": "abc",
            "controlProfileId": "p1", "controlProfileVersion": "v1",
            "correlationId": "CORR-1",
        },
        "httpErrorCode": None, "n8nErrorCode": None, "explanation": None,
        "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None,
    }
    out = _run_chain(envelope)
    assert out["ok"] is True, out
    ae = out["result"]["activityExecution"]
    assert ae["status"] == "SUCCEEDED"
    assert ae["executionId"] == "RUN-1B"
    assert ae["workflowRef"]["workflowId"] == "digitax-invoice-phase1-flow1b-pdf-ocr"
    assert ae["workflowRef"]["nodeId"] == "03.1 Run DigiTax controls"
    # Same activity identity as every Flow 1a workflow -- Flow 1b is a new
    # caller of the same published binding, not a second activity.
    assert ae["definitionRef"]["activityId"] == "digitax.invoice-intake.phase1.structured-control"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_report_outcome_maps_to_succeeded():
    envelope = {
        **BASE_ENVELOPE,
        "outcome": "REPORT",
        "report": {
            "status": "unauffaellig", "routing": "standard_review",
            "startedAt": "2026-08-14T10:00:00.100Z", "createdAt": "2026-08-14T10:00:01.000Z",
            "runId": "RUN-1", "reportId": "REP-1", "sourceSha256": "abc",
            "controlProfileId": "p1", "controlProfileVersion": "v1",
            "correlationId": "CORR-1",
        },
        "httpErrorCode": None, "n8nErrorCode": None, "explanation": None,
        "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None,
    }
    out = _run_chain(envelope)
    assert out["ok"] is True, out
    ae = out["result"]["activityExecution"]
    assert ae["status"] == "SUCCEEDED"
    assert ae["resultCode"] == "unauffaellig"
    assert ae["startedAt"] == "2026-08-14T10:00:00.100Z"
    assert ae["completedAt"] == "2026-08-14T10:00:01.000Z"
    assert ae["executionId"] == "RUN-1"
    # A1 correction round 1 (High-1): A5b requires the qualified semantic
    # reference, not the bare reportId, in all three locations.
    assert ae["controlReportRef"] == "phase1-control-report:REP-1"
    assert ae["outputRefs"] == ["phase1-control-report:REP-1"]
    assert "phase1-control-report:REP-1" in ae["evidenceRefs"]
    assert "p1" in ae["evidenceRefs"] and "v1" in ae["evidenceRefs"]
    assert ae["aiBindingRef"] is None


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_control_report_ref_uses_a5b_qualified_semantic_reference():
    """A1 correction round 1 (High-1) regression guard: enforces A5b's exact
    semantic qualifier `phase1-control-report:<reportId>`, not merely that
    controlReportRef/outputRefs/evidenceRefs are JSON Schema strings. Mirrors
    the exact check the accepted A5b evidenceStoreService.ingestActivityExecution
    performs (`expectedControlReportRef = \`phase1-control-report:${report.reportId}\``)."""
    envelope = {
        **BASE_ENVELOPE,
        "outcome": "REPORT",
        "report": {
            "status": "auffaellig", "routing": "priority_review",
            "startedAt": "2026-08-14T10:00:00.100Z", "createdAt": "2026-08-14T10:00:01.000Z",
            "runId": "RUN-QUAL", "reportId": "REP-84CB1F828E62", "sourceSha256": "abc",
            "controlProfileId": "inbound-starter-de-v1", "controlProfileVersion": "1.0.0",
            "correlationId": "CORR-1",
        },
        "httpErrorCode": None, "n8nErrorCode": None, "explanation": None,
        "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None,
    }
    out = _run_chain(envelope)
    assert out["ok"] is True, out
    ae = out["result"]["activityExecution"]
    expected_ref = "phase1-control-report:REP-84CB1F828E62"
    assert ae["controlReportRef"] == expected_ref
    assert ae["outputRefs"] == [expected_ref]
    assert expected_ref in ae["evidenceRefs"]
    assert "inbound-starter-de-v1" in ae["evidenceRefs"]
    assert "1.0.0" in ae["evidenceRefs"]
    # The bare, unqualified reportId (A1's rejected shape) must never appear.
    assert "REP-84CB1F828E62" not in ae["outputRefs"]
    assert ae["controlReportRef"] != "REP-84CB1F828E62"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_report_outcome_with_missing_correlation_id_fails_closed():
    """A1 round-1 review (Medium): a report with no correlationId at all
    must never be trusted as this run's evidence -- fail closed to FAILED
    with a stable contract/integrity reason code, no evidence refs."""
    envelope = {
        **BASE_ENVELOPE,
        "outcome": "REPORT",
        "report": {
            "status": "unauffaellig", "routing": "standard_review",
            "startedAt": "2026-08-14T10:00:00.100Z", "createdAt": "2026-08-14T10:00:01.000Z",
            "runId": "RUN-1", "reportId": "REP-1", "sourceSha256": "abc",
            "controlProfileId": "p1", "controlProfileVersion": "v1",
            # no correlationId key at all
        },
        "httpErrorCode": None, "n8nErrorCode": None, "explanation": None,
        "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None,
    }
    out = _run_chain(envelope)
    assert out["ok"] is True, out
    ae = out["result"]["activityExecution"]
    assert ae["status"] == "FAILED"
    assert ae["resultCode"] == "ACTIVITY_EXECUTION_REPORT_CORRELATION_MISMATCH"
    assert ae["executionId"].startswith("N8N-FAIL-")
    assert ae["inputRefs"] == []
    assert ae["outputRefs"] == []
    assert ae["evidenceRefs"] == []
    assert ae["controlReportRef"] is None, "the mismatched report must never be attached as authoritative evidence"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_report_outcome_with_mismatched_correlation_id_fails_closed():
    """Same fail-closed contract as the missing-correlationId case, but for
    a report that carries a real, non-empty correlationId belonging to a
    different run -- the exact scenario A1's finding names: a misrouted or
    buggy API response pointing at a control report from a different run."""
    envelope = {
        **BASE_ENVELOPE,
        "outcome": "REPORT",
        "report": {
            "status": "unauffaellig", "routing": "standard_review",
            "startedAt": "2026-08-14T10:00:00.100Z", "createdAt": "2026-08-14T10:00:01.000Z",
            "runId": "RUN-1", "reportId": "REP-1", "sourceSha256": "abc",
            "controlProfileId": "p1", "controlProfileVersion": "v1",
            "correlationId": "SOME-OTHER-RUNS-CORRELATION-ID",
        },
        "httpErrorCode": None, "n8nErrorCode": None, "explanation": None,
        "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None,
    }
    out = _run_chain(envelope)
    assert out["ok"] is True, out
    ae = out["result"]["activityExecution"]
    assert ae["status"] == "FAILED"
    assert ae["resultCode"] == "ACTIVITY_EXECUTION_REPORT_CORRELATION_MISMATCH"
    assert ae["executionId"].startswith("N8N-FAIL-")
    assert ae["inputRefs"] == []
    assert ae["outputRefs"] == []
    assert ae["evidenceRefs"] == []
    assert ae["controlReportRef"] is None, "the mismatched report must never be attached as authoritative evidence"
    # correlationId on the ActivityExecution itself is always the envelope's
    # own (trusted) value, never copied from the untrusted report.
    assert ae["correlationId"] == "CORR-1"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_http_error_outcome_maps_to_failed_never_succeeded():
    """The direct regression guard for the round-1 bug this plan fixes: a
    4xx/no-report response must never produce SUCCEEDED."""
    envelope = {
        **BASE_ENVELOPE,
        "outcome": "HTTP_ERROR", "report": None,
        "httpErrorCode": "ORGANIZATION_CONTEXT_REQUIRED", "n8nErrorCode": None,
        "explanation": "missing org",
        "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None,
    }
    out = _run_chain(envelope)
    assert out["ok"] is True, out
    ae = out["result"]["activityExecution"]
    assert ae["status"] == "FAILED"
    assert ae["resultCode"] == "ORGANIZATION_CONTEXT_REQUIRED"
    assert ae["executionId"].startswith("N8N-FAIL-")


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_transport_failure_outcome_maps_to_failed():
    envelope = {
        **BASE_ENVELOPE,
        "outcome": "TRANSPORT_FAILURE", "report": None,
        "httpErrorCode": None, "n8nErrorCode": "INVOICE_PROCESSING_SERVICE_UNAVAILABLE",
        "explanation": "ECONNREFUSED",
        "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None,
    }
    out = _run_chain(envelope)
    assert out["ok"] is True, out
    ae = out["result"]["activityExecution"]
    assert ae["status"] == "FAILED"
    assert ae["resultCode"] == "INVOICE_PROCESSING_SERVICE_UNAVAILABLE"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_timeout_outcome_maps_to_timed_out():
    envelope = {
        **BASE_ENVELOPE,
        "outcome": "TIMEOUT", "report": None,
        "httpErrorCode": None, "n8nErrorCode": "INVOICE_PROCESSING_SERVICE_TIMEOUT",
        "explanation": "connect ETIMEDOUT",
        "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None,
    }
    out = _run_chain(envelope)
    assert out["ok"] is True, out
    ae = out["result"]["activityExecution"]
    assert ae["status"] == "TIMED_OUT"
    assert ae["resultCode"] == "INVOICE_PROCESSING_SERVICE_TIMEOUT"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_pre_flight_rejected_outcome_maps_to_not_executed_with_instantaneous_gate():
    envelope = {
        **BASE_ENVELOPE,
        "outcome": "PRE_FLIGHT_REJECTED", "report": None,
        "httpErrorCode": None, "n8nErrorCode": "MISSING_INVOICE_FILE",
        "explanation": "no file",
        "phase1AttemptStartedAt": None, "gateDecisionAt": "2026-08-14T09:59:59.000Z",
    }
    out = _run_chain(envelope)
    assert out["ok"] is True, out
    ae = out["result"]["activityExecution"]
    assert ae["status"] == "NOT_EXECUTED"
    assert ae["resultCode"] == "MISSING_INVOICE_FILE"
    assert ae["startedAt"] == ae["completedAt"] == "2026-08-14T09:59:59.000Z"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_unknown_outcome_throws_instead_of_silently_assembling():
    envelope = {**BASE_ENVELOPE, "outcome": "SOMETHING_ELSE", "report": None,
                "httpErrorCode": None, "n8nErrorCode": None, "explanation": None,
                "phase1AttemptStartedAt": None, "gateDecisionAt": None}
    out = _run_chain(envelope)
    assert out["ok"] is False
    assert "ACTIVITY_EXECUTION_UNKNOWN_OUTCOME" in out["message"]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_every_outcome_produces_a_schema_valid_object():
    """Every one of the five real branch outcomes must pass 01.4's own
    embedded validator -- proving the validator actually runs and actually
    gates a real assembled object, not merely that it exists in source."""
    scenarios = [
        {**BASE_ENVELOPE, "outcome": "REPORT",
         "report": {"status": "unauffaellig", "routing": "standard_review",
                     "startedAt": "2026-08-14T10:00:00.100Z", "createdAt": "2026-08-14T10:00:01.000Z",
                     "runId": "RUN-1", "reportId": "REP-1", "sourceSha256": "abc",
                     "controlProfileId": "p1", "controlProfileVersion": "v1",
                     "correlationId": "CORR-1"},
         "httpErrorCode": None, "n8nErrorCode": None, "explanation": None,
         "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None},
        {**BASE_ENVELOPE, "outcome": "HTTP_ERROR", "report": None,
         "httpErrorCode": "ORGANIZATION_CONTEXT_REQUIRED", "n8nErrorCode": None,
         "explanation": "x", "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None},
        {**BASE_ENVELOPE, "outcome": "TRANSPORT_FAILURE", "report": None,
         "httpErrorCode": None, "n8nErrorCode": "INVOICE_PROCESSING_SERVICE_UNAVAILABLE",
         "explanation": "x", "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None},
        {**BASE_ENVELOPE, "outcome": "TIMEOUT", "report": None,
         "httpErrorCode": None, "n8nErrorCode": "INVOICE_PROCESSING_SERVICE_TIMEOUT",
         "explanation": "x", "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None},
        {**BASE_ENVELOPE, "outcome": "PRE_FLIGHT_REJECTED", "report": None,
         "httpErrorCode": None, "n8nErrorCode": "MISSING_INVOICE_FILE",
         "explanation": "x", "phase1AttemptStartedAt": None, "gateDecisionAt": "2026-08-14T09:59:59.000Z"},
        {**BASE_ENVELOPE, "outcome": "REPORT",
         "report": {"status": "unauffaellig", "routing": "standard_review",
                     "startedAt": "2026-08-14T10:00:00.100Z", "createdAt": "2026-08-14T10:00:01.000Z",
                     "runId": "RUN-1", "reportId": "REP-1", "sourceSha256": "abc",
                     "controlProfileId": "p1", "controlProfileVersion": "v1",
                     "correlationId": "SOME-OTHER-RUNS-CORRELATION-ID"},
         "httpErrorCode": None, "n8nErrorCode": None, "explanation": None,
         "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None},
    ]
    for envelope in scenarios:
        out = _run_chain(envelope)
        assert out["ok"] is True, (envelope["outcome"], out)


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_malformed_envelope_is_rejected_by_the_generated_validator():
    """A REPORT envelope whose report is missing required fields must still
    reach 01.3, produce a structurally malformed object, and be rejected by
    01.4 -- proving the validator, not merely 01.1's binding guard, is what
    blocks a bad object."""
    envelope = {
        **BASE_ENVELOPE,
        "outcome": "REPORT",
        # correlationId present and matching, so this exercises 01.4's schema
        # check specifically -- not the 01.2 correlation-integrity fail-closed
        # path (see test_report_outcome_with_missing_correlation_id_fails_closed).
        "report": {"status": "unauffaellig", "routing": "standard_review", "correlationId": "CORR-1"},  # missing startedAt/createdAt
        "httpErrorCode": None, "n8nErrorCode": None, "explanation": None,
        "phase1AttemptStartedAt": "2026-08-14T10:00:00.050Z", "gateDecisionAt": None,
    }
    out = _run_chain(envelope)
    assert out["ok"] is False
    assert "ACTIVITY_EXECUTION_SCHEMA_INVALID" in out["message"]
