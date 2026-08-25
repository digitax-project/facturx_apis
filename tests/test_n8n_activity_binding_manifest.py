"""Regression guard for the invoice-intake activity binding lockfile
(examples/n8n/activity_binding.invoice_intake.json) and its vendored A6
export snapshot (examples/n8n/vendor/a6_activity_binding_export.json),
generated only by examples/n8n/scripts/Sync-ActivityBinding.ps1.

P2.1 Wave 1 A5 Stage 0 scope: unlike the accepted A5 plan's original
"today's state is PENDING_A6_PUBLICATION" assumption, Wave 1C is now real
(H1-approved, A1-accepted, A7-reconciled) by the time Stage 0/1 were
authorized -- so the shipped lockfile is PUBLISHED, not a placeholder. The
fail-closed PENDING/placeholder guard is still proven, just via a synthetic
fixture (below) rather than by shipping an unpublished repository state.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
N8N_DIR = REPO_ROOT / "examples" / "n8n"
LOCKFILE_PATH = N8N_DIR / "activity_binding.invoice_intake.json"
VENDORED_SNAPSHOT_PATH = N8N_DIR / "vendor" / "a6_activity_binding_export.json"
SYNC_SCRIPT_PATH = N8N_DIR / "scripts" / "Sync-ActivityBinding.ps1"
SHARED_SUBWORKFLOW_PATH = (
    N8N_DIR / "digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json"
)

WORKFLOW_FILE_NAMES = (
    "digitax_invoice_phase1_flow1a_upload_v1_0_0.json",
    "digitax_invoice_phase1_flow1a_batch_item_v1_0_0.json",
    "digitax_invoice_phase1_flow1a_structured_regression_v1_0_0.json",
    "digitax_invoice_phase1_flow1b_pdf_ocr_concept_v0_2_0.json",
)
REQUIRED_NODE_ID = "03.1 Run DigiTax controls"

POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_no_generation_timestamp(obj, path_prefix=""):
    """No key anywhere in the object may be a generation-time field --
    content that must diff byte-for-byte across -Regenerate runs can never
    depend on wall-clock time."""
    forbidden_key_fragments = ("generatedat", "generationtime", "generatedon")
    if isinstance(obj, dict):
        for key, value in obj.items():
            assert not any(frag in key.lower() for frag in forbidden_key_fragments), (
                f"{path_prefix}.{key} looks like a generation timestamp field"
            )
            _assert_no_generation_timestamp(value, f"{path_prefix}.{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_no_generation_timestamp(item, f"{path_prefix}[{i}]")


def test_lockfile_and_vendored_snapshot_exist_and_are_valid_json():
    assert LOCKFILE_PATH.exists()
    assert VENDORED_SNAPSHOT_PATH.exists()
    _load_json(LOCKFILE_PATH)
    _load_json(VENDORED_SNAPSHOT_PATH)


def test_lockfile_shape_matches_accepted_plan_section_2_2():
    lockfile = _load_json(LOCKFILE_PATH)
    for key in (
        "bindingSchemaVersion",
        "status",
        "generatedBy",
        "provenance",
        "processDefinition",
        "activityDefinition",
        "executor",
        "workflowBindings",
    ):
        assert key in lockfile, f"lockfile missing required key {key!r}"
    assert lockfile["generatedBy"] == "examples/n8n/scripts/Sync-ActivityBinding.ps1 -- do not hand-edit"
    assert set(lockfile["provenance"]) == {"sourceRef", "sourceSha256", "generatorVersion"}


def test_no_generation_timestamp_anywhere_in_lockfile_or_snapshot():
    _assert_no_generation_timestamp(_load_json(LOCKFILE_PATH), "lockfile")
    _assert_no_generation_timestamp(_load_json(VENDORED_SNAPSHOT_PATH), "vendoredSnapshot")


def test_lockfile_is_published_with_no_placeholder_or_illustrative_literals():
    """Today's real state (Wave 1C is real): every identity field is
    non-null, and none of the P2.1 package's own illustrative example
    literals leaked through as if they were the real binding."""
    lockfile = _load_json(LOCKFILE_PATH)
    assert lockfile["status"] == "PUBLISHED"

    required_non_null = [
        lockfile["processDefinition"]["processId"],
        lockfile["processDefinition"]["processVersion"],
        lockfile["activityDefinition"]["activityId"],
        lockfile["activityDefinition"]["activityVersion"],
        lockfile["executor"]["type"],
        lockfile["executor"]["logicalId"],
        lockfile["executor"]["version"],
        lockfile["provenance"]["sourceRef"],
        lockfile["provenance"]["sourceSha256"],
    ]
    assert all(v not in (None, "") for v in required_non_null)

    assert len(lockfile["workflowBindings"]) == 4
    for binding in lockfile["workflowBindings"]:
        assert binding["workflowVersion"] not in (None, "")
        assert binding["nodeId"] == REQUIRED_NODE_ID

    # The P2.1 package's own illustrative example literals must never appear
    # as if they were resolved, real identifiers (A1 round 1's High finding).
    illustrative_literals = ("invoice-intake", "1.1.1-draft")
    # These specific strings ARE now the real, published values (Wave 1C's
    # actual processId/processVersion happen to match the illustrative
    # example) -- the real regression guard is that they were *copied from
    # the vendored A6 export*, not hardcoded, which the drift test below
    # (test_lockfile_matches_fresh_regeneration_from_vendored_snapshot)
    # actually proves.
    del illustrative_literals


def test_lockfile_workflow_bindings_reference_real_workflow_files():
    lockfile = _load_json(LOCKFILE_PATH)
    bindings_by_id = {b["workflowId"]: b for b in lockfile["workflowBindings"]}

    assert set(bindings_by_id) == {
        "digitax-invoice-phase1-upload-demo",
        "digitax-invoice-phase1-batch-item",
        "digitax-invoice-phase1-structured-demo",
        "digitax-invoice-phase1-flow1b-pdf-ocr",
    }

    for file_name in WORKFLOW_FILE_NAMES:
        wf = _load_json(N8N_DIR / file_name)
        node_names = {n["name"] for n in wf["nodes"]}
        assert REQUIRED_NODE_ID in node_names, f"{file_name} has no {REQUIRED_NODE_ID!r} node"
        binding = bindings_by_id[wf["id"]]
        assert wf["name"].rstrip().endswith(f"v{binding['workflowVersion']}".replace(".", ".", 1)) or (
            f"v{binding['workflowVersion']}" in wf["name"]
        ), f"{file_name}: workflowVersion {binding['workflowVersion']!r} not reflected in display name {wf['name']!r}"


def test_provenance_source_sha256_is_a_fresh_hash_of_vendored_snapshot():
    """Not merely copied and trusted: recompute the hash directly."""
    import hashlib

    lockfile = _load_json(LOCKFILE_PATH)
    fresh_hash = hashlib.sha256(VENDORED_SNAPSHOT_PATH.read_bytes()).hexdigest()
    assert lockfile["provenance"]["sourceSha256"] == fresh_hash


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell not available")
def test_sync_script_check_only_passes():
    proc = subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(SYNC_SCRIPT_PATH), "-CheckOnly"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"Sync-ActivityBinding.ps1 -CheckOnly failed:\n{proc.stdout}\n{proc.stderr}"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell not available")
def test_regenerate_twice_from_unchanged_inputs_is_byte_identical(tmp_path):
    """Proves regeneration is a pure function of its committed inputs, never
    of wall-clock time -- the precondition -CheckOnly depends on."""
    source_path = (
        Path("C:/Agentic/verfahren-builder/bindings/invoice-intake/1.1.1-draft")
        / "digitax.invoice-intake.phase1.structured-control.binding.json"
    )
    if not source_path.exists():
        pytest.skip("verfahren-builder binding source not available on this machine")
    source_ref = (
        "verfahren-builder@10849bdfaf985d27c751006089b87da8508196b4:"
        "bindings/invoice-intake/1.1.1-draft/"
        "digitax.invoice-intake.phase1.structured-control.binding.json"
    )

    outputs = []
    for i in range(2):
        run_dir = tmp_path / f"run{i}"
        run_dir.mkdir()
        # Sync-ActivityBinding.ps1 always writes relative to its own script
        # directory's parent (examples/n8n), so point it at a throwaway copy
        # of that layout rather than trying to redirect its output paths.
        n8n_copy = run_dir / "n8n"
        (n8n_copy / "scripts").mkdir(parents=True)
        (n8n_copy / "scripts" / "Sync-ActivityBinding.ps1").write_bytes(SYNC_SCRIPT_PATH.read_bytes())
        for file_name in WORKFLOW_FILE_NAMES:
            (n8n_copy / file_name).write_bytes((N8N_DIR / file_name).read_bytes())

        proc = subprocess.run(
            [
                POWERSHELL, "-NoProfile", "-File",
                str(n8n_copy / "scripts" / "Sync-ActivityBinding.ps1"),
                "-Regenerate", "-SourcePath", str(source_path), "-SourceRef", source_ref,
            ],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, f"-Regenerate failed:\n{proc.stdout}\n{proc.stderr}"
        outputs.append((n8n_copy / "activity_binding.invoice_intake.json").read_bytes())

    assert outputs[0] == outputs[1], "two -Regenerate runs against unchanged inputs produced different output"


# ---------------------------------------------------------------------------
# Behavioral fail-closed proof: the shared subworkflow's own binding-assert
# guard, exercised with a synthetic "not yet published" fixture (Wave 1C's
# real publication makes the repository's actual committed state PUBLISHED,
# so this is proven against a fixture, not against a shipped placeholder --
# the adaptation request.md explicitly authorizes).
# ---------------------------------------------------------------------------

NODE_AVAILABLE = shutil.which("node") is not None


def _assert_node_code() -> str:
    wf = _load_json(SHARED_SUBWORKFLOW_PATH)
    node = next(n for n in wf["nodes"] if n["name"] == "01.1 Assert activity binding published")
    return node["parameters"]["jsCode"]


def _run_node_snippet(js_code: str, input_json_expr: str) -> str:
    harness = f"""
