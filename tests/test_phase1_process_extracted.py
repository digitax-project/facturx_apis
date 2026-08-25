"""Tests for POST /v1/invoices/process-extracted -- the external-extraction
seam Flow 1b's n8n OCR/LLM extraction submits pre-extracted canonical
invoice fields plus field evidence to, instead of Flow 1b mirroring ORG-001
(and every other control) in n8n-side JavaScript (A1 review, High: "Flow 1b
does not use the canonical Phase-1 control API"). Every scenario here proves
the same control catalog/executor as /v1/invoices/process is used, and that
the caller cannot inject a fabricated status/routing/controls result.
"""
import hashlib

import pytest

from facturx.phase1.contracts import validate_canonical_invoice, validate_phase1_control_report

VALID_INVOICE = {
    "invoiceNumber": "UX-OCR-001",
    "issueDate": "2026-08-05",
    "typeCode": None,
    "currency": "EUR",
    "supplier": {
        "name": "Beispiel Lieferant GmbH",
        "address": {"street": "Lieferweg 1", "postalCode": "10115", "city": "Berlin", "countryCode": "DE"},
        "taxId": None,
        "vatId": "DE111111111",
    },
    "buyer": {
        "name": "Unternehmen X",
        "address": {"street": "Musterweg 10", "postalCode": "04109", "city": "Leipzig", "countryCode": "DE"},
        "taxId": None,
        "vatId": None,
    },
    "supply": {
        "description": "Synthetic consulting service",
        "deliveryDate": "2026-08-03",
        "periodStart": None,
        "periodEnd": None,
    },
    "totals": {
        "lineNet": 100.0, "taxBasis": 100.0, "taxAmount": 19.0, "grossAmount": 119.0,
        "payableAmount": 119.0, "chargeTotal": 0.0, "allowanceTotal": 0.0,
        "prepaidAmount": 0.0, "roundingAmount": 0.0,
    },
    "lineItems": [
        {"description": "Synthetic consulting service", "quantity": 1.0, "netAmount": 100.0, "vatRate": 19.0},
    ],
}


def _evidence_for(invoice: dict, confidence: float = 0.85) -> dict:
    """Builds a fieldEvidence entry for every scalar leaf in `invoice`,
    mirroring examples/n8n's "02.7 Normalize invoice" node's shape."""
    field_evidence: dict = {}

    def walk(prefix: str, value):
        if isinstance(value, dict):
            for key, sub in value.items():
                walk(f"{prefix}.{key}" if prefix else key, sub)
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                walk(f"{prefix}[{idx}]", item)
        else:
            field_evidence[prefix] = {
                "method": "llm",
                "confidence": confidence,
                "locator": prefix,
                "rawValue": value if isinstance(value, (str, int, float, bool)) else None,
                "state": "extracted" if value is not None else "not_extracted",
            }

    walk("invoice", invoice)
    return field_evidence


def _request_body(
    *, invoice=None, confidence=0.85, organization_id="unternehmen-x-demo",
    extraction_status="completed", overall_confidence=0.9, sha256_source=b"synthetic pdf bytes",
    **overrides,
):
    invoice = invoice if invoice is not None else VALID_INVOICE
    body = {
        "organizationId": organization_id,
        "document": {
            "filename": "invoice.pdf",
            "mimeType": "application/pdf",
            "sha256": hashlib.sha256(sha256_source).hexdigest(),
        },
        "extraction": {
            "status": extraction_status,
            "overallConfidence": overall_confidence,
            "adapterVersion": "local-vision-0.1.0",
            "warnings": [],
        },
        "invoice": invoice,
        "fieldEvidence": _evidence_for(invoice, confidence),
    }
    body.update(overrides)
    return body


def _assert_contract(body: dict):
    validate_canonical_invoice(body["canonicalInvoice"])
    validate_phase1_control_report(body["phase1ControlReport"])
    assert body["canonicalInvoice"]["document"]["sourceType"] == "plain_pdf"
    assert body["canonicalInvoice"]["extraction"]["method"] == "ocr_llm"


def test_valid_local_ai_extraction_is_unauffaellig(client):
    response = client.post("/v1/invoices/process-extracted", json=_request_body())
    assert response.status_code == 200
    body = response.json()
    _assert_contract(body)
    report = body["phase1ControlReport"]
    assert report["status"] == "unauffaellig"
    assert report["routing"] == "standard_review"
    control_ids = {c["controlId"]: c["outcome"] for c in report["controls"]}
    assert control_ids["DOC-001"] == "passed"
    assert control_ids["STR-003"] == "not_applicable"
    assert control_ids["STR-004"] == "not_applicable"
    assert control_ids["ORG-001"] == "passed"


def test_correlation_id_echoed_verbatim(client):
    response = client.post(
        "/v1/invoices/process-extracted",
        json=_request_body(),
        headers={"X-Correlation-ID": "flow1b-corr-001"},
    )
    assert response.status_code == 200
    assert response.json()["phase1ControlReport"]["correlationId"] == "flow1b-corr-001"


def test_failed_extraction_is_nicht_pruefbar_prioritized_review(client):
    response = client.post(
        "/v1/invoices/process-extracted",
        json=_request_body(extraction_status="failed", overall_confidence=0.0),
    )
    assert response.status_code == 200
    report = response.json()["phase1ControlReport"]
    assert report["status"] == "nicht_pruefbar"
    assert report["routing"] == "prioritized_review"
    control_ids = {c["controlId"]: c["outcome"] for c in report["controls"]}
    assert control_ids["DOC-001"] == "passed"
    assert control_ids["STR-003"] == "not_applicable"
    # Everything else was blocked because extraction failed -- never silently
    # evaluated against empty/garbage fields.
    assert control_ids["ORG-001"] == "not_run"
    assert control_ids["FRM-001"] == "not_run"


