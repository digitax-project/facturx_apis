"""Document intake: hashing, safety checks, and source-type/format detection.

Corresponds to DOC-001..DOC-005 in docs/invoice_phase1/control_catalog.md and
the "Intake"/"Safety checks"/"Format detection" rows of
docs/invoice_phase1/automation_boundary.md.

This module never raises for content the pipeline is designed to classify
(encrypted, unreadable-but-recognized, unknown structured format) -- those
become DOC-001/detectedFormat findings in the control report (HTTP 200). It
raises UnsupportedInputError for request-level rejections that never reach
the classification pipeline: bytes that aren't recognizable as a PDF or XML
at all (415), or a file/embedded-XML payload over the size limit (413).

Hardening notes (untrusted input from an external sender):
- All XML parsing here uses a locked-down lxml parser: no entity resolution
  (blocks internal-entity "billion laughs" expansion), no network access
  (blocks external-entity/XXE exfiltration and SSRF), no DTD loading.
- Only embedded PDF attachments using the well-known Factur-X/ZUGFeRD/
  Order-X filenames are extracted (via facturx.get_xml_from_pdf). Earlier
  drafts of this module also fell back to extracting *any* embedded file
  that merely looked like XML by filename heuristic
  (facturx.extract_any_xml_from_pdf) -- that fallback let an attacker embed
  and have this service parse an arbitrary attached XML file. It is
  intentionally not used on this path. The legacy `/facturx-pdfextractxml`
  endpoint still offers that behavior, but only as an explicit
  `accept_any_filename=True` opt-in on a request-by-request basis, not a
  default.
"""
import hashlib
from dataclasses import dataclass, field
from io import BytesIO
from typing import Optional

from lxml import etree
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from ..facturx import get_flavor, get_level, get_xml_from_pdf
from .errors import UnsupportedInputError

FACTURX_LEGACY_FORMAT_VERSION = "1.07.2"

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MiB
MAX_EMBEDDED_XML_BYTES = 5 * 1024 * 1024  # 5 MiB

# resolve_entities=False blocks internal general-entity expansion (the
# "billion laughs" DoS pattern) independent of network access.
# no_network=True additionally blocks fetching *external* entities/DTDs
# (XXE file/SSRF exfiltration). load_dtd=False skips DTD processing
# entirely. huge_tree=False (lxml's default, set explicitly here for
# clarity) caps overall tree size/depth.
_SECURE_XML_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    dtd_validation=False,
    load_dtd=False,
    huge_tree=False,
)


@dataclass
class DocumentInspection:
    source_type: str  # hybrid_pdf | plain_pdf | xml
    filename: str
    mime_type: str
    sha256: str
    detected_format: str  # factur-x | xrechnung | pdf | unknown
    format_version: Optional[str] = None
    profile: Optional[str] = None
    readable: bool = True
    encrypted: bool = False
    embedded_xml_bytes: Optional[bytes] = None
    xml_bytes: Optional[bytes] = None
    xml_etree: Optional[etree._Element] = None
    warnings: list[str] = field(default_factory=list)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _looks_like_xml(data: bytes) -> bool:
    stripped = data.lstrip(b"\xef\xbb\xbf \t\r\n")
    return stripped.startswith(b"<?xml") or stripped.startswith(b"<")


def _parse_untrusted_xml(xml_bytes: bytes) -> etree._Element:
    """The only place raw untrusted XML bytes are turned into an lxml tree
    on this path. Always goes through _SECURE_XML_PARSER."""
    return etree.fromstring(xml_bytes, parser=_SECURE_XML_PARSER)


def _detect_structured_format(xml_bytes: bytes, warnings: list[str]) -> tuple:
    """Returns (detected_format, format_version, profile, xml_etree) for XML bytes."""
    try:
        xml_etree = _parse_untrusted_xml(xml_bytes)
    except Exception as exc:
        warnings.append(f"XML_NOT_WELL_FORMED_OR_REJECTED: {exc}")
        return "unknown", None, None, None
    if _is_xrechnung(xml_etree):
        # Same CrossIndustryInvoice root tag as Factur-X, but the Guideline
        # ID identifies the German XRechnung CIUS specifically. Must be
        # checked before falling through to the generic Factur-X flavor
        # detection below, which only looks at the root tag name and would
        # otherwise misclassify it as factur-x.
        warnings.append("DETECTED_XRECHNUNG_GUIDELINE_ID")
        return "xrechnung", None, None, xml_etree
    try:
        flavor = get_flavor(xml_etree)
    except Exception as exc:
        warnings.append(f"UNRECOGNIZED_XML_FLAVOR: {exc}")
        return "unknown", None, None, xml_etree
    if flavor not in ("factur-x", "facturx"):
        # zugferd 1.0 / order-x are out of scope for the invoice control profile
        warnings.append(f"UNSUPPORTED_XML_FLAVOR: {flavor}")
        return "unknown", None, None, xml_etree
    try:
        level = get_level(xml_etree, flavor="factur-x")
    except Exception as exc:
        warnings.append(f"UNRECOGNIZED_PROFILE_LEVEL: {exc}")
        return "factur-x", FACTURX_LEGACY_FORMAT_VERSION, None, xml_etree
    return "factur-x", FACTURX_LEGACY_FORMAT_VERSION, level.upper(), xml_etree


