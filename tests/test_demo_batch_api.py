from io import BytesIO
from zipfile import ZipFile


def test_demo_endpoints_are_disabled_by_default(client, monkeypatch):
    monkeypatch.delenv("FACTURX_ENABLE_DEMO_ENDPOINTS", raising=False)
    assert client.get("/demo/batch").status_code == 404
    assert client.get("/v1/demo/mock-invoices").status_code == 404


def test_batch_page_catalog_and_real_xlsx_export(client, monkeypatch):
    monkeypatch.setenv("FACTURX_ENABLE_DEMO_ENDPOINTS", "true")
    page = client.get("/demo/batch")
    assert page.status_code == 200
    assert "DigiTax Invoice Control Lab" in page.text
    assert "Export to Excel" in page.text

    catalog = client.get("/v1/demo/mock-invoices")
    assert catalog.status_code == 200
    assert catalog.json()["llmUsed"] is False
    ids = {scenario["id"] for scenario in catalog.json()["scenarios"]}
    assert {"x_shared_unapproved_supplier", "y_unapproved_supplier"} <= ids

    export = client.post(
        "/v1/demo/results.xlsx",
        json={"rows": [{"batch": "X", "filename": "synthetic.pdf", "status": "unauffaellig"}]},
    )
    assert export.status_code == 200
    assert export.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    with ZipFile(BytesIO(export.content)) as workbook:
        assert "xl/worksheets/sheet1.xml" in workbook.namelist()
        assert b"synthetic.pdf" in workbook.read("xl/worksheets/sheet1.xml")


def test_profile_comparison_pair_differs_only_because_y_selects_org_002(
    client, monkeypatch
):
    monkeypatch.setenv("FACTURX_ENABLE_DEMO_ENDPOINTS", "true")
    cases = (
        ("x_shared_unapproved_supplier", "unternehmen-x-demo", "unauffaellig", False),
        ("y_unapproved_supplier", "unternehmen-y-demo", "klaerung_erforderlich", True),
    )
    reports = []
    for scenario_id, organization_id, expected_status, expect_org_002_failure in cases:
        generated = client.get(f"/v1/demo/mock-invoices/{scenario_id}")
        assert generated.status_code == 200
        assert generated.headers["x-digitax-synthetic-generator"] == "deterministic-template-v1"
        processed = client.post(
            "/v1/invoices/process",
            files={"file": (f"{scenario_id}.pdf", generated.content, "application/pdf")},
            data={"organizationId": organization_id},
        )
        assert processed.status_code == 200
        report = processed.json()["phase1ControlReport"]
        assert report["status"] == expected_status
        org_002 = next(
            (control for control in report["controls"] if control["controlId"] == "ORG-002"),
            None,
        )
        assert (org_002 is not None and org_002["outcome"] == "failed") is expect_org_002_failure
        reports.append(processed.json())

    x_invoice = reports[0]["canonicalInvoice"]["invoice"]
    y_invoice = reports[1]["canonicalInvoice"]["invoice"]
    assert x_invoice["supplier"] == y_invoice["supplier"]
    assert x_invoice["lineItems"] == y_invoice["lineItems"]
    assert x_invoice["totals"] == y_invoice["totals"]
