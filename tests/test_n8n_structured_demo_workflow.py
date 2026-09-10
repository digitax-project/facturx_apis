"""Regression guard for
examples/n8n/digitax_invoice_phase1_flow1a_structured_regression_v1_0_0.json
("DigiTax | Invoice Phase 1 | Flow 1a | Structured Regression | v1.0.0").

This is a structural check, not a live n8n import -- examples/n8n/README.md
records the real import/execution evidence (via the pinned n8nio/n8n:2.33.6
Docker image) separately. This test exists so a future edit can't silently
reintroduce a hardcoded host/credential, break the graph, remove either
human-review route, or drop the bounded-retry/API-failure fallback that
AGENTS.md requires (technical failures must route to nicht_pruefbar human
review with a failed step, stable error code, and correlation ID -- never an
unhandled execution error).
"""
import json
import re
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).parent.parent
    / "examples"
    / "n8n"
    / "digitax_invoice_phase1_flow1a_structured_regression_v1_0_0.json"
)

FORBIDDEN_PATTERNS = [
    (re.compile(r"host\.docker\.internal"), "a hardcoded local-dev host"),
    (re.compile(r"https?://(?!.*\{\{)"), "a hardcoded http(s) URL outside an expression"),
    (re.compile(r"vn ?impex", re.IGNORECASE), "the real organization name"),
]

HTTP_NODE_NAMES = ("02.1 Read API capabilities", "03.1 Run DigiTax controls")
FAILURE_NODE_NAMES = {
    "02.1 Read API capabilities": "02.3 Handle capabilities failure",
    "03.1 Run DigiTax controls": "03.2 Handle controls-call failure",
}
STATUS_ROUTING_NODE = "04.2 Route by review status"
REVIEW_NODES = (
    "05.1 Human review - standard",
    "05.2 Human review - prioritized",
    "05.3 Human review - unclassified",
)


def _load_workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _nodes_by_name(data: dict) -> dict:
    return {n["name"]: n for n in data["nodes"]}


def test_workflow_file_exists_and_is_valid_json():
    assert WORKFLOW_PATH.exists(), "structured demo workflow export is missing"
    _load_workflow()  # raises if not valid JSON


def test_workflow_has_no_instance_id():
    data = _load_workflow()
    assert "instanceId" not in data.get("meta", {})


def test_workflow_has_no_credentials():
    data = _load_workflow()
    for node in data["nodes"]:
        assert "credentials" not in node, f"node {node['name']!r} carries credentials"


def test_workflow_has_no_forbidden_content():
    text = json.dumps(_load_workflow())
    for pattern, description in FORBIDDEN_PATTERNS:
        assert not pattern.search(text), f"found {description} in the workflow export"


def test_workflow_connections_reference_existing_nodes_no_duplicates():
    data = _load_workflow()
    node_names = [n["name"] for n in data["nodes"]]
    node_ids = [n["id"] for n in data["nodes"]]
    assert len(node_ids) == len(set(node_ids)), "duplicate node ids"
    assert len(node_names) == len(set(node_names)), "duplicate node names"

    name_set = set(node_names)
    for source_name, outputs in data.get("connections", {}).items():
        assert source_name in name_set, f"connection source {source_name!r} does not exist"
        for branches in outputs.values():
            for branch in branches:
                for edge in branch:
                    assert edge["node"] in name_set, (
                        f"connection target {edge['node']!r} does not exist "
                        f"(referenced from {source_name!r})"
                    )


def test_api_urls_are_configurable_via_env_expression():
    data = _load_workflow()
    nodes = _nodes_by_name(data)
    for name in HTTP_NODE_NAMES:
        url = nodes[name]["parameters"]["url"]
        assert url.startswith("={{ $env."), (
            f"{name!r} must resolve its base URL from an environment "
            f"expression, not a hardcoded value; got {url!r}"
        )


def test_http_nodes_have_bounded_retry_and_error_branch():
    data = _load_workflow()
    nodes = _nodes_by_name(data)
    for name in HTTP_NODE_NAMES:
        node = nodes[name]
        assert node.get("retryOnFail") is True, f"{name!r} must retry transient failures"
        max_tries = node.get("maxTries")
        assert isinstance(max_tries, int) and 1 < max_tries <= 5, (
            f"{name!r} retry must be bounded (2-5 tries), got {max_tries!r}"
        )
        assert isinstance(node.get("waitBetweenTries"), int) and node["waitBetweenTries"] > 0
        assert node.get("onError") == "continueErrorOutput", (
            f"{name!r} must route exhausted failures to an error output, "
            "not fail the whole execution"
        )


