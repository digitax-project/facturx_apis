"""XSD validation for the structured Phase 1 path.

Deliberately does NOT call facturx.facturx.xml_check_xsd(): that function
always reserializes its input to bytes and reparses it via a plain
etree.parse(BytesIO(xml_bytes)) for the actual assertValid() call (see
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

XSD baseline, per level (this is the Stage 1 "upgrade to current Factur-X"
change -- see facturx/phase1/resources/facturx-1.09-en16931/PROVENANCE.json):
- en16931 -- the vendored, hash-verified Factur-X 1.09 EN16931 XSD (NOT the
  legacy 1.07.2 XSD facturx.py's legacy endpoints still use). This is the
  only profile POST /v1/invoices/process actually runs the starter control
  profile against (see pipeline.py's _PROCESSABLE_FACTURX_PROFILES), so it's
  the only one that needed a reviewed 1.09 upgrade this round.
- minimum/basicwl/basic/extended -- still the existing legacy 1.07.2 XSDs
  from facturx.FACTURX_LEVEL2xsd, UNCHANGED. /normalize and /validate are
  deliberately not profile-gated (see pipeline.py), so a document at one of
  these levels can still reach this function; it is not yet in scope to
  vendor and review 1.09 resources for them (see capabilities.py's
  "processableLevels" vs. recognizedLevels split, and the profile-narrowing
  decision in coordination/claude-codex/handover-log.md).
validate_structured_xml() returns which baseline it actually used
(StructuredValidationResult.xsd_version) so callers never have to guess.

Schematron/official business-rule validation (STR-004) is implemented
separately in schematron.py (also 1.09, EN16931-only, saxonche-offline) --
see facturx/phase1/controls/executor.py's evaluate_str_004().
"""
import importlib.resources
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from lxml import etree

from ...facturx import FACTURX_LEVEL2xsd

_EN16931_1_09_XSD_VERSION = "1.09"
_LEGACY_XSD_VERSION = "1.07.2"
_EN16931_1_09_RESOURCE_PACKAGE = "facturx.phase1"
_EN16931_1_09_RESOURCE_SUBPATH = "resources/facturx-1.09-en16931"
_EN16931_1_09_XSD_FILENAME = "Factur-X_EN16931.xsd"


@dataclass
class StructuredValidationResult:
    xsd_valid: bool
    xsd_message: Optional[str] = None
    xsd_version: Optional[str] = None


@lru_cache(maxsize=None)
def _load_legacy_schema(xsd_relative_path: str) -> etree.XMLSchema:
    resource = importlib.resources.files("facturx").joinpath(f"xsd/{xsd_relative_path}")
    with resource.open("rb") as f:
        return etree.XMLSchema(etree.parse(f))


@lru_cache(maxsize=None)
def _load_en16931_1_09_schema() -> etree.XMLSchema:
    resource = importlib.resources.files(_EN16931_1_09_RESOURCE_PACKAGE).joinpath(
        _EN16931_1_09_RESOURCE_SUBPATH, _EN16931_1_09_XSD_FILENAME
    )
    with importlib.resources.as_file(resource) as path:
        with open(path, "rb") as f:
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
    if level != "en16931" and level not in FACTURX_LEVEL2xsd:
        return StructuredValidationResult(
            xsd_valid=False,
            xsd_message=f"Unrecognized or undetected Factur-X level {level!r}; "
            f"expected one of {sorted(set(FACTURX_LEVEL2xsd) | {'en16931'})}.",
        )

    if level == "en16931":
        schema = _load_en16931_1_09_schema()
        xsd_version = _EN16931_1_09_XSD_VERSION
    else:
        schema = _load_legacy_schema(FACTURX_LEVEL2xsd[level])
        xsd_version = _LEGACY_XSD_VERSION

    try:
        schema.assertValid(xml_etree)
        return StructuredValidationResult(xsd_valid=True, xsd_version=xsd_version)
    except Exception as exc:
        return StructuredValidationResult(
            xsd_valid=False,
            xsd_message=f"The XML file is not valid against the official XML Schema "
            f"Definition for level {level!r} (XSD baseline {xsd_version}): {exc}",
            xsd_version=xsd_version,
        )
