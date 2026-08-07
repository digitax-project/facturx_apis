"""Hardening tests for facturx/phase1/document_intake.py: size limits, a
secure XML parser (no entity expansion, no network/DTD access), and refusing
to extract arbitrary embedded XML attachments by default.
"""
from io import BytesIO

import pytest
from lxml import etree
from pypdf import PdfWriter

from facturx.phase1.document_intake import (
    MAX_EMBEDDED_XML_BYTES,
    MAX_UPLOAD_BYTES,
    inspect_document,
)
from facturx.phase1.errors import UnsupportedInputError

BILLION_LAUGHS_XML = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100">
  &lol3;
</rsm:CrossIndustryInvoice>
"""

XXE_EXTERNAL_ENTITY_XML = b"""<?xml version="1.0"?>
<!DOCTYPE root [
 <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100">
  &xxe;
</rsm:CrossIndustryInvoice>
"""


def _blank_pdf_with_attachment(filename: str, data: bytes) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_attachment(filename, data)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _assert_no_entity_expansion(xml_etree) -> None:
    """resolve_entities=False keeps an entity reference as an inert
    lxml.etree._Entity node instead of raising -- which is the correct
    secure outcome (no expansion, no resource exhaustion), just not an
    exception. The property that actually matters: none of the "lol"
    payload the entity chain would expand to (millions of repeats) ever
    materializes as real text content, and no element .text contains it.
    """
    serialized = etree.tostring(xml_etree)
    assert b"lollollollol" not in serialized
    assert len(serialized) < 10_000, "entity appears to have been expanded"
    for el in xml_etree.iter():
        if isinstance(el.tag, str):  # skips comment/entity/PI pseudo-elements
            assert el.text is None or "lol" * 10 not in (el.text or "")


def test_billion_laughs_entity_expansion_is_not_expanded():
    """Must not hang/OOM: the entity chain must never actually expand into
    real text content, whether or not the parse itself succeeds."""
    inspection = inspect_document(BILLION_LAUGHS_XML, "bomb.xml", "application/xml")
    assert inspection.xml_etree is not None, "expected the document to still parse"
    _assert_no_entity_expansion(inspection.xml_etree)


def test_external_entity_xxe_is_not_resolved():
    inspection = inspect_document(XXE_EXTERNAL_ENTITY_XML, "xxe.xml", "application/xml")
    assert inspection.xml_etree is not None, "expected the document to still parse"
    serialized = etree.tostring(inspection.xml_etree)
    assert b"root:" not in serialized  # a line from a real /etc/passwd, if it leaked
    for el in inspection.xml_etree.iter():
        if isinstance(el.tag, str):
            assert el.text is None or "/bin/" not in (el.text or "")


def test_billion_laughs_inside_pdf_attachment_is_not_expanded():
    """Same entity bomb, but delivered as the well-known embedded filename
    inside a PDF -- the hardened parser must behave the same way during
    _detect_structured_format, not just for bare-XML uploads."""
    pdf_bytes = _blank_pdf_with_attachment("factur-x.xml", BILLION_LAUGHS_XML)
    inspection = inspect_document(pdf_bytes, "invoice.pdf", "application/pdf")
    assert inspection.source_type == "hybrid_pdf"
    assert inspection.xml_etree is not None
    _assert_no_entity_expansion(inspection.xml_etree)


def test_unrelated_embedded_xml_is_not_extracted_by_default():
    """A PDF with an embedded XML attachment under an arbitrary filename (not
    factur-x.xml/zugferd-invoice.xml/ZUGFeRD-invoice.xml/order-x.xml) must be
    treated as a plain PDF, not have its unrelated XML silently parsed and
    treated as the invoice's structured data."""
    pdf_bytes = _blank_pdf_with_attachment(
        "random_data.xml", b'<?xml version="1.0"?><root>unrelated content</root>'
    )
    inspection = inspect_document(pdf_bytes, "invoice.pdf", "application/pdf")
    assert inspection.source_type == "plain_pdf"
    assert inspection.detected_format == "pdf"
    assert inspection.xml_bytes is None


def test_oversized_upload_is_rejected_before_parsing():
    oversized = b"%PDF-1.4\n" + b"0" * (MAX_UPLOAD_BYTES + 1)
    with pytest.raises(UnsupportedInputError) as exc_info:
        inspect_document(oversized, "huge.pdf", "application/pdf")
    assert exc_info.value.error_code == "FILE_TOO_LARGE"
    assert exc_info.value.status_code == 413


def test_oversized_embedded_xml_falls_back_to_plain_pdf():
    """An embedded factur-x.xml attachment larger than the embedded-XML
    limit must not be parsed at all -- falls back to plain_pdf rather than
    handing an oversized payload to the XML parser."""
    huge_xml = (
        b'<?xml version="1.0"?><rsm:CrossIndustryInvoice '
        b'xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100">'
        + b"<!-- padding -->" * (MAX_EMBEDDED_XML_BYTES // 16 + 1000)
        + b"</rsm:CrossIndustryInvoice>"
    )
    assert len(huge_xml) > MAX_EMBEDDED_XML_BYTES
    pdf_bytes = _blank_pdf_with_attachment("factur-x.xml", huge_xml)
    inspection = inspect_document(pdf_bytes, "invoice.pdf", "application/pdf")
    assert inspection.source_type == "plain_pdf"
    assert any("EMBEDDED_XML_TOO_LARGE" in w for w in inspection.warnings)


def test_malformed_xml_is_classified_unknown_not_crashed():
    inspection = inspect_document(b"<not valid xml", "broken.xml", "application/xml")
    assert inspection.detected_format == "unknown"


CII_XRECHNUNG_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>UX-XR-001</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
  </rsm:ExchangedDocument>
</rsm:CrossIndustryInvoice>
"""


def test_cii_xrechnung_is_detected_by_guideline_id_not_misclassified_as_facturx():
    """A CII XRechnung uses the same CrossIndustryInvoice root tag as
    Factur-X -- facturx.get_flavor() alone would call this "factur-x" since
    it only looks at the root tag. The Guideline ID must be checked first."""
    inspection = inspect_document(CII_XRECHNUNG_XML, "xrechnung.xml", "application/xml")
    assert inspection.detected_format == "xrechnung"
    assert inspection.detected_format != "factur-x"


def test_cii_xrechnung_is_routed_to_nicht_pruefbar_as_unsupported(client):
    response = client.post(
        "/v1/invoices/process",
        files={"file": ("xrechnung.xml", CII_XRECHNUNG_XML, "application/xml")},
        data={"organizationId": "unternehmen-x-demo"},
    )
    assert response.status_code == 200
    report = response.json()["phase1ControlReport"]
    assert report["status"] == "nicht_pruefbar"
    doc_001 = next(c for c in report["controls"] if c["controlId"] == "DOC-001")
    assert "UNSUPPORTED_FORMAT" in doc_001["reasonCodes"]
