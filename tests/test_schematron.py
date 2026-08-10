"""Direct tests for facturx/phase1/validate/schematron.py: the offline
saxonche-based EN16931 Schematron runner. Covers both the valid/invalid
content paths and the safety properties required before untrusted XML is
allowed to reach a native XSLT2 engine (see schematron.py's module
docstring for the reasoning each of these confirms).
"""
import shutil

import pytest
from lxml import etree

from facturx.phase1.document_intake import _parse_untrusted_xml
from facturx.phase1.validate.schematron import (
    _xsl_resource,
    validate_schematron,
)

FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures"

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

XXE_XML = b"""<?xml version="1.0"?>
<!DOCTYPE root [
 <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100">
  &xxe;
</rsm:CrossIndustryInvoice>
"""


def test_valid_en16931_fixture_has_no_findings():
    xml_bytes = (FIXTURES / "facturx_valid_en16931.xml").read_bytes()
    tree = _parse_untrusted_xml(xml_bytes)
    result = validate_schematron(tree)
    assert result.status == "completed"
    assert result.findings == []


def test_schematron_invalid_fixture_reports_rule_id_and_location():
    xml_bytes = (FIXTURES / "facturx_schematron_invalid.xml").read_bytes()
    tree = _parse_untrusted_xml(xml_bytes)
    result = validate_schematron(tree)
    assert result.status == "completed"
    assert len(result.findings) >= 1
    for finding in result.findings:
        assert finding.rule_id.startswith("FX-SCH-")
        assert finding.message
        assert finding.location  # a real XPath, not empty


def test_none_input_is_not_applicable():
    result = validate_schematron(None)
    assert result.status == "not_applicable"
    assert result.findings == []


@pytest.mark.parametrize("payload", [BILLION_LAUGHS_XML, XXE_XML])
def test_entity_payloads_fail_safely_not_expanded_or_fetched(payload):
    """The hardened parser leaves the entity reference inert (unexpanded,
    unfetched); schematron.py reserializes that same tree, which does not
    reconstruct the DOCTYPE/entity declarations, so Saxon's own parser sees
    only a bare undeclared-entity reference and raises a clean parse error.
    This must never succeed and never hang -- a safe failure either way."""
    tree = _parse_untrusted_xml(payload)
    result = validate_schematron(tree)
    assert result.status == "unavailable"
    assert result.error_detail
    assert result.findings == []


def test_missing_codedb_resource_fails_safely_not_silently_passed(tmp_path):
    """Simulates a missing/corrupt bundled artifact: the control must report
    unavailable, never a false passed with zero findings."""
    xsl_resource = _xsl_resource()
    with __import__("importlib").resources.as_file(xsl_resource) as xsl_path:
        resource_dir = xsl_path.parent
        codedb_path = resource_dir / "FACTUR-X_EN16931_codedb.xml"
        backup_path = tmp_path / "codedb_backup.xml"
        shutil.move(str(codedb_path), str(backup_path))
        try:
            xml_bytes = (FIXTURES / "facturx_valid_en16931.xml").read_bytes()
            tree = _parse_untrusted_xml(xml_bytes)
            result = validate_schematron(tree)
        finally:
            shutil.move(str(backup_path), str(codedb_path))
    assert result.status == "unavailable"
    assert result.error_detail
    assert result.findings == []


def test_timeout_fails_safely_not_silently_passed(monkeypatch):
    """Forces the worker call to outlast the bound deterministically (a real
    Saxon run is normally much faster than any reasonable timeout, so
    asserting this against real execution speed would be flaky/environment-
    dependent -- this instead confirms the timeout *mechanism itself* fails
    safely, never returning a passed/completed result for work that didn't
    finish in time)."""
    import time

    from facturx.phase1.validate import schematron as schematron_module

    def _slow_run_sync(serialized_xml):
        time.sleep(2)
        return schematron_module.SchematronValidationResult(status="completed", findings=[])

    monkeypatch.setattr(schematron_module, "_run_sync", _slow_run_sync)

    xml_bytes = (FIXTURES / "facturx_valid_en16931.xml").read_bytes()
    tree = _parse_untrusted_xml(xml_bytes)
    result = validate_schematron(tree, timeout_seconds=0.05)
    assert result.status == "unavailable"
    assert "exceeded" in result.error_detail
    assert result.findings == []


def test_no_network_or_extra_resource_access_functions_in_vendored_stylesheet():
    """Static confirmation that the ONLY external-resource-access function
    anywhere in the vendored, trusted stylesheet is a single fixed relative
    document() call (verified during authoring: 116 occurrences, always the
    literal filename 'FACTUR-X_EN16931_codedb.xml', resolved against the
    stylesheet's own location, never against anything derived from invoice
    content). This guards against a future edit accidentally introducing a
    doc()/collection()/unparsed-text() call or a real http(s):// resource
    reference."""
    xsl_resource = _xsl_resource()
    with __import__("importlib").resources.as_file(xsl_resource) as xsl_path:
        content = xsl_path.read_text(encoding="utf-8")
    for forbidden in ("unparsed-text(", "collection(", "doc(", "doc-available(", "https://"):
        assert forbidden not in content
    import re

    document_calls = set(re.findall(r"document\([^)]*\)", content))
    assert document_calls == {"document('FACTUR-X_EN16931_codedb.xml')"}
