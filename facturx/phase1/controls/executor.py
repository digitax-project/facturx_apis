"""Evaluates individual controls against a canonical invoice.

Each function returns a ControlResult matching the `controls[]` items of
phase1_control_report.schema.json. A field's confidence is read from
field_evidence when present, defaulting to 1.0 when absent -- correct for
the structured XML path, where an element simply not being in a valid
document is exactly as confidently "missing" as one the source declares
absent (there's no separate "the parser didn't look" state for XML).

The PDF/OCR path does NOT share that default: facturx/phase1/normalize/
pdf_adapter.py emits an explicit confidence of 0.0 for any field its adapter
never processed at all (FieldState.NOT_EXTRACTED), so field_evidence always
has an entry there and this module's 1.0 fallback is never actually reached
for PDF-sourced data. That's what lets FRM-00x tell a confidently-missing
field (`failed`, blocking) apart from a merely low-confidence OR
never-attempted one (`not_reliable`, which routes the whole run to
nicht_pruefbar per AGENTS.md) -- see pdf_adapter.py's FieldState docstring.

Every non-`passed` outcome carries a human-readable `message` and, for
arithmetic/master-data findings, a structured `details` object (expected/
actual/difference/tolerance/formula, or a per-field `mismatches` list) --
reason codes alone don't tell a reviewer what was actually wrong.
"""
from dataclasses import dataclass, field as dc_field
from typing import Optional

from .catalog import CATALOG
from ..validate.schematron import SchematronValidationResult
from ..validate.structured import StructuredValidationResult

DEFAULT_CONFIDENCE_THRESHOLD = 0.7


@dataclass
class ControlResult:
    control_id: str
    title: str
    outcome: str  # passed | failed | not_run | not_applicable | not_reliable
    severity: str  # none | info | warning | blocking | technical
    reason_codes: list[str] = dc_field(default_factory=list)
    evidence_refs: list[str] = dc_field(default_factory=list)
    rule_version: str = "1.0.0"
    message: str | None = None
    details: Optional[dict] = None


def _severity_for(control_id: str, outcome: str) -> str:
    if outcome in ("passed", "not_applicable", "not_run"):
        return "none"
    return CATALOG[control_id].failure_severity


def not_run_result(control_id: str, message: str) -> ControlResult:
    definition = CATALOG[control_id]
    return ControlResult(
        control_id=control_id,
        title=definition.title,
        outcome="not_run",
        severity="none",
        reason_codes=["BLOCKED_BY_PRIOR_FAILURE"],
        rule_version=definition.rule_version,
        message=message,
    )


def evaluate_doc_001(
    readable: bool,
    encrypted: bool,
    format_supported: bool = True,
    detected_format: str = "",
    profile_supported: bool = True,
    profile: str | None = None,
) -> ControlResult:
    definition = CATALOG["DOC-001"]
    if not readable:
        return ControlResult(
            "DOC-001", definition.title, "failed", definition.failure_severity,
            reason_codes=["UNREADABLE_DOCUMENT"], rule_version=definition.rule_version,
            message="The document could not be parsed.",
        )
    if encrypted:
        return ControlResult(
            "DOC-001", definition.title, "failed", definition.failure_severity,
            reason_codes=["ENCRYPTED_DOCUMENT"], rule_version=definition.rule_version,
            message="The document is encrypted or password-protected.",
        )
    if not format_supported:
        return ControlResult(
            "DOC-001", definition.title, "failed", definition.failure_severity,
            reason_codes=["UNSUPPORTED_FORMAT"], rule_version=definition.rule_version,
            message=f"detectedFormat={detected_format!r} is not supported by the "
            "Phase 1 starter profile.",
        )
    if not profile_supported:
        # Distinct from UNSUPPORTED_FORMAT: the format itself (Factur-X) is
        # recognized, but only the EN16931 profile is processable by the
        # starter control profile for now -- minimum/basicwl/basic/extended
        # invoices are legitimately valid Factur-X, just not yet supported
        # by our content controls (see docs/invoice_phase1/control_catalog.md
        # profile-applicability note). XRechnung stays on the separate
        # UNSUPPORTED_FORMAT path above, unaffected by this check.
        return ControlResult(
            "DOC-001", definition.title, "failed", definition.failure_severity,
            reason_codes=["UNSUPPORTED_PROFILE"], rule_version=definition.rule_version,
            message=f"profile={profile!r} is not yet processable; only EN16931 is "
            "supported by the Phase 1 starter profile.",
        )
    return ControlResult("DOC-001", definition.title, "passed", "none", rule_version=definition.rule_version)


