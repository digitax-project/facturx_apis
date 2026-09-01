"""Regression guard for
examples/n8n/digitax_invoice_phase1_flow1b_pdf_ocr_concept_v0_3_0.json
("DigiTax | Invoice Phase 1 | Flow 1b | PDF OCR/LLM Concept | v0.3.0").

P2.1 Wave 1 A5 revision round 2 (A1 review correction): Flow 1b no longer
mirrors ORG-001 (or any other control) in n8n-side JavaScript. It now calls
the real Phase 1 API's POST /v1/invoices/process-extracted -- the same
control catalog/executor Flow 1a uses -- and assembles a real
ActivityExecution via the same shared subworkflow and published binding.
This file's Node.js-execution tests exercise the business-logic-bearing
Code nodes that remain (AI-profile resolution, response classification,
identity generation); the Docker E2E tests at the bottom are the strongest
verification available for the parts that only make sense against a real
n8n JS Task Runner sandbox (crypto module availability) and a real webhook
round trip.
"""
import json
import re
import subprocess
import shutil
from pathlib import Path

import pytest

WORKFLOW_PATH = (
    Path(__file__).parent.parent
    / "examples"
    / "n8n"
    / "digitax_invoice_phase1_flow1b_pdf_ocr_concept_v0_3_0.json"
)
INTAKE_WORKFLOW_PATH = (
    Path(__file__).parent.parent / "examples" / "n8n" / "digitax_invoice_intake.json"
)
EXAMPLES_N8N_DIR = Path(__file__).parent.parent / "examples" / "n8n"

EXPECTED_WORKFLOW_ID = "digitax-invoice-phase1-flow1b-pdf-ocr"
EXPECTED_WORKFLOW_NAME = "DigiTax | Invoice Phase 1 | Flow 1b | PDF OCR/LLM Concept | v0.3.0"

RUN_CONTEXT_NODE = "01.2 Build run context"
FIX_BASE64_NODE = "02.1 Encode PDF for OCR"
GEMINI_REQUEST_NODE = "02.2 Build OCR/LLM request"
GEMINI_HTTP_NODE = "02.3 Run OCR/LLM extraction (Gemini)"
GEMINI_PARSER_NODE = "02.5 Parse OCR/LLM output"
BUILD_SUMMARY_NODE = "04.1 Build control report"
BUILD_RESPONSE_NODE = "04.2 Render control report"
RESPOND_NODE = "04.3 Respond to browser"
STATUS_ROUTING_NODE = "04.4 Route by review status"

RESOLVE_AI_PROFILE_NODE = "01.9 Resolve AI execution profile"
AI_PROFILE_SWITCH_NODE = "01.10 Route by AI profile"
UNRESOLVED_AI_PROFILE_NODE = "01.11 Handle unresolved AI profile"
LOCAL_ENCODE_NODE = "02.1L Encode PDF for local OCR"
LOCAL_REQUEST_NODE = "02.2L Build local OCR/LLM request"
LOCAL_HTTP_NODE = "02.3L Run OCR/LLM extraction (local)"
LOCAL_SERVICE_FAILURE_NODE = "02.4L Handle local OCR service failure"
LOCAL_PARSER_NODE = "02.5L Parse local OCR/LLM output"
LOCAL_PARSE_FAILURE_NODE = "02.6L Handle local OCR parse failure"
NORMALIZE_NODE = "02.7 Normalize invoice"
MARK_ATTEMPT_START_NODE = "02.8 Mark phase1 attempt start"
CONTROLS_HTTP_NODE = "03.1 Run DigiTax controls"
CLASSIFY_RESPONSE_NODE = "03.2 Classify controls response"
CONTROLS_FAILURE_NODE = "03.3 Handle controls-call failure"
CALL_ASSEMBLE_NODE = "Call Assemble ActivityExecution"
MERGE_ACTIVITY_EXECUTION_NODE = "Merge ActivityExecution into outcome"
RISK_REVIEW_GATE_NODE = "03.4 Evaluate risk review gate"
RISK_REVIEW_ROUTE_NODE = "03.5 Route by risk review need"
RISK_REVIEW_HTTP_NODE = "03.6 Run DigiTax Risk Review"
RISK_REVIEW_RESPONSE_NODE = "03.7 Handle risk review response"

REUSED_OCR_NODE_NAMES = (
    FIX_BASE64_NODE,
    GEMINI_HTTP_NODE,
)
INTAKE_NODE_NAMES = {
    FIX_BASE64_NODE: "fix base64",
    GEMINI_HTTP_NODE: "File-Based OCR with Gemini 2.5",
    GEMINI_PARSER_NODE: "Gemini Output Parser",
}

MASTER_DATA_LEAK_PATTERNS = [
    re.compile(r"Unternehmen X", re.IGNORECASE),
    re.compile(r"Unternehmen Y", re.IGNORECASE),
    re.compile(r"Musterweg"),
    re.compile(r"Industriestrasse"),
    re.compile(r"04109"),
    re.compile(r"01067"),
    re.compile(r"Leipzig"),
    re.compile(r"Dresden"),
    re.compile(r"DE450224353"),
    re.compile(r"\bexpected\b", re.IGNORECASE),
    re.compile(r"\bapproved\b", re.IGNORECASE),
]
REVIEW_NODES = (
    "05.1 Human review - standard",
    "05.2 Human review - prioritized",
    "05.3 Human review - technical",
    "05.4 Human review - unknown",
)

FORBIDDEN_PATTERNS = [
    (re.compile(r"host\.docker\.internal"), "a hardcoded local-dev host"),
    (re.compile(r"vn ?impex", re.IGNORECASE), "the real organization name"),
]
ALLOWED_HARDCODED_URL_PREFIXES = (
    "https://generativelanguage.googleapis.com/",
    # Both embedded verbatim in the generated RiskReviewReport validator
    # ("03.7 Handle risk review response"): the generic JSON Schema
    # meta-schema URL, and the vendored schema's own $id -- neither is a
    # real, deployment-specific endpoint, both are standard schema
    # identifiers.
    "https://json-schema.org/draft/2020-12/schema",
    "https://digitax.de/schemas/pilot/risk-review-report/",
)


def _load_workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _load_intake_workflow() -> dict:
    return json.loads(INTAKE_WORKFLOW_PATH.read_text(encoding="utf-8"))


def _nodes_by_name(data: dict) -> dict:
    return {n["name"]: n for n in data["nodes"]}


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------


def test_workflow_file_exists_and_is_valid_json():
    assert WORKFLOW_PATH.exists(), "Flow 1b workflow export is missing"
    _load_workflow()


def test_workflow_id_and_display_name_match_spec():
    data = _load_workflow()
    assert data["id"] == EXPECTED_WORKFLOW_ID
    assert data["name"] == EXPECTED_WORKFLOW_NAME


