"""Guards facturx/phase1/resources/facturx-1.09-en16931/ against silent drift.

Every vendored XSD/XSLT/codedb file must exactly match the SHA-256 recorded
in PROVENANCE.json when it was copied from the pinned, PyPI-hash-verified
factur-x==6.6 wheel (see that file for the full source/license chain). If
this test fails, either the vendored file was edited/corrupted (fix: restore
from the pinned wheel) or the manifest is stale (fix: re-verify against the
wheel and update the hash deliberately, not just to make the test pass).
"""
import hashlib
import json
from pathlib import Path

RESOURCE_DIR = (
    Path(__file__).parent.parent
    / "facturx"
    / "phase1"
    / "resources"
    / "facturx-1.09-en16931"
)


def _load_manifest() -> dict:
    return json.loads((RESOURCE_DIR / "PROVENANCE.json").read_text(encoding="utf-8"))


def test_provenance_manifest_is_valid_json_with_expected_shape():
    manifest = _load_manifest()
    assert manifest["wheelSource"]["sha256"]
    assert manifest["files"]
    for entry in manifest["files"]:
        assert entry["filename"]
        assert entry["sha256"]


def test_every_manifest_file_exists_and_hash_matches():
    manifest = _load_manifest()
    for entry in manifest["files"]:
        path = RESOURCE_DIR / entry["filename"]
        assert path.exists(), f"{entry['filename']} listed in PROVENANCE.json but missing on disk"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == entry["sha256"], (
            f"{entry['filename']} SHA-256 drifted from PROVENANCE.json "
            f"(expected {entry['sha256']}, got {actual})"
        )


def test_no_extra_undocumented_files_in_resource_directory():
    manifest = _load_manifest()
    documented = {entry["filename"] for entry in manifest["files"]}
    # PROVENANCE.json itself and .gitattributes (forces these hash-pinned
    # vendored files to be stored as binary -- see its own comment for why)
    # are repo-control files, not vendored/hash-tracked artifacts.
    documented.add("PROVENANCE.json")
    documented.add(".gitattributes")
    on_disk = {p.name for p in RESOURCE_DIR.iterdir() if p.is_file()}
    assert on_disk == documented, (
        f"undocumented files in {RESOURCE_DIR}: {on_disk - documented}"
    )


def test_artifact_version_is_labelled_109_not_1092():
    """Regression guard for the exact mistake the reviewed decision warned
    against: never claim ZUGFeRD 2.5.2 / Factur-X 1.09.2 support for
    artifacts that are actually Factur-X 1.09."""
    manifest = _load_manifest()
    xsl_path = RESOURCE_DIR / "Factur-X_1.09_EN16931.xsl"
    content = xsl_path.read_text(encoding="utf-8")
    assert 'title="Schema for Factur-X; 1.09; EN16931-COMPLIANT (FULLY)"' in content
    assert "1.09.2" not in content
    assert "1.09.2" not in json.dumps(manifest["artifactLabel"])