def test_http_node_error_outputs_reach_dedicated_failure_handlers():
    data = _load_workflow()
    for http_name, failure_name in FAILURE_NODE_NAMES.items():
        branches = data["connections"][http_name]["main"]
        assert len(branches) == 2, f"{http_name!r} must have a success and an error output"
        error_branch = branches[1]
        targets = {edge["node"] for edge in error_branch}
        assert targets == {failure_name}, (
            f"{http_name!r} error output must go to {failure_name!r}, got {targets!r}"
        )


def test_api_failure_nodes_build_nicht_pruefbar_technical_review_payload():
    data = _load_workflow()
    nodes = _nodes_by_name(data)
    for http_name, failure_name in FAILURE_NODE_NAMES.items():
        code = nodes[failure_name]["parameters"]["jsCode"]
        assert '"nicht_pruefbar"' in code, f"{failure_name!r} must report status nicht_pruefbar"
        assert '"technical_review"' in code, f"{failure_name!r} must use a routing value distinct from the known review routes"
        assert "failedStep" in code and "n8nErrorCode" in code and "correlationId" in code, (
            f"{failure_name!r} must retain failed step, error code, and correlation ID"
        )


CALL_ASSEMBLE_NODE = "Call Assemble ActivityExecution"


def test_api_failure_nodes_feed_into_status_routing():
    """Every failure node now feeds the shared Assemble ActivityExecution
    call (which feeds Merge, which feeds the existing Status Routing switch)
    instead of Status Routing directly -- see
    test_status_routing_reached_via_merge_activity_execution below for the
    rest of that chain."""
    data = _load_workflow()
    for failure_name in FAILURE_NODE_NAMES.values():
        branches = data["connections"][failure_name]["main"]
        targets = {edge["node"] for branch in branches for edge in branch}
        assert targets == {CALL_ASSEMBLE_NODE}, (
            f"{failure_name!r} must route through the shared Assemble ActivityExecution call, "
            "not duplicate control-report logic"
        )


def test_status_routing_reached_via_merge_activity_execution():
    data = _load_workflow()
    assert (
        data["connections"][CALL_ASSEMBLE_NODE]["main"][0][0]["node"]
        == "Merge ActivityExecution into outcome"
    )
    assert (
        data["connections"]["Merge ActivityExecution into outcome"]["main"][0][0]["node"]
        == STATUS_ROUTING_NODE
    )


def test_technical_review_routing_value_falls_through_to_fallback():
    """The failure nodes emit routing="technical_review", which must not match
    either explicit Switch rule -- it must fall through to the fallback output,
    landing on the unclassified human-review node, not a specific queue."""
    data = _load_workflow()
    switch_node = _nodes_by_name(data)[STATUS_ROUTING_NODE]
    rule_values = {
        cond["rightValue"]
        for rule in switch_node["parameters"]["rules"]["values"]
        for cond in rule["conditions"]["conditions"]
    }
    assert "technical_review" not in rule_values
    assert switch_node["parameters"]["options"]["fallbackOutput"] == "extra"


def test_both_human_review_routes_and_fallback_exist():
    data = _load_workflow()
    name_set = {n["name"] for n in data["nodes"]}
    for required in REVIEW_NODES:
        assert required in name_set, f"missing required terminal node {required!r}"


def test_status_routing_has_three_outputs_wired_to_review_nodes():
    data = _load_workflow()
    branches = data["connections"][STATUS_ROUTING_NODE]["main"]
    assert len(branches) == 3
    targets = [b[0]["node"] for b in branches]
    assert targets == list(REVIEW_NODES)


def test_workflow_never_reaches_approval_booking_payment_or_supplier_nodes():
    data = _load_workflow()
    forbidden_terms = ("approv", "booking", "payment", "supplier communication", "pay_")
    for node in data["nodes"]:
        lowered = node["name"].lower()
        assert not any(term in lowered for term in forbidden_terms), (
            f"node {node['name']!r} looks like it goes past the Phase 1 human-review boundary"
        )
    terminal_types = {n["type"] for n in data["nodes"] if n["name"] in REVIEW_NODES}
    assert terminal_types == {"n8n-nodes-base.noOp"}, "human-review endpoints must be no-ops"


