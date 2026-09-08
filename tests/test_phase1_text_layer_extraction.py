"""Regression tests for the digitally-born-vs-scanned plain-PDF distinction
(Notion ticket https://app.notion.com/p/3d51cb2742ff81f18004cc82b72d621d,
"facturx_apis: distinguish digitally-born PDFs from scanned/OCR-needed
PDFs"): pipeline.py used to hardcode extraction.method="ocr_llm" for every
plain_pdf, regardless of whether it actually had a usable embedded text
layer. It now routes a digitally-born PDF (real, meaningful text layer)
through the `text_llm` path (facturx/phase1/normalize/text_llm_adapter.py)
and only a genuine scan (no usable text layer) through the unchanged
`ocr_llm` vision/OCR path (facturx/phase1/normalize/pdf_adapter.py).

Covers:
- document_intake.inspect_text_layer() directly, against three real PDFs
  (digitally-born, blank, and image-only/"scanned").
- POST /v1/invoices/process end to end for the digitally-born and scanned
  cases, including proof that the digitally-born path never calls
  pdf_extraction_adapter.extract() at all.
- POST /v1/invoices/normalize for the same distinction.
- POST /v1/invoices/extract-text, the pre-existing endpoint this reuses the
  exact same heuristic/threshold from.
"""
import hashlib

import pytest

from facturx.api import app
from facturx.phase1.api import get_pdf_extraction_adapter, get_text_extraction_adapter
from facturx.phase1.document_intake import MIN_REAL_TEXT_CHARS, inspect_text_layer
from facturx.phase1.normalize.pdf_adapter import (
    FieldState,
    MockPdfExtractionAdapter,
    PdfExtractionResult,
    PdfFieldValue,
)
from facturx.phase1.normalize.text_llm_adapter import MockTextExtractionAdapter

from conftest import DIGITALLY_BORN_PDF_TEXT_LINES


class _ExplodingPdfExtractionAdapter:
    """Fails loudly if the vision/OCR path is ever reached -- used to prove
    the text_llm path for a digitally-born PDF never touches it."""

    def extract(self, pdf_bytes: bytes):
        raise AssertionError(
            "pdf_extraction_adapter.extract() must not be called for a "
            "digitally-born PDF with a usable text layer"
        )


class _ExplodingTextExtractionAdapter:
    """Mirror of the above for the opposite direction: a genuine scan must
    never reach the text-structuring adapter either."""

    def extract(self, text: str):
        raise AssertionError(
            "text_extraction_adapter.extract() must not be called for a "
            "genuinely scanned PDF with no usable text layer"
        )


def _f(value, confidence=0.9, state=FieldState.EXTRACTED):
    return PdfFieldValue(value=value, confidence=confidence, state=state)


def _happy_path_fields() -> dict:
    return {
        "invoice.invoiceNumber": _f("DIGITAL-PDF-001", 0.95),
        "invoice.issueDate": _f("2026-08-20", 0.95),
        "invoice.currency": _f("EUR", 0.95),
        "invoice.supplier.name": _f("Beispiel Lieferant GmbH"),
        "invoice.supplier.address.street": _f("Lieferweg 1"),
        "invoice.supplier.address.postalCode": _f("10115"),
        "invoice.supplier.address.city": _f("Berlin"),
        "invoice.supplier.address.countryCode": _f("DE"),
        "invoice.buyer.name": _f("Unternehmen X"),
        "invoice.buyer.address.street": _f("Musterweg 10"),
        "invoice.buyer.address.postalCode": _f("04109"),
        "invoice.buyer.address.city": _f("Leipzig"),
        "invoice.buyer.address.countryCode": _f("DE"),
        "invoice.supply.description": _f("Synthetic consulting service"),
        "invoice.totals.lineNet": _f(100.0),
        "invoice.totals.taxBasis": _f(100.0),
        "invoice.totals.taxAmount": _f(19.0),
        "invoice.totals.grossAmount": _f(119.0),
        "invoice.totals.payableAmount": _f(119.0),
        "invoice.totals.chargeTotal": _f(0.0),
        "invoice.totals.allowanceTotal": _f(0.0),
        "invoice.totals.prepaidAmount": _f(0.0),
        "invoice.totals.roundingAmount": _f(0.0),
    }