def evaluate_str_003(structured_validation: StructuredValidationResult | None) -> ControlResult:
    definition = CATALOG["STR-003"]
    if structured_validation is None:
        return ControlResult(
            "STR-003", definition.title, "not_applicable", "none",
            reason_codes=["NOT_A_STRUCTURED_DOCUMENT"], rule_version=definition.rule_version,
        )
    # The XSD baseline actually used varies by detected profile (see
    # validate/structured.py: "1.09" for en16931, "1.07.2" for the other,
    # still-legacy-baseline recognized levels) -- report the real one used
    # for THIS request, not the catalog's static default.
    rule_version = structured_validation.xsd_version or definition.rule_version
    if structured_validation.xsd_valid:
        return ControlResult("STR-003", definition.title, "passed", "none", rule_version=rule_version)
    return ControlResult(
        "STR-003", definition.title, "failed", definition.failure_severity,
        reason_codes=["XSD_INVALID"], rule_version=rule_version,
        message=structured_validation.xsd_message,
    )


def evaluate_str_004(
    schematron_validation: SchematronValidationResult | None, xsd_valid: bool = True
) -> ControlResult:
    """Official EN16931 Schematron business rules, executed offline via
    saxonche against the vendored Factur-X 1.09 stylesheet (see
    validate/schematron.py). A flag="warning" finding is advisory according
    to the vendored artifact; the three current warnings include PEPPOL and
    Factur-X references. With zero non-warning findings STR-004 currently
    passes, but keeps the warnings visible in `details` rather than silently
    dropping them.

    `xsd_valid=False` means STR-003 already failed: real EN16931 Schematron
    rules assume XSD-valid input (its arithmetic/type conversions are not
    defined for a document that violates the type system XSD itself
    enforces -- confirmed directly: running it against this repo's own
    XSD-invalid fixture, whose invalidity is a non-numeric value in a
    decimal-typed field, makes Saxon raise FORG0001, not produce a
    meaningful business-rule finding). Schematron is not run in that case;
    STR-003 already reported the blocking finding.
    """
    definition = CATALOG["STR-004"]
    if not xsd_valid:
        return ControlResult(
            "STR-004", definition.title, "not_applicable", "none",
            reason_codes=["BLOCKED_BY_XSD_INVALID"], rule_version=definition.rule_version,
            message="Official Schematron business-rule validation requires a structurally "
            "XSD-valid document; not run because STR-003 (XSD) failed.",
        )
    if schematron_validation is None or schematron_validation.status == "not_applicable":
        return ControlResult(
            "STR-004", definition.title, "not_applicable", "none",
            reason_codes=["NOT_A_STRUCTURED_DOCUMENT"], rule_version=definition.rule_version,
        )
    if schematron_validation.status == "unavailable":
        # Never a passed control when Saxon or its bundled resources fail --
        # not_reliable forces nicht_pruefbar via aggregate(), same treatment
        # as any other check this implementation cannot currently perform.
        return ControlResult(
            "STR-004", definition.title, "not_reliable", definition.failure_severity,
            reason_codes=["SCHEMATRON_EXECUTION_UNAVAILABLE"], rule_version=definition.rule_version,
            message="Official Schematron business-rule validation could not be executed: "
            f"{schematron_validation.error_detail}",
        )

    blocking = [f for f in schematron_validation.findings if f.flag != "warning"]
    warnings = [f for f in schematron_validation.findings if f.flag == "warning"]

    def _finding_dict(f):
        return {"ruleId": f.rule_id, "flag": f.flag, "message": f.message, "location": f.location}

    if blocking:
        first = blocking[0]
        message = (
            f"{len(blocking)} official EN16931 business rule(s) failed"
            + (f", {len(warnings)} advisory warning(s)" if warnings else "")
            + f". First: [{first.rule_id}] {first.message}"
        )
        details = {"schematronFindings": [_finding_dict(f) for f in blocking + warnings]}
        return ControlResult(
            "STR-004", definition.title, "failed", definition.failure_severity,
            reason_codes=["SCHEMATRON_RULE_VIOLATION"],
            evidence_refs=[f.rule_id for f in blocking],
            rule_version=definition.rule_version, message=message, details=details,
        )
    if warnings:
        message = f"{len(warnings)} advisory Schematron warning(s), no blocking rule violations."
        details = {"schematronFindings": [_finding_dict(f) for f in warnings]}
        return ControlResult(
            "STR-004", definition.title, "passed", "none",
            evidence_refs=[f.rule_id for f in warnings],
            rule_version=definition.rule_version, message=message, details=details,
        )
    return ControlResult("STR-004", definition.title, "passed", "none", rule_version=definition.rule_version)


