"""Orchestrates the Phase 1 endpoints: inspect -> extract/validate ->
normalize -> (process only: load organization profile -> run controls ->
aggregate -> build report).

HTTP status semantics (enforced by facturx/phase1/api.py using the
exceptions raised here):
- UnsupportedInputError: the request can't even be classified (wrong content
  type entirely, missing/unrecognized organization context) -> 400/415.
- TechnicalProcessingError: an unclassified failure inside the pipeline
  (e.g. the structured-extraction call raising unexpectedly) -> 5xx.
- Everything else the pipeline is actually designed to classify (encrypted,
  unreadable-but-recognized, unsupported *detected* format, low-confidence
  or failed PDF extraction) flows through to a normal, schema-valid result
  -- for /process that's a report whose status may itself be
  nicht_pruefbar/klaerung_erforderlich/hinweis/unauffaellig -- HTTP 200.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .. import facturx as facturx_lib
from .contracts import validate_canonical_invoice
from .controls.aggregate import aggregate
from .controls.executor import (
    ControlResult,
    evaluate_content_controls,
    evaluate_doc_001,
    evaluate_extraction_confidence,
    evaluate_org_001,
    evaluate_org_002,
    evaluate_str_003,
    evaluate_str_004,
    not_run_result,
)
from .controls.profiles import ControlProfile, get_control_profile
from .document_intake import DocumentInspection, inspect_document
from .errors import TechnicalProcessingError, UnsupportedInputError
from .normalize.pdf_adapter import PdfExtractionAdapter, normalize_pdf_extraction
from .normalize.structured import normalize_structured_invoice
from .organization_master_data import resolve_master_data
from .report import build_report
from .validate.schematron import SchematronValidationResult, validate_schematron
from .validate.structured import StructuredValidationResult, validate_structured_xml

# The vendored Schematron artifact (facturx/phase1/resources/facturx-1.09-en16931/)
# is EN16931-specific and has only been reviewed for that profile -- see
# PROVENANCE.json. Running it against minimum/basicwl/basic/extended content
# (reachable only via /normalize and /validate, which are deliberately not
# profile-gated) would be an unreviewed use of the artifact, so it is skipped
# for those and STR-004 reports not_applicable/UNSUPPORTED_PROFILE instead.
_SCHEMATRON_REVIEWED_PROFILES = ("EN16931",)

_EMPTY_INVOICE = {
    "invoiceNumber": None,
    "issueDate": None,
    "typeCode": None,
    "currency": None,
    "supplier": {
        "name": None,
        "address": {"street": None, "postalCode": None, "city": None, "countryCode": None},
        "taxId": None,
        "vatId": None,
    },
    "buyer": {
        "name": None,
        "address": {"street": None, "postalCode": None, "city": None, "countryCode": None},
        "taxId": None,
        "vatId": None,
    },
    "supply": {"description": None, "deliveryDate": None, "periodStart": None, "periodEnd": None},
    "totals": {
        "lineNet": None, "taxBasis": None, "taxAmount": None, "grossAmount": None,
        "payableAmount": None, "chargeTotal": None, "allowanceTotal": None, "prepaidAmount": None,
        "roundingAmount": None,
    },
    "lineItems": [],
}


def _document_block(inspection: DocumentInspection) -> dict:
    return {
        "sourceType": inspection.source_type,
        "filename": inspection.filename,
        "mimeType": inspection.mime_type,
        "sha256": inspection.sha256,
        "detectedFormat": inspection.detected_format,
        "formatVersion": inspection.format_version,
        "profile": inspection.profile,
    }


def resolve_organization_context(organization_id: Optional[str], demo_mode: bool) -> dict:
    master_data = resolve_master_data(organization_id, demo_mode)
    if master_data is None:
        raise UnsupportedInputError(
            "ORGANIZATION_CONTEXT_REQUIRED",
            "This run requires an explicit organization context. Pass "
            "organizationId=unternehmen-x-demo, organizationId=unternehmen-y-demo, "
            "or demoMode=true; there is no "
            "silent fallback to demo master data.",
            status_code=400,
        )
    return master_data


def _build_canonical_invoice(
    inspection: DocumentInspection, extraction: dict, invoice: dict, field_evidence: dict
) -> dict:
    canonical_invoice = {
        "schemaVersion": "1.0.0",
        "document": _document_block(inspection),
        "extraction": extraction,
        "invoice": invoice,
        "fieldEvidence": field_evidence,
    }
    try:
        validate_canonical_invoice(canonical_invoice)
    except Exception as exc:
        raise TechnicalProcessingError(
            "CONTRACT_VALIDATION_FAILED", f"Internal canonical invoice was not schema-valid: {exc}"
        ) from exc
    return canonical_invoice


def _finalize_report(
    source_sha256: str,
    control_profile: ControlProfile,
    controls: list[ControlResult],
    status: str,
    routing: str,
    *,
    started_at: str,
    correlation_id: Optional[str] = None,
) -> dict:
    try:
        return build_report(
            source_sha256, control_profile, controls, status, routing,
            started_at=started_at, correlation_id=correlation_id,
        )
    except Exception as exc:
        raise TechnicalProcessingError(
            "CONTRACT_VALIDATION_FAILED", f"Internal control report was not schema-valid: {exc}"
        ) from exc


def _is_format_supported(inspection: DocumentInspection) -> bool:
    return inspection.detected_format in ("factur-x", "pdf")


# EN16931 is the only Factur-X profile the starter control profile has been
# tested against (per the reviewed Stage 1 decision). minimum/basicwl/basic/
# extended are legitimately valid Factur-X -- distinct from an unsupported
# *format* like xrechnung -- just not yet processable here; see DOC-001's
# UNSUPPORTED_PROFILE reason code and capabilities.py's recognized vs.
# processable levels.
_PROCESSABLE_FACTURX_PROFILES = ("EN16931",)


def _is_profile_supported(inspection: DocumentInspection) -> bool:
    if inspection.detected_format != "factur-x":
        return True
    return inspection.profile in _PROCESSABLE_FACTURX_PROFILES


@dataclass
class _ExtractionOutcome:
    canonical_invoice: dict
    invoice: dict
    field_evidence: dict
    structured_validation: Optional[StructuredValidationResult]
    extraction_status: str  # completed | partial | failed


def _extract_and_normalize(
    inspection: DocumentInspection,
    file_bytes: bytes,
    pdf_extraction_adapter: PdfExtractionAdapter,
) -> _ExtractionOutcome:
    """Shared by /process, /normalize, and /validate: turns an already-
    classified, already-DOC-001-passed document into a canonical invoice.
    Raises TechnicalProcessingError for an unclassified extraction failure;
    an anticipated extraction failure (e.g. the PDF adapter returning
    status="failed") is returned normally with extraction_status="failed"."""
    if inspection.source_type in ("hybrid_pdf", "xml"):
        try:
            # inspection.xml_etree was already parsed once, through
            # document_intake's hardened parser -- pass that, never raw
            # bytes, so untrusted XML is never reparsed unhardened for
            # XSD validation (see validate/structured.py's module docstring).
            level = inspection.profile.lower() if inspection.profile else None
            structured_validation = validate_structured_xml(inspection.xml_etree, level)
        except Exception as exc:
            raise TechnicalProcessingError(
                "STRUCTURED_EXTRACTION_UNAVAILABLE",
                f"Structured XML validation failed unexpectedly: {exc}",
            ) from exc
        try:
            invoice, field_evidence, warnings = normalize_structured_invoice(inspection.xml_etree)
        except Exception as exc:
            raise TechnicalProcessingError(
                "STRUCTURED_EXTRACTION_UNAVAILABLE",
                f"Structured normalization failed unexpectedly: {exc}",
            ) from exc
        extraction = {
            "method": "embedded_xml" if inspection.source_type == "hybrid_pdf" else "direct_xml",
            "status": "completed",
            "overallConfidence": 1.0,
            "adapterVersion": facturx_lib.VERSION,
            "warnings": warnings + inspection.warnings,
        }
        canonical_invoice = _build_canonical_invoice(inspection, extraction, invoice, field_evidence)
        return _ExtractionOutcome(
            canonical_invoice, invoice, field_evidence, structured_validation, "completed"
        )

    try:
        extraction_result = pdf_extraction_adapter.extract(file_bytes)
    except Exception as exc:
        raise TechnicalProcessingError(
            "PDF_EXTRACTION_UNAVAILABLE", f"PDF extraction adapter failed unexpectedly: {exc}"
        ) from exc
    invoice, field_evidence, warnings = normalize_pdf_extraction(extraction_result)
    extraction = {
        "method": "ocr_llm",
        "status": extraction_result.status,
        "overallConfidence": extraction_result.overall_confidence,
        "adapterVersion": "mock-adapter-0.1.0",
        "warnings": warnings + inspection.warnings,
    }
    canonical_invoice = _build_canonical_invoice(inspection, extraction, invoice, field_evidence)
    return _ExtractionOutcome(
        canonical_invoice, invoice, field_evidence, None, extraction_result.status
    )


def process_invoice(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    organization_id: Optional[str],
    demo_mode: bool,
    pdf_extraction_adapter: PdfExtractionAdapter,
    correlation_id: Optional[str] = None,
) -> tuple[dict, dict]:
    """Returns (canonical_invoice, phase1_control_report), both already
    validated against their own contract schemas."""
    started_at = datetime.now(timezone.utc).isoformat()
    organization_context = resolve_organization_context(organization_id, demo_mode)
    control_profile = get_control_profile(organization_context["controlProfileId"])
    inspection = inspect_document(file_bytes, filename, content_type)

    doc_001 = evaluate_doc_001(
        inspection.readable,
        inspection.encrypted,
        _is_format_supported(inspection),
        inspection.detected_format,
        _is_profile_supported(inspection),
        inspection.profile,
    )

    if doc_001.outcome != "passed":
        canonical_invoice, controls = _blocked_by_doc_001(inspection, doc_001, control_profile)
        report = _finalize_report(
            inspection.sha256, control_profile, controls, "nicht_pruefbar", "prioritized_review",
            started_at=started_at, correlation_id=correlation_id,
        )
        return canonical_invoice, report

    outcome = _extract_and_normalize(inspection, file_bytes, pdf_extraction_adapter)

    if outcome.extraction_status == "failed":
        controls = [doc_001, evaluate_str_003(outcome.structured_validation)] + [
            not_run_result(cid, "Blocked because extraction failed.")
            for cid in control_profile.control_ids
            if cid not in ("DOC-001", "STR-003")
        ]
        report = _finalize_report(
            inspection.sha256, control_profile, controls, "nicht_pruefbar", "prioritized_review",
            started_at=started_at, correlation_id=correlation_id,
        )
        return outcome.canonical_invoice, report

    # DOC-001 already gated out anything but EN16931 factur-x above (see
    # _is_profile_supported), so the vendored EN16931-only Schematron
    # artifact is always applicable whenever this line is reached for a
    # structured document -- the explicit profile check still guards it
    # against ever running on an unreviewed profile if that gate changes.
    # Schematron also only runs on an already-XSD-valid document: its
    # arithmetic assumes XSD-conformant types (verified directly -- an
    # XSD-invalid value like a non-numeric string in a decimal field makes
    # Saxon raise a dynamic type error, not a meaningful business-rule
    # finding), so an XSD failure short-circuits it to not_applicable
    # instead (see evaluate_str_004()).
    # None here means "not a structured document at all" (the PDF/OCR path
    # never sets structured_validation) -- distinct from "structured but
    # XSD-invalid". Only the latter should make evaluate_str_004() report
    # BLOCKED_BY_XSD_INVALID instead of NOT_A_STRUCTURED_DOCUMENT.
    xsd_valid = (
        outcome.structured_validation.xsd_valid
        if outcome.structured_validation is not None
        else True
    )
    schematron_validation = (
        validate_schematron(inspection.xml_etree)
        if xsd_valid and inspection.profile in _SCHEMATRON_REVIEWED_PROFILES
        else None
    )
    controls = [
        doc_001,
        evaluate_str_003(outcome.structured_validation),
        evaluate_str_004(schematron_validation, xsd_valid),
    ]
    controls.append(
        evaluate_extraction_confidence(outcome.canonical_invoice["extraction"]["overallConfidence"])
    )
    controls += evaluate_content_controls(outcome.invoice, outcome.field_evidence)
    controls.append(
        evaluate_org_001(
            outcome.invoice, outcome.field_evidence, organization_context["buyer"]
        )
    )
    if "ORG-002" in control_profile.control_ids:
        controls.append(
            evaluate_org_002(
                outcome.invoice,
                outcome.field_evidence,
                organization_context["approvedSuppliers"],
            )
        )

    status, routing = aggregate(controls)
    report = _finalize_report(
        inspection.sha256, control_profile, controls, status, routing,
        started_at=started_at, correlation_id=correlation_id,
    )
    return outcome.canonical_invoice, report


def process_extracted_invoice(
    document: dict,
    extraction: dict,
    invoice: dict,
    field_evidence: dict,
    organization_id: Optional[str],
    demo_mode: bool,
    correlation_id: Optional[str] = None,
) -> tuple[dict, dict]:
    """Runs the same catalog/executor as process_invoice() against canonical
    invoice fields and field evidence an external caller (Flow 1b's n8n
    OCR/LLM extraction) already produced, instead of extracting them from
    raw bytes itself. This is the seam examples/n8n/README.md's "Missing API
    contract" section asked for: a narrower endpoint accepting pre-extracted
    fields plus their evidence, so Flow 1b can stop mirroring ORG-001 (and
    every other control) in n8n-side JavaScript.

    `document`/`extraction` are already-normalized dicts (sourceType/method
    hardcoded by the caller, e.g. facturx/phase1/api.py -- never taken from
    the external request body) so a caller cannot claim e.g. sourceType=xml
    to route around the structured-document controls. `invoice`/
    `field_evidence` are exactly the caller-supplied, untrusted extraction
    result; this function never accepts a pre-computed status/routing/
    controls list from the caller -- every control outcome is (re)computed
    here, from the same functions process_invoice() uses, so the caller
    cannot inject a fabricated control result.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    organization_context = resolve_organization_context(organization_id, demo_mode)
    control_profile = get_control_profile(organization_context["controlProfileId"])

    canonical_invoice = {
        "schemaVersion": "1.0.0",
        "document": document,
        "extraction": extraction,
        "invoice": invoice,
        "fieldEvidence": field_evidence,
    }
    try:
        validate_canonical_invoice(canonical_invoice)
    except Exception as exc:
        raise UnsupportedInputError(
            "CANONICAL_INVOICE_INVALID",
            f"The submitted document/extraction/invoice/fieldEvidence did not match the "
            f"canonical invoice contract: {exc}",
            status_code=422,
        ) from exc

    # The document was already read and extracted by the external caller --
    # there is nothing left for DOC-001 to classify (readable/encrypted/
    # format-supported all trivially hold for an externally-supplied plain
    # PDF extraction), so it always evaluates to "passed" here. It still
    # runs through the real evaluate_doc_001() function, not a hand-built
    # ControlResult, so this stays the exact same executor Flow 1a uses.
    doc_001 = evaluate_doc_001(
        readable=True, encrypted=False, format_supported=True,
        detected_format=document["detectedFormat"], profile_supported=True, profile=None,
    )

    if extraction["status"] == "failed":
        controls = [doc_001, evaluate_str_003(None)] + [
            not_run_result(cid, "Blocked because extraction failed.")
            for cid in control_profile.control_ids
            if cid not in ("DOC-001", "STR-003")
        ]
        report = _finalize_report(
            document["sha256"], control_profile, controls, "nicht_pruefbar", "prioritized_review",
            started_at=started_at, correlation_id=correlation_id,
        )
        return canonical_invoice, report

    controls = [
        doc_001,
        evaluate_str_003(None),
        evaluate_str_004(None, xsd_valid=True),
        evaluate_extraction_confidence(extraction["overallConfidence"]),
    ]
    controls += evaluate_content_controls(invoice, field_evidence)
    controls.append(evaluate_org_001(invoice, field_evidence, organization_context["buyer"]))
    if "ORG-002" in control_profile.control_ids:
        controls.append(
            evaluate_org_002(invoice, field_evidence, organization_context["approvedSuppliers"])
        )

    status, routing = aggregate(controls)
    report = _finalize_report(
        document["sha256"], control_profile, controls, status, routing,
        started_at=started_at, correlation_id=correlation_id,
    )
    return canonical_invoice, report


