"""Regression guard for A6a correction round 1, plan section 5: strict
RiskReviewReport 1.1 response validation.

Mirrors tests/test_n8n_generated_validators.py's coverage pattern for the
AJV-standalone generated validator
(examples/n8n/generated/validate_risk_review_report.generated.js) and its
generator (examples/n8n/scripts/generate-evidence-validators.mjs), plus the
4 required functional cases the plan names: valid response, missing
required property, unsupported schema version, invalid disposition.
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
VALIDATOR_PATH = GENERATED_DIR / "validate_risk_review_report.generated.js"
PROVENANCE_PATH = GENERATED_DIR / "validator_provenance.json"
GENERATOR_SCRIPT_PATH = N8N_DIR / "scripts" / "generate-evidence-validators.mjs"
VENDOR_SCHEMA_PATH = N8N_DIR / "vendor" / "tcms_contracts" / "risk-review-report-v1.1.0.schema.json"
VENDOR_PROVENANCE_PATH = N8N_DIR / "vendor" / "tcms_contracts" / "schema_provenance.json"
BATCH_ITEM_PATH = N8N_DIR / "digitax_invoice_phase1_flow1a_batch_item_v1_1_0.json"

NODE_AVAILABLE = shutil.which("node") is not None
NODE_MODULES_AVAILABLE = (N8N_DIR / "node_modules" / "ajv").exists() and (
    N8N_DIR / "node_modules" / "ajv-formats"
).exists()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_vendored_schema_and_provenance_exist_and_match():
    import hashlib

    assert VENDOR_SCHEMA_PATH.exists()
    provenance = _load_json(VENDOR_PROVENANCE_PATH)
    entry = provenance["risk-review-report-v1.1.0"]
    assert entry["sourceSha256"] == hashlib.sha256(VENDOR_SCHEMA_PATH.read_bytes()).hexdigest()
    assert "tcms-framework@58a601222dbe805bcb4077bfbd501704ad5fed78" in entry["sourceRef"]
    text = json.dumps(provenance).lower()
    assert "generatedat" not in text


def test_generated_validator_exists_with_generated_header():
    assert VALIDATOR_PATH.exists()
    first_line = VALIDATOR_PATH.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("// GENERATED FILE -- do not hand-edit.")


def test_provenance_records_risk_review_report_generated():
    provenance = _load_json(PROVENANCE_PATH)
    assert provenance["risk-review-report"]["status"] == "GENERATED"


def test_provenance_source_sha256_matches_vendored_schema():
    import hashlib

    provenance = _load_json(PROVENANCE_PATH)
    assert provenance["risk-review-report"]["sourceSha256"] == hashlib.sha256(
        VENDOR_SCHEMA_PATH.read_bytes()
    ).hexdigest()


def test_generated_validator_has_no_require_or_module_reference():
    """Must be embeddable verbatim inside a sandboxed n8n Code node with no
    NODE_FUNCTION_ALLOW_EXTERNAL and no ajv/ajv-formats present at runtime."""
    source = VALIDATOR_PATH.read_text(encoding="utf-8")
    assert "require(" not in source
    assert "module." not in source
    assert "import " not in source


def test_generated_validator_source_embedded_verbatim_in_batch_item_workflow():
    validator_source = VALIDATOR_PATH.read_text(encoding="utf-8")
    wf = _load_json(BATCH_ITEM_PATH)
    node = next(n for n in wf["nodes"] if n["name"] == "04.6 Handle risk review response")
    assert validator_source in node["parameters"]["jsCode"], (
        "committed generated validator source does not appear verbatim inside "
        "the Batch Item workflow's 04.6 node -- regeneration was not followed by re-embedding"
    )


@pytest.mark.skipif(
    not (NODE_AVAILABLE and NODE_MODULES_AVAILABLE),
    reason="node.js or ajv/ajv-formats devDependencies not available",
)
def test_regenerating_produces_byte_identical_risk_review_validator(tmp_path):
    proc = subprocess.run(
        ["node", str(GENERATOR_SCRIPT_PATH)],
        cwd=str(N8N_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"generator failed:\n{proc.stdout}\n{proc.stderr}"
    regenerated = VALIDATOR_PATH.read_bytes()

    proc2 = subprocess.run(
        ["node", str(GENERATOR_SCRIPT_PATH)],
        cwd=str(N8N_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc2.returncode == 0
    assert VALIDATOR_PATH.read_bytes() == regenerated, "regeneration is not deterministic"


# ---------------------------------------------------------------------------
# Functional validation proof, executed directly against the generated
# validator (not the full 04.6 node -- see
# tests/test_n8n_batch_workflow.py's RISK_REVIEW_HANDLE_NODE coverage and
# the fail-closed proof below for the node-level behavior).
# ---------------------------------------------------------------------------


def _valid_risk_review_report() -> dict:
    return {
        "schemaVersion": "1.1.0",
        "reportId": "RRR-1",
        "requestId": "REQ-1",
        "correlationId": "CORR-1",
        "organizationId": "tcms-org-1",
        "processId": "digitax.invoice-intake",
        "processVersion": "1.1.1-draft",
        "activityId": "digitax.invoice-intake.phase1.structured-control",
        "activityVersion": "1.0.0",
        "processInstanceId": "P1",
        "sourceExecutionId": "RUN-1",
        "activityExecutionRef": "evidence://activity-execution/RUN-1",
        "activityExecutionSha256": "a" * 64,
        "controlReportRef": "evidence://phase1-control-report/REP-1",
        "controlReportSha256": "b" * 64,
        "riskCatalogVersionUsed": "flow1a-risk-catalog-2026-08-14",
        "triggerPolicyVersionUsed": "flow1a-trigger-policy-1.0.0",
        "disposition": "RISK_REVIEW_PROPOSED",
        "sourceFindings": [],
        "taxRisks": [],
        "proposedMeasures": [],
        "reviewStatus": "HUMAN_REVIEW_REQUIRED",
        "advisoryStatus": "COMPLETED",
        "technicalReasonCode": None,
        "createdAt": "2026-08-14T10:00:02.000Z",
    }


def _run_validator(fixture: dict) -> dict:
    # Written to a temp .js file, not `node -e` -- the ~80KB generated
    # validator source exceeds the Windows command-line length limit.
    source = VALIDATOR_PATH.read_text(encoding="utf-8")
    harness = f"""
{source}
const fixture = {json.dumps(fixture)};
const ok = validateRiskReviewReport(fixture);
process.stdout.write(JSON.stringify({{ ok, errors: validateRiskReviewReport.errors || null }}));
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
def test_valid_response_is_accepted():
    result = _run_validator(_valid_risk_review_report())
    assert result["ok"] is True, result["errors"]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_missing_required_property_is_rejected():
    fixture = _valid_risk_review_report()
    del fixture["reportId"]
    result = _run_validator(fixture)
    assert result["ok"] is False
    assert any(e["keyword"] == "required" for e in result["errors"])


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_unsupported_schema_version_is_rejected():
    fixture = _valid_risk_review_report()
    fixture["schemaVersion"] = "0.9.0"
    result = _run_validator(fixture)
    assert result["ok"] is False
    assert any(e["keyword"] == "const" for e in result["errors"])


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_invalid_disposition_is_rejected():
    fixture = _valid_risk_review_report()
    fixture["disposition"] = "NOT_A_REAL_DISPOSITION"
    result = _run_validator(fixture)
    assert result["ok"] is False
    assert any(e["keyword"] == "enum" for e in result["errors"])


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_rejects_additional_properties():
    fixture = _valid_risk_review_report()
    fixture["unexpectedField"] = "x"
    result = _run_validator(fixture)
    assert result["ok"] is False
    assert any(e["keyword"] == "additionalProperties" for e in result["errors"])


