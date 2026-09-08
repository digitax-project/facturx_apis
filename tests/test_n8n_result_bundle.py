"""Regression guard for A6a correction round 1, plan section 6: the frozen
TCMS-facing `resultBundle` envelope.

Mirrors tests/test_n8n_generated_validators.py and
tests/test_n8n_risk_review_report_validator.py's coverage pattern for the
AJV-standalone generated validator
(examples/n8n/generated/validate_result_bundle.generated.js), plus
end-to-end behavioral proofs against the real "04.7 Assemble result bundle"
node: A5c consumes response.resultBundle exclusively, so this is the
contract that actually matters.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
N8N_DIR = REPO_ROOT / "examples" / "n8n"
GENERATED_DIR = N8N_DIR / "generated"
VALIDATOR_PATH = GENERATED_DIR / "validate_result_bundle.generated.js"
PROVENANCE_PATH = GENERATED_DIR / "validator_provenance.json"
GENERATOR_SCRIPT_PATH = N8N_DIR / "scripts" / "generate-evidence-validators.mjs"
SCHEMA_PATH = N8N_DIR / "schemas" / "result-bundle-v1.0.0.schema.json"
BATCH_ITEM_PATH = N8N_DIR / "digitax_invoice_phase1_flow1a_batch_item_v1_1_0.json"

NODE_AVAILABLE = shutil.which("node") is not None
NODE_MODULES_AVAILABLE = (N8N_DIR / "node_modules" / "ajv").exists() and (
    N8N_DIR / "node_modules" / "ajv-formats"
).exists()

ASSEMBLE_BUNDLE_NODE = "04.7 Assemble result bundle"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_has_five_required_properties_and_forbids_additional():
    schema = _load_json(SCHEMA_PATH)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "resultBundleSchemaVersion",
        "phase1ControlReport",
        "activityExecution",
        "riskReviewReport",
        "routingStatus",
    }
    assert set(schema["properties"]) == set(schema["required"])


def test_generated_validator_exists_with_generated_header():
    assert VALIDATOR_PATH.exists()
    first_line = VALIDATOR_PATH.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("// GENERATED FILE -- do not hand-edit.")


def test_provenance_records_result_bundle_generated_and_matches_schema():
    import hashlib

    provenance = _load_json(PROVENANCE_PATH)
    assert provenance["result-bundle"]["status"] == "GENERATED"
    assert provenance["result-bundle"]["sourceSha256"] == hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()


def test_generated_validator_has_no_require_or_module_reference():
    source = VALIDATOR_PATH.read_text(encoding="utf-8")
    assert "require(" not in source
    assert "module." not in source
    assert "import " not in source


def test_generated_validator_source_embedded_verbatim_in_batch_item_workflow():
    validator_source = VALIDATOR_PATH.read_text(encoding="utf-8")
    wf = _load_json(BATCH_ITEM_PATH)
    node = next(n for n in wf["nodes"] if n["name"] == ASSEMBLE_BUNDLE_NODE)
    assert validator_source in node["parameters"]["jsCode"], (
        "committed generated validator source does not appear verbatim inside "
        "the Batch Item workflow's 04.7 node -- regeneration was not followed by re-embedding"
    )


@pytest.mark.skipif(
    not (NODE_AVAILABLE and NODE_MODULES_AVAILABLE),
    reason="node.js or ajv/ajv-formats devDependencies not available",
)
def test_regenerating_produces_byte_identical_result_bundle_validator():
    proc = subprocess.run(
        ["node", str(GENERATOR_SCRIPT_PATH)], cwd=str(N8N_DIR), capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, f"generator failed:\n{proc.stdout}\n{proc.stderr}"
    regenerated = VALIDATOR_PATH.read_bytes()
    proc2 = subprocess.run(
        ["node", str(GENERATOR_SCRIPT_PATH)], cwd=str(N8N_DIR), capture_output=True, text=True, timeout=60
    )
    assert proc2.returncode == 0
    assert VALIDATOR_PATH.read_bytes() == regenerated, "regeneration is not deterministic"


# ---------------------------------------------------------------------------
# Functional validation proof, against the standalone generated validator.
# ---------------------------------------------------------------------------


def _valid_bundle() -> dict:
    return {
        "resultBundleSchemaVersion": "1.0.0",
        "phase1ControlReport": {"reportId": "REP-1", "status": "unauffaellig"},
        "activityExecution": {"executionId": "RUN-1"},
        "riskReviewReport": None,
        "routingStatus": "NO_RISK_REVIEW_REQUIRED",
    }


def _run_validator(fixture: dict) -> dict:
    source = VALIDATOR_PATH.read_text(encoding="utf-8")
    harness = f"""
{source}
const fixture = {json.dumps(fixture)};
const ok = validateResultBundle(fixture);
process.stdout.write(JSON.stringify({{ ok, errors: validateResultBundle.errors || null }}));
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".mjs", delete=False, encoding="utf-8") as f:
        f.write(harness)
        script_path = f.name
    try:
        proc = subprocess.run(["node", script_path], capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0, f"node execution failed: {proc.stderr}"
        return json.loads(proc.stdout)
    finally:
        Path(script_path).unlink(missing_ok=True)


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_valid_bundle_is_accepted():
    assert _run_validator(_valid_bundle())["ok"] is True


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_valid_bundle_with_object_report_and_review_is_accepted():
    fixture = _valid_bundle()
    fixture["routingStatus"] = "RISK_REVIEW_PROPOSED"
    fixture["riskReviewReport"] = {"reportId": "RRR-1", "disposition": "RISK_REVIEW_PROPOSED"}
    assert _run_validator(fixture)["ok"] is True


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_phase1_control_report_null_is_accepted_pre_report_technical_failure():
    fixture = _valid_bundle()
    fixture["phase1ControlReport"] = None
    fixture["routingStatus"] = "TECHNICAL_FAILURE"
    assert _run_validator(fixture)["ok"] is True


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_missing_required_property_is_rejected():
    fixture = _valid_bundle()
    del fixture["routingStatus"]
    result = _run_validator(fixture)
    assert result["ok"] is False
    assert any(e["keyword"] == "required" for e in result["errors"])


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_additional_property_is_rejected():
    fixture = _valid_bundle()
    fixture["resultCode"] = "SOMETHING"
    result = _run_validator(fixture)
    assert result["ok"] is False
    assert any(e["keyword"] == "additionalProperties" for e in result["errors"])


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_wrong_result_bundle_schema_version_is_rejected():
    fixture = _valid_bundle()
    fixture["resultBundleSchemaVersion"] = "2.0.0"
    result = _run_validator(fixture)
    assert result["ok"] is False
    assert any(e["keyword"] == "const" for e in result["errors"])


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_activity_execution_null_is_rejected():
    """activityExecution is always the schema-valid execution the shared
    assembler produced -- never null, unlike phase1ControlReport."""
    fixture = _valid_bundle()
    fixture["activityExecution"] = None
    result = _run_validator(fixture)
    assert result["ok"] is False


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_routing_status_outside_enum_is_rejected():
    fixture = _valid_bundle()
    fixture["routingStatus"] = "SOMETHING_MADE_UP"
    result = _run_validator(fixture)
    assert result["ok"] is False
    assert any(e["keyword"] == "enum" for e in result["errors"])


# ---------------------------------------------------------------------------
# End-to-end proof against the real "04.7 Assemble result bundle" node.
# ---------------------------------------------------------------------------


def _run_assemble_bundle_node(e: dict) -> dict:
    wf = _load_json(BATCH_ITEM_PATH)
    node = next(n for n in wf["nodes"] if n["name"] == ASSEMBLE_BUNDLE_NODE)
    code = node["parameters"]["jsCode"]
    harness = f"""
const $input = {{ first: () => ({{ json: {json.dumps(e)} }}) }};
function run() {{
{code}
}}
try {{
  const result = run();
  process.stdout.write(JSON.stringify({{ ok: true, result: result[0].json }}));
}} catch (err) {{
  process.stdout.write(JSON.stringify({{ ok: false, message: err.message }}));
}}
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".mjs", delete=False, encoding="utf-8") as f:
        f.write(harness)
        script_path = f.name
    try:
        proc = subprocess.run(["node", script_path], capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0, f"node execution failed: {proc.stderr}"
        return json.loads(proc.stdout)
    finally:
        Path(script_path).unlink(missing_ok=True)


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_node_clean_report_produces_valid_result_bundle():
    e = {
        "ok": True,
        "statusCode": 200,
        "canonicalInvoice": {"invoiceNumber": "INV-1"},
        "phase1ControlReport": {"reportId": "REP-1", "status": "unauffaellig"},
        "activityExecution": {"executionId": "RUN-1"},
        "riskReviewReport": None,
        "routingStatus": "NO_RISK_REVIEW_REQUIRED",
    }
    out = _run_assemble_bundle_node(e)
    assert out["ok"] is True, out
    result = out["result"]
    # Legacy top-level shape preserved additively.
    assert result["ok"] is True
    assert result["canonicalInvoice"] == {"invoiceNumber": "INV-1"}
    # New, frozen, TCMS-facing nested contract.
    bundle = result["resultBundle"]
    assert bundle == {
        "resultBundleSchemaVersion": "1.0.0",
        "phase1ControlReport": {"reportId": "REP-1", "status": "unauffaellig"},
        "activityExecution": {"executionId": "RUN-1"},
        "riskReviewReport": None,
        "routingStatus": "NO_RISK_REVIEW_REQUIRED",
    }


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_node_finding_bearing_report_with_review_produces_valid_result_bundle():
    e = {
        "ok": True,
        "statusCode": 200,
        "canonicalInvoice": {"invoiceNumber": "INV-2"},
        "phase1ControlReport": {"reportId": "REP-2", "status": "klaerung_erforderlich"},
        "activityExecution": {"executionId": "RUN-2"},
        "riskReviewReport": {"reportId": "RRR-2", "disposition": "RISK_REVIEW_PROPOSED"},
        "routingStatus": "RISK_REVIEW_PROPOSED",
    }
    out = _run_assemble_bundle_node(e)
    assert out["ok"] is True, out
    bundle = out["result"]["resultBundle"]
    assert bundle["riskReviewReport"] == {"reportId": "RRR-2", "disposition": "RISK_REVIEW_PROPOSED"}
    assert bundle["routingStatus"] == "RISK_REVIEW_PROPOSED"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_node_phase1_api_failure_produces_null_phase1_control_report_in_bundle():
    e = {
        "ok": False,
        "statusCode": 400,
        "errorCode": "INVALID_REQUEST_BODY",
        "detail": "bad request",
        "activityExecution": {"executionId": "N8N-FAIL-P1"},
        "routingStatus": "TECHNICAL_FAILURE",
    }
    out = _run_assemble_bundle_node(e)
    assert out["ok"] is True, out
    result = out["result"]
    assert result["ok"] is False
    bundle = result["resultBundle"]
    assert bundle["phase1ControlReport"] is None
    assert bundle["activityExecution"] == {"executionId": "N8N-FAIL-P1"}
    assert bundle["routingStatus"] == "TECHNICAL_FAILURE"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_node_fail_closed_missing_tcms_org_id_produces_valid_result_bundle():
    e = {
        "ok": True,
        "statusCode": 200,
        "canonicalInvoice": {"invoiceNumber": "INV-3"},
        "phase1ControlReport": {"reportId": "REP-3", "status": "klaerung_erforderlich"},
        "activityExecution": {"executionId": "RUN-3"},
        "riskReviewReport": None,
        "routingStatus": "RISK_REVIEW_MISSING_TCMS_ORGANIZATION_ID",
    }
    out = _run_assemble_bundle_node(e)
    assert out["ok"] is True, out
    bundle = out["result"]["resultBundle"]
    assert bundle["routingStatus"] == "RISK_REVIEW_MISSING_TCMS_ORGANIZATION_ID"
    assert bundle["riskReviewReport"] is None


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_node_result_code_from_malformed_response_stays_out_of_bundle():
    """resultCode (set by 04.6 on a schema-invalid Risk Review response) is
    not one of the resultBundle's five strict properties -- it must land on
    the legacy top-level shape only, never inside resultBundle (which would
    fail additionalProperties:false)."""
    e = {
        "ok": True,
        "statusCode": 200,
        "canonicalInvoice": {"invoiceNumber": "INV-4"},
        "phase1ControlReport": {"reportId": "REP-4", "status": "klaerung_erforderlich"},
        "activityExecution": {"executionId": "RUN-4"},
        "riskReviewReport": None,
        "routingStatus": "TECHNICAL_FAILURE",
        "resultCode": "RISK_REVIEW_RESPONSE_SCHEMA_INVALID",
    }
    out = _run_assemble_bundle_node(e)
    assert out["ok"] is True, out
    result = out["result"]
    assert result["resultCode"] == "RISK_REVIEW_RESPONSE_SCHEMA_INVALID"
    assert "resultCode" not in result["resultBundle"]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_node_throws_if_it_would_produce_an_invalid_bundle():
    """An internal bug (this workflow itself producing a structurally wrong
    bundle), not caller input -- so it must throw loudly, the same as 01.4's
    ActivityExecution shape guard, rather than silently degrade."""
    e = {
        "ok": True,
        "statusCode": 200,
        "canonicalInvoice": {},
        "phase1ControlReport": {"reportId": "REP-5"},
        "activityExecution": {"executionId": "RUN-5"},
        "riskReviewReport": None,
        "routingStatus": "SOMETHING_NOT_IN_THE_ENUM",
    }
    out = _run_assemble_bundle_node(e)
    assert out["ok"] is False
    assert "RESULT_BUNDLE_SCHEMA_INVALID" in out["message"]