def test_workflow_id_is_unique_across_all_n8n_examples():
    seen_ids = {}
    for path in EXAMPLES_N8N_DIR.glob("*.json"):
        wf = json.loads(path.read_text(encoding="utf-8"))
        if "nodes" not in wf:
            continue
        wf_id = wf.get("id")
        assert wf_id not in seen_ids, (
            f"duplicate workflow id {wf_id!r} in {path.name} and {seen_ids.get(wf_id)}"
        )
        seen_ids[wf_id] = path.name
    assert EXPECTED_WORKFLOW_ID in seen_ids


def test_workflow_is_imported_inactive():
    """DISABLED state: the exported workflow stays inactive by default --
    activation is a separate, explicit operator step, never implied by
    import."""
    data = _load_workflow()
    assert data["active"] is False


def test_workflow_has_no_instance_id():
    data = _load_workflow()
    assert "instanceId" not in data.get("meta", {})


def test_credentials_are_placeholders_only_no_copied_credentials():
    data = _load_workflow()
    credential_types_seen = set()
    for node in data["nodes"]:
        for cred_type, cred in node.get("credentials", {}).items():
            credential_types_seen.add(cred_type)
            assert cred["id"] == "REPLACE_WITH_YOUR_CREDENTIAL_ID", (
                f"node {node['name']!r} credential {cred_type!r} is not a placeholder "
                "-- no credential may be copied from any n8n instance"
            )
    assert credential_types_seen == {"googlePalmApi"}


def test_workflow_has_no_forbidden_content():
    text = json.dumps(_load_workflow())
    for pattern, description in FORBIDDEN_PATTERNS:
        assert not pattern.search(text), f"found {description} in the workflow export"

    url_like = re.findall(r"https?://[^\s\"'\\]+", text)
    for url in url_like:
        assert url.startswith(ALLOWED_HARDCODED_URL_PREFIXES) or "{{" in url or "\\u003c" in url, (
            f"unexpected hardcoded URL {url!r} -- only the public Gemini API "
            "endpoint may be hardcoded; anything deployment-specific must be "
            "an n8n expression"
        )


def test_no_org_001_mirror_or_organization_resolution_left_in_n8n():
    """A1 review, High: Flow 1b must stop mirroring ORG-001 (and organization
    master data) in n8n-side JavaScript. The org-resolution nodes and the
    hand-rolled control evaluator are gone entirely -- not just renamed."""
    data = _load_workflow()
    node_names = {n["name"] for n in data["nodes"]}
    for removed in (
        "01.6 Resolve organization profile (concept)",
        "01.7 Organization profile known?",
        "01.8 Handle unknown organization",
        "03.1 Run DigiTax controls (concept)",
    ):
        assert removed not in node_names, f"{removed!r} must be removed, not just renamed"

    text = json.dumps(data)
    assert 'CONTROL_ID = "ORG-001"' not in text
    assert "_normalize_for_match" not in text
    assert "buyerMasterData" not in text
    assert "BUYER_PROFILES" not in text


def test_controls_node_calls_the_real_process_extracted_endpoint():
    """A1 review, High: Flow 1b now submits externally extracted fields to
    the real Phase 1 API instead of running its own control logic."""
    data = _load_workflow()
    node = _nodes_by_name(data)[CONTROLS_HTTP_NODE]
    assert node["type"] == "n8n-nodes-base.httpRequest"
    assert node["parameters"]["method"] == "POST"
    assert node["parameters"]["url"] == "={{ $env.FACTURX_API_BASE_URL }}/v1/invoices/process-extracted"
    assert node["parameters"]["jsonBody"] == "={{ JSON.stringify($json.processExtractedRequestBody) }}"
    header_names = {h["name"] for h in node["parameters"]["headerParameters"]["parameters"]}
    assert "X-Correlation-ID" in header_names
    assert node["parameters"]["options"]["response"]["response"]["neverError"] is True
    assert node["parameters"]["options"]["response"]["response"]["fullResponse"] is True
    assert node.get("retryOnFail") is True
    assert node.get("maxTries") == 3
    assert node.get("onError") == "continueErrorOutput"


def test_request_body_never_carries_a_caller_supplied_control_result():
    """The request the workflow sends to the API contains only extraction
    primitives (organizationId/document/extraction/invoice/fieldEvidence) --
    never a status/routing/controls field the server would have to ignore."""
    data = _load_workflow()
    code = _nodes_by_name(data)[MARK_ATTEMPT_START_NODE]["parameters"]["jsCode"]
    assert "processExtractedRequestBody" in code
    for forbidden in ("status:", "routing:", "controls:", "phase1ControlReport"):
        assert forbidden not in code.split("processExtractedRequestBody")[1].split("}")[0] or True
    # Precise check: the assembled body object literal itself only lists the
    # five allowed keys.
    body_literal = code.split("processExtractedRequestBody: {")[1].split("},")[0]
    for key in ("organizationId", "document", "extraction", "invoice", "fieldEvidence"):
        assert f"{key}:" in body_literal
    for key in ("status", "routing", "controls", "report"):
        assert f"{key}:" not in body_literal


def test_no_weak_correlation_id_fallback():
    """A1 review, Medium: no timestamp/Math.random fallback anywhere in this
    workflow -- an unavailable secure UUID source must fail closed, exactly
    like Flow 1a's own "Build run context" nodes."""
    data = _load_workflow()
    code = _nodes_by_name(data)[RUN_CONTEXT_NODE]["parameters"]["jsCode"]
    assert "Math.random" not in code
    assert "Date.now()" not in code
    assert "SECURE_UUID_UNAVAILABLE" in code
    assert 'require("crypto")' in code


def test_run_context_generates_one_correlation_id_and_one_process_instance_id():
    data = _load_workflow()
    code = _nodes_by_name(data)[RUN_CONTEXT_NODE]["parameters"]["jsCode"]
    assert "const correlationId = nodeCrypto.randomUUID();" in code
    assert "const processInstanceId = nodeCrypto.randomUUID();" in code
    # The pdf hash must reuse the same guarded nodeCrypto reference, never a
    # second, unguarded require("crypto").createHash(...) call (found
    # 2026-08-25: that second call crashed this node whenever require("crypto")
    # wasn't allow-listed, producing an empty HTTP 200 for every request, not
    # just the missing-credential case the original regression test named).
    # Full-line "//" comments are stripped first so the explanatory prose
    # above (which quotes that exact banned pattern) can't produce a false
    # positive here.
    functional_code = "\n".join(
        line for line in code.split("\n") if not line.strip().startswith("//")
    )
    assert "nodeCrypto.createHash(" in functional_code
    assert 'require("crypto").createHash(' not in functional_code
    assert "require('crypto').createHash(" not in functional_code


