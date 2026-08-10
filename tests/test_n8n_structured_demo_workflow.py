"""Regression guard for examples/n8n/digitax_invoice_phase1_structured_demo.json.

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
    / "digitax_invoice_phase1_structured_demo.json"
)

FORBIDDEN_PATTERNS = [
    (re.compile(r"host\.docker\.internal"), "a hardcoded local-dev host"),
    (re.compile(r"https?://(?!.*\{\{)"), "a hardcoded http(s) URL outside an expression"),
    (re.compile(r"vn ?impex", re.IGNORECASE), "the real organization name"),
]

HTTP_NODE_NAMES = ("GET /capabilities", "POST /v1/invoices/process")
FAILURE_NODE_NAMES = {
    "GET /capabilities": "API Failure - Capabilities",
    "POST /v1/invoices/process": "API Failure - Process Invoice",
}


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
        assert "failedStep" in code and "errorCode" in code and "correlationId" in code, (
            f"{failure_name!r} must retain failed step, error code, and correlation ID"
        )


def test_api_failure_nodes_feed_into_status_routing():
    data = _load_workflow()
    for failure_name in FAILURE_NODE_NAMES.values():
        branches = data["connections"][failure_name]["main"]
        targets = {edge["node"] for branch in branches for edge in branch}
        assert targets == {"Status Routing"}, (
            f"{failure_name!r} must route through the existing Status Routing switch, "
            "not duplicate its logic"
        )


def test_technical_review_routing_value_falls_through_to_fallback():
    """The failure nodes emit routing="technical_review", which must not match
    either explicit Switch rule -- it must fall through to the fallback output,
    landing on Human Review - Unclassified (fallback), not a specific queue."""
    data = _load_workflow()
    switch_node = _nodes_by_name(data)["Status Routing"]
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
    for required in (
        "Human Review - Standard",
        "Human Review - Prioritized",
        "Human Review - Unclassified (fallback)",
    ):
        assert required in name_set, f"missing required terminal node {required!r}"


def test_status_routing_has_three_outputs_wired_to_review_nodes():
    data = _load_workflow()
    branches = data["connections"]["Status Routing"]["main"]
    assert len(branches) == 3
    targets = [b[0]["node"] for b in branches]
    assert targets == [
        "Human Review - Standard",
        "Human Review - Prioritized",
        "Human Review - Unclassified (fallback)",
    ]


def test_workflow_never_reaches_approval_booking_payment_or_supplier_nodes():
    data = _load_workflow()
    forbidden_terms = ("approv", "booking", "payment", "supplier communication", "pay_")
    for node in data["nodes"]:
        lowered = node["name"].lower()
        assert not any(term in lowered for term in forbidden_terms), (
            f"node {node['name']!r} looks like it goes past the Phase 1 human-review boundary"
        )
    terminal_types = {n["type"] for n in data["nodes"] if n["name"].startswith("Human Review")}
    assert terminal_types == {"n8n-nodes-base.noOp"}, "human-review endpoints must be no-ops"
