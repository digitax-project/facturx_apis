from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from facturx.api import app
from facturx.facturx import generate_from_binary
from facturx.phase1.api import get_pdf_extraction_adapter, get_text_extraction_adapter

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture_bytes(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


def make_blank_pdf_bytes(encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    if encrypted:
        writer.encrypt("wrong-password")
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


# A real, meaningful invoice-shaped text layer -- real drawString text
# objects, not an image -- for the "digitally-born plain PDF" test case
# (facturx/phase1/document_intake.py's inspect_text_layer() must find a
# usable text layer here, routing pipeline.py to the `text_llm` path).
# "Unternehmen X" is this project's standard non-real placeholder buyer
# name, matching every other test fixture in this suite -- never a real
# pilot customer name.
DIGITALLY_BORN_PDF_TEXT_LINES = (
    "RECHNUNG / INVOICE",
    "Invoice No.: DIGITAL-PDF-001",
    "Issue date: 2026-08-20",
    "Currency: EUR",
    "Seller: Beispiel Lieferant GmbH",
    "Lieferweg 1, 10115 Berlin, DE",
    "Buyer: Unternehmen X",
    "Musterweg 10, 04109 Leipzig, DE",
    "Supply: Synthetic consulting service",
    "Net Total: 100.00 EUR",
    "Tax Amount: 19.00 EUR",
    "Gross Total: 119.00 EUR",
)


def make_digitally_born_pdf_bytes() -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for text_line in DIGITALLY_BORN_PDF_TEXT_LINES:
        c.drawString(72, y, text_line)
        y -= 18
    c.showPage()
    c.save()
    return buf.getvalue()


def make_scanned_pdf_bytes() -> bytes:
    """A plain PDF whose only page content is a rasterized image -- no text
    objects at all -- for the "genuinely scanned / no usable text layer"
    test case. pypdf's extract_text() only reads real text-showing content-
    stream operators, so this always extracts to "", exactly like a real
    scanned invoice with no embedded OCR text layer."""
    # A small solid-color bitmap built directly with Pillow (a transitive
    # dependency of reportlab>=4.0.0, already required by this project --
    # see requirements.txt) rather than a hand-rolled PNG byte literal.
    from PIL import Image

    image = Image.new("RGB", (50, 50), color=(120, 120, 120))
    png_buf = BytesIO()
    image.save(png_buf, format="PNG")

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(ImageReader(BytesIO(png_buf.getvalue())), 100, 100, width=200, height=200)
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture
def digitally_born_pdf_bytes() -> bytes:
    return make_digitally_born_pdf_bytes()


@pytest.fixture
def scanned_pdf_bytes() -> bytes:
    return make_scanned_pdf_bytes()


@pytest.fixture
def client():
    app.dependency_overrides.pop(get_pdf_extraction_adapter, None)
    app.dependency_overrides.pop(get_text_extraction_adapter, None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_pdf_extraction_adapter, None)
    app.dependency_overrides.pop(get_text_extraction_adapter, None)


@pytest.fixture
def valid_en16931_xml_bytes() -> bytes:
    return load_fixture_bytes("facturx_valid_en16931.xml")


@pytest.fixture
def invalid_xsd_xml_bytes() -> bytes:
    return load_fixture_bytes("facturx_invalid_xsd.xml")


@pytest.fixture
def valid_hybrid_pdf_bytes(valid_en16931_xml_bytes) -> bytes:
    blank_pdf = make_blank_pdf_bytes()
    return generate_from_binary(
        blank_pdf, valid_en16931_xml_bytes, flavor="factur-x", level="en16931", check_xsd=True
    )


@pytest.fixture
def blank_pdf_bytes() -> bytes:
    return make_blank_pdf_bytes()


@pytest.fixture
def schematron_invalid_xml_bytes() -> bytes:
    return load_fixture_bytes("facturx_schematron_invalid.xml")


@pytest.fixture
def incorrect_payable_xml_bytes() -> bytes:
    return load_fixture_bytes("facturx_incorrect_payable.xml")


@pytest.fixture
def minimum_profile_xml_bytes() -> bytes:
    return load_fixture_bytes("facturx_minimum_profile.xml")


@pytest.fixture
def invalid_xsd_hybrid_pdf_bytes(invalid_xsd_xml_bytes) -> bytes:
    """A hybrid PDF whose embedded XML is the same XSD-invalid fixture as
    invalid_xsd_xml_bytes -- used to prove that invalid *structured* XML is
    never silently replaced or supplemented by OCR/PDF extraction (pilot
    routing rule 3: "Invalid existing XML is never replaced by OCR")."""
    blank_pdf = make_blank_pdf_bytes()
    return generate_from_binary(
        blank_pdf, invalid_xsd_xml_bytes, flavor="factur-x", level="en16931", check_xsd=False
    )


@pytest.fixture
def hybrid_pdf_without_accepted_embedded_xml_bytes(valid_en16931_xml_bytes) -> bytes:
    """A PDF carrying an XML attachment under a filename that is NOT one of
    the well-known Factur-X/ZUGFeRD/Order-X names (facturx.get_xml_from_pdf's
    ALL_FILENAMES) -- exercises document_intake.py's deliberate refusal to
    extract arbitrary embedded XML by filename heuristic (see its module
    docstring). The attachment content is otherwise a genuinely valid
    EN16931 invoice, so a test asserting on this fixture proves the PDF is
    downgraded to plain_pdf (mock OCR/PDF path) because of the filename
    alone, not because the content itself was unreadable."""
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_attachment("unrecognized-attachment.xml", valid_en16931_xml_bytes)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()
