"""Required scenario tests per docs/invoice_phase1/test_matrix.md and
GitHub issue #1's acceptance criteria: FX-01, FX-04, PDF-01, PDF-02, PDF-03,
SYS-02. Every report-producing assertion also checks the shared contract:
schema-valid, catalog/profile identified, source hash matches, and no
booking/approval/payment action anywhere in the response.
"""
import hashlib
import re
from datetime import datetime
from pathlib import Path

import pytest

from facturx.api import app
from facturx.phase1 import api as api_module
from facturx.phase1 import pipeline as pipeline_module
from facturx.phase1.api import get_pdf_extraction_adapter
from facturx.phase1.contracts import validate_canonical_invoice, validate_phase1_control_report
from facturx.phase1.controls.executor import not_run_result
from facturx.phase1.controls.profiles import get_control_profile
from facturx.phase1.normalize.pdf_adapter import (
    FieldState,
    MockPdfExtractionAdapter,
    PdfExtractionResult,
    PdfFieldValue,
)
from facturx.phase1.report import build_report

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
    assert report["controlProfileVersion"] == "0.2.0"

    assert report["startedAt"]
    started_at = datetime.fromisoformat(report["startedAt"])
    created_at = datetime.fromisoformat(report["createdAt"])
    assert started_at <= created_at

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
    assert "STR-004" in control_ids
    str_004 = next(c for c in report["controls"] if c["controlId"] == "STR-004")
    assert str_004["outcome"] == "passed"


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
    str_004 = next(c for c in report["controls"] if c["controlId"] == "STR-004")
    assert str_004["outcome"] == "not_applicable"
    assert "BLOCKED_BY_XSD_INVALID" in str_004["reasonCodes"]


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


def test_cal003_nonzero_rounding_amount_reconciles_via_payable_not_gross(client):
    """Regression test: BT-114 (roundingAmount) belongs in the payable-amount
    reconciliation (payable = gross - prepaid + rounding), not the
    gross-amount one (gross = taxBasis + taxAmount). A non-zero rounding
    amount previously got added into the gross-amount check instead,
    producing a spurious AMOUNT_MISMATCH on a perfectly valid invoice."""
    xml_bytes = (
        Path(__file__).parent / "fixtures" / "facturx_valid_en16931_with_rounding.xml"
    ).read_bytes()
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.xml", xml_bytes, "application/xml")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    body = response.json()
    _assert_contract(body, xml_bytes)

    invoice = body["canonicalInvoice"]["invoice"]
    assert invoice["totals"]["roundingAmount"] == 0.01
    assert invoice["totals"]["grossAmount"] == 119.0
    assert invoice["totals"]["payableAmount"] == 119.01

    report = body["phase1ControlReport"]
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
    assert body["xsdVersion"] == "1.09"
    assert body["schematron"]["status"] == "completed"
    assert body["schematron"]["findings"] == []


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


