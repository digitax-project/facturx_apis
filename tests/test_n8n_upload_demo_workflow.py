"""Regression guard for
examples/n8n/digitax_invoice_phase1_flow1a_upload_v1_0_0.json
("DigiTax | Invoice Phase 1 | Flow 1a | Upload Demo | v1.0.0").

Structural check only -- examples/n8n/README.md and the coordination
handover log record the real webhook-execution evidence (via the isolated
docker-compose.phase1-upload-demo.yml stack against real n8n 2.33.7). This
test exists so a future edit can't silently reintroduce a hardcoded host,
drop the explicit technical_review route, embed a fixture in an
operator-facing workflow, break the graph, or start retrying deterministic
4xx input/contract errors.
"""
import json
import re
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).parent.parent
    / "examples"
    / "n8n"
    / "digitax_invoice_phase1_flow1a_upload_v1_0_0.json"
)

FORBIDDEN_PATTERNS = [
    (re.compile(r"host\.docker\.internal"), "a hardcoded local-dev host"),
    (re.compile(r"https?://(?!.*\{\{)"), "a hardcoded http(s) URL outside an expression"),
    (re.compile(r"vn ?impex", re.IGNORECASE), "the real organization name"),
]

WEBHOOK_NODE = "01.1 Receive invoice upload"
RUN_CONTEXT_NODE = "01.2 Build run context"
HTTP_NODE_NAMES = ("02.1 Read API capabilities", "03.1 Run DigiTax controls")
CLASSIFY_RESPONSE_NODE = "03.2 Classify controls response"
BUILD_REPORT_NODE = "04.1 Build control report"
RESPOND_NODE = "04.2 Respond to browser"
STATUS_ROUTING_NODE = "04.3 Route by review status"
REVIEW_NODES = (
    "05.1 Human review - standard",
    "05.2 Human review - prioritized",
    "05.3 Human review - technical",
    "05.4 Human review - unknown",
)


def _load_workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _nodes_by_name(data: dict) -> dict:
    return {n["name"]: n for n in data["nodes"]}


def test_workflow_file_exists_and_is_valid_json():
    assert WORKFLOW_PATH.exists(), "upload demo workflow export is missing"
    _load_workflow()


def test_workflow_has_no_instance_id_or_credentials():
    data = _load_workflow()
    assert "instanceId" not in data.get("meta", {})
    for node in data["nodes"]:
        assert "credentials" not in node, f"node {node['name']!r} carries credentials"


def test_workflow_has_no_forbidden_content():
    text = json.dumps(_load_workflow())
    for pattern, description in FORBIDDEN_PATTERNS:
        assert not pattern.search(text), f"found {description} in the workflow export"


def test_workflow_does_not_embed_an_invoice_fixture():
    """Unlike the regression demo, this is operator-facing and must accept a
    real upload -- it must never carry a baked-in invoice."""
    text = json.dumps(_load_workflow())
    assert "demoInvoiceBase64" not in text
    assert "CrossIndustryInvoice" not in text  # no inlined XML/base64 payload


def test_workflow_is_active_so_its_webhook_can_run():
    data = _load_workflow()
    assert data["active"] is True


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


def test_webhook_trigger_accepts_post_multipart():
    data = _load_workflow()
    webhook = _nodes_by_name(data)[WEBHOOK_NODE]
    assert webhook["type"] == "n8n-nodes-base.webhook"
    assert webhook["parameters"]["httpMethod"] == "POST"
    assert webhook["parameters"]["responseMode"] == "responseNode"


def test_run_context_created_before_any_http_call():
    data = _load_workflow()
    # Build run context must be the webhook's immediate next node -- the
    # correlation ID has to exist before either HTTP node runs.
    first_hop = data["connections"][WEBHOOK_NODE]["main"][0][0]["node"]
    assert first_hop == RUN_CONTEXT_NODE
    code = _nodes_by_name(data)[RUN_CONTEXT_NODE]["parameters"]["jsCode"]
    assert "correlationId" in code


def test_organization_id_only_defaults_under_explicit_demo_mode():
    data = _load_workflow()
    code = _nodes_by_name(data)[RUN_CONTEXT_NODE]["parameters"]["jsCode"]
    assert "demoModeRequested" in code
    assert '"unternehmen-x-demo"' in code
    # The default must be conditioned on demoModeRequested, not unconditional.
    assert "demoModeRequested ?" in code


def test_http_nodes_never_throw_on_http_error_status():
    """neverError means a 4xx/5xx API response is normal node output, not a
    thrown error -- which is what keeps the connection-level retry from ever
    firing on a deterministic input/contract error."""
    data = _load_workflow()
    nodes = _nodes_by_name(data)
    for name in HTTP_NODE_NAMES:
        options = nodes[name]["parameters"]["options"]
        response_opts = options["response"]["response"]
        assert response_opts["neverError"] is True, f"{name!r} must never throw on HTTP status"
        assert response_opts["fullResponse"] is True, f"{name!r} must expose statusCode for classification"


