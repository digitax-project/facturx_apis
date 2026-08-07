"""Wraps the existing XSD validation (facturx.facturx.xml_check_xsd) so a
validation failure becomes a structured finding (STR-003) inside the control
report instead of an uncaught exception.

Schematron/official business-rule validation (STR-004) is not implemented in
this slice -- there are no bundled or fetched Schematron artifacts. It is
deliberately left out of the starter control profile (see
facturx/phase1/controls/profiles.py) rather than reported as passed or
silently run.
"""
from dataclasses import dataclass
from typing import Optional

from ...facturx import xml_check_xsd


@dataclass
class StructuredValidationResult:
    xsd_valid: bool
    xsd_message: Optional[str] = None


def validate_structured_xml(xml_bytes: bytes, level: Optional[str]) -> StructuredValidationResult:
    try:
        xml_check_xsd(xml_bytes, flavor="factur-x", level=level or "autodetect")
        return StructuredValidationResult(xsd_valid=True)
    except Exception as exc:
        return StructuredValidationResult(xsd_valid=False, xsd_message=str(exc))