def evaluate_extraction_confidence(
    overall_confidence: float, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> ControlResult:
    """Defense in depth alongside the per-field confidence checks: an
    extraction adapter could in principle report high confidence on every
    individual field while its own overall confidence signal says the
    extraction as a whole shouldn't be trusted (a systemic scan-quality
    issue, a partial/garbled read, an adapter bug). Per-field checks alone
    wouldn't catch that -- this does, using the same 0.70 floor as
    everything else, per the reviewed decision to not lower it without
    benchmark evidence.
    """
    definition = CATALOG["DOC-007"]
    if overall_confidence < threshold:
        return ControlResult(
            "DOC-007", definition.title, "not_reliable", definition.failure_severity,
            reason_codes=["LOW_OVERALL_CONFIDENCE"], rule_version=definition.rule_version,
            message=f"Overall extraction confidence {overall_confidence:.2f} is below "
            f"the {threshold:.2f} reliability threshold.",
            details={"expected": f">= {threshold:.2f}", "actual": round(overall_confidence, 2)},
        )
    return ControlResult("DOC-007", definition.title, "passed", "none", rule_version=definition.rule_version)


def _confidence(field_evidence: dict, key: str) -> float:
    """Confidence for a field, defaulting to 1.0 when normalize recorded no
    evidence entry at all -- a structurally absent XML element is exactly as
    confidently "missing" as a PDF field the mock adapter never reported.
    """
    entry = field_evidence.get(key)
    if entry is None:
        return 1.0
    return entry.get("confidence", 1.0)


def _is_empty(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _check(value, field_evidence: dict, key: str, threshold: float) -> tuple:
    """The single place that decides passed/failed/not_reliable for one
    field. `value` MUST come from the canonical `invoice` dict (the single
    source of truth for extracted values) -- confidence is looked up from
    field_evidence separately, so a normalize function that forgets to
    attach evidence for a present field degrades to "fully confident"
    (the safe default for a structured extractor), not to a false
    "missing" verdict. Returns (outcome, reason_codes, evidence_refs, message).
    """
    confidence = _confidence(field_evidence, key)
    if confidence < threshold:
        message = (
            f"{key}: extraction confidence {confidence:.2f} is below the "
            f"{threshold:.2f} reliability threshold."
        )
        return "not_reliable", ["LOW_CONFIDENCE_EXTRACTION"], [key], message
    if _is_empty(value):
        return "failed", ["MISSING_FIELD"], [key], f"{key}: required value is missing."
    return "passed", [], [key], None


def _combine(parts: list[tuple]) -> tuple:
    outcomes = [p[0] for p in parts]
    reason_codes = sorted({rc for p in parts for rc in p[1]})
    evidence_refs = sorted({ref for p in parts for ref in p[2]})
    messages = [p[3] for p in parts if len(p) > 3 and p[3]]
    combined_message = " ".join(messages) if messages else None
    if "not_reliable" in outcomes:
        return "not_reliable", reason_codes, evidence_refs, combined_message
    if "failed" in outcomes:
        return "failed", reason_codes, evidence_refs, combined_message
    return "passed", reason_codes, evidence_refs, None


def _build(
    control_id: str,
    outcome: str,
    reason_codes: list[str],
    evidence_refs: list[str],
    message: Optional[str] = None,
    details: Optional[dict] = None,
) -> ControlResult:
    definition = CATALOG[control_id]
    return ControlResult(
        control_id=control_id,
        title=definition.title,
        outcome=outcome,
        severity=_severity_for(control_id, outcome),
        reason_codes=reason_codes,
        evidence_refs=evidence_refs,
        rule_version=definition.rule_version,
        message=message,
        details=details,
    )


def evaluate_content_controls(
    invoice: dict, field_evidence: dict, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> list[ControlResult]:
    def fv(value, key: str) -> tuple:
        return _check(value, field_evidence, key, threshold)

    supplier, buyer, supply, totals = (
        invoice["supplier"], invoice["buyer"], invoice["supply"], invoice["totals"]
    )
    results = []

    results.append(_build("FRM-001", *_combine([
        fv(supplier["name"], "invoice.supplier.name"), fv(buyer["name"], "invoice.buyer.name"),
    ])))

    results.append(_build("FRM-002", *_combine([
        fv(supplier["address"]["street"], "invoice.supplier.address.street"),
        fv(supplier["address"]["postalCode"], "invoice.supplier.address.postalCode"),
        fv(supplier["address"]["city"], "invoice.supplier.address.city"),
        fv(supplier["address"]["countryCode"], "invoice.supplier.address.countryCode"),
        fv(buyer["address"]["street"], "invoice.buyer.address.street"),
        fv(buyer["address"]["postalCode"], "invoice.buyer.address.postalCode"),
        fv(buyer["address"]["city"], "invoice.buyer.address.city"),
        fv(buyer["address"]["countryCode"], "invoice.buyer.address.countryCode"),
    ])))

    tax_id_status = fv(supplier["taxId"], "invoice.supplier.taxId")
    vat_id_status = fv(supplier["vatId"], "invoice.supplier.vatId")
    if tax_id_status[0] == "passed" or vat_id_status[0] == "passed":
        results.append(_build("FRM-003", "passed", [], sorted(set(tax_id_status[2] + vat_id_status[2]))))
    else:
        results.append(_build("FRM-003", *_combine([tax_id_status, vat_id_status])))

    results.append(_build("FRM-004", *fv(invoice["issueDate"], "invoice.issueDate")))
    results.append(_build("FRM-005", *fv(invoice["invoiceNumber"], "invoice.invoiceNumber")))
    results.append(_build("FRM-006", *fv(supply["description"], "invoice.supply.description")))

    delivery_status = fv(supply["deliveryDate"], "invoice.supply.deliveryDate")
    period_start_status = fv(supply["periodStart"], "invoice.supply.periodStart")
    period_end_status = fv(supply["periodEnd"], "invoice.supply.periodEnd")
    if delivery_status[0] == "passed" or (
        period_start_status[0] == "passed" and period_end_status[0] == "passed"
    ):
        results.append(_build("FRM-007", "passed", [], sorted(set(
            delivery_status[2] + period_start_status[2] + period_end_status[2]
        ))))
    else:
        results.append(_build("FRM-007", *_combine([delivery_status, period_start_status, period_end_status])))

    results.append(_evaluate_cal_001(invoice, field_evidence, threshold))
    results.append(_evaluate_cal_002(invoice, field_evidence, threshold))
    results.append(_evaluate_cal_003(invoice, field_evidence, threshold))
    results.append(_build("CAL-004", *fv(invoice["currency"], "invoice.currency")))

    return results


def _line_item_status(line_item: dict, idx: int, sub_field: str, field_evidence: dict, threshold: float) -> tuple:
    key = f"invoice.lineItems[{idx}].{sub_field}"
    return _check(line_item.get(sub_field), field_evidence, key, threshold)


def _evaluate_cal_001(invoice: dict, field_evidence: dict, threshold: float) -> ControlResult:
    totals = invoice["totals"]
    line_net_status = _check(totals["lineNet"], field_evidence, "invoice.totals.lineNet", threshold)
    line_items = invoice.get("lineItems") or []
    net_statuses = [_line_item_status(li, i, "netAmount", field_evidence, threshold) for i, li in enumerate(line_items)]
    combined = _combine([line_net_status] + net_statuses)
    if combined[0] != "passed":
        return _build("CAL-001", *combined)

    line_net = totals["lineNet"] or 0
    total_net_amount = sum(li.get("netAmount") or 0 for li in line_items)
    tolerance = round(0.02 * max(1, len(line_items)), 2)
    difference = round(line_net - total_net_amount, 2)
    if abs(difference) > tolerance:
        details = {
            "formula": "invoice.totals.lineNet == sum(invoice.lineItems[].netAmount)",
            "expected": round(total_net_amount, 2),
            "actual": round(line_net, 2),
            "difference": difference,
            "tolerance": tolerance,
        }
        message = (
            f"Line net total {line_net:.2f} does not match the sum of line item net "
            f"amounts {total_net_amount:.2f} (difference {difference:.2f}, tolerance "
            f"{tolerance:.2f})."
        )
        return _build("CAL-001", "failed", ["AMOUNT_MISMATCH"], combined[2], message, details)
    return _build("CAL-001", "passed", [], combined[2])


def _evaluate_cal_002(invoice: dict, field_evidence: dict, threshold: float) -> ControlResult:
    totals = invoice["totals"]
    charge_status = _check(totals["chargeTotal"], field_evidence, "invoice.totals.chargeTotal", threshold)
    allowance_status = _check(totals["allowanceTotal"], field_evidence, "invoice.totals.allowanceTotal", threshold)
    if charge_status[0] == "not_reliable" or allowance_status[0] == "not_reliable":
        return _build("CAL-002", *_combine([charge_status, allowance_status]))

    if (totals.get("chargeTotal") or 0) != 0 or (totals.get("allowanceTotal") or 0) != 0:
        # Not a genuine "does not apply" case: a document-level charge or
        # allowance IS present and reliably reported, but this control's
        # Σ(netAmount×vatRate) formula does not account for it, so the
        # tax-consistency check cannot be correctly performed. Reporting
        # not_applicable here would let aggregate() treat this as compatible
        # with unauffaellig -- a false green result for something we simply
        # can't calculate yet. not_reliable forces nicht_pruefbar instead,
        # same as any other check this implementation cannot perform.
        message = (
            "A document-level charge or allowance is present "
            f"(chargeTotal={totals.get('chargeTotal')!r}, "
            f"allowanceTotal={totals.get('allowanceTotal')!r}); this control's tax-"
            "consistency calculation does not yet account for them, so the result "
            "cannot be verified automatically."
        )
        return _build(
            "CAL-002", "not_reliable", ["CONTROL_SCOPE_UNSUPPORTED"],
            sorted(set(charge_status[2] + allowance_status[2])),
            message,
        )

    tax_amount_status = _check(totals["taxAmount"], field_evidence, "invoice.totals.taxAmount", threshold)
    line_items = invoice.get("lineItems") or []
    net_statuses = [_line_item_status(li, i, "netAmount", field_evidence, threshold) for i, li in enumerate(line_items)]
    rate_statuses = [_line_item_status(li, i, "vatRate", field_evidence, threshold) for i, li in enumerate(line_items)]
    combined = _combine([tax_amount_status] + net_statuses + rate_statuses)
    if combined[0] != "passed":
        return _build("CAL-002", *combined)

    expected_tax = sum(
        (li.get("netAmount") or 0) * (li.get("vatRate") or 0) / 100 for li in line_items
    )
    tolerance = round(0.02 * max(1, len(line_items)), 2)
    tax_amount = totals["taxAmount"] or 0
    difference = round(tax_amount - expected_tax, 2)
    if abs(difference) > tolerance:
        details = {
            "formula": "invoice.totals.taxAmount == sum(lineItems[].netAmount * lineItems[].vatRate / 100)",
            "expected": round(expected_tax, 2),
            "actual": round(tax_amount, 2),
            "difference": difference,
            "tolerance": tolerance,
        }
        message = (
            f"Tax amount {tax_amount:.2f} does not match the sum of line-item "
            f"net×VAT-rate amounts {expected_tax:.2f} (difference {difference:.2f}, "
            f"tolerance {tolerance:.2f})."
        )
        return _build("CAL-002", "failed", ["AMOUNT_MISMATCH"], combined[2], message, details)
    return _build("CAL-002", "passed", [], combined[2])


def _evaluate_cal_003(invoice: dict, field_evidence: dict, threshold: float) -> ControlResult:
    """Net, tax, gross, and payable totals reconcile.

    taxBasis/taxAmount/grossAmount/payableAmount are required: a genuinely
    missing value there is a real finding. prepaidAmount (BT-113) and
    roundingAmount (BT-114) are OPTIONAL per EN16931/CII -- most invoices
    have neither. A confidently-absent optional amount means 0, not a
    missing-field failure (this was the bug: a valid EN16931 invoice with no
    TotalPrepaidAmount element used to fail CAL-003 outright). Their
    confidence is still checked, though: a low-confidence or never-extracted
    optional amount must not be silently treated as 0 either.
    """
    totals = invoice["totals"]
    required_keys = ["taxBasis", "taxAmount", "grossAmount", "payableAmount"]
    optional_keys = ["prepaidAmount", "roundingAmount"]

    required_statuses = [
        _check(totals[k], field_evidence, f"invoice.totals.{k}", threshold)
        for k in required_keys
    ]
    optional_statuses = []
    for k in optional_keys:
        key = f"invoice.totals.{k}"
        confidence = _confidence(field_evidence, key)
        if confidence < threshold:
            message = (
                f"{key}: extraction confidence {confidence:.2f} is below the "
                f"{threshold:.2f} reliability threshold."
            )
            optional_statuses.append(("not_reliable", ["LOW_CONFIDENCE_EXTRACTION"], [key], message))
        else:
            optional_statuses.append(("passed", [], [key] if key in field_evidence else [], None))

    combined = _combine(required_statuses + optional_statuses)
    if combined[0] != "passed":
        return _build("CAL-003", *combined)

    tolerance = 0.02
    # BT-114 (roundingAmount) belongs in the payable-amount reconciliation,
    # not the gross-amount one: BT-112 (gross) = BT-109 (taxBasis) +
    # BT-110 (taxAmount); BT-115 (payable) = BT-112 - BT-113 (prepaid) +
    # BT-114 (rounding), per EN16931 BR-CO-16.
    gross_expected = (totals["taxBasis"] or 0) + (totals["taxAmount"] or 0)
    gross_actual = totals["grossAmount"] or 0
    gross_difference = round(gross_actual - gross_expected, 2)
    if abs(gross_difference) > tolerance:
        details = {
            "formula": "invoice.totals.grossAmount == invoice.totals.taxBasis + invoice.totals.taxAmount",
            "expected": round(gross_expected, 2),
            "actual": round(gross_actual, 2),
            "difference": gross_difference,
            "tolerance": tolerance,
        }
        message = (
            f"Gross amount {gross_actual:.2f} does not match taxBasis + taxAmount "
            f"{gross_expected:.2f} (difference {gross_difference:.2f}, tolerance "
            f"{tolerance:.2f})."
        )
        return _build("CAL-003", "failed", ["AMOUNT_MISMATCH"], combined[2], message, details)

    rounding_amount = totals.get("roundingAmount") or 0
    payable_expected = gross_actual - (totals.get("prepaidAmount") or 0) + rounding_amount
    payable_actual = totals["payableAmount"] or 0
    payable_difference = round(payable_actual - payable_expected, 2)
    if abs(payable_difference) > tolerance:
        details = {
            "formula": (
                "invoice.totals.payableAmount == invoice.totals.grossAmount - "
                "invoice.totals.prepaidAmount + invoice.totals.roundingAmount"
            ),
            "expected": round(payable_expected, 2),
            "actual": round(payable_actual, 2),
            "difference": payable_difference,
            "tolerance": tolerance,
        }
        message = (
            f"Payable amount {payable_actual:.2f} does not match grossAmount - "
            f"prepaidAmount + roundingAmount {payable_expected:.2f} (difference "
            f"{payable_difference:.2f}, tolerance {tolerance:.2f})."
        )
        return _build("CAL-003", "failed", ["AMOUNT_MISMATCH"], combined[2], message, details)
    return _build("CAL-003", "passed", [], combined[2])


def _normalize_for_match(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def evaluate_org_001(invoice: dict, field_evidence: dict, master_data: dict, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> ControlResult:
    buyer = invoice["buyer"]
    address = buyer["address"]
    buyer_name = _check(buyer["name"], field_evidence, "invoice.buyer.name", threshold)
    buyer_street = _check(address["street"], field_evidence, "invoice.buyer.address.street", threshold)
    buyer_postal = _check(address["postalCode"], field_evidence, "invoice.buyer.address.postalCode", threshold)
    buyer_city = _check(address["city"], field_evidence, "invoice.buyer.address.city", threshold)
    buyer_country = _check(address["countryCode"], field_evidence, "invoice.buyer.address.countryCode", threshold)
    combined = _combine([buyer_name, buyer_street, buyer_postal, buyer_city, buyer_country])
    if combined[0] != "passed":
        return _build("ORG-001", *combined)

    field_pairs = (
        ("invoice.buyer.name", buyer["name"], master_data["name"]),
        ("invoice.buyer.address.street", address["street"], master_data["street"]),
        ("invoice.buyer.address.postalCode", address["postalCode"], master_data["postalCode"]),
        ("invoice.buyer.address.city", address["city"], master_data["city"]),
        ("invoice.buyer.address.countryCode", address["countryCode"], master_data["countryCode"]),
    )
    mismatches = [
        {"field": field, "expected": expected, "actual": actual}
        for field, actual, expected in field_pairs
        if _normalize_for_match(actual) != _normalize_for_match(expected)
    ]
    if mismatches:
        message = "Buyer data does not match approved organization master data: " + "; ".join(
            f"{m['field']} expected {m['expected']!r}, got {m['actual']!r}" for m in mismatches
        )
        return _build(
            "ORG-001", "failed", ["MASTER_DATA_MISMATCH"], combined[2], message,
            {"mismatches": mismatches},
        )
    return _build("ORG-001", "passed", [], combined[2])