# ---------------------------------------------------------------------------
# P2.1 Wave 1 A5 Stage 1: identity propagation + shared ActivityExecution
# assembly. Named 01.3/02.9 (not 01.2/02.3) since those names are already
# taken by "01.2 Load demo fixture" and "02.3 Handle capabilities failure"
# in this workflow.
# ---------------------------------------------------------------------------

RUN_CONTEXT_NODE = "01.3 Build run context"
MARK_ATTEMPT_START_NODE = "02.9 Mark phase1 attempt start"
BUILD_REPORT_NODE = "04.1 Build control report"
CALL_ASSEMBLE_NODE = "Call Assemble ActivityExecution"
MERGE_NODE = "Merge ActivityExecution into outcome"


def test_run_context_inserted_between_fixture_and_capabilities_read():
    data = _load_workflow()
    assert data["connections"]["01.2 Load demo fixture"]["main"][0][0]["node"] == RUN_CONTEXT_NODE
    assert data["connections"][RUN_CONTEXT_NODE]["main"][0][0]["node"] == "02.1 Read API capabilities"


def test_mark_attempt_start_inserted_between_profile_check_and_controls_call():
    data = _load_workflow()
    assert data["connections"]["02.2 Check Factur-X profile"]["main"][0][0]["node"] == MARK_ATTEMPT_START_NODE
    assert data["connections"][MARK_ATTEMPT_START_NODE]["main"][0][0]["node"] == "03.1 Run DigiTax controls"


def test_run_context_generates_secure_ids_with_no_weak_fallback():
    code = _nodes_by_name(_load_workflow())[RUN_CONTEXT_NODE]["parameters"]["jsCode"]
    assert 'require("crypto").randomUUID' in code
    assert "correlationId" in code and "processInstanceId" in code
    assert "Math.random()" not in code
    assert "SECURE_UUID_UNAVAILABLE" in code


def test_controls_call_sends_x_correlation_id_header():
    node = _nodes_by_name(_load_workflow())["03.1 Run DigiTax controls"]
    assert node["parameters"]["sendHeaders"] is True
    headers = node["parameters"]["headerParameters"]["parameters"]
    header = next(h for h in headers if h["name"] == "X-Correlation-ID")
    assert RUN_CONTEXT_NODE in header["value"]


def test_branch_nodes_emit_normalized_envelope_and_no_full_activity_execution():
    data = _load_workflow()
    nodes = _nodes_by_name(data)

    capabilities_code = nodes["02.3 Handle capabilities failure"]["parameters"]["jsCode"]
    assert '"PRE_FLIGHT_REJECTED"' in capabilities_code
    assert "gateDecisionAt" in capabilities_code

    controls_failure_code = nodes["03.2 Handle controls-call failure"]["parameters"]["jsCode"]
    assert '"TRANSPORT_FAILURE"' in controls_failure_code
    assert '"TIMEOUT"' in controls_failure_code
    assert "ETIMEDOUT" in controls_failure_code

    build_report_code = nodes[BUILD_REPORT_NODE]["parameters"]["jsCode"]
    assert '"REPORT"' in build_report_code

    for name in ("02.3 Handle capabilities failure", "03.2 Handle controls-call failure", BUILD_REPORT_NODE):
        assert '"executionId"' not in nodes[name]["parameters"]["jsCode"]


def test_all_three_branch_nodes_converge_on_shared_assembly():
    data = _load_workflow()
    for source in ("02.3 Handle capabilities failure", "03.2 Handle controls-call failure", BUILD_REPORT_NODE):
        targets = {edge["node"] for branch in data["connections"][source]["main"] for edge in branch}
        assert targets == {CALL_ASSEMBLE_NODE}, f"{source!r} must feed {CALL_ASSEMBLE_NODE!r}"
    assert data["connections"][CALL_ASSEMBLE_NODE]["main"][0][0]["node"] == MERGE_NODE
    assert data["connections"][MERGE_NODE]["main"][0][0]["node"] == STATUS_ROUTING_NODE


def test_call_assemble_activity_execution_references_shared_subworkflow():
    node = _nodes_by_name(_load_workflow())[CALL_ASSEMBLE_NODE]
    assert node["type"] == "n8n-nodes-base.executeWorkflow"
    assert (
        node["parameters"]["workflowId"]["value"]
        == "digitax-invoice-phase1-shared-assemble-activity-execution"
    )
