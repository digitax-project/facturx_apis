"""Regression guard for examples/n8n/scripts/sync-embedded-literals.mjs (A6a
correction round 1, plan section 4): the two generated-literal embeds it
maintains (BINDING/WORKFLOW_BINDINGS inside the shared assembler's binding
guard, and the canonical-json-v1 functions inside the Batch Item workflow's
risk-review gate) must never silently drift from their committed sources.

Extends (does not replace) tests/test_n8n_activity_binding_manifest.py's
existing Sync-ActivityBinding.ps1 coverage: that script maintains the
lockfile itself; this one maintains the two *n8n Code node* embeds derived
from that lockfile and from examples/n8n/vendor/canonicalJson.js.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
N8N_DIR = REPO_ROOT / "examples" / "n8n"
SYNC_SCRIPT_PATH = N8N_DIR / "scripts" / "sync-embedded-literals.mjs"
LOCKFILE_PATH = N8N_DIR / "activity_binding.invoice_intake.json"
SHARED_ASSEMBLER_PATH = N8N_DIR / "digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json"
BATCH_ITEM_PATH = N8N_DIR / "digitax_invoice_phase1_flow1a_batch_item_v1_1_0.json"

NODE_AVAILABLE = shutil.which("node") is not None

BINDING_ASSERT_NODE_NAME = "01.1 Assert activity binding published"
RISK_REVIEW_GATE_NODE_NAME = "04.3 Evaluate risk review gate"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_node(workflow: dict, name: str) -> dict:
    return next(n for n in workflow["nodes"] if n["name"] == name)


def _extract_between(source: str, begin_marker: str, end_marker: str) -> str:
    begin_idx = source.index(begin_marker)
    end_idx = source.index(end_marker)
    begin_line_end = source.index("\n", begin_idx) + 1
    return source[begin_line_end:end_idx]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_sync_script_check_passes_on_committed_state():
    """The committed embeds already match a fresh regeneration byte-for-byte
    -- proves the sync script's markers are placed so regeneration is
    idempotent (a real bug this correction round found and fixed: the
    binding block's explanatory comments used to sit *inside* the markers,
    where every regeneration silently deleted them)."""
    proc = subprocess.run(
        ["node", str(SYNC_SCRIPT_PATH), "--check"],
        cwd=str(N8N_DIR),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"sync-embedded-literals.mjs --check failed:\n{proc.stdout}\n{proc.stderr}"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_regenerating_twice_is_byte_identical(tmp_path):
    """Regeneration is a pure function of its committed inputs: running it
    twice from the same starting state produces identical bytes both times
    (mirrors test_n8n_activity_binding_manifest.py's equivalent proof for
    Sync-ActivityBinding.ps1)."""
    work_dir = tmp_path / "n8n"
    work_dir.mkdir()
    (work_dir / "scripts").mkdir()
    (work_dir / "vendor").mkdir()
    (work_dir / "scripts" / "sync-embedded-literals.mjs").write_bytes(SYNC_SCRIPT_PATH.read_bytes())
    (work_dir / "activity_binding.invoice_intake.json").write_bytes(LOCKFILE_PATH.read_bytes())
    (work_dir / "digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json").write_bytes(
        SHARED_ASSEMBLER_PATH.read_bytes()
    )
    (work_dir / "digitax_invoice_phase1_flow1a_batch_item_v1_1_0.json").write_bytes(BATCH_ITEM_PATH.read_bytes())
    (work_dir / "vendor" / "canonicalJson.js").write_bytes((N8N_DIR / "vendor" / "canonicalJson.js").read_bytes())

    outputs = []
    for _ in range(2):
        proc = subprocess.run(
            ["node", str(work_dir / "scripts" / "sync-embedded-literals.mjs")],
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, f"regeneration failed:\n{proc.stdout}\n{proc.stderr}"
        outputs.append(
            (
                (work_dir / "digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json").read_bytes(),
                (work_dir / "digitax_invoice_phase1_flow1a_batch_item_v1_1_0.json").read_bytes(),
            )
        )
    assert outputs[0] == outputs[1], "two regenerations from unchanged inputs produced different output"


def test_embedded_workflow_binding_triples_match_lockfile_structurally():
    """Plan section 4's explicit requirement: a structural test comparing
    every embedded workflow id/version/node triple with the lockfile --
    field-by-field, not merely whole-block byte equality (which the --check
    test above already proves at a coarser grain)."""
    lockfile = _load_json(LOCKFILE_PATH)
    workflow = _load_json(SHARED_ASSEMBLER_PATH)
    node = _find_node(workflow, BINDING_ASSERT_NODE_NAME)
    code = node["parameters"]["jsCode"]

    embedded_block = _extract_between(code, "// GENERATED-BINDING-BEGIN", "// GENERATED-BINDING-END")
    binding_match = embedded_block.split("const WORKFLOW_BINDINGS", 1)
    embedded_binding = json.loads(binding_match[0].split("const BINDING =", 1)[1].rstrip().rstrip(";"))
    embedded_workflow_bindings = json.loads(binding_match[1].split("=", 1)[1].strip().rstrip(";").rstrip())

    assert embedded_binding == {
        "processId": lockfile["processDefinition"]["processId"],
        "processVersion": lockfile["processDefinition"]["processVersion"],
        "activityId": lockfile["activityDefinition"]["activityId"],
        "activityVersion": lockfile["activityDefinition"]["activityVersion"],
        "executorType": lockfile["executor"]["type"],
        "executorLogicalId": lockfile["executor"]["logicalId"],
        "executorVersion": lockfile["executor"]["version"],
    }

    lockfile_triples = {
        b["workflowId"]: {"workflowVersion": b["workflowVersion"], "nodeId": b["nodeId"]}
        for b in lockfile["workflowBindings"]
    }
    assert embedded_workflow_bindings == lockfile_triples

    # And specifically: the Batch Item entry must read 1.1.0, matching this
    # workflow's own real "id"/"name" (the exact class of bug plan section 4
    # closes -- a workflow published at a version this literal disagreed
    # with).
    batch_item = _load_json(BATCH_ITEM_PATH)
    assert embedded_workflow_bindings[batch_item["id"]]["workflowVersion"] == "1.1.0"
    assert f"v{embedded_workflow_bindings[batch_item['id']]['workflowVersion']}" in batch_item["name"]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_canonical_json_embed_matches_vendor_source_verbatim():
    vendor_source = (N8N_DIR / "vendor" / "canonicalJson.js").read_text(encoding="utf-8")
    expected_functions = _extract_between(
        vendor_source, "// CANONICAL-JSON-V1-BEGIN", "// CANONICAL-JSON-V1-END"
    )

    workflow = _load_json(BATCH_ITEM_PATH)
    node = _find_node(workflow, RISK_REVIEW_GATE_NODE_NAME)
    code = node["parameters"]["jsCode"]
    embedded_functions = _extract_between(
        code, "// GENERATED-CANONICAL-JSON-BEGIN", "// GENERATED-CANONICAL-JSON-END"
    )

    assert embedded_functions == expected_functions, (
        "embedded canonical-json-v1 functions in the risk-review gate node do not "
        "match examples/n8n/vendor/canonicalJson.js verbatim -- regeneration was "
        "not followed by re-embedding"
    )
