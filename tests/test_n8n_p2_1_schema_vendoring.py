"""Regression guard for the vendored, hash-pinned P2.1 schema snapshots
(examples/n8n/vendor/p2_1/) and their sync script
(examples/n8n/scripts/Sync-P2.1Schemas.ps1).

Scope correction (accepted by H1 for this Stage 0/1 implementation): only
activity-execution.schema.json is actively used (compiled into a validator
by generate-evidence-validators.mjs, embedded in the shared Assemble
ActivityExecution subworkflow). human-review-decision.schema.json is
vendored alongside it so the P2.1 schema pair stays atomically hash-pinned,
but it is deliberately unused -- Flow 2 / HumanReviewDecision is out of this
implementation's authorized scope. schema_provenance.json's "usage" field on
each entry records this explicitly.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
N8N_DIR = REPO_ROOT / "examples" / "n8n"
VENDOR_P2_1_DIR = N8N_DIR / "vendor" / "p2_1"
SCHEMA_PROVENANCE_PATH = VENDOR_P2_1_DIR / "schema_provenance.json"
ACTIVITY_EXECUTION_SCHEMA_PATH = VENDOR_P2_1_DIR / "activity-execution.schema.json"
HUMAN_REVIEW_DECISION_SCHEMA_PATH = VENDOR_P2_1_DIR / "human-review-decision.schema.json"
SYNC_SCRIPT_PATH = N8N_DIR / "scripts" / "Sync-P2.1Schemas.ps1"

RESEARCH_WORKSPACE_SCHEMAS_DIR = (
    REPO_ROOT.parent.parent
    / "arbeitsbericht"
    / "research"
    / "2026-08-12_execution_evidence_profile_p2_1"
    / "schemas"
)

POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_vendored_files_exist_and_are_valid_json():
    assert ACTIVITY_EXECUTION_SCHEMA_PATH.exists()
    assert HUMAN_REVIEW_DECISION_SCHEMA_PATH.exists()
    assert SCHEMA_PROVENANCE_PATH.exists()
    _load_json(ACTIVITY_EXECUTION_SCHEMA_PATH)
    _load_json(HUMAN_REVIEW_DECISION_SCHEMA_PATH)
    _load_json(SCHEMA_PROVENANCE_PATH)


def test_schema_provenance_has_no_generation_timestamp():
    provenance = _load_json(SCHEMA_PROVENANCE_PATH)
    text = json.dumps(provenance).lower()
    assert "generatedat" not in text
    assert "generationtime" not in text


def test_schema_provenance_marks_human_review_decision_as_deferred():
    provenance = _load_json(SCHEMA_PROVENANCE_PATH)
    assert provenance["activity-execution"]["usage"] == "ACTIVE_STAGE1_ACTIVITY_EXECUTION_VALIDATION"
    assert provenance["human-review-decision"]["usage"] == (
        "DEFERRED_VENDORED_FOR_ATOMIC_HASH_PIN_ONLY_NOT_GENERATED_FLOW_2_OUT_OF_SCOPE"
    )


def test_schema_provenance_hashes_match_vendored_files():
    provenance = _load_json(SCHEMA_PROVENANCE_PATH)
    assert provenance["activity-execution"]["sourceSha256"] == hashlib.sha256(
        ACTIVITY_EXECUTION_SCHEMA_PATH.read_bytes()
    ).hexdigest()
    assert provenance["human-review-decision"]["sourceSha256"] == hashlib.sha256(
        HUMAN_REVIEW_DECISION_SCHEMA_PATH.read_bytes()
    ).hexdigest()


@pytest.mark.skipif(
    not RESEARCH_WORKSPACE_SCHEMAS_DIR.exists(),
    reason="research workspace not available on this machine (local/dev-only double-check)",
)
def test_vendored_schemas_match_research_workspace_originals():
    for name, path in (
        ("activity-execution.schema.json", ACTIVITY_EXECUTION_SCHEMA_PATH),
        ("human-review-decision.schema.json", HUMAN_REVIEW_DECISION_SCHEMA_PATH),
    ):
        original = (RESEARCH_WORKSPACE_SCHEMAS_DIR / name).read_bytes()
        assert path.read_bytes() == original, f"{name} vendored copy diverges from the research workspace original"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell not available")
def test_sync_script_check_only_passes():
    proc = subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(SYNC_SCRIPT_PATH), "-CheckOnly"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"Sync-P2.1Schemas.ps1 -CheckOnly failed:\n{proc.stdout}\n{proc.stderr}"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell not available")
def test_sync_script_check_only_is_self_contained_and_ignores_an_inaccessible_research_workspace():
    """A1 round-1 review (High): -CheckOnly previously regenerated from the
    research workspace and failed with "Source schema not found" on any
    checkout that lacks that external, sibling-repository path -- including
    a genuine clean `git clone` of just this repository, which is exactly
    what CI provides. Passing a deliberately nonexistent
    -ResearchWorkspaceSchemasPath proves -CheckOnly no longer reads it at
    all."""
    proc = subprocess.run(
        [
            POWERSHELL, "-NoProfile", "-File", str(SYNC_SCRIPT_PATH), "-CheckOnly",
            "-ResearchWorkspaceSchemasPath", "C:\\this\\path\\does\\not\\exist\\anywhere",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"Sync-P2.1Schemas.ps1 -CheckOnly must succeed even with an inaccessible "
        f"research workspace path:\n{proc.stdout}\n{proc.stderr}"
    )
    assert "Source schema not found" not in proc.stdout
    assert "Source schema not found" not in proc.stderr


@pytest.mark.skipif(
    POWERSHELL is None or not RESEARCH_WORKSPACE_SCHEMAS_DIR.exists(),
    reason="PowerShell or the research workspace not available on this machine (local/dev-only)",
)
def test_sync_script_verify_against_source_passes():
    proc = subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(SYNC_SCRIPT_PATH), "-VerifyAgainstSource"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"Sync-P2.1Schemas.ps1 -VerifyAgainstSource failed:\n{proc.stdout}\n{proc.stderr}"