# ---------------------------------------------------------------------------
# document_intake.inspect_text_layer() unit tests
# ---------------------------------------------------------------------------


def test_digitally_born_pdf_has_usable_text_layer(digitally_born_pdf_bytes):
    result = inspect_text_layer(digitally_born_pdf_bytes)
    assert result.has_text is True
    assert result.char_count >= MIN_REAL_TEXT_CHARS
    for expected_line_fragment in ("DIGITAL-PDF-001", "Unternehmen X"):
        assert expected_line_fragment in result.text


def test_scanned_image_only_pdf_has_no_usable_text_layer(scanned_pdf_bytes):
    result = inspect_text_layer(scanned_pdf_bytes)
    assert result.has_text is False
    assert result.text.strip() == ""


def test_blank_pdf_has_no_usable_text_layer(blank_pdf_bytes):
    result = inspect_text_layer(blank_pdf_bytes)
    assert result.has_text is False


def test_unreadable_bytes_degrade_to_no_usable_text_rather_than_raising():
    result = inspect_text_layer(b"not a pdf at all")
    assert result.has_text is False
    assert result.text == ""


# ---------------------------------------------------------------------------
# POST /v1/invoices/process
# ---------------------------------------------------------------------------


def test_process_digitally_born_pdf_uses_text_llm_and_never_calls_ocr_adapter(
    client, digitally_born_pdf_bytes
):
    text_layer = inspect_text_layer(digitally_born_pdf_bytes)
    assert text_layer.has_text is True
    text_key = hashlib.sha256(text_layer.text.encode("utf-8")).hexdigest()

    result = PdfExtractionResult(
        status="completed", overall_confidence=0.93, fields=_happy_path_fields(), line_item_count=0
    )
    app.dependency_overrides[get_text_extraction_adapter] = lambda: MockTextExtractionAdapter(
        canned={text_key: result}
    )
    # Proves the digitally-born path never reaches the vision/OCR adapter.
    app.dependency_overrides[get_pdf_extraction_adapter] = lambda: _ExplodingPdfExtractionAdapter()

    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", digitally_born_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    extraction = body["canonicalInvoice"]["extraction"]
    assert extraction["method"] == "text_llm"
    assert extraction["status"] == "completed"
    assert extraction["overallConfidence"] == 0.93
    assert extraction["adapterVersion"] == "mock-text-adapter-0.1.0"
    assert body["canonicalInvoice"]["document"]["sourceType"] == "plain_pdf"

    field_evidence = body["canonicalInvoice"]["fieldEvidence"]
    assert field_evidence["invoice.invoiceNumber"]["method"] == "llm"
    assert body["canonicalInvoice"]["invoice"]["invoiceNumber"] == "DIGITAL-PDF-001"


def test_process_scanned_pdf_still_uses_ocr_llm_and_never_calls_text_adapter(
    client, scanned_pdf_bytes
):
    text_layer = inspect_text_layer(scanned_pdf_bytes)
    assert text_layer.has_text is False

    result = PdfExtractionResult(
        status="completed", overall_confidence=0.8, fields=_happy_path_fields(), line_item_count=0
    )
    sha256 = hashlib.sha256(scanned_pdf_bytes).hexdigest()
    app.dependency_overrides[get_pdf_extraction_adapter] = lambda: MockPdfExtractionAdapter(
        canned={sha256: result}
    )
    # Proves a genuine scan never reaches the text-structuring adapter.
    app.dependency_overrides[get_text_extraction_adapter] = lambda: _ExplodingTextExtractionAdapter()

    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", scanned_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    extraction = body["canonicalInvoice"]["extraction"]
    assert extraction["method"] == "ocr_llm"
    assert extraction["status"] == "completed"
    assert extraction["adapterVersion"] == "mock-adapter-0.1.0"

    field_evidence = body["canonicalInvoice"]["fieldEvidence"]
    assert field_evidence["invoice.invoiceNumber"]["method"] == "ocr"


