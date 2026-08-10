"""Regression guard for examples/n8n/digitax_invoice_phase1_flow1b_pdf_ocr.json.

Structural checks plus real execution of the two business-logic-bearing Code
nodes (ORG-001 evaluation, status aggregation) via Node.js -- this workflow
has no live Gemini credentials in CI, so this is the strongest verification
available short of a real end-to-end run. The coordination handover log
records the real `n8n import:workflow` evidence against n8nio/n8n:2.33.7
separately; this test is not a substitute for that.
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
    / "digitax_invoice_phase1_flow1b_pdf_ocr.json"
)
INTAKE_WORKFLOW_PATH = (
    Path(__file__).parent.parent / "examples" / "n8n" / "digitax_invoice_intake.json"
)
EXAMPLES_N8N_DIR = Path(__file__).parent.parent / "examples" / "n8n"

EXPECTED_WORKFLOW_ID = "digitax-invoice-phase1-flow1b-pdf-ocr"
EXPECTED_WORKFLOW_NAME = "DigiTax Flow 1b - PDF OCR/LLM"

REUSED_OCR_NODE_NAMES = (
    "fix base64",
    "Build Gemini Request",
    "File-Based OCR with Gemini 2.5",
    "Gemini Output Parser",
)
REVIEW_NODES = (
    "Human Review - Standard",
    "Human Review - Prioritized",
    "Human Review - Technical",
    "Human Review - Unknown (fallback)",
)

FORBIDDEN_PATTERNS = [
    (re.compile(r"host\.docker\.internal"), "a hardcoded local-dev host"),
    (re.compile(r"vn ?impex", re.IGNORECASE), "the real organization name"),
    # https://generativelanguage.googleapis.com is Google's fixed, public
    # Gemini API endpoint -- a real API contract, not a deployment-specific
    # host -- so it's excluded from the "no hardcoded URL" check below.
]
ALLOWED_HARDCODED_URL_PREFIX = "https://generativelanguage.googleapis.com/"


def _load_workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _load_intake_workflow() -> dict:
    return json.loads(INTAKE_WORKFLOW_PATH.read_text(encoding="utf-8"))


def _nodes_by_name(data: dict) -> dict:
    return {n["name"]: n for n in data["nodes"]}


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
        wf_id = wf.get("id")
        assert wf_id not in seen_ids, (
            f"duplicate workflow id {wf_id!r} in {path.name} and {seen_ids.get(wf_id)}"
        )
        seen_ids[wf_id] = path.name
    assert EXPECTED_WORKFLOW_ID in seen_ids


def test_workflow_is_imported_inactive():
    """Task requirement: import into the isolated instance as inactive only."""
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
    # Only the reused Gemini OCR node carries a credential reference at all.
    assert credential_types_seen == {"googlePalmApi"}


def test_workflow_has_no_forbidden_content():
    text = json.dumps(_load_workflow())
    for pattern, description in FORBIDDEN_PATTERNS:
        assert not pattern.search(text), f"found {description} in the workflow export"

    url_like = re.findall(r"https?://[^\s\"'\\]+", text)
    for url in url_like:
        assert url.startswith(ALLOWED_HARDCODED_URL_PREFIX) or "{{" in url or "\\u003c" in url, (
            f"unexpected hardcoded URL {url!r} -- only the public Gemini API "
            "endpoint may be hardcoded; anything deployment-specific must be "
            "an n8n expression"
        )


def test_ocr_nodes_reused_verbatim_from_intake_workflow():
    """The four proven OCR nodes must not have their extraction logic
    replaced -- same node id, same jsCode/core parameters as the historical
    digitax_invoice_intake.json. The only permitted addition is fail-safe
    error-handling wiring (onError), never a logic change."""
    flow1b_nodes = _nodes_by_name(_load_workflow())
    intake_nodes = _nodes_by_name(_load_intake_workflow())

    for name in REUSED_OCR_NODE_NAMES:
        assert name in flow1b_nodes, f"missing reused node {name!r}"
        assert name in intake_nodes, f"reference node {name!r} missing from intake workflow"
        flow1b_node = flow1b_nodes[name]
        intake_node = intake_nodes[name]
        assert flow1b_node["id"] == intake_node["id"], f"{name!r} node id must be unchanged"

        if "jsCode" in flow1b_node.get("parameters", {}):
            assert flow1b_node["parameters"]["jsCode"] == intake_node["parameters"]["jsCode"], (
                f"{name!r} jsCode must be byte-for-byte identical to the historical workflow"
            )
        else:
            # File-Based OCR with Gemini 2.5: compare the extraction-relevant
            # parameters (method/url/body), not incidental fields.
            for key in ("method", "url", "jsonBody", "nodeCredentialType"):
                assert flow1b_node["parameters"].get(key) == intake_node["parameters"].get(key), (
                    f"{name!r} parameter {key!r} must be unchanged"
                )
            assert flow1b_node.get("retryOnFail") == intake_node.get("retryOnFail")
            assert flow1b_node.get("maxTries") == intake_node.get("maxTries")

    # The one documented, deliberate addition: Gemini Output Parser gets
    # fail-safe error routing that the historical workflow never had.
    assert flow1b_nodes["Gemini Output Parser"].get("onError") == "continueErrorOutput"
    assert "onError" not in intake_nodes["Gemini Output Parser"]


def test_fix_base64_binary_property_matches_run_context_output():
    """fix base64 is reused with its hardcoded binaryPropertyName='data' --
    Build Run Context must attach the upload under that same property name,
    not the 'invoiceFile' name used by the unrelated Flow 1a upload demo."""
    data = _load_workflow()
    nodes = _nodes_by_name(data)
    fix_base64_code = nodes["fix base64"]["parameters"]["jsCode"]
    assert "binaryPropertyName = 'data'" in fix_base64_code
    run_context_code = nodes["Build Run Context"]["parameters"]["jsCode"]
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


def test_org_001_control_naming_matches_spec():
    data = _load_workflow()
    code = _nodes_by_name(data)["Evaluate ORG-001 (temporary mirror)"]["parameters"]["jsCode"]
    assert 'CONTROL_ID = "ORG-001"' in code
    assert 'TITLE = "Stammdatenabgleich Rechnungsempfänger"' in code
    assert "zugferd" not in code.lower() and "gateway" not in code.lower(), (
        "must not be called a ZUGFeRD gateway"
    )


def test_org_001_compares_exactly_the_five_required_buyer_fields():
    data = _load_workflow()
    code = _nodes_by_name(data)["Evaluate ORG-001 (temporary mirror)"]["parameters"]["jsCode"]
    for field in (
        "invoice.buyer.name",
        "invoice.buyer.address.street",
        "invoice.buyer.address.postalCode",
        "invoice.buyer.address.city",
        "invoice.buyer.address.countryCode",
    ):
        assert field in code, f"ORG-001 must reference {field!r}"


def test_confidence_threshold_matches_api_default():
    data = _load_workflow()
    code = _nodes_by_name(data)["Evaluate ORG-001 (temporary mirror)"]["parameters"]["jsCode"]
    assert "THRESHOLD = 0.70" in code


def test_explicit_technical_review_route_distinct_from_unknown_fallback():
    data = _load_workflow()
    switch_node = _nodes_by_name(data)["Status Routing"]
    rule_values = {
        cond["rightValue"]
        for rule in switch_node["parameters"]["rules"]["values"]
        for cond in rule["conditions"]["conditions"]
    }
    assert {"standard_review", "prioritized_review", "technical_review"} <= rule_values
    assert switch_node["parameters"]["options"]["fallbackOutput"] == "extra"

    branches = data["connections"]["Status Routing"]["main"]
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


def test_every_failure_and_success_path_converges_on_single_response_builder():
    data = _load_workflow()
    payload_sources = (
        "Build Invalid Upload Payload",
        "Build Unknown Organization Payload",
        "Build OCR Service Failure Payload",
        "Build OCR Parse Failure Payload",
        "Build Review Summary",
    )
    for source in payload_sources:
        targets = {edge["node"] for branch in data["connections"][source]["main"] for edge in branch}
        assert targets == {"Build Browser Response"}, f"{source!r} must feed Build Browser Response"

    assert data["connections"]["Build Browser Response"]["main"][0][0]["node"] == "Respond to Webhook"
    assert data["connections"]["Respond to Webhook"]["main"][0][0]["node"] == "Status Routing"


def test_browser_response_is_html():
    data = _load_workflow()
    respond_node = _nodes_by_name(data)["Respond to Webhook"]
    assert respond_node["parameters"]["respondWith"] == "text"
    headers = respond_node["parameters"]["options"]["responseHeaders"]["entries"]
    content_type = next(h["value"] for h in headers if h["name"] == "Content-Type")
    assert "text/html" in content_type


def test_temporary_implementation_is_disclosed_in_the_response():
    """Prompt item 6: never fake API reuse -- the browser-facing result
    itself must say this is a temporary n8n-side implementation."""
    data = _load_workflow()
    code = _nodes_by_name(data)["Build Browser Response"]["parameters"]["jsCode"]
    assert "temporary n8n-side implementation" in code
    assert "cannot yet consume" in code or "no injection seam" in code


def test_workflow_never_reaches_approval_booking_payment_or_supplier_nodes():
    data = _load_workflow()
    forbidden_terms = ("approv", "booking", "payment", "supplier communication", "pay_")
    for node in data["nodes"]:
        lowered = node["name"].lower()
        assert not any(term in lowered for term in forbidden_terms), (
            f"node {node['name']!r} looks like it goes past the human-review boundary"
        )


def test_digitax_invoice_intake_json_is_unchanged():
    """The historical workflow must remain untouched as a source, per the
    task's first requirement."""
    import subprocess as sp

    result = sp.run(
        ["git", "diff", "--quiet", "--", str(INTAKE_WORKFLOW_PATH)],
        cwd=INTAKE_WORKFLOW_PATH.parent.parent.parent,
    )
    assert result.returncode == 0, "digitax_invoice_intake.json must not be modified"


