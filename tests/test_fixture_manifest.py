"""Guards tests/fixtures/MANIFEST.json against drift: every listed static
fixture file must actually exist, and every "verifiedBy" test name must
actually exist as a collected pytest test -- so the manifest can't silently
go stale (a renamed/deleted test claiming to verify a fixture the manifest
promises is tested)."""
import json
import re
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MANIFEST_PATH = FIXTURES_DIR / "MANIFEST.json"


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_is_valid_json_with_required_fields():
    manifest = _load_manifest()
    assert manifest["fixtures"]
    for entry in manifest["fixtures"]:
        for key in ("file", "purpose", "expectedStatus", "explanation", "verifiedBy"):
            assert key in entry, f"fixture entry missing {key!r}: {entry.get('file')}"
        assert entry["verifiedBy"], f"{entry['file']} has no verifiedBy tests"


def test_every_static_fixture_file_exists():
    manifest = _load_manifest()
    for entry in manifest["fixtures"]:
        filename = entry["file"]
        if filename.startswith("("):
            continue  # documented as generated-at-test-time, not a static file
        assert (FIXTURES_DIR / filename).exists(), f"{filename} listed in MANIFEST.json but missing"


def test_every_verifiedby_test_actually_exists():
    manifest = _load_manifest()
    tests_dir = Path(__file__).parent
    source_cache: dict[str, str] = {}

    for entry in manifest["fixtures"]:
        for ref in entry["verifiedBy"]:
            rel_path, test_name = ref.split("::")
            if rel_path not in source_cache:
                source_cache[rel_path] = (tests_dir.parent / rel_path).read_text(encoding="utf-8")
            source = source_cache[rel_path]
            assert re.search(rf"^def {re.escape(test_name)}\(", source, re.MULTILINE), (
                f"{ref} listed in MANIFEST.json but no such test function found in {rel_path}"
            )