def test_overall_confidence_forces_nicht_pruefbar_even_when_every_field_looks_confident(
    client, blank_pdf_bytes
):
    """Defense in depth: an adapter could in principle report high
    confidence on every individual field while its own overall-confidence
    signal says the extraction as a whole shouldn't be trusted (garbled
    scan, partial read, adapter bug). Per-field checks alone wouldn't catch
    that -- DOC-007 (evaluate_extraction_confidence) must."""
    fields = _happy_path_fields()  # every field individually high-confidence
    result = PdfExtractionResult(
        status="completed", overall_confidence=0.5, fields=fields, line_item_count=1
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
    doc_007 = next(c for c in report["controls"] if c["controlId"] == "DOC-007")
    assert doc_007["outcome"] == "not_reliable"
    assert "LOW_OVERALL_CONFIDENCE" in doc_007["reasonCodes"]
    # and every per-field control genuinely did pass on its own -- proves
    # this is DOC-007 catching something the per-field checks would have missed
    frm_005 = next(c for c in report["controls"] if c["controlId"] == "FRM-005")
    assert frm_005["outcome"] == "passed"


def test_cal002_low_confidence_charge_is_not_reliable_not_a_false_green(client, blank_pdf_bytes):
    """A low-confidence but non-zero chargeTotal must not be silently
    ignored (treated as absent -> 0 -> CAL-002 runs its normal check and
    could pass) nor silently trusted as a real 0. It must route to
    not_reliable, same as any other low-confidence amount."""
    fields = _happy_path_fields()
    fields["invoice.totals.chargeTotal"] = _f(5.0, confidence=0.4)
    result = PdfExtractionResult(
        status="completed", overall_confidence=0.85, fields=fields, line_item_count=1
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
    cal_002 = next(c for c in report["controls"] if c["controlId"] == "CAL-002")
    assert cal_002["outcome"] == "not_reliable"
    assert cal_002["outcome"] not in ("passed", "not_applicable")
    assert "LOW_CONFIDENCE_EXTRACTION" in cal_002["reasonCodes"]
    assert report["status"] == "nicht_pruefbar"


@pytest.mark.parametrize("field_name", ["chargeTotal", "allowanceTotal"])
def test_cal002_reliable_nonzero_charge_or_allowance_cannot_produce_green_report(
    client, blank_pdf_bytes, field_name
):
    """CAL-002's Σ(netAmount×vatRate) formula does not account for
    document-level charges/allowances. A RELIABLY reported (high-confidence)
    non-zero charge or allowance must not be reported as not_applicable
    (which aggregate() treats as compatible with unauffaellig -- a false
    green result for a calculation this implementation genuinely cannot
    perform). It must route to not_reliable/CONTROL_SCOPE_UNSUPPORTED and
    force nicht_pruefbar, end to end through /v1/invoices/process."""
    fields = _happy_path_fields()
    fields[f"invoice.totals.{field_name}"] = _f(10.0, confidence=0.95)
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
    cal_002 = next(c for c in report["controls"] if c["controlId"] == "CAL-002")
    assert cal_002["outcome"] == "not_reliable"
    assert cal_002["outcome"] not in ("passed", "not_applicable")
    assert "CONTROL_SCOPE_UNSUPPORTED" in cal_002["reasonCodes"]
    assert cal_002["message"]
    assert report["status"] == "nicht_pruefbar"
    assert report["status"] != "unauffaellig"


def test_cal_and_org_findings_expose_expected_actual_difference_and_formula(client):
    """Rich-finding requirement: arithmetic mismatches must expose expected
    value, actual value, difference, tolerance, and formula -- reason codes
    alone don't tell a reviewer what was actually wrong."""
    xml_bytes = (
        Path(__file__).parent / "fixtures" / "facturx_valid_en16931.xml"
    ).read_bytes()
    # Mutate the line total so CAL-001 fails with a known, checkable mismatch.
    mutated = xml_bytes.replace(b"<ram:LineTotalAmount>100.00</ram:LineTotalAmount>",
                                 b"<ram:LineTotalAmount>105.00</ram:LineTotalAmount>", 1)
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.xml", mutated, "application/xml")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    report = response.json()["phase1ControlReport"]
    cal_001 = next(c for c in report["controls"] if c["controlId"] == "CAL-001")
    assert cal_001["outcome"] == "failed"
    assert cal_001["message"]
    details = cal_001["details"]
    assert details is not None
    assert details["formula"]
    # The line item's own net amount was mutated to 105.00; the header
    # lineNet total (100.00) was left untouched -- so the sum of line items
    # (105) is what CAL-001 "expects" the header lineNet to equal, and the
    # header's actual reported value (100) is what it found.
    assert details["expected"] == 105.0
    assert details["actual"] == 100.0
    assert details["difference"] == -5.0
    assert details["tolerance"] is not None


def test_org001_mismatch_details_identify_which_fields_differ(client, blank_pdf_bytes):
    fields = _happy_path_fields()
    fields["invoice.buyer.address.city"] = _f("Munich", confidence=0.95)
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
    report = response.json()["phase1ControlReport"]
    org_001 = next(c for c in report["controls"] if c["controlId"] == "ORG-001")
    assert org_001["outcome"] == "failed"
    assert org_001["message"]
    details = org_001["details"]
    assert details is not None
    mismatches = details["mismatches"]
    fields_that_differ = {m["field"] for m in mismatches}
    assert "invoice.buyer.address.city" in fields_that_differ
    city_mismatch = next(m for m in mismatches if m["field"] == "invoice.buyer.address.city")
    assert city_mismatch["actual"] == "Munich"
    assert city_mismatch["expected"] == "Leipzig"
    # unaffected fields must not show up as mismatches
    assert "invoice.buyer.name" not in fields_that_differ


def test_pdf_field_states_are_persisted_in_field_evidence(client, blank_pdf_bytes):
    """The extracted/confirmed_missing/not_extracted distinction must survive
    normalization into fieldEvidence, not just exist internally in
    PdfFieldValue -- reviewers and n8n need to see it in the actual response."""
    fields = _happy_path_fields()
    fields["invoice.invoiceNumber"] = _f(None, confidence=0.95, state=FieldState.CONFIRMED_MISSING)
    del fields["invoice.supply.description"]  # never processed -> NOT_EXTRACTED
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
    evidence = response.json()["canonicalInvoice"]["fieldEvidence"]
    assert evidence["invoice.invoiceNumber"]["state"] == "confirmed_missing"
    assert evidence["invoice.supply.description"]["state"] == "not_extracted"
    assert evidence["invoice.buyer.name"]["state"] == "extracted"


def test_xml_field_evidence_state_is_extracted(client, valid_hybrid_pdf_bytes):
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", valid_hybrid_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    evidence = response.json()["canonicalInvoice"]["fieldEvidence"]
    assert evidence["invoice.invoiceNumber"]["state"] == "extracted"


def test_org001_buyer_country_mismatch_fails(client, blank_pdf_bytes):
    """ORG-001 must compare buyer countryCode too, not just
    name/street/postalCode/city -- a foreign buyer address with an otherwise
    matching name/street/postal/city text is still not the same organization."""
    fields = _happy_path_fields()
    fields["invoice.buyer.address.countryCode"] = _f("FR", confidence=0.95)
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
    org_001 = next(c for c in report["controls"] if c["controlId"] == "ORG-001")
    assert org_001["outcome"] == "failed"
    assert "MASTER_DATA_MISMATCH" in org_001["reasonCodes"]
    assert report["status"] == "klaerung_erforderlich"


def test_factur_x_minimum_profile_is_unsupported_profile_not_unsupported_format(client):
    """Only EN16931 is processable by the starter control profile (reviewed
    Stage 1 decision). A recognized-but-not-yet-processable Factur-X profile
    (MINIMUM here) must get its own UNSUPPORTED_PROFILE reason code --
    distinct from UNSUPPORTED_FORMAT, which is for formats that aren't
    recognized as Factur-X at all (e.g. XRechnung, unknown XML)."""
    xml_bytes = (Path(__file__).parent / "fixtures" / "facturx_minimum_profile.xml").read_bytes()
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.xml", xml_bytes, "application/xml")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    report = response.json()["phase1ControlReport"]
    assert report["status"] == "nicht_pruefbar"
    doc_001 = next(c for c in report["controls"] if c["controlId"] == "DOC-001")
    assert doc_001["outcome"] == "failed"
    assert "UNSUPPORTED_PROFILE" in doc_001["reasonCodes"]
    assert "UNSUPPORTED_FORMAT" not in doc_001["reasonCodes"]


def test_schematron_invalid_xml_is_klaerung_erforderlich_with_retained_rule_ids(
    client, schematron_invalid_xml_bytes
):
    """XSD-valid (SpecifiedTaxRegistration is optional in the XSD) but
    violates EN16931 BR-CO-26/BR-S-02 (no Seller identifier at all). STR-003
    must pass; STR-004 must fail with the real, retained official rule IDs
    -- this is the "which standard rule failed and why" traceability the
    fixture catalog exists to prove."""
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.xml", schematron_invalid_xml_bytes, "application/xml")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    body = response.json()
    _assert_contract(body, schematron_invalid_xml_bytes)

    report = body["phase1ControlReport"]
    assert report["status"] == "klaerung_erforderlich"
    assert report["routing"] == "prioritized_review"
    str_003 = next(c for c in report["controls"] if c["controlId"] == "STR-003")
    assert str_003["outcome"] == "passed"
    str_004 = next(c for c in report["controls"] if c["controlId"] == "STR-004")
    assert str_004["outcome"] == "failed"
    assert str_004["severity"] == "blocking"
    assert "SCHEMATRON_RULE_VIOLATION" in str_004["reasonCodes"]
    assert "FX-SCH-A-000001" in str_004["evidenceRefs"]
    findings = str_004["details"]["schematronFindings"]
    assert any(f["ruleId"] == "FX-SCH-A-000001" and "BR-CO-26" in f["message"] for f in findings)
    assert all(f["location"] for f in findings), "every finding must carry a real XPath locator"


def test_incorrect_payable_amount_is_klaerung_erforderlich_caught_by_control_and_schematron(
    client, incorrect_payable_xml_bytes
):
    """Deliberately wrong DuePayableAmount (grossAmount - prepaidAmount +
    roundingAmount != payableAmount, BR-CO-16). Caught independently by both
    the DigiTax CAL-003 business control (expected/actual/difference/formula)
    and the official EN16931 Schematron rule (STR-004) -- this is the
    "distinguish format validation from DigiTax business controls" case:
    two different mechanisms independently agreeing this invoice is wrong."""
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.xml", incorrect_payable_xml_bytes, "application/xml")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    body = response.json()
    _assert_contract(body, incorrect_payable_xml_bytes)

    report = body["phase1ControlReport"]
    assert report["status"] == "klaerung_erforderlich"
    assert report["routing"] == "prioritized_review"

    cal_003 = next(c for c in report["controls"] if c["controlId"] == "CAL-003")
    assert cal_003["outcome"] == "failed"
    assert cal_003["details"]["expected"] == 119.01
    assert cal_003["details"]["actual"] == 125.0

    str_004 = next(c for c in report["controls"] if c["controlId"] == "STR-004")
    assert str_004["outcome"] == "failed"
    assert "FX-SCH-A-000122" in str_004["evidenceRefs"]
    assert "BR-CO-16" in str_004["details"]["schematronFindings"][0]["message"]


def test_hybrid_pdf_without_accepted_embedded_xml_falls_back_to_plain_pdf(
    client, hybrid_pdf_without_accepted_embedded_xml_bytes
):
    """A PDF with an XML attachment under an unrecognized filename must be
    treated as a plain PDF (mock OCR path), never silently parsed as
    structured data -- document_intake.py deliberately does not extract
    arbitrary embedded attachments by filename heuristic (see its module
    docstring). Confirmed via /inspect (source-type classification) and
    /process (still produces a normal, schema-valid, non-error result via
    the PDF/mock-adapter path, not a crash or a false structured pass)."""
    inspect_response = client.post(
        "/v1/invoices/inspect",
        files={"file": ("invoice.pdf", hybrid_pdf_without_accepted_embedded_xml_bytes, "application/pdf")},
    )
    assert inspect_response.status_code == 200
    inspection = inspect_response.json()
    assert inspection["sourceType"] == "plain_pdf"
    assert inspection["detectedFormat"] == "pdf"
    assert inspection["profile"] is None

    result = PdfExtractionResult(
        status="completed", overall_confidence=0.9, fields=_happy_path_fields(), line_item_count=1
    )
    _seed_pdf_adapter(hybrid_pdf_without_accepted_embedded_xml_bytes, result)
    process_response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", hybrid_pdf_without_accepted_embedded_xml_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert process_response.status_code == 200
    body = process_response.json()
    _assert_contract(body, hybrid_pdf_without_accepted_embedded_xml_bytes)
    assert body["canonicalInvoice"]["extraction"]["method"] == "ocr_llm"
    assert body["canonicalInvoice"]["document"]["sourceType"] == "plain_pdf"
    report = body["phase1ControlReport"]
    assert report["status"] == "unauffaellig"
    assert report["routing"] == "standard_review"
    str_003 = next(c for c in report["controls"] if c["controlId"] == "STR-003")
    assert str_003["outcome"] == "not_applicable"
    assert "NOT_A_STRUCTURED_DOCUMENT" in str_003["reasonCodes"]
    str_004 = next(c for c in report["controls"] if c["controlId"] == "STR-004")
    assert str_004["outcome"] == "not_applicable"
    assert "NOT_A_STRUCTURED_DOCUMENT" in str_004["reasonCodes"]


def test_capabilities_distinguishes_recognized_from_processable_profiles(client):
    response = client.get("/capabilities")
    assert response.status_code == 200
    factur_x = response.json()["structuredFormats"]["factur-x"]
    assert factur_x["processableLevels"] == ["en16931"]
    assert set(factur_x["recognizedLevels"]) == {
        "minimum", "basicwl", "basic", "en16931", "extended",
    }
    assert set(factur_x["processableLevels"]).issubset(set(factur_x["recognizedLevels"]))


# ---------------------------------------------------------------------------
# X-Correlation-ID / startedAt (P2.1 A4 contract, schemaVersion 1.1.0).
# ---------------------------------------------------------------------------

def test_correlation_id_header_echoed_verbatim_on_happy_path(client, valid_hybrid_pdf_bytes):
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", valid_hybrid_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
        headers={"X-Correlation-ID": "CORR-Test-001"},
    )
    assert response.status_code == 200
    body = response.json()
    _assert_contract(body, valid_hybrid_pdf_bytes)
    assert body["phase1ControlReport"]["correlationId"] == "CORR-Test-001"


def test_correlation_id_header_echoed_on_doc001_blocked_path(client):
    """DOC-001-blocked (nicht_pruefbar) path -- correlationId must still be
    present and correct, not only on the happy path."""
    xml_bytes = (Path(__file__).parent / "fixtures" / "facturx_minimum_profile.xml").read_bytes()
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.xml", xml_bytes, "application/xml")},
        data={"organizationId": "unternehmen-x-demo"},
        headers={"X-Correlation-ID": "CORR-Test-002"},
    )
    assert response.status_code == 200
    report = response.json()["phase1ControlReport"]
    assert report["status"] == "nicht_pruefbar"
    assert report["correlationId"] == "CORR-Test-002"