# ---------------------------------------------------------------------------
# Real execution of the business-logic-bearing Code nodes via Node.js.
# No live Gemini credentials exist in CI/this checkout, so this is the
# strongest available proof that the reused control logic actually behaves
# correctly, not just that the code looks right.
# ---------------------------------------------------------------------------

NODE_AVAILABLE = shutil.which("node") is not None


def _run_node_snippet(js_code: str, input_json_expr: str) -> dict:
    """Wraps an n8n Code node body (which uses `return [...]` and
    `$input.first()`) in a function, executes it with `$input` providing the
    given single item, and returns the first output item's `json`."""
    harness = f"""
const $input = {{ first: () => ({{ json: {input_json_expr} }}) }};
function run() {{
{js_code}
}}
const result = run();
process.stdout.write(JSON.stringify(result[0].json));
"""
    proc = subprocess.run(
        ["node", "-e", harness],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, f"node execution failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _org001_code() -> str:
    data = _load_workflow()
    return _nodes_by_name(data)["Evaluate ORG-001 (temporary mirror)"]["parameters"]["jsCode"]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_org001_real_execution_passes_when_fields_match():
    invoice_input = json.dumps({
        "invoice": {
            "buyer": {
                "name": "Unternehmen X",
                "address": {"street": "Musterweg 10", "postalCode": "04109", "city": "Leipzig", "countryCode": "DE"},
            }
        },
        "fieldEvidence": {
            k: {"confidence": 0.85, "locator": k}
            for k in (
                "invoice.buyer.name", "invoice.buyer.address.street",
                "invoice.buyer.address.postalCode", "invoice.buyer.address.city",
                "invoice.buyer.address.countryCode",
            )
        },
        "buyerMasterData": {"name": "Unternehmen X", "street": "Musterweg 10", "postalCode": "04109", "city": "Leipzig", "countryCode": "DE"},
    })
    result = _run_node_snippet(_org001_code(), invoice_input)
    assert result["org001"]["outcome"] == "passed"
    assert result["org001"]["severity"] == "none"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_org001_real_execution_fails_on_master_data_mismatch():
    invoice_input = json.dumps({
        "invoice": {
            "buyer": {
                "name": "Unternehmen X",
                "address": {"street": "Musterweg 10", "postalCode": "04109", "city": "WRONG CITY", "countryCode": "DE"},
            }
        },
        "fieldEvidence": {
            k: {"confidence": 0.85, "locator": k}
            for k in (
                "invoice.buyer.name", "invoice.buyer.address.street",
                "invoice.buyer.address.postalCode", "invoice.buyer.address.city",
                "invoice.buyer.address.countryCode",
            )
        },
        "buyerMasterData": {"name": "Unternehmen X", "street": "Musterweg 10", "postalCode": "04109", "city": "Leipzig", "countryCode": "DE"},
    })
    result = _run_node_snippet(_org001_code(), invoice_input)
    assert result["org001"]["outcome"] == "failed"
    assert result["org001"]["severity"] == "blocking"
    assert result["org001"]["reasonCodes"] == ["MASTER_DATA_MISMATCH"]
    assert result["org001"]["details"]["mismatches"][0]["field"] == "invoice.buyer.address.city"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_org001_real_execution_never_auto_passes_on_low_confidence():
    """Prompt item 7: low-confidence or missing OCR fields must route to
    nicht_pruefbar/clarification, never an automatic pass -- even when the
    (unreliable) extracted value happens to match master data exactly."""
    invoice_input = json.dumps({
        "invoice": {
            "buyer": {
                "name": "Unternehmen X",
                "address": {"street": "Musterweg 10", "postalCode": "04109", "city": "Leipzig", "countryCode": "DE"},
            }
        },
        "fieldEvidence": {
            "invoice.buyer.name": {"confidence": 0.2, "locator": "invoice.buyer.name"},  # below threshold
            "invoice.buyer.address.street": {"confidence": 0.85, "locator": "invoice.buyer.address.street"},
            "invoice.buyer.address.postalCode": {"confidence": 0.85, "locator": "invoice.buyer.address.postalCode"},
            "invoice.buyer.address.city": {"confidence": 0.85, "locator": "invoice.buyer.address.city"},
            "invoice.buyer.address.countryCode": {"confidence": 0.85, "locator": "invoice.buyer.address.countryCode"},
        },
        "buyerMasterData": {"name": "Unternehmen X", "street": "Musterweg 10", "postalCode": "04109", "city": "Leipzig", "countryCode": "DE"},
    })
    result = _run_node_snippet(_org001_code(), invoice_input)
    assert result["org001"]["outcome"] == "not_reliable"
    assert result["org001"]["reasonCodes"] == ["LOW_CONFIDENCE_EXTRACTION"]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_org001_real_execution_fails_closed_on_missing_field():
    invoice_input = json.dumps({
        "invoice": {
            "buyer": {
                "name": None,
                "address": {"street": "Musterweg 10", "postalCode": "04109", "city": "Leipzig", "countryCode": "DE"},
            }
        },
        "fieldEvidence": {
            k: {"confidence": 0.85, "locator": k}
            for k in (
                "invoice.buyer.name", "invoice.buyer.address.street",
                "invoice.buyer.address.postalCode", "invoice.buyer.address.city",
                "invoice.buyer.address.countryCode",
            )
        },
        "buyerMasterData": {"name": "Unternehmen X", "street": "Musterweg 10", "postalCode": "04109", "city": "Leipzig", "countryCode": "DE"},
    })
    result = _run_node_snippet(_org001_code(), invoice_input)
    assert result["org001"]["outcome"] == "failed"
    assert result["org001"]["reasonCodes"] == ["MISSING_FIELD"]


def _aggregation_code() -> str:
    data = _load_workflow()
    return _nodes_by_name(data)["Build Review Summary"]["parameters"]["jsCode"]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
@pytest.mark.parametrize(
    "org001_outcome,expected_status,expected_routing",
    [
        ("passed", "unauffaellig", "standard_review"),
        ("failed", "klaerung_erforderlich", "prioritized_review"),
        ("not_reliable", "nicht_pruefbar", "prioritized_review"),
    ],
)
def test_status_aggregation_matches_real_aggregate_py_semantics(
    org001_outcome, expected_status, expected_routing
):
    """Mirrors facturx/phase1/controls/aggregate.py's mapping exactly for a
    single control -- technical_review must never appear here, since that
    routing value only exists for genuine service/input failures upstream
    of this node, not for a real content-classification outcome."""
    invoice_input = json.dumps({
        "correlationId": "test-corr-id",
        "invoice": {"invoiceNumber": "TEST-1"},
        "organizationId": "unternehmen-x-demo",
        "org001": {
            "controlId": "ORG-001",
            "title": "Stammdatenabgleich Rechnungsempfänger",
            "outcome": org001_outcome,
            "severity": "blocking" if org001_outcome != "passed" else "none",
            "reasonCodes": [],
            "evidenceRefs": [],
            "ruleVersion": "1.0.0",
            "message": None,
            "details": None,
        },
    })
    result = _run_node_snippet(_aggregation_code(), invoice_input)
    assert result["status"] == expected_status
    assert result["routing"] == expected_routing
