"""Regression guard for the developer stack (compose.dev.yml +
examples/n8n/scripts/n8n-init.sh) staying in sync with the actual set of
n8n workflows this repository ships.

A1 round-1 review finding (High): the developer stack still imported only
the original four workflows and did not set NODE_FUNCTION_ALLOW_BUILTIN,
so a Flow 1a run through `docker compose -f compose.dev.yml up --build`
would fail either at secure UUID generation or at the missing shared
Assemble ActivityExecution workflow call. These tests catch that class of
drift without requiring Docker.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
COMPOSE_DEV_PATH = REPO_ROOT / "compose.dev.yml"
N8N_INIT_PATH = REPO_ROOT / "examples" / "n8n" / "scripts" / "n8n-init.sh"
N8N_DIR = REPO_ROOT / "examples" / "n8n"

EXPECTED_WORKFLOW_FILES = (
    "digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json",
    "digitax_invoice_phase1_flow1a_structured_regression_v1_0_0.json",
    "digitax_invoice_phase1_flow1a_upload_v1_0_0.json",
    "digitax_invoice_phase1_flow1a_batch_item_v1_1_0.json",
    "digitax_invoice_phase1_flow1b_pdf_ocr_concept_v0_3_0.json",
)
EXPECTED_ACTIVE_IDS = {
    "digitax-invoice-phase1-upload-demo",
    "digitax-invoice-phase1-batch-item",
    "digitax-invoice-phase1-shared-assemble-activity-execution",
}
EXPECTED_INACTIVE_IDS = {
    "digitax-invoice-phase1-structured-demo",
    "digitax-invoice-phase1-flow1b-pdf-ocr",
}


def _n8n_init_source() -> str:
    return N8N_INIT_PATH.read_text(encoding="utf-8")


def _parse_shell_var(source: str, name: str) -> set:
    match = re.search(rf'^{name}="([^"]*)"', source, re.MULTILINE)
    assert match, f"could not find {name}=\"...\" in n8n-init.sh"
    return set(match.group(1).split())


def test_n8n_init_workflow_ids_match_every_shipped_workflow_file():
    """Every workflow file this repository actually ships (its own id, read
    from the file itself) must have an entry in n8n-init.sh's WORKFLOW_IDS
    and a workflow_file_for_id() mapping -- not a hand-maintained, driftable
    duplicate list."""
    source = _n8n_init_source()
    workflow_ids = _parse_shell_var(source, "WORKFLOW_IDS")

    actual_ids = set()
    for file_name in EXPECTED_WORKFLOW_FILES:
        wf = json.loads((N8N_DIR / file_name).read_text(encoding="utf-8"))
        actual_ids.add(wf["id"])
        assert f'{wf["id"]}) echo "{file_name}"' in source, (
            f"n8n-init.sh's workflow_file_for_id() has no mapping for {wf['id']!r} -> {file_name!r}"
        )

    assert workflow_ids == actual_ids, (
        f"n8n-init.sh WORKFLOW_IDS {workflow_ids} does not match the actual "
        f"shipped workflow ids {actual_ids}"
    )
    assert len(workflow_ids) == 5, "expected exactly five workflows in the developer stack"


def test_n8n_init_active_ids_match_expected_policy():
    source = _n8n_init_source()
    active_ids = _parse_shell_var(source, "ACTIVE_IDS")
    assert active_ids == EXPECTED_ACTIVE_IDS, (
        f"n8n-init.sh ACTIVE_IDS {active_ids} does not match the expected "
        f"active-state policy {EXPECTED_ACTIVE_IDS} (shared subworkflow must be "
        "published even though it has no webhook)"
    )


def test_n8n_init_shared_subworkflow_imported_before_its_callers():
    """The shared subworkflow must be importable before Upload/Batch/
    Structured Regression, which reference it by id."""
    source = _n8n_init_source()
    workflow_ids_line = re.search(r'^WORKFLOW_IDS="([^"]*)"', source, re.MULTILINE).group(1)
    ordered_ids = workflow_ids_line.split()
    shared_index = ordered_ids.index("digitax-invoice-phase1-shared-assemble-activity-execution")
    for caller_id in (
        "digitax-invoice-phase1-upload-demo",
        "digitax-invoice-phase1-batch-item",
        "digitax-invoice-phase1-structured-demo",
    ):
        assert shared_index < ordered_ids.index(caller_id)


def test_n8n_init_verification_messages_say_five():
    source = _n8n_init_source()
    assert "expect exactly 5" in source
    assert "5 workflows imported" in source


def test_compose_dev_yml_sets_crypto_builtin_allowlist_on_runtime_n8n_service():
    """The long-running n8n service (which actually executes Code nodes)
    must allow require("crypto") -- the JS Task Runner sandbox exposes no
    bare `crypto` global and denies require() of built-ins by default."""
    text = COMPOSE_DEV_PATH.read_text(encoding="utf-8")

    # Isolate the "n8n:" service block (long-running), not "n8n-init:".
    n8n_service_match = re.search(r"\n  n8n:\n(.*?)(?=\n  \w|\nnetworks:|\Z)", text, re.DOTALL)
    assert n8n_service_match, "could not locate the 'n8n:' service block in compose.dev.yml"
    n8n_service_block = n8n_service_match.group(1)

    assert "NODE_FUNCTION_ALLOW_BUILTIN=crypto" in n8n_service_block, (
        "compose.dev.yml's long-running n8n service must set "
        "NODE_FUNCTION_ALLOW_BUILTIN=crypto or every Flow 1a run will fail "
        "with SECURE_UUID_UNAVAILABLE"
    )


def test_compose_dev_yml_describes_five_workflows_not_four():
    text = COMPOSE_DEV_PATH.read_text(encoding="utf-8")
    assert "four versioned" not in text.lower(), "compose.dev.yml's own description is stale (still says four)"
    assert "five versioned" in text.lower()


def test_compose_files_set_risk_review_base_url_on_runtime_n8n_service():
    """A6a synthetic TCMS demo: Batch Item v1.1.0's gated advisory step reads
    FACTURX_RISK_REVIEW_API_BASE_URL. Both the dev stack and the presentation
    demo stack's long-running n8n service must set it, or every
    finding-bearing case would fail closed with routingStatus
    TECHNICAL_FAILURE."""
    upload_demo_compose = N8N_DIR / "docker-compose.phase1-upload-demo.yml"

    for compose_path, service_pattern in (
        (COMPOSE_DEV_PATH, r"\n  n8n:\n(.*?)(?=\n  \w|\nnetworks:|\Z)"),
        (upload_demo_compose, r"\n  n8n:\n(.*?)(?=\nnetworks:|\Z)"),
    ):
        text = compose_path.read_text(encoding="utf-8")
        match = re.search(service_pattern, text, re.DOTALL)
        assert match, f"could not locate the 'n8n:' service block in {compose_path}"
        assert "FACTURX_RISK_REVIEW_API_BASE_URL" in match.group(1), (
            f"{compose_path} must set FACTURX_RISK_REVIEW_API_BASE_URL on the "
            "runtime n8n service"
        )