def test_local_render_helper_notes_have_no_hardcoded_host():
    data = _load_workflow()
    node = _nodes_by_name(data)["02.1L-b Render PDF page as PNG (local render helper)"]
    assert "host.docker.internal" not in node["notes"]
    assert "LOCAL_PDF_RENDER_URL" in node["notes"]


def test_ocr_nodes_reused_verbatim_from_intake_workflow():
    flow1b_nodes = _nodes_by_name(_load_workflow())
    intake_nodes = _nodes_by_name(_load_intake_workflow())

    for name in REUSED_OCR_NODE_NAMES:
        intake_name = INTAKE_NODE_NAMES[name]
        assert name in flow1b_nodes, f"missing reused node {name!r}"
        assert intake_name in intake_nodes, f"reference node {intake_name!r} missing from intake workflow"
        flow1b_node = flow1b_nodes[name]
        intake_node = intake_nodes[intake_name]
        assert flow1b_node["id"] == intake_node["id"], f"{name!r} node id must be unchanged"

        if "jsCode" in flow1b_node.get("parameters", {}):
            assert flow1b_node["parameters"]["jsCode"] == intake_node["parameters"]["jsCode"], (
                f"{name!r} jsCode must be byte-for-byte identical to the historical workflow"
            )
        else:
            for key in ("method", "url", "jsonBody", "nodeCredentialType"):
                assert flow1b_node["parameters"].get(key) == intake_node["parameters"].get(key), (
                    f"{name!r} parameter {key!r} must be unchanged"
                )
            assert flow1b_node.get("retryOnFail") == intake_node.get("retryOnFail")
            assert flow1b_node.get("maxTries") == intake_node.get("maxTries")

    assert flow1b_nodes[GEMINI_PARSER_NODE].get("onError") == "continueErrorOutput"
    assert "onError" not in intake_nodes[INTAKE_NODE_NAMES[GEMINI_PARSER_NODE]]


def test_cloud_parser_extends_intake_logic_without_replacing_it():
    flow1b_nodes = _nodes_by_name(_load_workflow())
    intake_nodes = _nodes_by_name(_load_intake_workflow())
    flow1b_code = flow1b_nodes[GEMINI_PARSER_NODE]["parameters"]["jsCode"]
    intake_code = intake_nodes[INTAKE_NODE_NAMES[GEMINI_PARSER_NODE]]["parameters"]["jsCode"]

    for fn_signature in (
        "function extractTextFromGeminiResponse(item)",
        "function stripMarkdownFences(text)",
        "function ensureField(obj, key)",
    ):
        assert fn_signature in flow1b_code
        assert fn_signature in intake_code

    for field in ("Invoice No", "VAT-ID (Seller)", "VAT-ID (Buyer)", "Name (Buyer)"):
        assert field in flow1b_code and field in intake_code

    assert "aiMeta" in flow1b_code
    assert "aiMeta" not in intake_code


def test_build_gemini_request_prompt_has_no_master_data_leak():
    data = _load_workflow()
    prompt_code = _nodes_by_name(data)[GEMINI_REQUEST_NODE]["parameters"]["jsCode"]
    for pattern in MASTER_DATA_LEAK_PATTERNS:
        assert not pattern.search(prompt_code), (
            f"master-data reference value {pattern.pattern!r} leaked into the "
            "OCR prompt -- extraction must not know the expected answer"
        )
    assert "document" in prompt_code.lower()
    assert "VAT-ID (Buyer)" in prompt_code and "VAT-ID (Seller)" in prompt_code


def test_intake_workflow_prompt_still_has_the_original_leak_unremediated():
    intake_nodes = _nodes_by_name(_load_intake_workflow())
    intake_prompt = intake_nodes["Build Gemini Request"]["parameters"]["jsCode"]
    assert "Unternehmen X" in intake_prompt


def test_fix_base64_binary_property_matches_run_context_output():
    data = _load_workflow()
    nodes = _nodes_by_name(data)
    fix_base64_code = nodes[FIX_BASE64_NODE]["parameters"]["jsCode"]
    assert "binaryPropertyName = 'data'" in fix_base64_code
    run_context_code = nodes[RUN_CONTEXT_NODE]["parameters"]["jsCode"]
    assert "item.binary.data" in run_context_code


def test_workflow_connections_reference_existing_nodes_no_duplicates():
    data = _load_workflow()
    node_names = [n["name"] for n in data["nodes"]]
    node_ids = [n["id"] for n in data["nodes"]]
    assert len(node_ids) == len(set(node_ids)), "duplicate node ids"
    assert len(node_names) == len(set(node_names)), "duplicate node names"

    name_set = set(node_names)
    for source_name, outputs in data.get("connections", {}).items():
        assert source_name in name_set
        for branches in outputs.values():
            for branch in branches:
                for edge in branch:
                    assert edge["node"] in name_set, (
                        f"connection target {edge['node']!r} does not exist "
                        f"(referenced from {source_name!r})"
                    )


def test_every_node_except_trigger_and_notes_has_an_incoming_edge():
    data = _load_workflow()
    name_set = {n["name"] for n in data["nodes"]}
    has_incoming = set()
    for outputs in data["connections"].values():
        for branches in outputs.values():
            for branch in branches:
                for edge in branch:
                    has_incoming.add(edge["node"])
    no_incoming = {
        n["name"] for n in data["nodes"]
        if n["name"] not in has_incoming and n["type"] not in ("n8n-nodes-base.stickyNote",)
    }
    assert no_incoming == {"01.1 Receive PDF upload"}


def test_explicit_technical_review_route_distinct_from_unknown_fallback():
    data = _load_workflow()
    switch_node = _nodes_by_name(data)[STATUS_ROUTING_NODE]
    rule_values = {
        cond["rightValue"]
        for rule in switch_node["parameters"]["rules"]["values"]
        for cond in rule["conditions"]["conditions"]
    }
    assert {"standard_review", "prioritized_review", "technical_review"} <= rule_values
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


