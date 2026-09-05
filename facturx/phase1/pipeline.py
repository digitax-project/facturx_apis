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
import re
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
from .organization_master_data import build_buyer_master_data_context, resolve_master_data
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


def resolve_organization_context(
    organization_id: Optional[str],
    demo_mode: bool,
    buyer_master_data: Optional[dict] = None,
    control_profile_id: Optional[str] = None,
) -> dict:
    # A real (non-demo) caller sends its own buyer master data directly --
    # no fixture lookup, no hardcoded organization list. This always wins
    # over organizationId/demoMode when present, since a real caller has no
    # reason to also want the demo fixture path.
    if buyer_master_data is not None:
        if not control_profile_id:
            raise UnsupportedInputError(
                "CONTROL_PROFILE_ID_REQUIRED",
                "controlProfileId is required whenever buyerMasterData is supplied.",
                status_code=400,
            )
        return build_buyer_master_data_context(
            organization_id, control_profile_id, buyer_master_data
        )

    master_data = resolve_master_data(organization_id, demo_mode)
    if master_data is None:
        raise UnsupportedInputError(
            "ORGANIZATION_CONTEXT_REQUIRED",
            "This run requires an explicit organization context. Pass "
            "organizationId=unternehmen-x-demo, organizationId=unternehmen-y-demo, "
            "demoMode=true, or a real buyerMasterData object with a "
            "controlProfileId; there is no silent fallback to demo master data.",
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
    invoice = _normalize_turkish_locale_characters(invoice)
    invoice = _normalize_extracted_dates(invoice)
    invoice = _normalize_country_codes(invoice)
    invoice = _normalize_currency_code(invoice)
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
    buyer_master_data: Optional[dict] = None,
    control_profile_id: Optional[str] = None,
) -> tuple[dict, dict]:
    """Returns (canonical_invoice, phase1_control_report), both already
    validated against their own contract schemas."""
    started_at = datetime.now(timezone.utc).isoformat()
    organization_context = resolve_organization_context(
        organization_id, demo_mode, buyer_master_data, control_profile_id
    )
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


