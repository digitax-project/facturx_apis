"""Plain-PDF extraction adapter seam.

docs/invoice_phase1/agent_handover.md asks for one plain-PDF fixture
"supplied through a mock extraction adapter" -- not real OCR/LLM. This module
defines the interface a real adapter (OCR/text extraction plus constrained
LLM mapping, per automation_boundary.md) would implement, plus a
deterministic MockPdfExtractionAdapter used until that real integration
exists. The adapter is selected via FastAPI dependency injection (see
facturx/phase1/api.py), so swapping it in later doesn't touch calling code.

Every extracted field carries its own confidence AND an explicit FieldState
(extracted / confirmed_missing / not_extracted), exactly like a real
OCR/LLM adapter would need to report. This three-way split is required, not
cosmetic: a field the adapter never processed (not_extracted) is not the
same fact as one it positively determined is absent (confirmed_missing).
Conflating them would let an incomplete OCR/LLM run silently masquerade as
a confirmed invoice defect instead of routing to human review. See
FieldState below for the exact contract a real adapter must satisfy, and
AGENTS.md's "Low-confidence or incomplete PDF extraction must route to
human review" rule.
"""
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol


class FieldState(str, Enum):
    """What the adapter is actually claiming about one field.

    EXTRACTED: the adapter read a value (confidence reflects how sure it is
    the value itself is correct).
    CONFIRMED_MISSING: the adapter positively determined the field does not
    exist on the document (confidence reflects how sure it is about that
    absence) -- this is a real business fact and must be able to produce a
    blocking finding (e.g. FRM-005 MISSING_FIELD), not just route to review.
    NOT_EXTRACTED: the adapter did not process this field at all (crashed,
    timed out, wasn't asked, region unreadable, etc.). This is NOT the same
    as a confirmed absence and must never be scored as though it were --
    it always routes to not_reliable/nicht_pruefbar, regardless of any
    confidence value that might otherwise be attached to it.
    """

    EXTRACTED = "extracted"
    CONFIRMED_MISSING = "confirmed_missing"
    NOT_EXTRACTED = "not_extracted"


@dataclass
class PdfFieldValue:
    value: object = None
    confidence: float = 0.0
    state: FieldState = FieldState.EXTRACTED

    def __post_init__(self):
        if self.state == FieldState.NOT_EXTRACTED:
            # A field the adapter never processed can never be scored as
            # reliable, no matter what confidence a caller passed in.
            self.confidence = 0.0
            self.value = None


NOT_EXTRACTED = PdfFieldValue(value=None, confidence=0.0, state=FieldState.NOT_EXTRACTED)


@dataclass
class PdfExtractionResult:
    status: str  # completed | partial | failed
    overall_confidence: float
    fields: dict[str, PdfFieldValue] = field(default_factory=dict)
    line_item_count: int = 0
    warnings: list[str] = field(default_factory=list)


class PdfExtractionAdapter(Protocol):
    def extract(self, pdf_bytes: bytes) -> PdfExtractionResult: ...


class MockPdfExtractionAdapter:
    """Deterministic stand-in for a real OCR/LLM extraction service.

    Results are looked up by the sha256 of the uploaded PDF bytes, seeded by
    the caller (tests seed exactly the scenario they need; a default result
    can be supplied for ad-hoc/demo use). An unseeded file returns a
    "failed" extraction -- the same anticipated outcome a real adapter
    failing to read an unknown document would produce -- rather than raising,
    since that's a content-classification result, not a service crash.
    """

    def __init__(
        self,
        canned: Optional[dict[str, PdfExtractionResult]] = None,
        default: Optional[PdfExtractionResult] = None,
    ):
        self._canned = canned or {}
        self._default = default

    def extract(self, pdf_bytes: bytes) -> PdfExtractionResult:
        sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        if sha256 in self._canned:
            return self._canned[sha256]
        if self._default is not None:
            return self._default
        return PdfExtractionResult(
            status="failed",
            overall_confidence=0.0,
            warnings=["NO_MOCK_RESULT_SEEDED_FOR_THIS_FILE"],
        )


def _get(result: PdfExtractionResult, key: str) -> PdfFieldValue:
    # A key absent from `fields` entirely means the adapter never processed
    # this field at all -- NOT_EXTRACTED, confidence 0.0, which always
    # routes to not_reliable/nicht_pruefbar downstream. This is distinct
    # from CONFIRMED_MISSING (adapter positively determined the field is
    # absent, a real business fact that can produce a blocking finding) and
    # from a low-confidence EXTRACTED value. Conflating "never looked" with
    # "confidently absent" would let incomplete OCR/LLM output masquerade as
    # a genuine invoice defect instead of routing to human review.
    return result.fields.get(key, NOT_EXTRACTED)


