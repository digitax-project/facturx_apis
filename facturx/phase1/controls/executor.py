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
"""
from dataclasses import dataclass, field as dc_field

from .catalog import CATALOG
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


def evaluate_doc_001(readable: bool, encrypted: bool, format_supported: bool = True, detected_format: str = "") -> ControlResult:
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
    return ControlResult("DOC-001", definition.title, "passed", "none", rule_version=definition.rule_version)


def evaluate_str_003(structured_validation: StructuredValidationResult | None) -> ControlResult:
    definition = CATALOG["STR-003"]
    if structured_validation is None:
        return ControlResult(
            "STR-003", definition.title, "not_applicable", "none",
            reason_codes=["NOT_A_STRUCTURED_DOCUMENT"], rule_version=definition.rule_version,
        )
    if structured_validation.xsd_valid:
        return ControlResult("STR-003", definition.title, "passed", "none", rule_version=definition.rule_version)
    return ControlResult(
        "STR-003", definition.title, "failed", definition.failure_severity,
        reason_codes=["XSD_INVALID"], rule_version=definition.rule_version,
        message=structured_validation.xsd_message,
    )


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
    "missing" verdict.
    """
    confidence = _confidence(field_evidence, key)
    if confidence < threshold:
        return "not_reliable", ["LOW_CONFIDENCE_EXTRACTION"], [key]
    if _is_empty(value):
        return "failed", ["MISSING_FIELD"], [key]
    return "passed", [], [key]


def _combine(parts: list[tuple]) -> tuple:
    outcomes = [p[0] for p in parts]
    reason_codes = sorted({rc for p in parts for rc in p[1]})
    evidence_refs = sorted({ref for p in parts for ref in p[2]})
    if "not_reliable" in outcomes:
        return "not_reliable", reason_codes, evidence_refs
    if "failed" in outcomes:
        return "failed", reason_codes, evidence_refs
    return "passed", reason_codes, evidence_refs


def _build(control_id: str, outcome: str, reason_codes: list[str], evidence_refs: list[str]) -> ControlResult:
    definition = CATALOG[control_id]
    return ControlResult(
        control_id=control_id,
        title=definition.title,
        outcome=outcome,
        severity=_severity_for(control_id, outcome),
        reason_codes=reason_codes,
        evidence_refs=evidence_refs,
        rule_version=definition.rule_version,
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

    line_net = totals["lineNet"]
    total_net_amount = sum(li.get("netAmount") or 0 for li in line_items)
    tolerance = 0.02 * max(1, len(line_items))
    if abs((line_net or 0) - total_net_amount) > tolerance:
        return _build("CAL-001", "failed", ["AMOUNT_MISMATCH"], combined[2])
    return _build("CAL-001", "passed", [], combined[2])


def _evaluate_cal_002(invoice: dict, field_evidence: dict, threshold: float) -> ControlResult:
    totals = invoice["totals"]
    charge_status = _check(totals["chargeTotal"], field_evidence, "invoice.totals.chargeTotal", threshold)
    allowance_status = _check(totals["allowanceTotal"], field_evidence, "invoice.totals.allowanceTotal", threshold)
    if charge_status[0] == "not_reliable" or allowance_status[0] == "not_reliable":
        return _build("CAL-002", *_combine([charge_status, allowance_status]))

    if (totals.get("chargeTotal") or 0) != 0 or (totals.get("allowanceTotal") or 0) != 0:
        return _build(
            "CAL-002", "not_applicable", ["DOCUMENT_LEVEL_ALLOWANCE_OR_CHARGE_PRESENT"],
            sorted(set(charge_status[2] + allowance_status[2])),
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
    tolerance = 0.02 * max(1, len(line_items))
    tax_amount = totals["taxAmount"] or 0
    if abs(tax_amount - expected_tax) > tolerance:
        return _build("CAL-002", "failed", ["AMOUNT_MISMATCH"], combined[2])
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
            optional_statuses.append(("not_reliable", ["LOW_CONFIDENCE_EXTRACTION"], [key]))
        else:
            optional_statuses.append(("passed", [], [key] if key in field_evidence else []))

    combined = _combine(required_statuses + optional_statuses)
    if combined[0] != "passed":
        return _build("CAL-003", *combined)

    tolerance = 0.02
    # BT-114 (roundingAmount) belongs in the payable-amount reconciliation,
    # not the gross-amount one: BT-112 (gross) = BT-109 (taxBasis) +
    # BT-110 (taxAmount); BT-115 (payable) = BT-112 - BT-113 (prepaid) +
    # BT-114 (rounding), per EN16931 BR-CO-16. A non-zero rounding amount
    # was previously added into the gross-amount check instead, which could
    # produce a spurious AMOUNT_MISMATCH on a perfectly reconciling invoice.
    gross_expected = (totals["taxBasis"] or 0) + (totals["taxAmount"] or 0)
    if abs((totals["grossAmount"] or 0) - gross_expected) > tolerance:
        return _build("CAL-003", "failed", ["AMOUNT_MISMATCH"], combined[2])
    rounding_amount = totals.get("roundingAmount") or 0
    payable_expected = (totals["grossAmount"] or 0) - (totals.get("prepaidAmount") or 0) + rounding_amount
    if abs((totals["payableAmount"] or 0) - payable_expected) > tolerance:
        return _build("CAL-003", "failed", ["AMOUNT_MISMATCH"], combined[2])
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
    combined = _combine([buyer_name, buyer_street, buyer_postal, buyer_city])
    if combined[0] != "passed":
        return _build("ORG-001", *combined)

    matches = (
        _normalize_for_match(buyer["name"]) == _normalize_for_match(master_data["name"])
        and _normalize_for_match(address["street"]) == _normalize_for_match(master_data["street"])
        and _normalize_for_match(address["postalCode"]) == _normalize_for_match(master_data["postalCode"])
        and _normalize_for_match(address["city"]) == _normalize_for_match(master_data["city"])
    )
    if not matches:
        return _build("ORG-001", "failed", ["MASTER_DATA_MISMATCH"], combined[2])
    return _build("ORG-001", "passed", [], combined[2])
