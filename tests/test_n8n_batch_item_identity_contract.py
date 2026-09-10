"""Behavioral regression guard for A6a correction round 1, plan section 3:
the Batch Item workflow's phase1ProfileKey / tcmsOrganizationId / legacy
organizationId identity split, and the RISK_REVIEW_MISSING_TCMS_ORGANIZATION_ID
fail-closed path.

Real execution of "01.2 Build run context" and "04.3 Evaluate risk review
gate" via Node.js (the same subprocess-harness technique already used by
test_n8n_activity_execution_assembly.py and
test_n8n_activity_binding_manifest.py), not string-presence assertions.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
N8N_DIR = REPO_ROOT / "examples" / "n8n"
BATCH_ITEM_PATH = N8N_DIR / "digitax_invoice_phase1_flow1a_batch_item_v1_1_0.json"

NODE_AVAILABLE = shutil.which("node") is not None

RUN_CONTEXT_NODE = "01.2 Build run context"
RISK_REVIEW_GATE_NODE = "04.3 Evaluate risk review gate"


def _load_workflow() -> dict:
    return json.loads(BATCH_ITEM_PATH.read_text(encoding="utf-8"))


def _node_code(name: str) -> str:
    wf = _load_workflow()
    node = next(n for n in wf["nodes"] if n["name"] == name)
    return node["parameters"]["jsCode"]


def _run_run_context(body: dict) -> dict:
    code = _node_code(RUN_CONTEXT_NODE)
    harness = f"""
const $input = {{ first: () => ({{ json: {{ body: {json.dumps(body)} }}, binary: undefined }}) }};
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
    proc = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, f"node execution failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _run_risk_review_gate(merged: dict, ctx: dict) -> dict:
    code = _node_code(RISK_REVIEW_GATE_NODE)
    harness = f"""
const $input = {{ first: () => ({{ json: {json.dumps(merged)} }}) }};
const __nodeData = {{ "{RUN_CONTEXT_NODE}": {json.dumps(ctx)} }};
function $(name) {{ return {{ item: {{ json: __nodeData[name] }} }}; }}
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
    proc = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, f"node execution failed: {proc.stderr}"
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# "01.2 Build run context": phase1ProfileKey / tcmsOrganizationId resolution.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_run_context_resolves_phase1_profile_key_from_new_field():
    out = _run_run_context({"phase1ProfileKey": "unternehmen-x-demo", "tcmsOrganizationId": "tcms-org-1"})
    assert out["ok"] is True, out
    assert out["result"]["phase1ProfileKey"] == "unternehmen-x-demo"
    assert out["result"]["tcmsOrganizationId"] == "tcms-org-1"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_run_context_falls_back_to_legacy_organization_id_for_profile_key_only():
    """Legacy organizationId is a compatibility alias for phase1ProfileKey
    only -- it must never populate tcmsOrganizationId."""
    out = _run_run_context({"organizationId": "unternehmen-y-demo"})
    assert out["ok"] is True, out
    assert out["result"]["phase1ProfileKey"] == "unternehmen-y-demo"
    assert out["result"]["tcmsOrganizationId"] is None


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_run_context_prefers_new_field_over_legacy_alias_when_both_present():
    out = _run_run_context({"phase1ProfileKey": "new-key", "organizationId": "old-key"})
    assert out["ok"] is True, out
    assert out["result"]["phase1ProfileKey"] == "new-key"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_run_context_leaves_both_null_when_neither_field_is_sent():
    out = _run_run_context({})
    assert out["ok"] is True, out
    assert out["result"]["phase1ProfileKey"] is None
    assert out["result"]["tcmsOrganizationId"] is None


# ---------------------------------------------------------------------------
# "04.3 Evaluate risk review gate": tcmsOrganizationId fail-closed path.
# ---------------------------------------------------------------------------


def _merged_with_finding(status: str = "klaerung_erforderlich") -> dict:
    return {
        "ok": True,
        "phase1ControlReport": {
            "reportId": "REP-IDENT-1",
            "status": status,
            "controls": [
                {"controlId": "C1", "outcome": "failed", "severity": "blocking", "ruleVersion": "1.0.0"}
            ],
        },
        "activityExecution": {
            "executionId": "RUN-IDENT-1",
            "definitionRef": {
                "processId": "digitax.invoice-intake",
                "processVersion": "1.1.1-draft",
                "activityId": "digitax.invoice-intake.phase1.structured-control",
                "activityVersion": "1.0.0",
            },
        },
    }


def _ctx(process_instance_id="P1", correlation_id="C1", tcms_organization_id=None):
    return {
        "processInstanceId": process_instance_id,
        "correlationId": correlation_id,
        "tcmsOrganizationId": tcms_organization_id,
    }


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_finding_bearing_report_without_tcms_organization_id_fails_closed():
    out = _run_risk_review_gate(_merged_with_finding(), _ctx(tcms_organization_id=None))
    assert out["ok"] is True, out
    result = out["result"]
    assert result["needsRiskReview"] is False
    assert result["routingStatus"] == "RISK_REVIEW_MISSING_TCMS_ORGANIZATION_ID"
    assert result["riskReviewReport"] is None
    assert "riskReviewRequest" not in result


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_finding_bearing_report_with_tcms_organization_id_proceeds_and_uses_it():
    out = _run_risk_review_gate(_merged_with_finding(), _ctx(tcms_organization_id="tcms-org-42"))
    assert out["ok"] is True, out
    result = out["result"]
    assert result["needsRiskReview"] is True
    assert result["riskReviewRequest"]["organizationId"] == "tcms-org-42"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_clean_report_is_unaffected_by_missing_tcms_organization_id():
    out = _run_risk_review_gate(_merged_with_finding(status="unauffaellig"), _ctx(tcms_organization_id=None))
    assert out["ok"] is True, out
    result = out["result"]
    assert result["needsRiskReview"] is False
    assert result["routingStatus"] == "NO_RISK_REVIEW_REQUIRED"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_technical_failure_report_is_unaffected_by_missing_tcms_organization_id():
    merged = {"ok": False}
    out = _run_risk_review_gate(merged, _ctx(tcms_organization_id=None))
    assert out["ok"] is True, out
    result = out["result"]
    assert result["needsRiskReview"] is False
    assert result["routingStatus"] == "TECHNICAL_FAILURE"