def test_correlation_id_header_echoed_on_extraction_failed_path(client, blank_pdf_bytes):
    """Extraction-failed path (PDF adapter itself reports status="failed")
    -- correlationId must still be present and correct."""
    result = PdfExtractionResult(status="failed", overall_confidence=0.0, fields={}, line_item_count=0)
    _seed_pdf_adapter(blank_pdf_bytes, result)

    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", blank_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
        headers={"X-Correlation-ID": "CORR-Test-003"},
    )
    assert response.status_code == 200
    report = response.json()["phase1ControlReport"]
    assert report["status"] == "nicht_pruefbar"
    assert report["correlationId"] == "CORR-Test-003"


def test_correlation_id_omitted_is_key_absent_not_null(client, valid_hybrid_pdf_bytes):
    """Byte-identical-for-existing-callers per field: correlationId itself
    is absent from the report, not present-and-null, when the caller never
    sends X-Correlation-ID."""
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", valid_hybrid_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    report = response.json()["phase1ControlReport"]
    assert "correlationId" not in report


def test_invalid_correlation_id_is_rejected_before_any_processing(client, valid_hybrid_pdf_bytes):
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", valid_hybrid_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
        headers={"X-Correlation-ID": "has a space"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error_code"] == "INVALID_CORRELATION_ID"
    assert "canonicalInvoice" not in body
    assert "phase1ControlReport" not in body


def test_invalid_correlation_id_never_reads_the_upload(client, valid_hybrid_pdf_bytes, monkeypatch):
    """The spy: an invalid X-Correlation-ID header must be rejected inside
    the route's try block before _read_upload_bounded() ever runs, since
    that call now happens after header validation, not before it."""
    async def _fail_if_called(*args, **kwargs):
        raise AssertionError("_read_upload_bounded must not be called for an invalid header")

    monkeypatch.setattr(api_module, "_read_upload_bounded", _fail_if_called)

    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", valid_hybrid_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
        headers={"X-Correlation-ID": "has a space"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "INVALID_CORRELATION_ID"


def test_valid_correlation_id_echoed_in_pre_report_error_body(client, valid_hybrid_pdf_bytes):
    """A valid correlationId survives a later, pre-report rejection
    (ORGANIZATION_CONTEXT_REQUIRED) and is echoed in the error body --
    exactly the failure case where a caller most needs to correlate."""
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", valid_hybrid_pdf_bytes, "application/pdf")},
        headers={"X-Correlation-ID": "CORR-Test-004"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error_code"] == "ORGANIZATION_CONTEXT_REQUIRED"
    assert body["detail"]["correlationId"] == "CORR-Test-004"


def test_invalid_correlation_id_takes_precedence_over_invalid_organization_id(
    client, valid_hybrid_pdf_bytes
):
    """Correlation-id validation happens first, before organization-context
    resolution; an invalid value is never echoed back as if trustworthy."""
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", valid_hybrid_pdf_bytes, "application/pdf")},
        headers={"X-Correlation-ID": "has a space"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error_code"] == "INVALID_CORRELATION_ID"
    assert "correlationId" not in body["detail"]


def test_build_report_started_at_and_created_at_are_independently_threaded():
    """Deterministic, non-timing-dependent proof that startedAt and
    createdAt are separately threaded parameters, not aliases of a single
    call: an explicit, clearly-in-the-past started_at value is threaded
    through unchanged while createdAt is computed independently inside
    build_report() itself."""
    control_profile = get_control_profile("inbound-starter-de-v1")
    controls = [not_run_result("DOC-001", "deterministic unit test")]
    fixed_started_at = "2020-01-01T00:00:00+00:00"

    report = build_report(
        "a" * 64,
        control_profile,
        controls,
        "nicht_pruefbar",
        "prioritized_review",
        started_at=fixed_started_at,
    )

    assert report["startedAt"] == fixed_started_at
    assert report["createdAt"] != fixed_started_at
    created_at = datetime.fromisoformat(report["createdAt"])
    assert created_at.year >= 2026
