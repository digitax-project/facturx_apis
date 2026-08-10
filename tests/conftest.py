from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from facturx.api import app
from facturx.facturx import generate_from_binary
from facturx.phase1.api import get_pdf_extraction_adapter

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


@pytest.fixture
def client():
    app.dependency_overrides.pop(get_pdf_extraction_adapter, None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_pdf_extraction_adapter, None)


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