def test_low_overall_confidence_is_nicht_pruefbar_not_a_false_pass(client):
    response = client.post(
        "/v1/invoices/process-extracted",
        json=_request_body(overall_confidence=0.4),
    )
    assert response.status_code == 200
    report = response.json()["phase1ControlReport"]
    assert report["status"] == "nicht_pruefbar"
    doc007 = next(c for c in report["controls"] if c["controlId"] == "DOC-007")
    assert doc007["outcome"] == "not_reliable"


def test_buyer_master_data_mismatch_is_klaerung_erforderlich(client):
    mismatched = {**VALID_INVOICE, "buyer": {**VALID_INVOICE["buyer"], "name": "Someone Else GmbH"}}
    response = client.post("/v1/invoices/process-extracted", json=_request_body(invoice=mismatched))
    assert response.status_code == 200
    report = response.json()["phase1ControlReport"]
    assert report["status"] == "klaerung_erforderlich"
    assert report["routing"] == "prioritized_review"
    org001 = next(c for c in report["controls"] if c["controlId"] == "ORG-001")
    assert org001["outcome"] == "failed"
    assert "MASTER_DATA_MISMATCH" in org001["reasonCodes"]


def test_low_confidence_field_is_not_reliable_never_auto_passes(client):
    response = client.post("/v1/invoices/process-extracted", json=_request_body(confidence=0.2))
    assert response.status_code == 200
    report = response.json()["phase1ControlReport"]
    assert report["status"] == "nicht_pruefbar"


def test_missing_organization_context_is_400_not_defaulted(client):
    body = _request_body()
    del body["organizationId"]
    response = client.post("/v1/invoices/process-extracted", json=body)
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "ORGANIZATION_CONTEXT_REQUIRED"


def test_demo_mode_selects_fictional_organization(client):
    body = _request_body()
    del body["organizationId"]
    body["demoMode"] = True
    response = client.post("/v1/invoices/process-extracted", json=body)
    assert response.status_code == 200
    assert response.json()["phase1ControlReport"]["controlProfileId"] == "inbound-starter-de-v1"


@pytest.mark.parametrize(
    "mutate,expected_message_fragment",
    [
        (lambda b: b.pop("document"), "document"),
        (lambda b: b["document"].pop("sha256"), "document.sha256"),
        (lambda b: b["document"].__setitem__("sha256", "not-a-hash"), "document.sha256"),
        (lambda b: b["extraction"].__setitem__("status", "bogus"), "extraction.status"),
        (lambda b: b["extraction"].__setitem__("overallConfidence", 1.5), "extraction.overallConfidence"),
        (lambda b: b.pop("invoice"), "invoice"),
        (lambda b: b.pop("fieldEvidence"), "fieldEvidence"),
    ],
)
def test_malformed_request_body_is_422_not_500(client, mutate, expected_message_fragment):
    body = _request_body()
    mutate(body)
    response = client.post("/v1/invoices/process-extracted", json=body)
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] in ("INVALID_REQUEST_BODY", "CANONICAL_INVOICE_INVALID")
    assert expected_message_fragment in response.json()["detail"]["detail"]


def test_caller_supplied_control_results_are_never_trusted():
    """Requirement: "Do not trust caller-supplied control results." Even a
    request that also carries a forged, fully-green status/controls/report
    must still produce the server's own, independently computed result --
    here, deliberately mismatched master data, so a passthrough bug would be
    caught (the forged payload claims unauffaellig; the real evaluation must
    still say klaerung_erforderlich)."""
    from fastapi.testclient import TestClient

    from facturx.api import app

    mismatched = {**VALID_INVOICE, "buyer": {**VALID_INVOICE["buyer"], "name": "Forged Buyer GmbH"}}
    body = _request_body(invoice=mismatched)
    body["status"] = "unauffaellig"
    body["routing"] = "standard_review"
    body["phase1ControlReport"] = {"status": "unauffaellig", "routing": "standard_review", "controls": []}
    body["controls"] = [{"controlId": "ORG-001", "outcome": "passed", "severity": "none"}]

    with TestClient(app) as client:
        response = client.post("/v1/invoices/process-extracted", json=body)
    assert response.status_code == 200
    report = response.json()["phase1ControlReport"]
    assert report["status"] == "klaerung_erforderlich"
    org001 = next(c for c in report["controls"] if c["controlId"] == "ORG-001")
    assert org001["outcome"] == "failed"


def test_source_type_and_extraction_method_are_never_taken_from_caller(client):
    """A caller cannot claim e.g. an embedded-XML/structured source to route
    around STR-003/STR-004 -- sourceType/detectedFormat/extraction.method
    are always hardcoded server-side for this endpoint, regardless of what
    the request body contains (this endpoint accepts no such fields at all,
    but a caller stuffing them into document/extraction must still be
    ignored, not echoed back)."""
    body = _request_body()
    body["document"]["sourceType"] = "xml"
    body["document"]["detectedFormat"] = "factur-x"
    body["extraction"]["method"] = "direct_xml"
    response = client.post("/v1/invoices/process-extracted", json=body)
    assert response.status_code == 200
    canonical_invoice = response.json()["canonicalInvoice"]
    assert canonical_invoice["document"]["sourceType"] == "plain_pdf"
    assert canonical_invoice["document"]["detectedFormat"] == "pdf"
    assert canonical_invoice["extraction"]["method"] == "ocr_llm"
    control_ids = {c["controlId"]: c["outcome"] for c in response.json()["phase1ControlReport"]["controls"]}
    assert control_ids["STR-003"] == "not_applicable"
    assert control_ids["STR-004"] == "not_applicable"
