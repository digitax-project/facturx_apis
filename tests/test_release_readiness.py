from pathlib import Path

from facturx.api import API_VERSION


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_openapi_exposes_release_version(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert API_VERSION == "1.1.0"
    assert response.json()["info"]["version"] == API_VERSION


def test_demo_generator_has_no_machine_specific_output_path():
    source = (REPO_ROOT / "examples/demo/generate_demo_invoices.py").read_text(
        encoding="utf-8"
    )

    assert "C:\\Users\\" not in source
    assert 'DEFAULT_OUTPUT_DIR = REPO_ROOT / ".demo-output"' in source


def test_smoke_evidence_redacts_internal_resume_tokens():
    source = (
        REPO_ROOT / "examples/n8n/scripts/Manage-Phase1UploadDemo.ps1"
    ).read_text(encoding="utf-8")

    assert '"resumeToken"' in source
    assert '"[redacted]"' in source
