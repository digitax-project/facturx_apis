"""Regression test for examples/demo/generate_demo_invoices.py -- the
2026-08-10 afternoon demo assets (see
coordination/claude-codex/2026-08-10_afternoon-demo-plan.md, workstream A).

Verifies, for each demo scenario, through the real public API (the same
FastAPI app api.py serves, via TestClient):
- the generated hybrid PDF's visible text matches the invoice values (the
  same values normalize_structured_invoice() read from the embedded XML --
  see generate_demo_invoices.build_hybrid_pdf()'s docstring for why this
  can't drift)
- the embedded XML is byte-identical to the accepted source fixture
  (nothing was altered while embedding)
- /v1/invoices/inspect detects hybrid_pdf / factur-x / EN16931
- /v1/invoices/process produces exactly the expected status, routing, and
  (for the incorrect-payable scenario) the exact official Schematron rule
  ID and DigiTax control finding the demo script is about to present live
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "demo"))
import generate_demo_invoices as demo  # noqa: E402


def _scenario(scenario_id: str) -> dict:
    return next(s for s in demo.SCENARIOS if s["id"] == scenario_id)


def test_valid_scenario_visible_text_matches_embedded_xml_and_api_result(client):
    scenario = _scenario("valid")
    pdf_bytes, xml_bytes, invoice = demo.build_hybrid_pdf(scenario)

    assert invoice["invoiceNumber"].encode() in pdf_bytes
    assert b"119,00" in pdf_bytes  # grossAmount and payableAmount, de-DE formatted
    assert xml_bytes == (demo.FIXTURES_DIR / scenario["xmlFixture"]).read_bytes()

    inspect_response = client.post(
        "/v1/invoices/inspect", files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")}
    )
    assert inspect_response.status_code == 200
    inspection = inspect_response.json()
    assert inspection["sourceType"] == "hybrid_pdf"
    assert inspection["detectedFormat"] == "factur-x"
    assert inspection["profile"] == "EN16931"

    process_response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert process_response.status_code == 200
    body = process_response.json()
    canonical_invoice = body["canonicalInvoice"]
    report = body["phase1ControlReport"]

    expected_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    assert canonical_invoice["document"]["sha256"] == expected_sha256
    assert report["sourceSha256"] == expected_sha256
    assert canonical_invoice["extraction"]["method"] == "embedded_xml"
    assert canonical_invoice["extraction"]["overallConfidence"] == 1.0

    assert report["status"] == scenario["expectedStatus"] == "unauffaellig"
    assert report["routing"] == scenario["expectedRouting"] == "standard_review"
    str_003 = next(c for c in report["controls"] if c["controlId"] == "STR-003")
    assert str_003["outcome"] == "passed"
    assert str_003["ruleVersion"] == "1.09"
    str_004 = next(c for c in report["controls"] if c["controlId"] == "STR-004")
    assert str_004["outcome"] == "passed"
    assert str_004["ruleVersion"] == "1.09"


def test_incorrect_payable_scenario_matches_official_and_digitax_findings(client):
    scenario = _scenario("incorrect_payable")
    pdf_bytes, xml_bytes, invoice = demo.build_hybrid_pdf(scenario)

    assert invoice["invoiceNumber"].encode() in pdf_bytes
    assert b"125,00" in pdf_bytes  # the wrong payableAmount, visible on the page
    assert xml_bytes == (demo.FIXTURES_DIR / scenario["xmlFixture"]).read_bytes()

    process_response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert process_response.status_code == 200
    report = process_response.json()["phase1ControlReport"]
    assert report["status"] == scenario["expectedStatus"] == "klaerung_erforderlich"
    assert report["routing"] == scenario["expectedRouting"] == "prioritized_review"

    str_004 = next(c for c in report["controls"] if c["controlId"] == "STR-004")
    assert str_004["outcome"] == "failed"
    assert "FX-SCH-A-000122" in str_004["evidenceRefs"]
    assert "BR-CO-16" in str_004["details"]["schematronFindings"][0]["message"]

    cal_003 = next(c for c in report["controls"] if c["controlId"] == "CAL-003")
    assert cal_003["outcome"] == "failed"
    assert cal_003["details"]["expected"] == 119.01
    assert cal_003["details"]["actual"] == 125.0


def test_generated_pdfs_carry_the_honest_109_label_never_1092():
    for scenario in demo.SCENARIOS:
        pdf_bytes, _xml_bytes, _invoice = demo.build_hybrid_pdf(scenario)
        assert b"Factur-X 1.09 EN16931" in pdf_bytes
        assert b"1.09.2" not in pdf_bytes


def test_hybrid_pdfs_use_only_the_accepted_xml_fixtures():
    """Boundary check: this generator must not hand-author or invent any
    new XML content -- only the already-accepted, already-reviewed fixture
    files in tests/fixtures/."""
    accepted = {"facturx_valid_en16931.xml", "facturx_incorrect_payable.xml"}
    used = {s["xmlFixture"] for s in demo.SCENARIOS}
    assert used <= accepted
    for filename in used:
        path = demo.FIXTURES_DIR / filename
        assert path.exists()
        # sanity: these are the exact files already covered by
        # tests/fixtures/MANIFEST.json, not a local copy that could drift
        manifest_files = {
            e["file"] for e in __import__("json").loads(
                (demo.FIXTURES_DIR / "MANIFEST.json").read_text(encoding="utf-8")
            )["fixtures"]
        }
        assert filename in manifest_files
