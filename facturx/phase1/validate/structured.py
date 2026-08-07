"""XSD validation for the structured Phase 1 path.

Deliberately does NOT call facturx.facturx.xml_check_xsd(): that function
always reserializes its input to bytes and reparses it via a plain
etree.parse(BytesIO(...)) for the actual assertValid() call (see
facturx.py's xml_check_xsd, the `t = etree.parse(BytesIO(xml_bytes))` line)
-- even when handed an already-parsed etree. That reparse uses lxml's
default parser, which resolves entities, undoing the entity-expansion/XXE
hardening applied once in document_intake.py's _SECURE_XML_PARSER. A caller
who assumes "I already parsed this securely, so passing the etree in is
safe" would be wrong, silently.

This module instead validates the SAME already-hardened-parsed etree
directly (lxml.etree.XMLSchema.assertValid() accepts a bare _Element, no
reparse needed) against the matching bundled Factur-X XSD, so untrusted
XML is only ever parsed once, through the hardened parser, on this path.

Schematron/official business-rule validation (STR-004) is not implemented in
this slice -- there are no bundled or fetched Schematron artifacts. It is
deliberately left out of the starter control profile (see
facturx/phase1/controls/profiles.py) rather than reported as passed or
silently run.
"""
import importlib.resources
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from lxml import etree

from ...facturx import FACTURX_LEVEL2xsd


@dataclass
class StructuredValidationResult:
    xsd_valid: bool
    xsd_message: Optional[str] = None


@lru_cache(maxsize=None)
def _load_schema(xsd_relative_path: str) -> etree.XMLSchema:
    resource = importlib.resources.files("facturx").joinpath(f"xsd/{xsd_relative_path}")
    with resource.open("rb") as f:
        return etree.XMLSchema(etree.parse(f))


def validate_structured_xml(
    xml_etree: Optional[etree._Element], level: Optional[str]
) -> StructuredValidationResult:
    """`xml_etree` must already come from document_intake's hardened parser.
    `level` must already be resolved (e.g. inspection.profile.lower()) --
    this function does not itself parse or re-detect anything from raw
    bytes."""
    if xml_etree is None:
        return StructuredValidationResult(
            xsd_valid=False, xsd_message="No parsed XML document is available to validate."
        )
    if level not in FACTURX_LEVEL2xsd:
        return StructuredValidationResult(
            xsd_valid=False,
            xsd_message=f"Unrecognized or undetected Factur-X level {level!r}; "
            f"expected one of {sorted(FACTURX_LEVEL2xsd)}.",
        )

    schema = _load_schema(FACTURX_LEVEL2xsd[level])
    try:
        schema.assertValid(xml_etree)
        return StructuredValidationResult(xsd_valid=True)
    except Exception as exc:
        return StructuredValidationResult(
            xsd_valid=False,
            xsd_message=f"The XML file is not valid against the official XML Schema "
            f"Definition for level {level!r}: {exc}",
        )