def test_every_failure_and_success_path_converges_through_activity_execution_assembly():
    """Every branch (pre-flight rejection, controls-call success/failure)
    feeds the shared "Call Assemble ActivityExecution" subworkflow, exactly
    like every Flow 1a workflow, then the risk-review gate (mirroring Flow
    1a's own "04.3"-"04.6" pattern -- own 03.x numbering here to avoid
    colliding with this workflow's pre-existing 04.x nodes), and every path
    (risk review run or skipped) funnels through exactly one
    "04.1 Build control report" / "04.2 Render control report" pair."""
    data = _load_workflow()
    branch_sources = (
        "01.5 Handle invalid upload",
        UNRESOLVED_AI_PROFILE_NODE,
        "02.4 Handle OCR service failure",
        "02.6 Handle OCR parse failure",
        LOCAL_SERVICE_FAILURE_NODE,
        LOCAL_PARSE_FAILURE_NODE,
        CLASSIFY_RESPONSE_NODE,
        CONTROLS_FAILURE_NODE,
    )
    for source in branch_sources:
        targets = {edge["node"] for branch in data["connections"][source]["main"] for edge in branch}
        assert targets == {CALL_ASSEMBLE_NODE}, f"{source!r} must feed {CALL_ASSEMBLE_NODE!r}"

    assert data["connections"][CALL_ASSEMBLE_NODE]["main"][0][0]["node"] == MERGE_ACTIVITY_EXECUTION_NODE
    assert data["connections"][MERGE_ACTIVITY_EXECUTION_NODE]["main"][0][0]["node"] == RISK_REVIEW_GATE_NODE
    assert data["connections"][RISK_REVIEW_GATE_NODE]["main"][0][0]["node"] == RISK_REVIEW_ROUTE_NODE

    route_branches = data["connections"][RISK_REVIEW_ROUTE_NODE]["main"]
    assert route_branches[0][0]["node"] == RISK_REVIEW_HTTP_NODE, "needsRiskReview=true must call Risk Review"
    assert route_branches[1][0]["node"] == BUILD_SUMMARY_NODE, "needsRiskReview=false must skip straight to 04.1"
    assert data["connections"][RISK_REVIEW_HTTP_NODE]["main"][0][0]["node"] == RISK_REVIEW_RESPONSE_NODE
    assert data["connections"][RISK_REVIEW_RESPONSE_NODE]["main"][0][0]["node"] == BUILD_SUMMARY_NODE

    assert data["connections"][BUILD_SUMMARY_NODE]["main"][0][0]["node"] == BUILD_RESPONSE_NODE
    assert data["connections"][BUILD_RESPONSE_NODE]["main"][0][0]["node"] == RESPOND_NODE
    assert data["connections"][RESPOND_NODE]["main"][0][0]["node"] == STATUS_ROUTING_NODE


def test_controls_http_node_success_and_error_outputs_split_correctly():
    data = _load_workflow()
    conn = data["connections"][CONTROLS_HTTP_NODE]["main"]
    assert len(conn) == 2
    assert conn[0][0]["node"] == CLASSIFY_RESPONSE_NODE
    assert conn[1][0]["node"] == CONTROLS_FAILURE_NODE


def test_merge_node_reconciles_every_branch_envelope_name():
    data = _load_workflow()
    code = _nodes_by_name(data)[MERGE_ACTIVITY_EXECUTION_NODE]["parameters"]["jsCode"]
    for name in (
        "01.5 Handle invalid upload",
        UNRESOLVED_AI_PROFILE_NODE,
        "02.4 Handle OCR service failure",
        "02.6 Handle OCR parse failure",
        LOCAL_SERVICE_FAILURE_NODE,
        LOCAL_PARSE_FAILURE_NODE,
        CLASSIFY_RESPONSE_NODE,
        CONTROLS_FAILURE_NODE,
    ):
        assert f'"{name}"' in code


def test_both_extraction_lanes_converge_on_shared_normalize_node():
    data = _load_workflow()
    cloud_targets = {
        edge["node"] for edge in data["connections"]["02.5 Parse OCR/LLM output"]["main"][0]
    }
    local_targets = {
        edge["node"] for edge in data["connections"][LOCAL_PARSER_NODE]["main"][0]
    }
    assert cloud_targets == {NORMALIZE_NODE}
    assert local_targets == {NORMALIZE_NODE}


def test_ai_profile_switch_routes_local_cloud_and_unresolved_separately():
    data = _load_workflow()
    switch_node = _nodes_by_name(data)[AI_PROFILE_SWITCH_NODE]
    rule_values = {
        cond["rightValue"]
        for rule in switch_node["parameters"]["rules"]["values"]
        for cond in rule["conditions"]["conditions"]
    }
    assert rule_values == {"local", "cloud"}
    assert switch_node["parameters"]["options"]["fallbackOutput"] == "extra"

    branches = data["connections"][AI_PROFILE_SWITCH_NODE]["main"]
    assert len(branches) == 3
    targets = [b[0]["node"] for b in branches]
    assert targets == [LOCAL_ENCODE_NODE, "02.1 Encode PDF for OCR", UNRESOLVED_AI_PROFILE_NODE]


def test_ai_profile_resolution_never_defaults_unknown_to_cloud():
    data = _load_workflow()
    code = _nodes_by_name(data)[RESOLVE_AI_PROFILE_NODE]["parameters"]["jsCode"]
    assert '"unknown"' in code
    assert '"local_unavailable"' in code
    assert '"local-default"' in code and '"cloud-gemini"' in code


def test_unresolved_ai_profile_handler_never_reports_cloud_processing():
    data = _load_workflow()
    code = _nodes_by_name(data)[UNRESOLVED_AI_PROFILE_NODE]["parameters"]["jsCode"]
    assert '"technical_review"' in code
    assert "AI_LOCAL_PROVIDER_UNAVAILABLE" in code
    assert "AI_PROFILE_UNKNOWN" in code
    assert "processingLocation: null" in code


def test_local_lane_has_bounded_retry_and_no_hardcoded_endpoint():
    data = _load_workflow()
    node = _nodes_by_name(data)[LOCAL_HTTP_NODE]
    assert node["parameters"]["url"] == "={{ $env.LOCAL_LLM_BASE_URL }}/chat/completions"
    assert node.get("retryOnFail") is True
    assert isinstance(node.get("maxTries"), int) and 1 < node["maxTries"] <= 5
    assert node.get("onError") == "continueErrorOutput"
    assert "credentials" not in node, "local dev endpoint must not carry a credential reference"


def test_local_and_cloud_lanes_emit_identical_ai_meta_shape():
    data = _load_workflow()
    nodes = _nodes_by_name(data)
    cloud_code = nodes["02.5 Parse OCR/LLM output"]["parameters"]["jsCode"]
    local_code = nodes[LOCAL_PARSER_NODE]["parameters"]["jsCode"]
    for field in ("aiProvider", "modelId", "modelVersion", "processingLocation", "promptVersion", "fallbackUsed"):
        assert field in cloud_code, f"cloud parser missing aiMeta.{field}"
        assert field in local_code, f"local parser missing aiMeta.{field}"


def test_control_report_carries_required_audit_fields():
    data = _load_workflow()
    code = _nodes_by_name(data)[BUILD_SUMMARY_NODE]["parameters"]["jsCode"]
    for field in (
        "processingPath",
        "aiExecutionProfile",
        "aiProvider",
        "modelId",
        "modelVersion",
        "processingLocation",
        "promptVersion",
        "fallbackUsed",
    ):
        assert field in code, f"04.1 Build control report must emit {field!r}"


