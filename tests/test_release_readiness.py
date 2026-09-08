from pathlib import Path

from facturx.api import API_VERSION


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_openapi_exposes_release_version(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert API_VERSION == "1.1.0"
    assert response.json()["info"]["version"] == API_VERSION


def test_openapi_documents_correlation_id_header_and_400_response(client):
    """The generated OpenAPI document must expose the X-Correlation-ID
    header's actual constraints and the intentional 400
    INVALID_CORRELATION_ID response, without the runtime behavior ever
    becoming FastAPI's automatic 422 for an invalid value -- documentation
    completeness must never come from relaxing the route's own explicit
    validation into a framework-level one."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    operation = response.json()["paths"]["/v1/invoices/process"]["post"]

    header_param = next(
        p for p in operation["parameters"] if p["name"] == "X-Correlation-ID"
    )
    assert header_param["schema"]["pattern"] == "^[A-Za-z0-9._:-]{1,200}$"
    assert header_param["schema"]["minLength"] == 1
    assert header_param["schema"]["maxLength"] == 200

    assert "400" in operation["responses"]
    assert "422" in operation["responses"], (
        "422 remains FastAPI's own default validation-error response for "
        "other parameters (e.g. a missing file) and must not be removed"
    )

    # Runtime proof, not just documentation: an invalid header is still
    # rejected with the documented 400, never the automatic 422.
    invalid_response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", b"not a pdf", "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
        headers={"X-Correlation-ID": "has a space"},
    )
    assert invalid_response.status_code == 400
    assert invalid_response.json()["detail"]["error_code"] == "INVALID_CORRELATION_ID"


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