# ---------------------------------------------------------------------------
# End-to-end fail-closed proof against the real "04.6 Handle risk review
# response" node (not just the standalone validator function above) --
# required by the plan's own verification list ("malformed Risk Review
# fail-closed test").
# ---------------------------------------------------------------------------


def _run_handle_response_node(prior: dict, response: dict) -> dict:
    wf = _load_json(BATCH_ITEM_PATH)
    node = next(n for n in wf["nodes"] if n["name"] == "04.6 Handle risk review response")
    code = node["parameters"]["jsCode"]
    harness = f"""
const $input = {{ first: () => ({{ json: {json.dumps(response)} }}) }};
const __prior = {json.dumps(prior)};
function $(name) {{ return {{ item: {{ json: __prior }} }}; }}
function run() {{
{code}
}}
try {{
  const result = run();
  process.stdout.write(JSON.stringify({{ ok: true, result: result[0].json }}));
}} catch (e) {{
  process.stdout.write(JSON.stringify({{ ok: false, message: e.message }}));
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
def test_node_accepts_a_real_valid_2xx_response():
    prior = {"needsRiskReview": True, "phase1ControlReport": {"status": "klaerung_erforderlich"}}
    response = {"statusCode": 200, "body": _valid_risk_review_report()}
    out = _run_handle_response_node(prior, response)
    assert out["ok"] is True, out
    result = out["result"]
    assert result["riskReviewReport"] == _valid_risk_review_report()
    assert result["routingStatus"] == "RISK_REVIEW_PROPOSED"
    assert "resultCode" not in result


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_node_fails_closed_on_a_malformed_2xx_response():
    """A6a correction round 1 (section 5): a 2xx response missing a
    required field must never be partially trusted -- the prior node's
    already-assembled evidence is preserved, but riskReviewReport is
    dropped, not passed through."""
    prior = {
        "needsRiskReview": True,
        "phase1ControlReport": {"reportId": "REP-KEEP", "status": "klaerung_erforderlich"},
        "activityExecution": {"executionId": "RUN-KEEP"},
    }
    malformed = _valid_risk_review_report()
    del malformed["reportId"]
    response = {"statusCode": 200, "body": malformed}
    out = _run_handle_response_node(prior, response)
    assert out["ok"] is True, out
    result = out["result"]
    assert result["riskReviewReport"] is None
    assert result["routingStatus"] == "TECHNICAL_FAILURE"
    assert result["resultCode"] == "RISK_REVIEW_RESPONSE_SCHEMA_INVALID"
    # Prior evidence is preserved, not discarded.
    assert result["phase1ControlReport"]["reportId"] == "REP-KEEP"
    assert result["activityExecution"]["executionId"] == "RUN-KEEP"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_node_fails_closed_on_unsupported_schema_version_in_2xx_response():
    prior = {"needsRiskReview": True}
    fixture = _valid_risk_review_report()
    fixture["schemaVersion"] = "0.9.0"
    response = {"statusCode": 200, "body": fixture}
    out = _run_handle_response_node(prior, response)
    assert out["ok"] is True, out
    result = out["result"]
    assert result["riskReviewReport"] is None
    assert result["routingStatus"] == "TECHNICAL_FAILURE"
    assert result["resultCode"] == "RISK_REVIEW_RESPONSE_SCHEMA_INVALID"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_node_fails_closed_on_invalid_disposition_in_2xx_response():
    prior = {"needsRiskReview": True}
    fixture = _valid_risk_review_report()
    fixture["disposition"] = "NOT_A_REAL_DISPOSITION"
    response = {"statusCode": 200, "body": fixture}
    out = _run_handle_response_node(prior, response)
    assert out["ok"] is True, out
    result = out["result"]
    assert result["riskReviewReport"] is None
    assert result["routingStatus"] == "TECHNICAL_FAILURE"
    assert result["resultCode"] == "RISK_REVIEW_RESPONSE_SCHEMA_INVALID"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_node_non_2xx_failure_has_no_result_code():
    """A connection/HTTP-level failure is a different failure mode from a
    schema-invalid response body -- it must not carry
    RISK_REVIEW_RESPONSE_SCHEMA_INVALID."""
    prior = {"needsRiskReview": True}
    response = {"statusCode": 503, "body": {}}
    out = _run_handle_response_node(prior, response)
    assert out["ok"] is True, out
    result = out["result"]
    assert result["riskReviewReport"] is None
    assert result["routingStatus"] == "TECHNICAL_FAILURE"
    assert "resultCode" not in result