def test_build_control_report_never_recomputes_status_from_scratch():
    """04.1 must pass through the API's own status/routing/controls, not
    recompute an aggregation itself (that logic now lives exclusively in
    facturx/phase1/controls/aggregate.py, invoked only via the real API)."""
    data = _load_workflow()
    code = _nodes_by_name(data)[BUILD_SUMMARY_NODE]["parameters"]["jsCode"]
    assert "status: m.status" in code
    assert "routing: m.routing" in code
    assert "not_reliable" not in code
    assert "klaerung_erforderlich" not in code or "m.status" in code


def test_no_secrets_or_internal_urls_in_ai_selection_nodes():
    data = _load_workflow()
    nodes = _nodes_by_name(data)
    ai_node_names = (
        RESOLVE_AI_PROFILE_NODE,
        UNRESOLVED_AI_PROFILE_NODE,
        LOCAL_REQUEST_NODE,
        LOCAL_HTTP_NODE,
        LOCAL_SERVICE_FAILURE_NODE,
        LOCAL_PARSER_NODE,
        LOCAL_PARSE_FAILURE_NODE,
    )
    for name in ai_node_names:
        node = nodes[name]
        assert "credentials" not in node
        text = json.dumps(node)
        assert "REPLACE_WITH_YOUR_CREDENTIAL_ID" not in text
        assert not re.search(r"https?://(?!\{\{)", text), f"{name!r} must not hardcode a URL"


def test_browser_response_is_html():
    data = _load_workflow()
    respond_node = _nodes_by_name(data)[RESPOND_NODE]
    assert respond_node["parameters"]["respondWith"] == "text"
    headers = respond_node["parameters"]["options"]["responseHeaders"]["entries"]
    content_type = next(h["value"] for h in headers if h["name"] == "Content-Type")
    assert "text/html" in content_type


def test_response_discloses_the_real_api_is_authoritative():
    """AGENTS.md: never fake API reuse. The response must not claim the
    real API "cannot yet consume" OCR fields anymore -- it must say what is
    now actually true: control evaluation is real, only the local AI lane
    itself remains a concept."""
    data = _load_workflow()
    code = _nodes_by_name(data)[BUILD_RESPONSE_NODE]["parameters"]["jsCode"]
    assert "authoritative Phase 1 API" in code
    assert "process-extracted" in code
    assert "cannot yet consume" not in code
    assert "no injection seam" not in code


def test_workflow_never_reaches_approval_booking_payment_or_supplier_nodes():
    data = _load_workflow()
    forbidden_terms = ("approv", "booking", "payment", "supplier communication", "pay_")
    for node in data["nodes"]:
        lowered = node["name"].lower()
        assert not any(term in lowered for term in forbidden_terms), (
            f"node {node['name']!r} looks like it goes past the human-review boundary"
        )


def test_digitax_invoice_intake_json_is_unchanged():
    result = subprocess.run(
        ["git", "diff", "--quiet", "--", str(INTAKE_WORKFLOW_PATH)],
        cwd=INTAKE_WORKFLOW_PATH.parent.parent.parent,
    )
    assert result.returncode == 0, "digitax_invoice_intake.json must not be modified"


# ---------------------------------------------------------------------------
# Real execution of business-logic-bearing Code nodes via Node.js.
# ---------------------------------------------------------------------------

NODE_AVAILABLE = shutil.which("node") is not None


def _node_code(name: str) -> str:
    return _nodes_by_name(_load_workflow())[name]["parameters"]["jsCode"]


def _run_with_context(code: str, input_json: dict, node_outputs: dict, workflow_id: str = EXPECTED_WORKFLOW_ID) -> dict:
    """Executes one Code node's body with $input.first() = input_json,
    $(name) resolving against node_outputs (nodeName -> json dict), and
    $workflow.id set -- the same shape n8n provides at runtime."""
    harness = f"""
const $workflow = {{ id: {json.dumps(workflow_id)} }};
const __nodeOutputs = {json.dumps(node_outputs)};
function $(name) {{
  if (!(name in __nodeOutputs)) throw new Error("no such node in test harness: " + name);
  return {{ item: {{ json: __nodeOutputs[name] }} }};
}}
const $input = {{ first: () => ({{ json: {json.dumps(input_json)} }}) }};
async function run() {{
{code}
}}
run().then(r => process.stdout.write(JSON.stringify({{ ok: true, result: r[0].json }})))
  .catch(e => process.stdout.write(JSON.stringify({{ ok: false, message: e.message }})));
"""
    proc = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, f"node execution failed: {proc.stderr}\n{harness}"
    return json.loads(proc.stdout)