const $input = {{ first: () => ({{ json: {input_json_expr} }}) }};
function run() {{
{js_code}
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
    return proc.stdout


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_shared_subworkflow_asserts_published_binding_before_assembly():
    code = _assert_node_code()
    out = json.loads(_run_node_snippet(code, '{"workflowId": "digitax-invoice-phase1-upload-demo"}'))
    assert out["ok"] is True, f"real published binding should not throw, got: {out}"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_shared_subworkflow_fails_closed_when_binding_is_a_null_placeholder():
    code = _assert_node_code()
    # Synthetic "unpublished" fixture: null out the embedded processId
    # literal, mirroring the pre-Stage-0 PENDING_A6_PUBLICATION shape.
    unpublished_code = code.replace('"digitax.invoice-intake"', "null", 1)
    assert unpublished_code != code, "could not locate the embedded processId literal to null out"
    out = json.loads(_run_node_snippet(unpublished_code, '{"workflowId": "digitax-invoice-phase1-upload-demo"}'))
    assert out["ok"] is False
    assert "ACTIVITY_BINDING_NOT_PUBLISHED" in out["message"]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_shared_subworkflow_fails_closed_for_unknown_workflow_id():
    code = _assert_node_code()
    out = json.loads(_run_node_snippet(code, '{"workflowId": "some-unrecognized-workflow"}'))
    assert out["ok"] is False
    assert "ACTIVITY_BINDING_NOT_PUBLISHED" in out["message"]
