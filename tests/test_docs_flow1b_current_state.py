"""Regression guard for A1 review round 2
(coordination/control-plane/runs/2026-08-25-vnimpex-pilot-integration/A1/
a3-invoice-review-round2.md): active documentation and workflow metadata
must describe Flow 1b's current architecture (extraction in n8n, every
control evaluated by the authoritative Phase-1 API), not the removed
n8n-side ORG-001 mirror. These stale phrases must not silently return.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
ROOT_README = REPO_ROOT / "README.md"
N8N_README = REPO_ROOT / "examples" / "n8n" / "README.md"
FLOW1B_WORKFLOW_PATH = (
    REPO_ROOT
    / "examples"
    / "n8n"
    / "digitax_invoice_phase1_flow1b_pdf_ocr_concept_v0_3_0.json"
)

STALE_ACTIVE_PHRASES = (
    "temporary, n8n-side-only mirror",
    "temporary concept mirror",
    "which control it mirrors",
    "missing-API-contract gap",
)


def _root_readme_text() -> str:
    return ROOT_README.read_text(encoding="utf-8")


def _n8n_readme_text() -> str:
    return N8N_README.read_text(encoding="utf-8")


def test_root_readme_no_longer_calls_flow1b_a_temporary_mirror():
    text = _root_readme_text()
    for phrase in STALE_ACTIVE_PHRASES:
        assert phrase not in text, f"stale active-doc phrase returned in README.md: {phrase!r}"
    assert "n8n performs only OCR/LLM extraction" in text
    assert "POST /v1/invoices/process-extracted" in text


def test_n8n_readme_workflow_family_intro_has_no_mirror_or_gap_language():
    """examples/n8n/README.md's current workflow-family introduction (the
    numbered section-name list and the VERSION INFO sticky-note description)
    must not describe Flow 1b's controls step as a mirror or reference the
    (closed) missing-API-contract gap as a current functional detail."""
    text = _n8n_readme_text()
    intro_match = re.search(
        r"\*\*Every workflow node\*\*.*?(?=\n## )", text, re.DOTALL
    )
    assert intro_match, "could not locate the workflow-family introduction section"
    intro = intro_match.group(0)

    for phrase in STALE_ACTIVE_PHRASES:
        assert phrase not in intro, (
            f"stale active-doc phrase returned in examples/n8n/README.md's "
            f"workflow-family introduction: {phrase!r}"
        )
    assert "every\n   workflow, including Flow 1b, calls" in intro


def test_n8n_readme_verification_inventory_reports_five_workflows():
    text = _n8n_readme_text()
    assert "4 workflows, no duplicates" not in text, (
        "verification inventory is stale: still reports four imported workflows"
    )
    assert "5 workflows" in text
    assert "Assemble ActivityExecution" in text.split("### Verification")[-1].split(
        "## General rule"
    )[0]


def test_flow1b_sticky_note_5_describes_only_ai_profile_resolution():
    """A1 review, Medium: Sticky Note 5 must no longer claim a removed
    organization-profile lookup or the obsolete 01.6 range."""
    data = json.loads(FLOW1B_WORKFLOW_PATH.read_text(encoding="utf-8"))
    sticky_notes = {n["name"]: n for n in data["nodes"] if n["name"] == "Sticky Note 5"}
    assert "Sticky Note 5" in sticky_notes, "Sticky Note 5 must still exist (topology unchanged)"
    content = sticky_notes["Sticky Note 5"]["parameters"]["content"]

    assert "01.6" not in content, "Sticky Note 5 still references the removed 01.6 range"
    assert "Organization" not in content, (
        "Sticky Note 5 still references the removed organization-profile lookup"
    )
    assert "01.9-01.11" in content
    assert "01.9" in content and "01.10" in content and "01.11" in content
    assert "nicht_pruefbar/technical_review" in content


def test_flow1b_sticky_note_5_position_and_topology_unchanged():
    """This is a documentation-only correction: node count, ids, and this
    sticky note's canvas position must not move."""
    data = json.loads(FLOW1B_WORKFLOW_PATH.read_text(encoding="utf-8"))
    node = next(n for n in data["nodes"] if n["name"] == "Sticky Note 5")
    assert node["id"] == "note-1b-05"
    assert node["position"] == [-2300, -280]
    assert node["type"] == "n8n-nodes-base.stickyNote"
