"""Regression guard for the AJV-standalone generated ActivityExecution
validator (examples/n8n/generated/validate_activity_execution.generated.js)
and its generator (examples/n8n/scripts/generate-evidence-validators.mjs).

Scope correction: only ActivityExecution is generated and embedded.
HumanReviewDecision has no generated validator in this repository --
Flow 2 / HumanReviewDecision is out of this implementation's authorized
scope (see test_n8n_p2_1_schema_vendoring.py for the vendored-but-deferred
schema itself).
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
VALIDATOR_PATH = GENERATED_DIR / "validate_activity_execution.generated.js"
HUMAN_REVIEW_VALIDATOR_PATH = GENERATED_DIR / "validate_human_review_decision.generated.js"
PROVENANCE_PATH = GENERATED_DIR / "validator_provenance.json"
GENERATOR_SCRIPT_PATH = N8N_DIR / "scripts" / "generate-evidence-validators.mjs"
SHARED_SUBWORKFLOW_PATH = (
    N8N_DIR / "digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json"
)

NODE_AVAILABLE = shutil.which("node") is not None
NODE_MODULES_AVAILABLE = (N8N_DIR / "node_modules" / "ajv").exists() and (
    N8N_DIR / "node_modules" / "ajv-formats"
).exists()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_generated_validator_exists_with_generated_header():
    assert VALIDATOR_PATH.exists()
    first_line = VALIDATOR_PATH.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("// GENERATED FILE -- do not hand-edit.")


def test_human_review_decision_validator_was_not_generated():
    """The scope correction's explicit boundary: no generated validator for
    HumanReviewDecision exists anywhere in this repository."""
    assert not HUMAN_REVIEW_VALIDATOR_PATH.exists()


def test_provenance_records_activity_execution_generated_and_hrd_deferred():
    provenance = _load_json(PROVENANCE_PATH)
    assert provenance["activity-execution"]["status"] == "GENERATED"
    assert provenance["human-review-decision"]["status"] == "DEFERRED_NOT_GENERATED_FLOW_2_OUT_OF_SCOPE"
    text = json.dumps(provenance).lower()
    assert "generatedat" not in text


def test_provenance_source_sha256_matches_vendored_schema():
    import hashlib

    provenance = _load_json(PROVENANCE_PATH)
    schema_path = N8N_DIR / "vendor" / "p2_1" / "activity-execution.schema.json"
    assert provenance["activity-execution"]["sourceSha256"] == hashlib.sha256(
        schema_path.read_bytes()
    ).hexdigest()


def test_generated_validator_has_no_require_or_module_reference():
    """Must be embeddable verbatim inside a sandboxed n8n Code node with no
    NODE_FUNCTION_ALLOW_EXTERNAL and no ajv/ajv-formats present at runtime."""
    source = VALIDATOR_PATH.read_text(encoding="utf-8")
    assert "require(" not in source
    assert "module." not in source
    assert "import " not in source


def test_generated_validator_source_embedded_verbatim_in_shared_subworkflow():
    validator_source = VALIDATOR_PATH.read_text(encoding="utf-8")
    wf = _load_json(SHARED_SUBWORKFLOW_PATH)
    node = next(n for n in wf["nodes"] if n["name"] == "01.4 Validate against ActivityExecution shape")
    assert validator_source in node["parameters"]["jsCode"], (
        "committed generated validator source does not appear verbatim inside "
        "the shared subworkflow's 01.4 node -- regeneration was not followed by re-embedding"
    )


@pytest.mark.skipif(
    not (NODE_AVAILABLE and NODE_MODULES_AVAILABLE),
    reason="node.js or ajv/ajv-formats devDependencies not available",
)
def test_regenerating_produces_byte_identical_output(tmp_path):
    proc = subprocess.run(
        ["node", str(GENERATOR_SCRIPT_PATH)],
        cwd=str(N8N_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"generator failed:\n{proc.stdout}\n{proc.stderr}"
    # The generator always writes into examples/n8n/generated/ (no
    # output-path override), so re-run it and diff in place -- it is
    # idempotent by construction (test below re-confirms bytes match after
    # this run too).
    regenerated = VALIDATOR_PATH.read_bytes()
    provenance_after = PROVENANCE_PATH.read_bytes()

    proc2 = subprocess.run(
        ["node", str(GENERATOR_SCRIPT_PATH)],
        cwd=str(N8N_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc2.returncode == 0
    assert VALIDATOR_PATH.read_bytes() == regenerated, "regeneration is not deterministic"
    assert PROVENANCE_PATH.read_bytes() == provenance_after


# ---------------------------------------------------------------------------
# Functional / format-enforcement proof, executed directly.
# ---------------------------------------------------------------------------


def _valid_activity_execution() -> dict:
    return {
        "schemaVersion": "1.0.0",
        "executionId": "E1",
        "processInstanceId": "P1",
        "correlationId": "C1",
        "definitionRef": {
            "processId": "digitax.invoice-intake",
            "processVersion": "1.1.1-draft",
            "activityId": "digitax.invoice-intake.phase1.structured-control",
            "activityVersion": "1.0.0",
        },
        "workflowRef": {
            "workflowId": "digitax-invoice-phase1-upload-demo",
            "workflowVersion": "1.0.0",
            "nodeId": "03.1 Run DigiTax controls",
        },
        "startedAt": "2026-08-14T10:00:00.000Z",
        "completedAt": "2026-08-14T10:00:01.000Z",
        "status": "SUCCEEDED",
        "resultCode": "unauffaellig",
        "executor": {
            "type": "DETERMINISTIC_SERVICE",
            "logicalId": "digitax.invoice.phase1-controls",
            "version": "1.1.0",
        },
        "inputRefs": [],
        "outputRefs": [],
        "evidenceRefs": [],
        "controlReportRef": "r1",
        "aiBindingRef": None,
    }


def _run_validator(fixture: dict) -> dict:
    # Written to a temp .js file and run via `node <file>`, not `node -e` --
    # the ~33KB generated validator source exceeds the Windows command-line
    # length limit when passed as a single -e argument.
    source = VALIDATOR_PATH.read_text(encoding="utf-8")
    harness = f"""
{source}
const fixture = {json.dumps(fixture)};
const ok = validateActivityExecution(fixture);
process.stdout.write(JSON.stringify({{ ok, errors: validateActivityExecution.errors || null }}));
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
def test_generated_validator_accepts_a_valid_object():
    result = _run_validator(_valid_activity_execution())
    assert result["ok"] is True, result["errors"]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_generated_validator_rejects_missing_required_field():
    fixture = _valid_activity_execution()
    del fixture["executionId"]
    result = _run_validator(fixture)
    assert result["ok"] is False
    assert any(e["keyword"] == "required" for e in result["errors"])


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_generated_validator_enforces_date_time_format_via_ajv_formats():
    """Direct proof that ajv-formats' registration actually happened: AJV
    core alone treats "format" as a no-op, so this would silently pass
    without it."""
    fixture = _valid_activity_execution()
    fixture["startedAt"] = "not-a-date"
    result = _run_validator(fixture)
    assert result["ok"] is False
    assert any(e["keyword"] == "format" for e in result["errors"])


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_generated_validator_rejects_additional_properties():
    fixture = _valid_activity_execution()
    fixture["unexpectedField"] = "x"
    result = _run_validator(fixture)
    assert result["ok"] is False
    assert any(e["keyword"] == "additionalProperties" for e in result["errors"])


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_generated_validator_enforces_ai_service_conditional_binding():
    fixture = _valid_activity_execution()
    fixture["executor"]["type"] = "AI_SERVICE"
    # aiBindingRef stays null -> must fail the allOf/if/then requirement.
    result = _run_validator(fixture)
    assert result["ok"] is False
