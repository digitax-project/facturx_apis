"""Regression guard for examples/n8n/vendor/canonicalJson.js (A6a correction
round 1, plan section 2): a byte-for-byte port of the accepted A5b TCMS
implementation (server/utils/canonicalJson.ts), embedded into the Batch Item
workflow's "04.3 Evaluate risk review gate" node by
examples/n8n/scripts/sync-embedded-literals.mjs.

Tests required by the plan:
- fixed primitive/object/array vectors;
- recursive key-permutation equality;
- generated-source drift check (delegates to the sync script's own --check);
- a corrected local fixture whose JavaScript hash is independently compared
  with A5b's canonical implementation (skipped if the accepted A5b worktree
  or its `tsx` devDependency is not available on this machine -- this test
  never edits or depends on modifying that worktree, only reads it).
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
N8N_DIR = REPO_ROOT / "examples" / "n8n"
VENDOR_PATH = N8N_DIR / "vendor" / "canonicalJson.js"
SYNC_SCRIPT_PATH = N8N_DIR / "scripts" / "sync-embedded-literals.mjs"

NODE_AVAILABLE = shutil.which("node") is not None

# Accepted A5b worktree this vendor file is ported from (read-only; never
# written to by this test or any tooling it invokes). This lives in the
# separate ResearchAssistant coordination workspace, not under this repo's
# own working directory -- the path is fixed by that workspace's own layout,
# not derivable from REPO_ROOT.
A5B_WORKTREE = Path(
    r"C:\Users\Tyto\Desktop\diss\ResearchAssistant\work\repos\tcms-framework"
    r"\.claude\worktrees\a2-tcms-baseline-correction"
)
A5B_CANONICAL_TS = A5B_WORKTREE / "server" / "utils" / "canonicalJson.ts"
A5B_AVAILABLE = A5B_CANONICAL_TS.exists() and (A5B_WORKTREE / "node_modules" / "tsx").exists()


def _run_node(js_snippet: str) -> dict:
    harness = f"""
const {{ canonicalJsonStringify, canonicalPayloadSha256, CANONICAL_JSON_VERSION }} = require({json.dumps(str(VENDOR_PATH))});
{js_snippet}
"""
    proc = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, f"node execution failed: {proc.stderr}"
    return json.loads(proc.stdout)


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_vendor_file_exists_with_expected_markers():
    source = VENDOR_PATH.read_text(encoding="utf-8")
    assert "// CANONICAL-JSON-V1-BEGIN" in source
    assert "// CANONICAL-JSON-V1-END" in source
    assert 'CANONICAL_JSON_VERSION = "canonical-json-v1"' in source


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_fixed_primitive_vectors():
    result = _run_node(
        """
process.stdout.write(JSON.stringify({
  nullValue: canonicalJsonStringify(null),
  undefinedValue: canonicalJsonStringify(undefined),
  trueValue: canonicalJsonStringify(true),
  falseValue: canonicalJsonStringify(false),
  stringValue: canonicalJsonStringify("hello \\"world\\""),
  intValue: canonicalJsonStringify(42),
  floatValue: canonicalJsonStringify(3.5),
  negativeValue: canonicalJsonStringify(-7),
  zeroValue: canonicalJsonStringify(0),
  emptyArray: canonicalJsonStringify([]),
  emptyObject: canonicalJsonStringify({}),
  simpleArray: canonicalJsonStringify([1, "a", true, null]),
}));
"""
    )
    assert result["nullValue"] == "null"
    assert result["undefinedValue"] == "null"
    assert result["trueValue"] == "true"
    assert result["falseValue"] == "false"
    assert result["stringValue"] == '"hello \\"world\\""'
    assert result["intValue"] == "42"
    assert result["floatValue"] == "3.5"
    assert result["negativeValue"] == "-7"
    assert result["zeroValue"] == "0"
    assert result["emptyArray"] == "[]"
    assert result["emptyObject"] == "{}"
    assert result["simpleArray"] == '[1,"a",true,null]'


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_fixed_object_vector_sorts_keys_and_drops_undefined():
    result = _run_node(
        """
process.stdout.write(JSON.stringify({
  out: canonicalJsonStringify({ b: 2, a: 1, c: undefined, d: { z: 9, y: 8 } }),
}));
"""
    )
    assert result["out"] == '{"a":1,"b":2,"d":{"y":8,"z":9}}'


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_non_finite_number_throws():
    result = _run_node(
        """
try {
  canonicalJsonStringify(Infinity);
  process.stdout.write(JSON.stringify({ threw: false }));
} catch (e) {
  process.stdout.write(JSON.stringify({ threw: true, message: e.message }));
}
"""
    )
    assert result["threw"] is True
    assert "non-finite" in result["message"]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_recursive_key_permutation_equality():
    """Deeply nested objects with the same content but different key
    insertion order at every level must serialize identically -- and
    therefore hash identically."""
    result = _run_node(
        """