def test_http_nodes_have_bounded_retry_and_error_branch():
    data = _load_workflow()
    nodes = _nodes_by_name(data)
    for name in HTTP_NODE_NAMES:
        node = nodes[name]
        assert node.get("retryOnFail") is True
        max_tries = node.get("maxTries")
        assert isinstance(max_tries, int) and 1 < max_tries <= 5
        assert isinstance(node.get("waitBetweenTries"), int) and node["waitBetweenTries"] > 0
        assert node.get("onError") == "continueErrorOutput"


def test_4xx_and_5xx_responses_are_never_retried_only_classified():
    """The classification node, not the HTTP node's retry mechanism, is
    responsible for 4xx/5xx -- and it must say so explicitly, not silently
    retry a deterministic input/contract error."""
    data = _load_workflow()
    code = _nodes_by_name(data)[CLASSIFY_RESPONSE_NODE]["parameters"]["jsCode"]
    assert "Not retried" in code
    assert "input/contract error" in code


def test_api_urls_are_configurable_via_env_expression():
    data = _load_workflow()
    nodes = _nodes_by_name(data)
    for name in HTTP_NODE_NAMES:
        url = nodes[name]["parameters"]["url"]
        assert url.startswith("={{ $env."), f"{name!r} base URL must be configurable, got {url!r}"


def test_organization_id_sent_dynamically_not_hardcoded():
    data = _load_workflow()
    process_node = _nodes_by_name(data)["03.1 Run DigiTax controls"]
    params = process_node["parameters"]["bodyParameters"]["parameters"]
    org_param = next(p for p in params if p["name"] == "organizationId")
    assert org_param["value"].startswith("={{"), "organizationId must come from run context, not a literal"
    file_param = next(p for p in params if p["parameterType"] == "formBinaryData")
    assert file_param["inputDataFieldName"] == "invoiceFile"


def test_explicit_technical_review_route_distinct_from_unknown_fallback():
    data = _load_workflow()
    switch_node = _nodes_by_name(data)[STATUS_ROUTING_NODE]
    rule_values = {
        cond["rightValue"]
        for rule in switch_node["parameters"]["rules"]["values"]
        for cond in rule["conditions"]["conditions"]
    }
    assert {"standard_review", "prioritized_review", "technical_review"} <= rule_values, (
        "technical_review must be an explicit switch rule, not left to fall through to the unknown fallback"
    )
    assert switch_node["parameters"]["options"]["fallbackOutput"] == "extra"

    branches = data["connections"][STATUS_ROUTING_NODE]["main"]
    assert len(branches) == 4
    targets = [b[0]["node"] for b in branches]
    assert targets == list(REVIEW_NODES)


def test_all_four_review_terminal_nodes_exist_and_are_noops():
    data = _load_workflow()
    name_set = {n["name"] for n in data["nodes"]}
    for required in REVIEW_NODES:
        assert required in name_set, f"missing required terminal node {required!r}"
    terminal_types = {n["type"] for n in data["nodes"] if n["name"] in REVIEW_NODES}
    assert terminal_types == {"n8n-nodes-base.noOp"}


CALL_ASSEMBLE_NODE = "Call Assemble ActivityExecution"
MERGE_ACTIVITY_EXECUTION_NODE = "Merge ActivityExecution into outcome"


def test_every_failure_and_success_path_converges_on_single_response_builder():
    """No duplicated respond-to-browser or routing logic, and no branch
    constructs its own ActivityExecution: every payload source emits a
    normalized envelope into the single shared Assemble ActivityExecution
    call, which feeds the single Merge node, which feeds the same
    control-report builder node, the same browser-response node, and the
    same status-routing switch."""
    data = _load_workflow()
    payload_sources = (
        "01.5 Handle invalid upload",
        "02.3 Handle capabilities failure",
        "02.5 Handle capability gate failure",
        "03.2 Classify controls response",
        "03.3 Handle controls-call failure",
    )
    for source in payload_sources:
        targets = {edge["node"] for branch in data["connections"][source]["main"] for edge in branch}
        assert targets == {CALL_ASSEMBLE_NODE}, f"{source!r} must feed {CALL_ASSEMBLE_NODE!r}"

    assert data["connections"][CALL_ASSEMBLE_NODE]["main"][0][0]["node"] == MERGE_ACTIVITY_EXECUTION_NODE
    assert data["connections"][MERGE_ACTIVITY_EXECUTION_NODE]["main"][0][0]["node"] == BUILD_REPORT_NODE
    assert data["connections"][BUILD_REPORT_NODE]["main"][0][0]["node"] == RESPOND_NODE
    assert data["connections"][RESPOND_NODE]["main"][0][0]["node"] == STATUS_ROUTING_NODE


