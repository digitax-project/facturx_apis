import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INVENTORY = REPO_ROOT / "docs/invoice_phase1/schematron_rule_inventory.json"


def test_generated_schematron_inventory_is_current():
    result = subprocess.run(
        [sys.executable, "tools/generate_schematron_rule_inventory.py", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_schematron_inventory_documents_all_assertions():
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    metadata = inventory["metadata"]

    assert metadata["assertionTemplateCount"] == 427
    assert metadata["uniqueTechnicalIdCount"] == 302
    assert metadata["explicitStandardReferenceCount"] == 209
    assert metadata["profileConstraintWithoutReferenceCount"] == 218
    assert metadata["severityCounts"] == {"blocking": 424, "warning": 3}
    assert len(inventory["rules"]) == 427