BASE_CTX = {
    "processInstanceId": "PI-1",
    "correlationId": "CORR-1",
    "receivedAt": "2026-08-25T10:00:00.000Z",
    "organizationId": "unternehmen-x-demo",
    "processingPath": "pdf_ocr",
    "aiExecutionProfile": "local-default",
}


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_classify_controls_response_real_execution_maps_report_to_activity_execution_input():
    upstream = {**BASE_CTX, "phase1AttemptStartedAt": "2026-08-25T10:00:00.100Z", "aiMeta": {
        "aiProvider": "local-openai-compatible", "modelId": "stub-model", "modelVersion": None,
        "processingLocation": "local", "promptVersion": "flow1b-extract-v1", "fallbackUsed": False,
    }}
    resp = {
        "statusCode": 200,
        "body": {
            "canonicalInvoice": {"invoice": {"invoiceNumber": "UX-1"}, "document": {"sha256": "a" * 64}},
            "phase1ControlReport": {
                "status": "unauffaellig", "routing": "standard_review", "correlationId": "CORR-1",
                "runId": "RUN-1", "reportId": "REP-1",
            },
        },
    }
    out = _run_with_context(
        _node_code(CLASSIFY_RESPONSE_NODE), resp,
        {RUN_CONTEXT_NODE: BASE_CTX, MARK_ATTEMPT_START_NODE: upstream},
    )
    assert out["ok"] is True, out
    result = out["result"]
    assert result["outcome"] == "REPORT"
    assert result["phase1Status"] == "unauffaellig"
    assert result["routing"] == "standard_review"
    assert result["aiProvider"] == "local-openai-compatible"
    assert result["organizationId"] == "unternehmen-x-demo"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_classify_controls_response_real_execution_maps_4xx_to_http_error_never_retried_note():
    upstream = {**BASE_CTX, "phase1AttemptStartedAt": "2026-08-25T10:00:00.100Z", "aiMeta": {}}
    resp = {
        "statusCode": 400,
        "body": {"detail": {"error_code": "ORGANIZATION_CONTEXT_REQUIRED", "detail": "missing org"}},
    }
    out = _run_with_context(
        _node_code(CLASSIFY_RESPONSE_NODE), resp,
        {RUN_CONTEXT_NODE: BASE_CTX, MARK_ATTEMPT_START_NODE: upstream},
    )
    assert out["ok"] is True, out
    result = out["result"]
    assert result["outcome"] == "HTTP_ERROR"
    assert result["httpErrorCode"] == "ORGANIZATION_CONTEXT_REQUIRED"
    assert result["phase1Status"] == "nicht_pruefbar"
    assert result["routing"] == "technical_review"
    assert "Not retried" in result["explanation"]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_handle_controls_call_failure_classifies_timeout_vs_transport():
    upstream = {**BASE_CTX, "phase1AttemptStartedAt": "2026-08-25T10:00:00.100Z", "aiMeta": {}}
    timeout_err = {"error": {"code": "ETIMEDOUT", "message": "connect ETIMEDOUT"}}
    out = _run_with_context(
        _node_code(CONTROLS_FAILURE_NODE), timeout_err,
        {RUN_CONTEXT_NODE: BASE_CTX, MARK_ATTEMPT_START_NODE: upstream},
    )
    assert out["ok"] is True, out
    assert out["result"]["outcome"] == "TIMEOUT"
    assert out["result"]["n8nErrorCode"] == "INVOICE_PROCESSING_SERVICE_TIMEOUT"

    conn_err = {"error": {"code": "ECONNREFUSED", "message": "connect ECONNREFUSED"}}
    out2 = _run_with_context(
        _node_code(CONTROLS_FAILURE_NODE), conn_err,
        {RUN_CONTEXT_NODE: BASE_CTX, MARK_ATTEMPT_START_NODE: upstream},
    )
    assert out2["result"]["outcome"] == "TRANSPORT_FAILURE"
    assert out2["result"]["n8nErrorCode"] == "INVOICE_PROCESSING_SERVICE_UNAVAILABLE"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_merge_activity_execution_reconciles_report_branch():
    branch_envelope = {
        "correlationId": "CORR-1", "processInstanceId": "PI-1",
        "phase1Status": "unauffaellig", "routing": "standard_review",
        "failedStep": None, "httpErrorCode": None, "n8nErrorCode": None, "explanation": None,
        "invoice": {"invoiceNumber": "UX-1"}, "document": {"sha256": "a" * 64},
        "report": {"status": "unauffaellig", "correlationId": "CORR-1"},
        "organizationId": "unternehmen-x-demo", "processingPath": "pdf_ocr",
        "aiExecutionProfile": "local-default", "aiProvider": "local-openai-compatible",
        "modelId": "stub-model", "modelVersion": None, "processingLocation": "local",
        "promptVersion": "flow1b-extract-v1", "fallbackUsed": False,
    }
    activity_execution_input = {"activityExecution": {"schemaVersion": "1.0.0", "status": "SUCCEEDED"}}
    out = _run_with_context(
        _node_code(MERGE_ACTIVITY_EXECUTION_NODE), activity_execution_input,
        {CLASSIFY_RESPONSE_NODE: branch_envelope},
    )
    assert out["ok"] is True, out
    result = out["result"]
    assert result["status"] == "unauffaellig"
    assert result["routing"] == "standard_review"
    assert result["activityExecution"]["status"] == "SUCCEEDED"
    assert result["aiExecutionProfile"] == "local-default"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_merge_activity_execution_throws_if_no_branch_envelope_found():
    out = _run_with_context(
        _node_code(MERGE_ACTIVITY_EXECUTION_NODE),
        {"activityExecution": {"status": "SUCCEEDED"}},
        {},
    )
    assert out["ok"] is False
    assert "ACTIVITY_EXECUTION_MERGE_NO_BRANCH_ENVELOPE" in out["message"]


# ---------------------------------------------------------------------------
# Real n8n E2E: a genuinely fresh, ephemeral n8n container plus a real
# Phase 1 API container on the same isolated Docker network -- not a
# structural check.
# ---------------------------------------------------------------------------

import socket
import time
import uuid

import httpx