_XRECHNUNG_GUIDELINE_ID_PATH = (
    "//rsm:ExchangedDocumentContext"
    "/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID"
)
_XRECHNUNG_GUIDELINE_MARKERS = ("xrechnung", "kosit")


def _is_xrechnung(xml_etree: etree._Element) -> bool:
    from ..facturx import XML_NAMESPACES

    try:
        matches = xml_etree.xpath(
            _XRECHNUNG_GUIDELINE_ID_PATH, namespaces=XML_NAMESPACES["factur-x"]
        )
    except Exception:
        return False
    guideline_id = (matches[0].text or "").strip().lower() if matches else ""
    return any(marker in guideline_id for marker in _XRECHNUNG_GUIDELINE_MARKERS)


def inspect_document(
    file_bytes: bytes, filename: str, content_type: str
) -> DocumentInspection:
    if not file_bytes:
        raise UnsupportedInputError(
            "EMPTY_FILE", "The uploaded file is empty.", status_code=400
        )
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise UnsupportedInputError(
            "FILE_TOO_LARGE",
            f"The uploaded file exceeds the {MAX_UPLOAD_BYTES} byte limit.",
            status_code=413,
        )

    sha256 = _sha256(file_bytes)
    warnings: list[str] = []

    if file_bytes.startswith(b"%PDF"):
        return _inspect_pdf(file_bytes, filename, content_type, sha256, warnings)
    if _looks_like_xml(file_bytes):
        detected_format, format_version, profile, xml_etree = (
            _detect_structured_format(file_bytes, warnings)
        )
        return DocumentInspection(
            source_type="xml",
            filename=filename,
            mime_type=content_type or "application/xml",
            sha256=sha256,
            detected_format=detected_format,
            format_version=format_version,
            profile=profile,
            readable=True,
            encrypted=False,
            xml_bytes=file_bytes,
            xml_etree=xml_etree,
            warnings=warnings,
        )

    raise UnsupportedInputError(
        "UNSUPPORTED_CONTENT_TYPE",
        "The uploaded file is neither a recognizable PDF nor a recognizable "
        "XML document.",
        status_code=415,
    )


def _inspect_pdf(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    sha256: str,
    warnings: list[str],
) -> DocumentInspection:
    readable = True
    encrypted = False
    try:
        reader = PdfReader(BytesIO(file_bytes))
        encrypted = bool(reader.is_encrypted)
        if not encrypted:
            # touch page count to force a basic structural read
            _ = len(reader.pages)
    except PdfReadError as exc:
        readable = False
        warnings.append(f"PDF_UNREADABLE: {exc}")
    except Exception as exc:
        readable = False
        warnings.append(f"PDF_UNREADABLE: {exc}")

    if not readable or encrypted:
        return DocumentInspection(
            source_type="plain_pdf",
            filename=filename,
            mime_type=content_type or "application/pdf",
            sha256=sha256,
            detected_format="pdf",
            readable=readable,
            encrypted=encrypted,
            warnings=warnings,
        )

    embedded_xml_bytes = None
    try:
        # Only well-known Factur-X/ZUGFeRD/Order-X attachment filenames are
        # accepted -- see module docstring. No arbitrary-embedded-file
        # fallback on this path.
        _, embedded_xml_bytes = get_xml_from_pdf(BytesIO(file_bytes), check_xsd=False)
    except Exception as exc:
        warnings.append(f"EMBEDDED_XML_EXTRACTION_FAILED: {exc}")
        embedded_xml_bytes = None

    if embedded_xml_bytes and len(embedded_xml_bytes) > MAX_EMBEDDED_XML_BYTES:
        warnings.append(
            f"EMBEDDED_XML_TOO_LARGE: {len(embedded_xml_bytes)} bytes "
            f"exceeds the {MAX_EMBEDDED_XML_BYTES} byte limit; treated as plain PDF"
        )
        embedded_xml_bytes = None

    if embedded_xml_bytes:
        detected_format, format_version, profile, xml_etree = (
            _detect_structured_format(embedded_xml_bytes, warnings)
        )
        return DocumentInspection(
            source_type="hybrid_pdf",
            filename=filename,
            mime_type=content_type or "application/pdf",
            sha256=sha256,
            detected_format=detected_format,
            format_version=format_version,
            profile=profile,
            readable=True,
            encrypted=False,
            embedded_xml_bytes=embedded_xml_bytes,
            xml_bytes=embedded_xml_bytes,
            xml_etree=xml_etree,
            warnings=warnings,
        )

    return DocumentInspection(
        source_type="plain_pdf",
        filename=filename,
        mime_type=content_type or "application/pdf",
        sha256=sha256,
        detected_format="pdf",
        readable=True,
        encrypted=False,
        warnings=warnings,
    )