def test_call_assemble_activity_execution_references_shared_subworkflow():
    data = _load_workflow()
    nodes = _nodes_by_name(data)
    call_node = nodes[CALL_ASSEMBLE_NODE]
    assert call_node["type"] == "n8n-nodes-base.executeWorkflow"
    assert (
        call_node["parameters"]["workflowId"]["value"]
        == "digitax-invoice-phase1-shared-assemble-activity-execution"
    )


def test_no_branch_node_constructs_a_full_activity_execution_object():
    data = _load_workflow()
    nodes = _nodes_by_name(data)
    for source in (
        "01.5 Handle invalid upload",
        "02.3 Handle capabilities failure",
        "02.5 Handle capability gate failure",
        "03.2 Classify controls response",
        "03.3 Handle controls-call failure",
    ):
        code = nodes[source]["parameters"]["jsCode"]
        assert '"executionId"' not in code, f"{source!r} must not construct a full ActivityExecution object"


def test_browser_response_is_html_and_never_requires_raw_json_inspection():
    data = _load_workflow()
    respond_node = _nodes_by_name(data)[RESPOND_NODE]
    assert respond_node["parameters"]["respondWith"] == "text"
    headers = respond_node["parameters"]["options"]["responseHeaders"]["entries"]
    content_type = next(h["value"] for h in headers if h["name"] == "Content-Type")
    assert "text/html" in content_type

    builder_code = _nodes_by_name(data)[BUILD_REPORT_NODE]["parameters"]["jsCode"]
    for expected_field in ("invoiceNumber", "totals", "correlationId", "controls"):
        assert expected_field in builder_code, f"response HTML must surface {expected_field!r}"


def test_workflow_never_reaches_approval_booking_payment_or_supplier_nodes():
    data = _load_workflow()
    forbidden_terms = ("approv", "booking", "payment", "supplier communication", "pay_")
    for node in data["nodes"]:
        lowered = node["name"].lower()
        assert not any(term in lowered for term in forbidden_terms), (
            f"node {node['name']!r} looks like it goes past the Phase 1 human-review boundary"
        )


# ---------------------------------------------------------------------------
# P2.1 Wave 1 A5 Stage 1: identity propagation + shared ActivityExecution
# assembly.
# ---------------------------------------------------------------------------

MARK_ATTEMPT_START_NODE = "02.6 Mark phase1 attempt start"


def test_run_context_generates_secure_ids_with_no_weak_fallback():
    code = _nodes_by_name(_load_workflow())[RUN_CONTEXT_NODE]["parameters"]["jsCode"]
    assert 'require("crypto").randomUUID' in code
    assert "processInstanceId" in code
    assert "Math.random()" not in code, "no weak fallback may remain anywhere in this node"
    assert "SECURE_UUID_UNAVAILABLE" in code


def test_mark_attempt_start_immediately_precedes_controls_call():
    data = _load_workflow()
    assert MARK_ATTEMPT_START_NODE in _nodes_by_name(data)
    assert data["connections"]["02.4 Required capability present?"]["main"][0][0]["node"] == MARK_ATTEMPT_START_NODE
    assert data["connections"][MARK_ATTEMPT_START_NODE]["main"][0][0]["node"] == "03.1 Run DigiTax controls"


def test_controls_call_sends_x_correlation_id_header():
    node = _nodes_by_name(_load_workflow())["03.1 Run DigiTax controls"]
    assert node["parameters"]["sendHeaders"] is True
    headers = node["parameters"]["headerParameters"]["parameters"]
    header = next(h for h in headers if h["name"] == "X-Correlation-ID")
    assert "correlationId" in header["value"]


def test_branch_nodes_emit_normalized_envelope_with_correct_outcome_literal():
    data = _load_workflow()
    nodes = _nodes_by_name(data)
    expected_outcomes = {
        "01.5 Handle invalid upload": "PRE_FLIGHT_REJECTED",
        "02.3 Handle capabilities failure": "PRE_FLIGHT_REJECTED",
        "02.5 Handle capability gate failure": "PRE_FLIGHT_REJECTED",
    }
    for node_name, outcome in expected_outcomes.items():
        code = nodes[node_name]["parameters"]["jsCode"]
        assert f'"{outcome}"' in code
        assert "gateDecisionAt" in code
        assert '"executionId"' not in code

    classify_code = nodes["03.2 Classify controls response"]["parameters"]["jsCode"]
    assert '"REPORT"' in classify_code
    assert '"HTTP_ERROR"' in classify_code

    failure_code = nodes["03.3 Handle controls-call failure"]["parameters"]["jsCode"]
    assert '"TRANSPORT_FAILURE"' in failure_code
    assert '"TIMEOUT"' in failure_code
    assert "ETIMEDOUT" in failure_code
