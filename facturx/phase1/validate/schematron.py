"""Offline EN16931 Schematron (official business-rule) execution for STR-004.

Runs the vendored, hash-verified Factur-X 1.09 EN16931 compiled Schematron
stylesheet (facturx/phase1/resources/facturx-1.09-en16931/, see PROVENANCE.json
there) through pinned saxonche (SaxonC-HE 13.0, offline, no Java, no network at
runtime) -- lxml/libxslt cannot run it because it is genuine XSLT 2.0.

Security posture (conditions from the reviewed Stage 1 decision):
- The XML handed to Saxon is NEVER the raw untrusted bytes and never re-read
  from disk with Saxon's own file parser. It is always the SAME etree that
  document_intake.py already parsed once through its hardened parser
  (resolve_entities=False, no_network=True, load_dtd=False), reserialized to a
  string and handed to Saxon via proc.parse_xml(xml_text=...). Verified
  directly (see tests/test_schematron.py): a billion-laughs or XXE payload
  that the hardened parser already reduced to an inert, unexpanded entity
  reference reserializes WITHOUT its DOCTYPE/entity declarations (lxml does
  not reconstruct them when serializing a parsed _Element), so Saxon's parser
  sees only a bare, undeclared entity reference and raises a clean parse
  error (SXXP0003) -- never expansion, never a file:// or network fetch.
- The only external-resource access anywhere in the stylesheet is a single
  fixed relative document('FACTUR-X_EN16931_codedb.xml') call, resolved by
  Saxon against the STYLESHEET's own on-disk location (verified directly --
  removing the codedb file produces a clean I/O error naming that exact
  path), never against anything derived from the untrusted invoice content.
  There is no document()/doc()/collection()/unparsed-text() call anywhere
  else in the file, and no http(s):// URI in it that is anything other than
  an inert XML namespace name (verified by inspecting the raw file content).
- Execution runs in a worker thread with a hard wall-clock bound
  (EXECUTION_TIMEOUT_SECONDS). On timeout this returns status="unavailable"
  immediately; SaxonC-HE (a native extension) has no supported hard-kill from
  Python, so the worker thread itself may keep running in the background
  until the native call returns on its own -- a known, documented residual
  limitation (see handover-log.md), not a security hole: the caller never
  receives a "passed" result from a run that didn't actually finish.
- Any failure to execute (missing/corrupt artifact, timeout, Saxon raising,
  unparseable SVRL output) returns status="unavailable" with an error detail.
  It is the executor.py caller's responsibility to turn that into a
  not_reliable control outcome, never a passed one -- see evaluate_str_004().
"""
import concurrent.futures
import importlib.resources
from dataclasses import dataclass, field
from typing import Optional

from lxml import etree

RESOURCE_PACKAGE = "facturx.phase1"
RESOURCE_SUBPATH = "resources/facturx-1.09-en16931"
XSL_FILENAME = "Factur-X_1.09_EN16931.xsl"
ARTIFACT_VERSION = "1.09"

EXECUTION_TIMEOUT_SECONDS = 15

SVRL_NS = "http://purl.oclc.org/dsdl/svrl"
_SVRL_FAILED_ASSERT = f"{{{SVRL_NS}}}failed-assert"
_SVRL_TEXT = f"{{{SVRL_NS}}}text"


@dataclass
class SchematronFinding:
    rule_id: str
    message: str
    flag: Optional[str] = None  # "warning" (advisory) or None (blocking BR-* assertion)
    location: Optional[str] = None  # XPath of the offending node, from the stylesheet itself


@dataclass
class SchematronValidationResult:
    status: str  # "completed" | "not_applicable" | "unavailable"
    findings: list = field(default_factory=list)  # list[SchematronFinding]
    error_detail: Optional[str] = None


def _xsl_resource():
    return importlib.resources.files(RESOURCE_PACKAGE).joinpath(RESOURCE_SUBPATH, XSL_FILENAME)


def _run_sync(serialized_xml: str) -> SchematronValidationResult:
    from saxonche import PySaxonProcessor  # imported lazily: keeps import-time cheap, and

    xsl_resource = _xsl_resource()
    try:
        with importlib.resources.as_file(xsl_resource) as xsl_path:
            with PySaxonProcessor(license=False) as proc:
                source_node = proc.parse_xml(xml_text=serialized_xml)
                xslt = proc.new_xslt30_processor()
                executable = xslt.compile_stylesheet(stylesheet_file=str(xsl_path))
                result_xml = executable.transform_to_string(xdm_node=source_node)
    except Exception as exc:
        return SchematronValidationResult(status="unavailable", error_detail=str(exc))

    if not result_xml:
        return SchematronValidationResult(
            status="unavailable", error_detail="Schematron execution returned no output."
        )
    try:
        svrl_root = etree.fromstring(result_xml.encode("utf-8"))
    except Exception as exc:
        return SchematronValidationResult(
            status="unavailable",
            error_detail=f"Could not parse the Schematron SVRL output: {exc}",
        )

    findings = []
    for failed_assert in svrl_root.iter(_SVRL_FAILED_ASSERT):
        text_el = failed_assert.find(_SVRL_TEXT)
        message = (text_el.text or "").strip() if text_el is not None else ""
        findings.append(
            SchematronFinding(
                rule_id=failed_assert.get("id") or "UNKNOWN_RULE",
                message=message,
                flag=failed_assert.get("flag"),
                location=failed_assert.get("location"),
            )
        )
    return SchematronValidationResult(status="completed", findings=findings)


def validate_schematron(
    xml_etree: Optional[etree._Element], timeout_seconds: float = EXECUTION_TIMEOUT_SECONDS
) -> SchematronValidationResult:
    """`xml_etree` must already come from document_intake's hardened parser (same
    contract as validate/structured.py's validate_structured_xml) or be None for
    a non-structured document. Never parses raw bytes itself."""
    if xml_etree is None:
        return SchematronValidationResult(status="not_applicable")

    try:
        serialized_xml = etree.tostring(xml_etree, encoding="unicode")
    except Exception as exc:
        return SchematronValidationResult(
            status="unavailable", error_detail=f"Could not serialize the parsed document: {exc}"
        )

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(_run_sync, serialized_xml)
    try:
        return future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError:
        return SchematronValidationResult(
            status="unavailable",
            error_detail=f"Schematron execution exceeded the {timeout_seconds:.0f}s bound.",
        )
    except Exception as exc:
        return SchematronValidationResult(status="unavailable", error_detail=str(exc))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