_NON_ISO_DATE_RE = re.compile(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EXTRACTED_INVOICE_DATE_PATHS = (
    ("issueDate",),
    ("supply", "deliveryDate"),
    ("supply", "periodStart"),
    ("supply", "periodEnd"),
)


def _normalize_extracted_dates(invoice: dict) -> dict:
    """Converts DD.MM.YYYY/DD/MM/YYYY date strings to ISO 8601 (YYYY-MM-DD)
    before schema validation.

    Confirmed live 2026-09-03: Flow 1b's own local-AI extraction prompt
    already explicitly instructs "Dates use YYYY-MM-DD" -- the model still
    returned "10.05.2025" verbatim from the source document, causing a hard
    CANONICAL_INVOICE_INVALID (422) that blocked the invoice from reaching
    controls at all, not even a nicht_pruefbar review routing. Relying on
    prompt compliance alone was not sufficient; this is a defensive
    normalization at the actual validation boundary, so it protects the
    cloud lane the same way if the same non-compliance ever happens there.
    Only DD.MM.YYYY / DD/MM/YYYY (dot or slash, day-first) is converted --
    the two real-world variants observed in German invoices so far. A date
    already in ISO form is left untouched.

    Confirmed live again 2026-09-03 (text-extraction-first prototype): the
    same prompt instruction not to echo a vague delivery term ("soon as
    possible") into a date field, and to return null instead, was itself
    not reliably followed on every run -- one run returned the phrase
    verbatim, again causing a hard CANONICAL_INVOICE_INVALID instead of a
    review-routed result. Any value that is still not ISO-shaped after the
    DD.MM.YYYY conversion attempt above is therefore nulled here rather
    than left to fail schema validation -- prompt compliance alone was not
    sufficient for this case either.
    """
    for path in _EXTRACTED_INVOICE_DATE_PATHS:
        node = invoice
        for key in path[:-1]:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                break
        else:
            leaf_key = path[-1]
            value = node.get(leaf_key) if isinstance(node, dict) else None
            if isinstance(value, str):
                stripped = value.strip()
                match = _NON_ISO_DATE_RE.match(stripped)
                if match:
                    day, month, year = match.groups()
                    node[leaf_key] = f"{year}-{int(month):02d}-{int(day):02d}"
                elif not _ISO_DATE_RE.match(stripped):
                    node[leaf_key] = None
    return invoice


_TURKISH_LOCALE_CHAR_MAP = str.maketrans({"İ": "I", "ı": "i"})


def _normalize_turkish_locale_characters(invoice: dict) -> dict:
    """Folds Turkish-locale dotted/dotless I variants (U+0130 'İ', U+0131 'ı')
    to plain ASCII I/i, recursively across every string value in the
    invoice dict.

    Confirmed live 2026-09-03 (acceptance-test round 3, seed 99): a real
    supplier invoice typeset with a Turkish-locale font produced extracted
    text like "LEİPZİG" and a Turkish-dotted-I-corrupted street name
    instead of the buyer's real city/street -- present in the PDF's own
    text layer, before either
    the local or cloud model ever sees it, so both extracted it faithfully
    and ORG-001's buyer-address string comparison then failed on a
    visually-identical-looking but codepoint-different city name. This is
    a source-document character-encoding artifact, not an extraction
    error, so it is folded here (broadly, across all string fields, since
    the corruption showed up in the buyer's name, street, AND city on that
    one document -- not confined to a single enum-like field the way the
    country/currency fixes above are) rather than fixed per-field or
    relied upon to never recur. This does NOT fix an actual wrong
    character in the source document itself (the same invoice separately
    had "GMBG" printed instead of "GmbH" -- a genuine typo, not a
    Turkish-locale substitution -- which no normalization can recover)."""
    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str):
                    node[key] = value.translate(_TURKISH_LOCALE_CHAR_MAP)
                else:
                    walk(value)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                if isinstance(item, str):
                    node[i] = item.translate(_TURKISH_LOCALE_CHAR_MAP)
                else:
                    walk(item)

    walk(invoice)
    return invoice


_ISO_COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$")
# Confirmed live 2026-09-03 (first genuinely random 10-invoice acceptance
# draw from a real supplier archive, not the hand-picked tuning set): 6/10
# files hard-crashed on this exact validation, none of the earlier curated
# tuning files ever exercised it -- the tuning set was all-domestic (German)
# invoices, so the countryCode field was never actually stress-tested there.
# The extraction prompt already asks for header info generally but never
# states the countryCode fields specifically need an ISO 3166-1 alpha-2
# code; the model reasonably returns whatever the document itself prints
# (often the full country name, in German or English). As with dates,
# prompt compliance alone was not sufficient -- this is the same defensive
# normalization pattern at the actual validation boundary. Deliberately a
# bounded lookup (not a full ISO-3166 library dependency) covering the
# trading-partner countries actually seen in Unternehmen X's real supplier base
# so far; an unrecognized name is left as-is and still fails validation
# visibly rather than being guessed at.
_COUNTRY_NAME_TO_ISO2 = {
    "germany": "DE", "deutschland": "DE", "allemagne": "DE",
    "netherlands": "NL", "niederlande": "NL", "the netherlands": "NL", "holland": "NL",
    "vietnam": "VN", "việt nam": "VN", "viet nam": "VN",
    "france": "FR", "frankreich": "FR",
    "italy": "IT", "italien": "IT", "italia": "IT",
    "spain": "ES", "spanien": "ES", "espana": "ES", "españa": "ES",
    "austria": "AT", "oesterreich": "AT", "österreich": "AT",
    "switzerland": "CH", "schweiz": "CH", "suisse": "CH",
    "belgium": "BE", "belgien": "BE",
    "poland": "PL", "polen": "PL",
    "czech republic": "CZ", "tschechien": "CZ", "czechia": "CZ",
    "china": "CN", "china (mainland)": "CN",
    "united states": "US", "usa": "US", "u.s.a.": "US", "united states of america": "US",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB",
    "denmark": "DK", "daenemark": "DK", "dänemark": "DK",
    "sweden": "SE", "schweden": "SE",
    "portugal": "PT",
    "luxembourg": "LU", "luxemburg": "LU",
    "hungary": "HU", "ungarn": "HU",
    "slovakia": "SK", "slowakei": "SK",
    "turkey": "TR", "tuerkei": "TR", "türkei": "TR",
    "india": "IN", "indien": "IN",
    "hong kong": "HK",
    "taiwan": "TW",
    "south korea": "KR", "korea": "KR",
    "japan": "JP",
}
_COUNTRY_CODE_PATHS = (
    ("supplier", "address", "countryCode"),
    ("buyer", "address", "countryCode"),
)


