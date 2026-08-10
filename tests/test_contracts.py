"""Guards against the packaged runtime schema copies
(facturx/phase1/schemas/) drifting from the documentation copies
(docs/invoice_phase1/contracts/), and exercises contracts.py's loader
directly (independent of any pipeline behavior)."""
import json
from pathlib import Path

import pytest

from facturx.phase1 import contracts

REPO_ROOT = Path(__file__).parent.parent
DOCS_CONTRACTS_DIR = REPO_ROOT / "docs" / "invoice_phase1" / "contracts"
PACKAGED_SCHEMAS_DIR = REPO_ROOT / "facturx" / "phase1" / "schemas"

SCHEMA_FILENAMES = [
    contracts.CANONICAL_INVOICE_SCHEMA_FILENAME,
    contracts.PHASE1_CONTROL_REPORT_SCHEMA_FILENAME,
]


@pytest.mark.parametrize("filename", SCHEMA_FILENAMES)
def test_packaged_schema_matches_docs_copy(filename):
    docs_copy = (DOCS_CONTRACTS_DIR / filename).read_text(encoding="utf-8")
    packaged_copy = (PACKAGED_SCHEMAS_DIR / filename).read_text(encoding="utf-8")
    assert json.loads(docs_copy) == json.loads(packaged_copy), (
        f"{filename} in facturx/phase1/schemas/ has drifted from "
        f"docs/invoice_phase1/contracts/ -- keep both in sync"
    )


def test_validate_canonical_invoice_loads_from_package_not_repo_path():
    example = json.loads(
        (REPO_ROOT / "docs" / "invoice_phase1" / "examples" / "canonical_invoice.example.json")
        .read_text(encoding="utf-8")
    )
    contracts.validate_canonical_invoice(example)  # must not raise


def test_validate_phase1_control_report_loads_from_package_not_repo_path():
    example = json.loads(
        (REPO_ROOT / "docs" / "invoice_phase1" / "examples" / "phase1_control_report.example.json")
        .read_text(encoding="utf-8")
    )
    contracts.validate_phase1_control_report(example)  # must not raise
