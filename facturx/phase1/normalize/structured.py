"""Normalizes a Factur-X/ZUGFeRD Cross Industry Invoice (CII) XML tree into
the shared canonical_invoice contract (docs/invoice_phase1/contracts/canonical_invoice.schema.json).

Embedded XML is the authoritative machine input for structured invoices
(AGENTS.md Phase 1 Rules), so every extracted field is recorded with
method="xml", confidence=1.0, and a BT-<n> locator per
docs/invoice_phase1/examples/canonical_invoice.example.json.
"""
from datetime import datetime
from typing import Optional

from lxml import etree

from ...facturx import XML_NAMESPACES

_NS = XML_NAMESPACES["factur-x"]


def _text(node, path: str) -> Optional[str]:
    result = node.xpath(path, namespaces=_NS)
    if not result:
        return None
    value = result[0].text
    return value.strip() if value else None


def _first(node, path: str):
    result = node.xpath(path, namespaces=_NS)
    return result[0] if result else None


def _udt_date(node, path: str) -> Optional[str]:
    """Parses a udt:DateTimeString[@format='102'] (CCYYMMDD) node into ISO 8601."""
    el = _first(node, path)
    if el is None or not el.text:
        return None
    raw = el.text.strip()
    fmt = el.get("format", "102")
    if fmt != "102" or len(raw) != 8:
        return None
    try:
        return datetime.strptime(raw, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _number(node, path: str) -> Optional[float]:
    text = _text(node, path)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _evidence(locator: str, raw_value, confidence: float = 1.0, method: str = "xml"):
    return {
        "method": method,
        "confidence": confidence,
        "locator": locator,
        "rawValue": raw_value,
    }


def _party(node, party_path: str, prefix: str, evidence: dict) -> dict:
    party_node = _first(node, party_path)
    if party_node is None:
        return {
            "name": None,
            "address": {"street": None, "postalCode": None, "city": None, "countryCode": None},
            "taxId": None,
            "vatId": None,
        }
    name = _text(party_node, "ram:Name")
    street = _text(party_node, "ram:PostalTradeAddress/ram:LineOne")
    postal_code = _text(party_node, "ram:PostalTradeAddress/ram:PostcodeCode")
    city = _text(party_node, "ram:PostalTradeAddress/ram:CityName")
    country = _text(party_node, "ram:PostalTradeAddress/ram:CountryID")
    vat_id = _text(party_node, "ram:SpecifiedTaxRegistration[ram:ID/@schemeID='VA']/ram:ID")
    tax_id = _text(party_node, "ram:SpecifiedTaxRegistration[ram:ID/@schemeID='FC']/ram:ID")

    if name is not None:
        evidence[f"invoice.{prefix}.name"] = _evidence(f"{prefix}:name", name)
    if street is not None:
        evidence[f"invoice.{prefix}.address.street"] = _evidence(f"{prefix}:address:street", street)
    if postal_code is not None:
        evidence[f"invoice.{prefix}.address.postalCode"] = _evidence(f"{prefix}:address:postalCode", postal_code)
    if city is not None:
        evidence[f"invoice.{prefix}.address.city"] = _evidence(f"{prefix}:address:city", city)
    if country is not None:
        evidence[f"invoice.{prefix}.address.countryCode"] = _evidence(f"{prefix}:address:countryCode", country)
    if vat_id is not None:
        evidence[f"invoice.{prefix}.vatId"] = _evidence("BT-31/BT-48", vat_id)
    if tax_id is not None:
        evidence[f"invoice.{prefix}.taxId"] = _evidence("BT-32/BT-49", tax_id)

    return {
        "name": name,
        "address": {
            "street": street,
            "postalCode": postal_code,
            "city": city,
            "countryCode": country,
        },
        "taxId": tax_id,
        "vatId": vat_id,
    }


def normalize_structured_invoice(xml_etree: etree._Element) -> tuple[dict, dict, list[str]]:
    """Returns (invoice_dict, field_evidence, warnings) matching the
    `invoice`/`fieldEvidence` parts of canonical_invoice.schema.json."""
    warnings: list[str] = []
    evidence: dict = {}

    invoice_number = _text(xml_etree, "//rsm:ExchangedDocument/ram:ID")
    if invoice_number is not None:
        evidence["invoice.invoiceNumber"] = _evidence("BT-1", invoice_number)

    type_code = _text(xml_etree, "//rsm:ExchangedDocument/ram:TypeCode")

    issue_date = _udt_date(
        xml_etree, "//rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString"
    )
    if issue_date is not None:
        evidence["invoice.issueDate"] = _evidence("BT-2", issue_date)

    currency = _text(
        xml_etree,
        "//ram:ApplicableHeaderTradeSettlement/ram:InvoiceCurrencyCode",
    )
    if currency is not None:
        evidence["invoice.currency"] = _evidence("BT-5", currency)

    supplier = _party(
        xml_etree,
        "//ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty",
        "supplier",
        evidence,
    )
    buyer = _party(
        xml_etree,
        "//ram:ApplicableHeaderTradeAgreement/ram:BuyerTradeParty",
        "buyer",
        evidence,
    )

    supply_description = _text(
        xml_etree, "//ram:IncludedSupplyChainTradeLineItem[1]/ram:SpecifiedTradeProduct/ram:Name"
    )
    delivery_date = _udt_date(
        xml_etree,
        "//ram:ApplicableHeaderTradeDelivery/ram:ActualDeliverySupplyChainEvent"
        "/ram:OccurrenceDateTime/udt:DateTimeString",
    )
    period_start = _udt_date(
        xml_etree,
        "//ram:ApplicableHeaderTradeSettlement/ram:BillingSpecifiedPeriod"
        "/ram:StartDateTime/udt:DateTimeString",
    )
    period_end = _udt_date(
        xml_etree,
        "//ram:ApplicableHeaderTradeSettlement/ram:BillingSpecifiedPeriod"
        "/ram:EndDateTime/udt:DateTimeString",
    )
    if delivery_date is not None:
        evidence["invoice.supply.deliveryDate"] = _evidence("BT-72", delivery_date)
    if supply_description is not None:
        evidence["invoice.supply.description"] = _evidence("BT-153", supply_description)

    summation_path = (
        "//ram:ApplicableHeaderTradeSettlement"
        "/ram:SpecifiedTradeSettlementHeaderMonetarySummation"
    )
    line_net = _number(xml_etree, f"{summation_path}/ram:LineTotalAmount")
    charge_total = _number(xml_etree, f"{summation_path}/ram:ChargeTotalAmount")
    allowance_total = _number(xml_etree, f"{summation_path}/ram:AllowanceTotalAmount")
    tax_basis = _number(xml_etree, f"{summation_path}/ram:TaxBasisTotalAmount")
    tax_amount = _number(xml_etree, f"{summation_path}/ram:TaxTotalAmount")
    gross_amount = _number(xml_etree, f"{summation_path}/ram:GrandTotalAmount")
    prepaid_amount = _number(xml_etree, f"{summation_path}/ram:TotalPrepaidAmount")
    rounding_amount = _number(xml_etree, f"{summation_path}/ram:RoundingAmount")
    payable_amount = _number(xml_etree, f"{summation_path}/ram:DuePayableAmount")

    for field_name, locator, value in (
        ("lineNet", "BT-106", line_net),
        ("taxBasis", "BT-109", tax_basis),
        ("taxAmount", "BT-110", tax_amount),
        ("grossAmount", "BT-112", gross_amount),
        ("payableAmount", "BT-115", payable_amount),
        ("chargeTotal", "BT-108", charge_total),
        ("allowanceTotal", "BT-107", allowance_total),
        ("prepaidAmount", "BT-113", prepaid_amount),
        ("roundingAmount", "BT-114", rounding_amount),
    ):
        if value is not None:
            evidence[f"invoice.totals.{field_name}"] = _evidence(locator, value)

    line_items = []
    for idx, line_node in enumerate(
        xml_etree.xpath("//ram:IncludedSupplyChainTradeLineItem", namespaces=_NS), start=1
    ):
        description = _text(line_node, "ram:SpecifiedTradeProduct/ram:Name")
        quantity = _number(line_node, "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity")
        net_amount = _number(
            line_node,
            "ram:SpecifiedLineTradeSettlement/ram:SpecifiedTradeSettlementLineMonetarySummation"
            "/ram:LineTotalAmount",
        )
        vat_rate = _number(
            line_node,
            "ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax/ram:RateApplicablePercent",
        )
        line_items.append(
            {
                "description": description,
                "quantity": quantity,
                "netAmount": net_amount,
                "vatRate": vat_rate,
            }
        )
        if net_amount is not None:
            evidence[f"invoice.lineItems[{idx - 1}].netAmount"] = _evidence(
                f"BT-131 (line {idx})", net_amount
            )
        if vat_rate is not None:
            evidence[f"invoice.lineItems[{idx - 1}].vatRate"] = _evidence(
                f"BT-152 (line {idx})", vat_rate
            )
        if quantity is not None:
            evidence[f"invoice.lineItems[{idx - 1}].quantity"] = _evidence(
                f"BT-129 (line {idx})", quantity
            )
        if description is not None:
            evidence[f"invoice.lineItems[{idx - 1}].description"] = _evidence(
                f"BT-153 (line {idx})", description
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
        "totals": {
            "lineNet": line_net,
            "taxBasis": tax_basis,
            "taxAmount": tax_amount,
            "grossAmount": gross_amount,
            "payableAmount": payable_amount,
            "chargeTotal": charge_total,
            "allowanceTotal": allowance_total,
            "prepaidAmount": prepaid_amount,
            "roundingAmount": rounding_amount,
        },
        "lineItems": line_items,
    }
    return invoice, evidence, warnings