const objA = {
  reportId: "REP-1",
  controls: [
    { controlId: "C1", severity: "blocking", outcome: "failed" },
    { controlId: "C2", severity: "info", outcome: "passed" },
  ],
  meta: { createdAt: "2026-08-14T10:00:00Z", version: "1.0.0" },
};
const objB = {
  meta: { version: "1.0.0", createdAt: "2026-08-14T10:00:00Z" },
  controls: [
    { severity: "blocking", controlId: "C1", outcome: "failed" },
    { outcome: "passed", controlId: "C2", severity: "info" },
  ],
  reportId: "REP-1",
};
process.stdout.write(JSON.stringify({
  strA: canonicalJsonStringify(objA),
  strB: canonicalJsonStringify(objB),
  hashA: canonicalPayloadSha256(objA),
  hashB: canonicalPayloadSha256(objB),
}));
"""
    )
    assert result["strA"] == result["strB"]
    assert result["hashA"] == result["hashB"]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_key_permutation_does_not_reorder_array_elements():
    """Array item ORDER is preserved (only object keys are sorted) --
    reordering array elements themselves must change the hash."""
    result = _run_node(
        """
const arr1 = canonicalJsonStringify([{ a: 1 }, { b: 2 }]);
const arr2 = canonicalJsonStringify([{ b: 2 }, { a: 1 }]);
process.stdout.write(JSON.stringify({ arr1, arr2, equal: arr1 === arr2 }));
"""
    )
    assert result["equal"] is False


@pytest.mark.skipif(not NODE_AVAILABLE, reason="node.js not available")
def test_generated_source_drift_check():
    """Delegates to the sync script's own --check mode: the embedded
    canonical-json-v1 block inside the Batch Item workflow's risk-review
    gate node (and the binding block inside the shared assembler) must
    match a fresh regeneration byte-for-byte."""
    proc = subprocess.run(
        ["node", str(SYNC_SCRIPT_PATH), "--check"],
        cwd=str(N8N_DIR),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"sync-embedded-literals.mjs --check failed:\n{proc.stdout}\n{proc.stderr}"
    assert "OK" in proc.stdout


@pytest.mark.skipif(
    not (NODE_AVAILABLE and A5B_AVAILABLE),
    reason="accepted A5b worktree or its tsx devDependency not available on this machine",
)
def test_local_fixture_hash_matches_a5b_canonical_implementation():
    """Independent cross-implementation proof (plan section 2's explicit
    requirement): a fixture's hash computed by the vendored
    examples/n8n/vendor/canonicalJson.js must equal the hash the accepted
    A5b canonicalJson.ts computes for the identical fixture, run directly
    from the accepted A5b worktree via its own `tsx` devDependency -- never
    by re-copying or re-implementing A5b's algorithm a second time, and
    never by adding or modifying any file inside that worktree."""
    fixture = {
        "schemaVersion": "1.0.0",
        "executionId": "RUN-CROSS-1",
        "controlReportRef": "phase1-control-report:REP-CROSS-1",
        "outputRefs": ["phase1-control-report:REP-CROSS-1"],
        "evidenceRefs": ["phase1-control-report:REP-CROSS-1", "inbound-starter-de-v1", "1.0.0"],
        "nested": {"z": 1, "a": [3, 1, 2], "m": {"y": True, "x": False}},
    }

    our_hash = _run_node(
        f"process.stdout.write(JSON.stringify({{ hash: canonicalPayloadSha256({json.dumps(fixture)}) }}));"
    )["hash"]

    # Node's ESM resolver requires a real file:// URL for an absolute Windows
    # path with a drive letter -- a bare "C:/..." specifier is parsed as an
    # (invalid) URL scheme "c:" instead.
    a5b_module_url = "file:///" + str(A5B_CANONICAL_TS).replace("\\", "/")
    a5b_script = f"""
import {{ canonicalPayloadSha256 }} from {json.dumps(a5b_module_url)};
const fixture = {json.dumps(fixture)};
process.stdout.write(JSON.stringify({{ hash: canonicalPayloadSha256(fixture) }}));
"""
    # Written to a temp .mjs file, not passed via tsx's -e flag: an inline
    # -e argument goes through tsx.cmd's own cmd.exe quoting on Windows,
    # which mangles multi-line/quote-heavy script content (the same reason
    # test_n8n_generated_validators.py's _run_validator uses a temp file).
    tsx_bin = A5B_WORKTREE / "node_modules" / ".bin" / "tsx.cmd"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".mjs", delete=False, encoding="utf-8") as f:
        f.write(a5b_script)
        a5b_script_path = f.name
    try:
        proc = subprocess.run(
            [str(tsx_bin), a5b_script_path],
            cwd=str(A5B_WORKTREE),
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        Path(a5b_script_path).unlink(missing_ok=True)
    assert proc.returncode == 0, f"tsx execution against A5b's canonicalJson.ts failed:\n{proc.stdout}\n{proc.stderr}"
    a5b_hash = json.loads(proc.stdout)["hash"]

    assert our_hash == a5b_hash, (
        f"vendor/canonicalJson.js hash {our_hash!r} does not match A5b's own "
        f"canonicalJson.ts hash {a5b_hash!r} for the identical fixture"
    )
