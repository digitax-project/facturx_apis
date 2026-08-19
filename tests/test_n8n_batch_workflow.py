import json
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).parent.parent
    / "examples"
    / "n8n"
    / "digitax_invoice_phase1_flow1a_batch_item_v1_0_0.json"
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
    assert WEBHOOK_NODE in organization["value"]
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
    assert data["connections"][MERGE_NODE]["main"][0][0]["node"] == RESPOND_NODE


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
