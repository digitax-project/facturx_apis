"""Required scenario tests per docs/invoice_phase1/test_matrix.md and
GitHub issue #1's acceptance criteria: FX-01, FX-04, PDF-01, PDF-02, PDF-03,
SYS-02. Every report-producing assertion also checks the shared contract:
schema-valid, catalog/profile identified, source hash matches, and no
booking/approval/payment action anywhere in the response.
"""
import hashlib
import re
from pathlib import Path

import pytest

from facturx.api import app
from facturx.phase1 import pipeline as pipeline_module
from facturx.phase1.api import get_pdf_extraction_adapter
from facturx.phase1.contracts import validate_canonical_invoice, validate_phase1_control_report
from facturx.phase1.normalize.pdf_adapter import (
    FieldState,
    MockPdfExtractionAdapter,
    PdfExtractionResult,
    PdfFieldValue,
)

DISALLOWED_ACTION_KEYWORDS = ("approve", "book", "pay", "reject", "contact_supplier")


def _assert_contract(body: dict, source_bytes: bytes):
    canonical_invoice = body["canonicalInvoice"]
    report = body["phase1ControlReport"]

    validate_canonical_invoice(canonical_invoice)
    validate_phase1_control_report(report)

    assert canonical_invoice["document"]["sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert report["sourceSha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert report["catalogVersion"]
    assert report["controlProfileId"] == "inbound-starter-de-v1"

    dumped = str(body).lower()
    for keyword in DISALLOWED_ACTION_KEYWORDS:
        # Word-boundary match: "approved" (as in "approved organization master
        # data", a legitimate control title) must not trip on "approve".
        assert not re.search(rf"\b{keyword}\b", dumped), (
            f"found disallowed action keyword {keyword!r} in response"
        )


def _seed_pdf_adapter(pdf_bytes: bytes, result: PdfExtractionResult):
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    adapter = MockPdfExtractionAdapter(canned={sha256: result})
    app.dependency_overrides[get_pdf_extraction_adapter] = lambda: adapter


def _f(value, confidence=0.9, state=FieldState.EXTRACTED):
    return PdfFieldValue(value=value, confidence=confidence, state=state)


def _happy_path_fields() -> dict:
    """Fresh dict each call -- PdfFieldValue is mutable and tests mutate copies."""
    return {
        "invoice.invoiceNumber": _f("UX-PDF-001", 0.95),
        "invoice.issueDate": _f("2026-08-05", 0.95),
        "invoice.currency": _f("EUR", 0.95),
        "invoice.supplier.name": _f("Beispiel Lieferant GmbH"),
        "invoice.supplier.address.street": _f("Lieferweg 1"),
        "invoice.supplier.address.postalCode": _f("10115"),
        "invoice.supplier.address.city": _f("Berlin"),
        "invoice.supplier.address.countryCode": _f("DE"),
        "invoice.supplier.vatId": _f("DE111111111"),
        "invoice.buyer.name": _f("Unternehmen X", 0.95),
        "invoice.buyer.address.street": _f("Musterweg 10", 0.95),
        "invoice.buyer.address.postalCode": _f("04109", 0.95),
        "invoice.buyer.address.city": _f("Leipzig", 0.95),
        "invoice.buyer.address.countryCode": _f("DE", 0.95),
        "invoice.supply.description": _f("Synthetic consulting service"),
        "invoice.supply.deliveryDate": _f("2026-08-03"),
        "invoice.totals.lineNet": _f(100.0),
        "invoice.totals.taxBasis": _f(100.0),
        "invoice.totals.taxAmount": _f(19.0),
        "invoice.totals.grossAmount": _f(119.0),
        "invoice.totals.payableAmount": _f(119.0),
        "invoice.totals.chargeTotal": _f(0.0),
        "invoice.totals.allowanceTotal": _f(0.0),
        "invoice.totals.prepaidAmount": _f(0.0),
        "invoice.totals.roundingAmount": _f(0.0),
        "invoice.lineItems[0].description": _f("Synthetic consulting service"),
        "invoice.lineItems[0].quantity": _f(1.0),
        "invoice.lineItems[0].netAmount": _f(100.0),
        "invoice.lineItems[0].vatRate": _f(19.0),
    }


def test_fx01_valid_zugferd_hybrid_pdf_is_unauffaellig(client, valid_hybrid_pdf_bytes):
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", valid_hybrid_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    body = response.json()
    _assert_contract(body, valid_hybrid_pdf_bytes)

    report = body["phase1ControlReport"]
    assert report["status"] == "unauffaellig"
    assert report["routing"] == "standard_review"
    control_ids = {c["controlId"] for c in report["controls"]}
    assert "STR-004" not in control_ids, "Schematron is not implemented and must not appear as run"


def test_fx04_xsd_invalid_xml_is_klaerung_erforderlich(client, invalid_xsd_xml_bytes):
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.xml", invalid_xsd_xml_bytes, "application/xml")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    body = response.json()
    _assert_contract(body, invalid_xsd_xml_bytes)

    report = body["phase1ControlReport"]
    assert report["status"] == "klaerung_erforderlich"
    assert report["routing"] == "prioritized_review"
    str_003 = next(c for c in report["controls"] if c["controlId"] == "STR-003")
    assert str_003["outcome"] == "failed"
    assert str_003["severity"] == "blocking"
    assert "XSD_INVALID" in str_003["reasonCodes"]


def test_pdf01_readable_pdf_all_fields_is_unauffaellig(client, blank_pdf_bytes):
    result = PdfExtractionResult(
        status="completed", overall_confidence=0.9, fields=_happy_path_fields(), line_item_count=1
    )
    _seed_pdf_adapter(blank_pdf_bytes, result)

    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", blank_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    body = response.json()
    _assert_contract(body, blank_pdf_bytes)

    report = body["phase1ControlReport"]
    assert report["status"] == "unauffaellig"
    assert body["canonicalInvoice"]["extraction"]["method"] == "ocr_llm"
    str_003 = next(c for c in report["controls"] if c["controlId"] == "STR-003")
    assert str_003["outcome"] == "not_applicable"


def test_pdf02_missing_invoice_number_is_klaerung_erforderlich(client, blank_pdf_bytes):
    fields = _happy_path_fields()
    # Adapter positively determined the field is absent -- CONFIRMED_MISSING,
    # not a low-confidence or never-attempted read -- so this must be a
    # blocking finding, not not_reliable.
    fields["invoice.invoiceNumber"] = _f(None, 0.95, FieldState.CONFIRMED_MISSING)
    result = PdfExtractionResult(
        status="completed", overall_confidence=0.9, fields=fields, line_item_count=1
    )
    _seed_pdf_adapter(blank_pdf_bytes, result)

    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", blank_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    body = response.json()
    _assert_contract(body, blank_pdf_bytes)

    report = body["phase1ControlReport"]
    assert report["status"] == "klaerung_erforderlich"
    frm_005 = next(c for c in report["controls"] if c["controlId"] == "FRM-005")
    assert frm_005["outcome"] == "failed"
    assert "MISSING_FIELD" in frm_005["reasonCodes"]


def test_pdf03_low_confidence_totals_is_nicht_pruefbar(client, blank_pdf_bytes):
    fields = _happy_path_fields()
    for key in ("invoice.totals.taxAmount", "invoice.totals.taxBasis", "invoice.totals.grossAmount"):
        fields[key] = _f(fields[key].value, 0.4)  # below the 0.7 reliability threshold
    result = PdfExtractionResult(
        status="completed", overall_confidence=0.6, fields=fields, line_item_count=1
    )
    _seed_pdf_adapter(blank_pdf_bytes, result)

    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", blank_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    body = response.json()
    _assert_contract(body, blank_pdf_bytes)

    report = body["phase1ControlReport"]
    assert report["status"] == "nicht_pruefbar"
    assert report["routing"] == "prioritized_review"
    cal_003 = next(c for c in report["controls"] if c["controlId"] == "CAL-003")
    assert cal_003["outcome"] == "not_reliable"
    assert "LOW_CONFIDENCE_EXTRACTION" in cal_003["reasonCodes"]


def test_sys02_unexpected_structured_extraction_failure_is_5xx_not_200(
    client, valid_hybrid_pdf_bytes, monkeypatch
):
    def _boom(*args, **kwargs):
        raise RuntimeError("Factur-X service unavailable")

    monkeypatch.setattr(pipeline_module, "normalize_structured_invoice", _boom)

    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", valid_hybrid_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )

    assert 500 <= response.status_code < 600
    body = response.json()
    assert body["detail"]["error_code"] == "STRUCTURED_EXTRACTION_UNAVAILABLE"


def test_missing_organization_context_is_rejected_not_defaulted(client, blank_pdf_bytes):
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", blank_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "ORGANIZATION_CONTEXT_REQUIRED"


def test_unsupported_content_type_is_415(client):
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.docx", b"not a pdf or xml", "application/octet-stream")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 415


def test_cal003_valid_invoice_without_total_prepaid_amount_is_unauffaellig(client):
    """Regression test: a confidently-absent OPTIONAL amount (BT-113
    TotalPrepaidAmount is not required by EN16931/CII) must default to 0,
    not be treated as a missing required field. Previously this fixture made
    CAL-003 fail outright even though STR-003 (XSD) passed."""
    xml_bytes = (Path(__file__).parent / "fixtures" / "facturx_valid_en16931_no_prepaid.xml").read_bytes()
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.xml", xml_bytes, "application/xml")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    body = response.json()
    _assert_contract(body, xml_bytes)

    report = body["phase1ControlReport"]
    str_003 = next(c for c in report["controls"] if c["controlId"] == "STR-003")
    assert str_003["outcome"] == "passed"
    cal_003 = next(c for c in report["controls"] if c["controlId"] == "CAL-003")
    assert cal_003["outcome"] == "passed"
    assert report["status"] == "unauffaellig"


def test_normalize_endpoint_returns_canonical_invoice_only(client, valid_hybrid_pdf_bytes):
    response = client.post(
        "/v1/invoices/normalize",
        files={"file": ("invoice.pdf", valid_hybrid_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"canonicalInvoice"}
    validate_canonical_invoice(body["canonicalInvoice"])
    assert body["canonicalInvoice"]["invoice"]["invoiceNumber"] == "UX-2026-001"
    assert "phase1ControlReport" not in body


def test_validate_endpoint_structured_valid(client, valid_hybrid_pdf_bytes):
    response = client.post(
        "/v1/invoices/validate",
        files={"file": ("invoice.pdf", valid_hybrid_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["applicable"] is True
    assert body["xsdValid"] is True
    assert body["schematron"] == "not_implemented"


def test_validate_endpoint_structured_invalid(client, invalid_xsd_xml_bytes):
    response = client.post(
        "/v1/invoices/validate",
        files={"file": ("invoice.xml", invalid_xsd_xml_bytes, "application/xml")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["applicable"] is True
    assert body["xsdValid"] is False
    assert body["xsdMessage"]


def test_validate_endpoint_plain_pdf_not_applicable(client, blank_pdf_bytes):
    response = client.post(
        "/v1/invoices/validate",
        files={"file": ("invoice.pdf", blank_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["applicable"] is False
    assert body["reasonCode"] == "NOT_A_STRUCTURED_DOCUMENT"


def test_pdf_field_never_extracted_is_not_reliable_not_missing(client, blank_pdf_bytes):
    """A field the adapter never processed at all (not seeded -> NOT_EXTRACTED,
    confidence 0.0) must route to not_reliable/nicht_pruefbar. It must NOT be
    silently scored as a confident business-fact failure (MISSING_FIELD) --
    that would let incomplete OCR/LLM output masquerade as an invoice defect."""
    fields = _happy_path_fields()
    del fields["invoice.totals.taxAmount"]  # adapter never attempted this field
    result = PdfExtractionResult(
        status="completed", overall_confidence=0.9, fields=fields, line_item_count=1
    )
    _seed_pdf_adapter(blank_pdf_bytes, result)

    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", blank_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    body = response.json()
    _assert_contract(body, blank_pdf_bytes)

    report = body["phase1ControlReport"]
    assert report["status"] == "nicht_pruefbar"
    cal_002 = next(c for c in report["controls"] if c["controlId"] == "CAL-002")
    assert cal_002["outcome"] == "not_reliable"
    assert "MISSING_FIELD" not in cal_002["reasonCodes"]