def test_process_zugferd_hybrid_pdf_unaffected(client, valid_hybrid_pdf_bytes):
    """The structured (ZUGFeRD/hybrid) path never goes near text-layer
    detection at all -- confirms it is untouched by this change."""
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("invoice.pdf", valid_hybrid_pdf_bytes, "application/pdf")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["canonicalInvoice"]["extraction"]["method"] == "embedded_xml"
    assert body["canonicalInvoice"]["document"]["sourceType"] == "hybrid_pdf"


# ---------------------------------------------------------------------------
# POST /v1/invoices/normalize
# ---------------------------------------------------------------------------


def test_normalize_digitally_born_pdf_uses_text_llm(client, digitally_born_pdf_bytes):
    text_layer = inspect_text_layer(digitally_born_pdf_bytes)
    text_key = hashlib.sha256(text_layer.text.encode("utf-8")).hexdigest()
    result = PdfExtractionResult(
        status="completed", overall_confidence=0.9, fields=_happy_path_fields(), line_item_count=0
    )
    app.dependency_overrides[get_text_extraction_adapter] = lambda: MockTextExtractionAdapter(
        canned={text_key: result}
    )
    app.dependency_overrides[get_pdf_extraction_adapter] = lambda: _ExplodingPdfExtractionAdapter()

    response = client.post(
        "/v1/invoices/normalize",
        files={"file": ("invoice.pdf", digitally_born_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["canonicalInvoice"]["extraction"]["method"] == "text_llm"


def test_normalize_scanned_pdf_uses_ocr_llm(client, scanned_pdf_bytes):
    result = PdfExtractionResult(
        status="completed", overall_confidence=0.8, fields=_happy_path_fields(), line_item_count=0
    )
    sha256 = hashlib.sha256(scanned_pdf_bytes).hexdigest()
    app.dependency_overrides[get_pdf_extraction_adapter] = lambda: MockPdfExtractionAdapter(
        canned={sha256: result}
    )
    app.dependency_overrides[get_text_extraction_adapter] = lambda: _ExplodingTextExtractionAdapter()

    response = client.post(
        "/v1/invoices/normalize",
        files={"file": ("invoice.pdf", scanned_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["canonicalInvoice"]["extraction"]["method"] == "ocr_llm"


# ---------------------------------------------------------------------------
# POST /v1/invoices/extract-text (pre-existing endpoint, now refactored to
# call the same shared inspect_text_layer() pipeline.py uses)
# ---------------------------------------------------------------------------


def test_extract_text_endpoint_reports_has_text_for_digitally_born_pdf(
    client, digitally_born_pdf_bytes
):
    response = client.post(
        "/v1/invoices/extract-text",
        files={"file": ("invoice.pdf", digitally_born_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hasText"] is True
    assert body["charCount"] >= MIN_REAL_TEXT_CHARS
    assert "DIGITAL-PDF-001" in body["text"]


def test_extract_text_endpoint_reports_no_text_for_scanned_pdf(client, scanned_pdf_bytes):
    response = client.post(
        "/v1/invoices/extract-text",
        files={"file": ("invoice.pdf", scanned_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hasText"] is False
    assert body["text"] == ""


def test_extract_text_endpoint_reports_no_text_for_blank_pdf(client, blank_pdf_bytes):
    response = client.post(
        "/v1/invoices/extract-text",
        files={"file": ("invoice.pdf", blank_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["hasText"] is False


def test_digitally_born_fixture_text_lines_are_actually_present(digitally_born_pdf_bytes):
    """Sanity check on the fixture itself (tests/conftest.py), not on
    product code: proves DIGITALLY_BORN_PDF_TEXT_LINES is really what got
    rendered into the PDF's text layer, so the tests above aren't
    accidentally passing against an empty/mismatched fixture."""
    text = inspect_text_layer(digitally_born_pdf_bytes).text
    for line in DIGITALLY_BORN_PDF_TEXT_LINES:
        assert line in text
