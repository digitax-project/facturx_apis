import json
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).parent.parent
    / "examples"
    / "n8n"
    / "digitax_invoice_phase1_flow1a_batch_item_v1_1_0.json"
)


def _workflow():
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


WEBHOOK_NODE = "01.1 Receive batch item"
PROCESS_NODE = "03.1 Run DigiTax controls"
RESPOND_NODE = "04.2 Respond to batch caller"


def test_batch_workflow_is_portable_and_profile_dynamic():
    workflow = _workflow()
    nodes = {node["name"]: node for node in workflow["nodes"]}
    assert workflow["active"] is True
    assert "instanceId" not in workflow.get("meta", {})
    assert all("credentials" not in node for node in workflow["nodes"])
    assert nodes[WEBHOOK_NODE]["parameters"]["path"] == "phase1-invoice-batch-item"

    process = nodes[PROCESS_NODE]
    assert process["parameters"]["url"].startswith("={{ $env.")
    parameters = process["parameters"]["bodyParameters"]["parameters"]
    organization = next(item for item in parameters if item["name"] == "organizationId")
    # A6a correction round 1 (section 3): the Phase-1 API keeps its existing
    # multipart field name "organizationId", but n8n now supplies its value
    # from the resolved phase1ProfileKey (01.2 Build run context), not the
    # raw webhook body directly.
    assert "01.2 Build run context" in organization["value"]
    assert "phase1ProfileKey" in organization["value"]
    assert "unternehmen-x-demo" not in organization["value"]
    assert "unternehmen-y-demo" not in organization["value"]


def test_batch_workflow_returns_json_with_cors_and_bounded_retry():
    nodes = {node["name"]: node for node in _workflow()["nodes"]}
    process = nodes[PROCESS_NODE]
    assert process["retryOnFail"] is True
    assert process["maxTries"] == 3
    assert process["parameters"]["options"]["response"]["response"]["neverError"] is True

    respond = nodes[RESPOND_NODE]
    assert respond["parameters"]["respondWith"] == "json"
    headers = respond["parameters"]["options"]["responseHeaders"]["entries"]
    assert {item["name"]: item["value"] for item in headers}["Access-Control-Allow-Origin"] == "*"


# ---------------------------------------------------------------------------
# P2.1 Wave 1 A5 Stage 1: identity propagation + shared ActivityExecution
# assembly. This workflow previously had no Build run context node at all
# (01.1 fed 03.1 directly) -- Stage 1 adds one.
# ---------------------------------------------------------------------------

RUN_CONTEXT_NODE = "01.2 Build run context"
MARK_ATTEMPT_START_NODE = "01.3 Mark phase1 attempt start"
BUILD_REPORT_NODE = "04.1 Build control report"
CALL_ASSEMBLE_NODE = "Call Assemble ActivityExecution"
MERGE_NODE = "Merge ActivityExecution into outcome"


def test_run_context_inserted_between_webhook_and_attempt_start():
    data = _workflow()
    assert data["connections"][WEBHOOK_NODE]["main"][0][0]["node"] == RUN_CONTEXT_NODE
    assert data["connections"][RUN_CONTEXT_NODE]["main"][0][0]["node"] == MARK_ATTEMPT_START_NODE
    assert data["connections"][MARK_ATTEMPT_START_NODE]["main"][0][0]["node"] == PROCESS_NODE


def test_run_context_generates_secure_ids_with_no_weak_fallback():
    nodes = {node["name"]: node for node in _workflow()["nodes"]}
    code = nodes[RUN_CONTEXT_NODE]["parameters"]["jsCode"]
    assert 'require("crypto").randomUUID' in code
    assert "correlationId" in code and "processInstanceId" in code
    assert "Math.random()" not in code
    assert "SECURE_UUID_UNAVAILABLE" in code


def test_controls_call_sends_x_correlation_id_header():
    nodes = {node["name"]: node for node in _workflow()["nodes"]}
    node = nodes[PROCESS_NODE]
    assert node["parameters"]["sendHeaders"] is True
    headers = node["parameters"]["headerParameters"]["parameters"]
    header = next(h for h in headers if h["name"] == "X-Correlation-ID")
    assert RUN_CONTEXT_NODE in header["value"]


def test_both_controls_outputs_feed_call_assemble_via_build_control_report():
    data = _workflow()
    branches = data["connections"][PROCESS_NODE]["main"]
    targets = {edge["node"] for branch in branches for edge in branch}
    assert targets == {BUILD_REPORT_NODE}, "both success and error outputs must converge on the classifier"
    assert data["connections"][BUILD_REPORT_NODE]["main"][0][0]["node"] == CALL_ASSEMBLE_NODE
    assert data["connections"][CALL_ASSEMBLE_NODE]["main"][0][0]["node"] == MERGE_NODE
    assert data["connections"][MERGE_NODE]["main"][0][0]["node"] == RISK_REVIEW_GATE_NODE


# ---------------------------------------------------------------------------
# A6a synthetic TCMS demo extension (v1.1.0): gated DigiTax Risk Review call
# and bounded result bundle. See examples/n8n/README.md's "A6a synthetic
# TCMS demo extension" section and
# coordination/control-plane/runs/2026-08-25-unternehmen-x-pilot-integration/A6-n8n-integration/A6a-auth-boundary-amendment.md.
# ---------------------------------------------------------------------------