def normalize_pdf_extraction(
    result: PdfExtractionResult,
    field_evidence_method: str = "ocr",
) -> tuple[dict, dict, list[str]]:
    """Returns (invoice_dict, field_evidence, warnings) matching the
    `invoice`/`fieldEvidence` parts of canonical_invoice.schema.json.
    Every present field is recorded with its own confidence -- normalize
    never drops or filters by confidence, that's the control executor's job.

    `field_evidence_method` is the per-field `evidence.method` value (see
    canonical_invoice.schema.json's `evidence.method` enum: "xml", "ocr",
    "llm", "derived", "master_data"). Defaults to "ocr" for the vision/OCR
    extraction path (pipeline.py's `ocr_llm` method); the text-structuring
    path for a digitally-born PDF (`text_llm`) passes "llm" instead -- that
    field never went through OCR at all, it was read from the PDF's own
    embedded text layer and only structured by an LLM call.
    """
    warnings = list(result.warnings)
    evidence: dict = {}

    def emit(key: str, locator: str):
        field_value = _get(result, key)
        evidence[key] = {
            "method": field_evidence_method,
            "confidence": field_value.confidence,
            "locator": locator,
            "rawValue": field_value.value,
            "state": field_value.state.value,
        }
        return field_value.value

    invoice_number = emit("invoice.invoiceNumber", "invoice.invoiceNumber")
    issue_date = emit("invoice.issueDate", "invoice.issueDate")
    type_code = emit("invoice.typeCode", "invoice.typeCode")
    currency = emit("invoice.currency", "invoice.currency")

    def party(prefix: str) -> dict:
        return {
            "name": emit(f"invoice.{prefix}.name", f"invoice.{prefix}.name"),
            "address": {
                "street": emit(
                    f"invoice.{prefix}.address.street", f"invoice.{prefix}.address.street"
                ),
                "postalCode": emit(
                    f"invoice.{prefix}.address.postalCode",
                    f"invoice.{prefix}.address.postalCode",
                ),
                "city": emit(f"invoice.{prefix}.address.city", f"invoice.{prefix}.address.city"),
                "countryCode": emit(
                    f"invoice.{prefix}.address.countryCode",
                    f"invoice.{prefix}.address.countryCode",
                ),
            },
            "taxId": emit(f"invoice.{prefix}.taxId", f"invoice.{prefix}.taxId"),
            "vatId": emit(f"invoice.{prefix}.vatId", f"invoice.{prefix}.vatId"),
        }

    supplier = party("supplier")
    buyer = party("buyer")

    supply_description = emit("invoice.supply.description", "invoice.supply.description")
    delivery_date = emit("invoice.supply.deliveryDate", "invoice.supply.deliveryDate")
    period_start = emit("invoice.supply.periodStart", "invoice.supply.periodStart")
    period_end = emit("invoice.supply.periodEnd", "invoice.supply.periodEnd")

    totals = {}
    for field_name in (
        "lineNet",
        "taxBasis",
        "taxAmount",
        "grossAmount",
        "payableAmount",
        "chargeTotal",
        "allowanceTotal",
        "prepaidAmount",
        "roundingAmount",
    ):
        key = f"invoice.totals.{field_name}"
        totals[field_name] = emit(key, key)

    line_items = []
    for idx in range(result.line_item_count):
        line_items.append(
            {
                "description": emit(
                    f"invoice.lineItems[{idx}].description",
                    f"invoice.lineItems[{idx}].description",
                ),
                "quantity": emit(
                    f"invoice.lineItems[{idx}].quantity", f"invoice.lineItems[{idx}].quantity"
                ),
                "netAmount": emit(
                    f"invoice.lineItems[{idx}].netAmount", f"invoice.lineItems[{idx}].netAmount"
                ),
                "vatRate": emit(
                    f"invoice.lineItems[{idx}].vatRate", f"invoice.lineItems[{idx}].vatRate"
                ),
            }
        )

    invoice = {
        "invoiceNumber": invoice_number,
        "issueDate": issue_date,
        "typeCode": type_code,
        "currency": currency,
        "supplier": supplier,
        "buyer": buyer,
        "supply": {
            "description": supply_description,
            "deliveryDate": delivery_date,
            "periodStart": period_start,
            "periodEnd": period_end,
        },
        "totals": totals,
        "lineItems": line_items,
    }
    return invoice, evidence, warnings