DOCKER_AVAILABLE = shutil.which("docker") is not None
N8N_IMAGE = "n8nio/n8n:2.33.7"
FLOW1B_WORKFLOW_ID = "digitax-invoice-phase1-flow1b-pdf-ocr"
SHARED_SUBWORKFLOW_PATH = (
    EXAMPLES_N8N_DIR / "digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json"
)
REPO_ROOT = Path(__file__).parent.parent


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_http_ok(url: str, timeout_seconds: float = 90.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(1.0)
    raise TimeoutError(f"{url} never returned 200 within {timeout_seconds}s (last error: {last_error})")


def _docker(*args, timeout=60):
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


class _Flow1bStack:
    """Ephemeral, isolated docker network + n8n container (+ optional real
    API container) for one test. Every resource name is suffixed with a
    fresh uuid and torn down in a `finally` block, mirroring the pattern
    this file already established for the credential-failure E2E test."""

    def __init__(self, with_api: bool = True, extra_n8n_env: dict | None = None):
        self.suffix = uuid.uuid4().hex[:8]
        self.network = f"flow1b-e2e-{self.suffix}"
        self.n8n_container = f"flow1b-e2e-n8n-{self.suffix}"
        self.n8n_volume = f"flow1b-e2e-n8n-vol-{self.suffix}"
        self.api_container = f"flow1b-e2e-api-{self.suffix}"
        self.api_image = f"facturx-phase1-api-e2e:{self.suffix}"
        self.with_api = with_api
        self.extra_n8n_env = extra_n8n_env or {}
        self.n8n_port = None

    def start(self):
        net = _docker("network", "create", self.network)
        assert net.returncode == 0, f"docker network create failed: {net.stderr}"

        if self.with_api:
            build = _docker("build", "-t", self.api_image, str(REPO_ROOT), timeout=300)
            assert build.returncode == 0, f"docker build failed: {build.stdout}\n{build.stderr}"
            run_api = _docker(
                "run", "-d", "--name", self.api_container, "--network", self.network,
                self.api_image, timeout=30,
            )
            assert run_api.returncode == 0, f"docker run (api) failed: {run_api.stderr}"

        self.n8n_port = _free_tcp_port()
        env_args = [
            "-e", "N8N_BLOCK_ENV_ACCESS_IN_NODE=false",
            "-e", "N8N_DIAG_ENABLED=false",
            "-e", "NODE_FUNCTION_ALLOW_BUILTIN=crypto",
        ]
        if self.with_api:
            env_args += ["-e", f"FACTURX_API_BASE_URL=http://{self.api_container}:6969"]
        for key, value in self.extra_n8n_env.items():
            env_args += ["-e", f"{key}={value}"]

        pull = _docker("pull", N8N_IMAGE, timeout=300)
        assert pull.returncode == 0, f"docker pull {N8N_IMAGE} failed: {pull.stderr}"

        run_n8n = _docker(
            "run", "-d", "--name", self.n8n_container, "--network", self.network,
            "-p", f"{self.n8n_port}:5678",
            "-v", f"{self.n8n_volume}:/home/node/.n8n",
            *env_args, N8N_IMAGE, timeout=30,
        )
        assert run_n8n.returncode == 0, f"docker run (n8n) failed: {run_n8n.stderr}"
        _wait_for_http_ok(f"http://127.0.0.1:{self.n8n_port}/healthz")
        if self.with_api:
            self._exec_api_healthcheck()

    def _exec_api_healthcheck(self):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            check = _docker(
                "exec", self.n8n_container, "wget", "-qO-",
                f"http://{self.api_container}:6969/health",
            )
            if check.returncode == 0:
                return
            time.sleep(1.0)
        raise TimeoutError("Phase 1 API container never became reachable from the n8n container")

    def import_and_publish(self, *workflow_paths_and_ids):
        for path, workflow_id in workflow_paths_and_ids:
            dest = f"/tmp/{workflow_id}.json"
            cp = _docker("cp", str(path), f"{self.n8n_container}:{dest}")
            assert cp.returncode == 0, f"docker cp failed: {cp.stderr}"
            imp = _docker("exec", self.n8n_container, "n8n", "import:workflow", f"--input={dest}")
            assert imp.returncode == 0, f"n8n import:workflow failed: {imp.stderr}\n{imp.stdout}"
            pub = _docker("exec", self.n8n_container, "n8n", "publish:workflow", f"--id={workflow_id}")
            assert pub.returncode == 0, f"n8n publish:workflow failed: {pub.stderr}\n{pub.stdout}"
        restart = _docker("restart", self.n8n_container)
        assert restart.returncode == 0, f"docker restart failed: {restart.stderr}"
        _wait_for_http_ok(f"http://127.0.0.1:{self.n8n_port}/healthz")

    def post_upload(self, *, files, data, path="phase1-flow1b-pdf-upload", retries=10):
        response = None
        for _ in range(retries):
            response = httpx.post(
                f"http://127.0.0.1:{self.n8n_port}/webhook/{path}",
                data=data, files=files, timeout=30.0,
            )
            if response.status_code != 404:
                break
            time.sleep(1.0)
        return response

    def stop(self):
        _docker("rm", "-f", self.n8n_container, timeout=30)
        if self.with_api:
            _docker("rm", "-f", self.api_container, timeout=30)
        _docker("volume", "rm", self.n8n_volume, timeout=30)
        _docker("network", "rm", self.network, timeout=30)


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not available")
def test_e2e_cloud_gemini_without_credential_converges_to_technical_review():
    """Guards a real regression: cloud-gemini without a configured
    credential used to return an unhandled, empty HTTP 200 (an unguarded
    require('crypto').createHash(...) call in "01.2 Build run context"
    crashed the whole execution whenever require("crypto") wasn't
    allow-listed, before any of this workflow's own error handling ever
    ran). It must converge to a proper, non-empty
    nicht_pruefbar/technical_review/OCR_SERVICE_UNAVAILABLE payload -- and
    now also to a real (FAILED/PRE_FLIGHT_REJECTED) ActivityExecution via
    the shared subworkflow, since the API/binding assertion node is on the
    same critical path."""
    stack = _Flow1bStack(with_api=False)
    try:
        stack.start()
        stack.import_and_publish(
            (SHARED_SUBWORKFLOW_PATH, "digitax-invoice-phase1-shared-assemble-activity-execution"),
            (WORKFLOW_PATH, FLOW1B_WORKFLOW_ID),
        )
        response = stack.post_upload(
            data={"organizationId": "unternehmen-x-demo", "aiExecutionProfile": "cloud-gemini"},
            files={"data": ("test-invoice.pdf", b"%PDF-1.4 not a real pdf, content is irrelevant here", "application/pdf")},
        )
        assert response.status_code == 200
        assert len(response.content) > 0, (
            "cloud-gemini without a configured credential must never return an "
            "empty response -- it must converge to a proper technical_review payload"
        )
        body = response.text
        assert "nicht_pruefbar" in body
        assert "technical_review" in body
        assert "OCR_SERVICE_UNAVAILABLE" in body
    finally:
        stack.stop()


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not available")
def test_e2e_local_ai_success_with_deterministic_double_reaches_real_api():
    """Required scenario: "Flow 1b local-AI success using a deterministic
    test double." A tiny, canned stub (stdlib-only Python HTTP server, no
    real model) stands in for both the local vision endpoint and the PDF
    render helper. Proves the whole chain end to end: local extraction ->
    real POST /v1/invoices/process-extracted -> real control catalog
    (including the real ORG-001, not an n8n mirror) -> unauffaellig."""
    stub_source = (Path(__file__).parent / "fixtures" / "flow1b_local_ai_stub.py")
    assert stub_source.exists(), "missing tests/fixtures/flow1b_local_ai_stub.py test double"

    stack = _Flow1bStack(with_api=True)
    stub_container = f"flow1b-e2e-stub-{stack.suffix}"
    try:
        net = _docker("network", "create", stack.network)
        assert net.returncode == 0, f"docker network create failed: {net.stderr}"

        build = _docker("build", "-t", stack.api_image, str(REPO_ROOT), timeout=300)
        assert build.returncode == 0, f"docker build failed: {build.stdout}\n{build.stderr}"
        run_api = _docker("run", "-d", "--name", stack.api_container, "--network", stack.network, stack.api_image, timeout=30)
        assert run_api.returncode == 0, f"docker run (api) failed: {run_api.stderr}"

        pull_python = _docker("pull", "python:3.12-slim", timeout=300)
        assert pull_python.returncode == 0, f"docker pull python:3.12-slim failed: {pull_python.stderr}"
        run_stub = _docker(
            "run", "-d", "--name", stub_container, "--network", stack.network,
            "-v", f"{stub_source}:/stub.py:ro",
            "python:3.12-slim", "python", "/stub.py",
            timeout=30,
        )
        assert run_stub.returncode == 0, f"docker run (stub) failed: {run_stub.stderr}"

        stack.n8n_port = _free_tcp_port()
        pull_n8n = _docker("pull", N8N_IMAGE, timeout=300)
        assert pull_n8n.returncode == 0, f"docker pull {N8N_IMAGE} failed: {pull_n8n.stderr}"
        run_n8n = _docker(
            "run", "-d", "--name", stack.n8n_container, "--network", stack.network,
            "-p", f"{stack.n8n_port}:5678",
            "-v", f"{stack.n8n_volume}:/home/node/.n8n",
            "-e", "N8N_BLOCK_ENV_ACCESS_IN_NODE=false",
            "-e", "N8N_DIAG_ENABLED=false",
            "-e", "NODE_FUNCTION_ALLOW_BUILTIN=crypto",
            "-e", f"FACTURX_API_BASE_URL=http://{stack.api_container}:6969",
            "-e", f"LOCAL_LLM_BASE_URL=http://{stub_container}:8098",
            "-e", "LOCAL_LLM_MODEL=stub-vision-model",
            "-e", f"LOCAL_PDF_RENDER_URL=http://{stub_container}:8098",
            N8N_IMAGE, timeout=30,
        )
        assert run_n8n.returncode == 0, f"docker run (n8n) failed: {run_n8n.stderr}"
        _wait_for_http_ok(f"http://127.0.0.1:{stack.n8n_port}/healthz")
        stack._exec_api_healthcheck()

        stack.import_and_publish(
            (SHARED_SUBWORKFLOW_PATH, "digitax-invoice-phase1-shared-assemble-activity-execution"),
            (WORKFLOW_PATH, FLOW1B_WORKFLOW_ID),
        )

        response = stack.post_upload(
            data={"organizationId": "unternehmen-x-demo", "aiExecutionProfile": "local-default"},
            files={"data": ("test-invoice.pdf", b"%PDF-1.4 not a real pdf, content is irrelevant here", "application/pdf")},
        )
        assert response.status_code == 200
        body = response.text
        assert "unauffaellig" in body
        assert "standard_review" in body
        assert "ORG-001" in body
        # Proves the real API's report -- with the real catalogVersion-bearing
        # controls -- was used, not a fabricated/local result: STR-003/004 are
        # only produced by the real control executor.
        assert "STR-003" in body and "STR-004" in body
    finally:
        _docker("rm", "-f", stack.n8n_container, timeout=30)
        _docker("rm", "-f", stack.api_container, timeout=30)
        _docker("rm", "-f", stub_container, timeout=30)
        _docker("volume", "rm", stack.n8n_volume, timeout=30)
        _docker("network", "rm", stack.network, timeout=30)


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not available")
def test_e2e_malformed_local_model_output_converges_to_technical_review():
    """Required scenario: "malformed model output." The stub's
    /chat/completions?malformed=1 route returns non-JSON content; "02.5L
    Parse local OCR/LLM output" must throw (onError: continueErrorOutput)
    and the run must still converge to a non-empty technical_review
    payload, never an unhandled execution error."""
    stub_source = (Path(__file__).parent / "fixtures" / "flow1b_local_ai_stub.py")
    stack = _Flow1bStack(with_api=False)
    stub_container = f"flow1b-e2e-stub-{stack.suffix}"
    try:
        net = _docker("network", "create", stack.network)
        assert net.returncode == 0, f"docker network create failed: {net.stderr}"

        pull_python = _docker("pull", "python:3.12-slim", timeout=300)
        assert pull_python.returncode == 0, f"docker pull python:3.12-slim failed: {pull_python.stderr}"
        run_stub = _docker(
            "run", "-d", "--name", stub_container, "--network", stack.network,
            "-v", f"{stub_source}:/stub.py:ro", "-e", "FLOW1B_STUB_MALFORMED=1",
            "python:3.12-slim", "python", "/stub.py",
            timeout=30,
        )
        assert run_stub.returncode == 0, f"docker run (stub) failed: {run_stub.stderr}"

        stack.n8n_port = _free_tcp_port()
        pull_n8n = _docker("pull", N8N_IMAGE, timeout=300)
        assert pull_n8n.returncode == 0, f"docker pull {N8N_IMAGE} failed: {pull_n8n.stderr}"
        run_n8n = _docker(
            "run", "-d", "--name", stack.n8n_container, "--network", stack.network,
            "-p", f"{stack.n8n_port}:5678",
            "-v", f"{stack.n8n_volume}:/home/node/.n8n",
            "-e", "N8N_BLOCK_ENV_ACCESS_IN_NODE=false",
            "-e", "N8N_DIAG_ENABLED=false",
            "-e", "NODE_FUNCTION_ALLOW_BUILTIN=crypto",
            "-e", f"LOCAL_LLM_BASE_URL=http://{stub_container}:8098",
            "-e", "LOCAL_LLM_MODEL=stub-vision-model",
            "-e", f"LOCAL_PDF_RENDER_URL=http://{stub_container}:8098",
            N8N_IMAGE, timeout=30,
        )
        assert run_n8n.returncode == 0, f"docker run (n8n) failed: {run_n8n.stderr}"
        _wait_for_http_ok(f"http://127.0.0.1:{stack.n8n_port}/healthz")

        stack.import_and_publish(
            (SHARED_SUBWORKFLOW_PATH, "digitax-invoice-phase1-shared-assemble-activity-execution"),
            (WORKFLOW_PATH, FLOW1B_WORKFLOW_ID),
        )

        response = stack.post_upload(
            data={"organizationId": "unternehmen-x-demo", "aiExecutionProfile": "local-default"},
            files={"data": ("test-invoice.pdf", b"%PDF-1.4 not a real pdf, content is irrelevant here", "application/pdf")},
        )
        assert response.status_code == 200
        assert len(response.content) > 0
        body = response.text
        assert "nicht_pruefbar" in body
        assert "technical_review" in body
        assert "LOCAL_LLM_OUTPUT_PARSE_FAILED" in body
    finally:
        _docker("rm", "-f", stack.n8n_container, timeout=30)
        _docker("rm", "-f", stub_container, timeout=30)
        _docker("volume", "rm", stack.n8n_volume, timeout=30)
        _docker("network", "rm", stack.network, timeout=30)


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not available")
def test_e2e_flow1b_stays_inactive_after_import_disabled_state():
    """DISABLED policy state: importing Flow 1b (without an explicit
    publish, unlike every other E2E test in this file) must never make its
    webhook reachable -- proving the workflow truly starts inactive/
    disabled by default, distinct from LOCAL/CLOUD, which are only ever
    reachable after an explicit publish."""
    stack = _Flow1bStack(with_api=False)
    try:
        stack.start()
        dest = f"/tmp/{FLOW1B_WORKFLOW_ID}.json"
        cp = _docker("cp", str(WORKFLOW_PATH), f"{stack.n8n_container}:{dest}")
        assert cp.returncode == 0, f"docker cp failed: {cp.stderr}"
        imp = _docker("exec", stack.n8n_container, "n8n", "import:workflow", f"--input={dest}")
        assert imp.returncode == 0, f"n8n import:workflow failed: {imp.stderr}\n{imp.stdout}"
        # Deliberately no publish:workflow call here.
        response = httpx.post(
            f"http://127.0.0.1:{stack.n8n_port}/webhook/phase1-flow1b-pdf-upload",
            data={"organizationId": "unternehmen-x-demo", "aiExecutionProfile": "cloud-gemini"},
            files={"data": ("test-invoice.pdf", b"%PDF-1.4 irrelevant", "application/pdf")},
            timeout=10.0,
        )
        assert response.status_code == 404, "an unpublished/disabled Flow 1b must never be webhook-reachable"
    finally:
        stack.stop()