def _normalize_country_codes(invoice: dict) -> dict:
    """Maps a known full country name (English or German, the two languages
    seen in practice) to its ISO 3166-1 alpha-2 code before schema
    validation. See the module comment above _COUNTRY_NAME_TO_ISO2 for why
    this exists. A value already ISO-shaped is left untouched; an
    unrecognized name is left as-is and still fails validation visibly."""
    for path in _COUNTRY_CODE_PATHS:
        node = invoice
        for key in path[:-1]:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                break
        else:
            leaf_key = path[-1]
            value = node.get(leaf_key) if isinstance(node, dict) else None
            if isinstance(value, str):
                stripped = value.strip()
                if not _ISO_COUNTRY_CODE_RE.match(stripped):
                    mapped = _COUNTRY_NAME_TO_ISO2.get(stripped.lower())
                    if mapped:
                        node[leaf_key] = mapped
    return invoice


_ISO_CURRENCY_CODE_RE = re.compile(r"^[A-Z]{3}$")
# Same category and same evidence source as _COUNTRY_NAME_TO_ISO2 above: the
# very same round-1 random draw that surfaced the country-name bug also
# produced a currency field of '€' (the euro glyph itself, as printed on
# the invoice) instead of the 3-letter ISO 4217 code, with an identical
# root cause -- the prompt never states currency must be an ISO code either.
_CURRENCY_SYMBOL_TO_ISO = {
    "€": "EUR", "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "$": "USD", "us$": "USD", "usd": "USD", "dollar": "USD",
    "£": "GBP", "gbp": "GBP", "pound": "GBP",
    "¥": "JPY", "jpy": "JPY", "yen": "JPY",
    "chf": "CHF", "sfr": "CHF",
    "₫": "VND", "vnd": "VND", "dong": "VND",
    "¥ (cny)": "CNY", "cny": "CNY", "rmb": "CNY",
}


def _normalize_currency_code(invoice: dict) -> dict:
    """Maps a known currency symbol/name to its ISO 4217 code before schema
    validation. See the module comment above _CURRENCY_SYMBOL_TO_ISO for why
    this exists. A value already ISO-shaped is left untouched; an
    unrecognized value is left as-is and still fails validation visibly."""
    value = invoice.get("currency")
    if isinstance(value, str):
        stripped = value.strip()
        if not _ISO_CURRENCY_CODE_RE.match(stripped):
            mapped = _CURRENCY_SYMBOL_TO_ISO.get(stripped.lower())
            if mapped:
                invoice["currency"] = mapped
    return invoice


def process_extracted_invoice(
    document: dict,
    extraction: dict,
    invoice: dict,
    field_evidence: dict,
    organization_id: Optional[str],
    demo_mode: bool,
    correlation_id: Optional[str] = None,
    buyer_master_data: Optional[dict] = None,
    control_profile_id: Optional[str] = None,
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
    organization_context = resolve_organization_context(
        organization_id, demo_mode, buyer_master_data, control_profile_id
    )
    control_profile = get_control_profile(organization_context["controlProfileId"])

    invoice = _normalize_turkish_locale_characters(invoice)
    invoice = _normalize_extracted_dates(invoice)
    invoice = _normalize_country_codes(invoice)
    invoice = _normalize_currency_code(invoice)

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