def normalize_invoice(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    pdf_extraction_adapter: PdfExtractionAdapter,
) -> dict:
    """Returns a schema-valid canonical_invoice only -- no controls, no
    organization context required (POST /v1/invoices/normalize)."""
    # Deliberately NOT profile-gated here (unlike process_invoice): this
    # endpoint runs no controls and produces no aggregated report, so the
    # "only EN16931 is processable" restriction -- which is about whether
    # the starter control profile has been tested against a given profile
    # -- doesn't apply. A recognized Factur-X document at any profile level
    # can still be normalized.
    inspection = inspect_document(file_bytes, filename, content_type)
    doc_001 = evaluate_doc_001(
        inspection.readable,
        inspection.encrypted,
        _is_format_supported(inspection),
        inspection.detected_format,
    )
    if doc_001.outcome != "passed":
        # Normalization has no organization context or report profile. The
        # blocked canonical invoice is profile-independent.
        canonical_invoice, _controls = _blocked_by_doc_001(inspection, doc_001, None)
        return canonical_invoice

    outcome = _extract_and_normalize(inspection, file_bytes, pdf_extraction_adapter)
    return outcome.canonical_invoice


def validate_invoice(file_bytes: bytes, filename: str, content_type: str) -> dict:
    """Returns XSD and (for EN16931) Schematron validation findings for a
    structured document (POST /v1/invoices/validate) -- format validation
    only, never a DigiTax business control (those only run via /process, see
    controls/executor.py). Plain PDFs are `applicable: false`, not an error
    -- there is nothing to XSD/Schematron-validate."""
    inspection = inspect_document(file_bytes, filename, content_type)

    if inspection.source_type not in ("hybrid_pdf", "xml"):
        return {
            "applicable": False,
            "reasonCode": "NOT_A_STRUCTURED_DOCUMENT",
            "detectedFormat": inspection.detected_format,
        }
    if not _is_format_supported(inspection):
        return {
            "applicable": False,
            "reasonCode": "UNSUPPORTED_FORMAT",
            "detectedFormat": inspection.detected_format,
        }

    try:
        # Same rule as in _extract_and_normalize: pass the already-hardened
        # etree, never raw bytes.
        level = inspection.profile.lower() if inspection.profile else None
        result = validate_structured_xml(inspection.xml_etree, level)
    except Exception as exc:
        raise TechnicalProcessingError(
            "STRUCTURED_EXTRACTION_UNAVAILABLE",
            f"Structured XML validation failed unexpectedly: {exc}",
        ) from exc

    if not result.xsd_valid:
        # Real EN16931 Schematron rules assume XSD-valid input -- verified
        # directly (see controls/executor.py's evaluate_str_004() docstring):
        # running it against XSD-invalid content can make the engine raise a
        # dynamic type error instead of a meaningful business-rule finding.
        # Not run; xsdMessage above already explains what's wrong.
        schematron_block = {"status": "not_applicable", "reasonCode": "BLOCKED_BY_XSD_INVALID"}
    elif inspection.profile in _SCHEMATRON_REVIEWED_PROFILES:
        schematron_result = validate_schematron(inspection.xml_etree)
        schematron_block: dict = {"status": schematron_result.status}
        if schematron_result.status == "completed":
            schematron_block["findings"] = [
                {
                    "ruleId": f.rule_id,
                    "flag": f.flag,
                    "message": f.message,
                    "location": f.location,
                }
                for f in schematron_result.findings
            ]
        elif schematron_result.status == "unavailable":
            schematron_block["errorDetail"] = schematron_result.error_detail
    else:
        # Recognized Factur-X profile, but not EN16931 -- the vendored
        # Schematron artifact is only reviewed for EN16931 (see
        # PROVENANCE.json), so this is honestly reported as not run rather
        # than silently executed against an unreviewed profile.
        schematron_block = {"status": "not_applicable", "reasonCode": "UNSUPPORTED_PROFILE"}

    return {
        "applicable": True,
        "detectedFormat": inspection.detected_format,
        "formatVersion": inspection.format_version,
        "profile": inspection.profile,
        "xsdValid": result.xsd_valid,
        "xsdMessage": result.xsd_message,
        "xsdVersion": result.xsd_version,
        "schematron": schematron_block,
    }


def _blocked_by_doc_001(
    inspection: DocumentInspection,
    doc_001: ControlResult,
    control_profile: ControlProfile | None,
) -> tuple[dict, list[ControlResult]]:
    extraction = {
        "method": "ocr_llm" if inspection.source_type == "plain_pdf" else "embedded_xml",
        "status": "failed",
        "overallConfidence": 0.0,
        "adapterVersion": None,
        "warnings": inspection.warnings,
    }
    canonical_invoice = _build_canonical_invoice(inspection, extraction, dict(_EMPTY_INVOICE), {})
    profile_control_ids = control_profile.control_ids if control_profile else ("DOC-001",)
    controls = [doc_001] + [
        not_run_result(cid, "Blocked because DOC-001 did not pass.")
        for cid in profile_control_ids
        if cid != "DOC-001"
    ]
    return canonical_invoice, controls