RISK_REVIEW_GATE_NODE = "04.3 Evaluate risk review gate"
RISK_REVIEW_ROUTE_NODE = "04.4 Route by risk review need"
RISK_REVIEW_CALL_NODE = "04.5 Run DigiTax Risk Review"
RISK_REVIEW_HANDLE_NODE = "04.6 Handle risk review response"
ASSEMBLE_BUNDLE_NODE = "04.7 Assemble result bundle"


def test_risk_review_extension_wires_gate_through_to_respond_node():
    data = _workflow()
    assert data["connections"][RISK_REVIEW_GATE_NODE]["main"][0][0]["node"] == RISK_REVIEW_ROUTE_NODE
    route_branches = data["connections"][RISK_REVIEW_ROUTE_NODE]["main"]
    assert route_branches[0][0]["node"] == RISK_REVIEW_CALL_NODE
    assert route_branches[1][0]["node"] == ASSEMBLE_BUNDLE_NODE
    call_branches = data["connections"][RISK_REVIEW_CALL_NODE]["main"]
    targets = {edge["node"] for branch in call_branches for edge in branch}
    assert targets == {RISK_REVIEW_HANDLE_NODE}, "both success and error outputs must converge on the handler"
    assert data["connections"][RISK_REVIEW_HANDLE_NODE]["main"][0][0]["node"] == ASSEMBLE_BUNDLE_NODE
    assert data["connections"][ASSEMBLE_BUNDLE_NODE]["main"][0][0]["node"] == RESPOND_NODE


def test_risk_review_gate_never_calls_the_service_for_a_clean_report():
    nodes = {node["name"]: node for node in _workflow()["nodes"]}
    code = nodes[RISK_REVIEW_GATE_NODE]["parameters"]["jsCode"]
    assert '"unauffaellig"' in code
    assert "needsRiskReview: false" in code
    assert '"NO_RISK_REVIEW_REQUIRED"' in code
    assert '"TECHNICAL_FAILURE"' in code


def test_risk_review_gate_never_recomputes_a_control_and_reuses_run_identity():
    nodes = {node["name"]: node for node in _workflow()["nodes"]}
    code = nodes[RISK_REVIEW_GATE_NODE]["parameters"]["jsCode"]
    # Findings are selected, never recomputed: no new control-evaluation logic.
    assert '["failed", "not_reliable", "not_run"]' in code
    # Identity propagation: no fresh UUID minted for the Risk Review call.
    assert "randomUUID" not in code
    assert "requestId: ctx.processInstanceId" in code
    assert "correlationId: ctx.correlationId" in code
    assert 'schemaVersion: "1.1.0"' in code


def test_risk_review_call_is_bounded_retry_and_never_throws_on_http_error():
    nodes = {node["name"]: node for node in _workflow()["nodes"]}
    node = nodes[RISK_REVIEW_CALL_NODE]
    assert node["parameters"]["url"] == "={{ $env.FACTURX_RISK_REVIEW_API_BASE_URL }}/v1/risk-review"
    assert node["retryOnFail"] is True
    assert node["maxTries"] == 3
    assert node["onError"] == "continueErrorOutput"
    assert node["parameters"]["options"]["response"]["response"]["neverError"] is True
    assert "credentials" not in node


def test_risk_review_response_passes_disposition_through_as_routing_status():
    nodes = {node["name"]: node for node in _workflow()["nodes"]}
    code = nodes[RISK_REVIEW_HANDLE_NODE]["parameters"]["jsCode"]
    assert "riskReviewReport: body" in code
    assert "routingStatus: body.disposition" in code
    assert '"TECHNICAL_FAILURE"' in code


def test_assemble_result_bundle_is_additive_to_existing_dashboard_shape():
    nodes = {node["name"]: node for node in _workflow()["nodes"]}
    code = nodes[ASSEMBLE_BUNDLE_NODE]["parameters"]["jsCode"]
    for field in ("ok", "statusCode", "canonicalInvoice", "errorCode", "detail"):
        assert field in code, f"existing Batch Demo dashboard field {field!r} must be preserved"
    for field in ("phase1ControlReport", "activityExecution", "riskReviewReport", "routingStatus"):
        assert field in code, f"bounded result bundle field {field!r} must be present"


def test_no_ai_execution_profile_ref_is_set_for_the_risk_review_request():
    nodes = {node["name"]: node for node in _workflow()["nodes"]}
    code = nodes[RISK_REVIEW_GATE_NODE]["parameters"]["jsCode"]
    assert "aiExecutionProfileRef" not in code


def test_build_control_report_emits_normalized_envelope():
    nodes = {node["name"]: node for node in _workflow()["nodes"]}
    code = nodes[BUILD_REPORT_NODE]["parameters"]["jsCode"]
    for outcome in ("REPORT", "HTTP_ERROR", "TRANSPORT_FAILURE", "TIMEOUT"):
        assert f'"{outcome}"' in code
    assert '"executionId"' not in code, "the branch node must not construct a full ActivityExecution object"


def test_call_assemble_activity_execution_references_shared_subworkflow():
    nodes = {node["name"]: node for node in _workflow()["nodes"]}
    call_node = nodes[CALL_ASSEMBLE_NODE]
    assert call_node["type"] == "n8n-nodes-base.executeWorkflow"
    assert (
        call_node["parameters"]["workflowId"]["value"]
        == "digitax-invoice-phase1-shared-assemble-activity-execution"
    )
