"""Control metadata for the candidate catalog described in
docs/invoice_phase1/control_catalog.md. Only a subset is selected into the
starter control profile (see profiles.py); everything here is defined so it
isn't forgotten, not so it's implicitly claimed to run.

`failureSeverity` is the severity used when a control's outcome is `failed`.
`ruleVersion` is retained on every control result per EVD-003.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ControlDefinition:
    control_id: str
    title: str
    failure_severity: str  # blocking | warning | info
    rule_version: str
    selected_in_starter_profile: bool
    exclusion_reason: str | None = None


CATALOG: dict[str, ControlDefinition] = {
    "DOC-001": ControlDefinition(
        "DOC-001",
        "Input readable, supported, and not encrypted",
        "blocking",
        "1.0.0",
        selected_in_starter_profile=True,
    ),
    "STR-003": ControlDefinition(
        "STR-003",
        "Structured document valid for detected XSD",
        "blocking",
        # Default/fallback label only -- evaluate_str_003() overrides this with
        # the XSD baseline actually used for the request (see
        # validate/structured.py: "1.09" for en16931, "1.07.2" for the other,
        # still-legacy-baseline recognized levels).
        "1.09",
        selected_in_starter_profile=True,
    ),
    "DOC-007": ControlDefinition(
        "DOC-007",
        "Overall extraction confidence sufficient for reliable assessment",
        "blocking",
        "1.0.0",
        selected_in_starter_profile=True,
    ),
    "STR-004": ControlDefinition(
        "STR-004",
        "Official structured business rules (Schematron) satisfied",
        "blocking",
        "1.09",
        selected_in_starter_profile=True,
    ),
    "FRM-001": ControlDefinition(
        "FRM-001", "Supplier and buyer names present", "blocking", "1.0.0", True
    ),
    "FRM-002": ControlDefinition(
        "FRM-002", "Supplier and buyer addresses present", "blocking", "1.0.0", True
    ),
    "FRM-003": ControlDefinition(
        "FRM-003", "Supplier tax number or VAT ID present", "blocking", "1.0.0", True
    ),
    "FRM-004": ControlDefinition(
        "FRM-004", "Issue date present", "blocking", "1.0.0", True
    ),
    "FRM-005": ControlDefinition(
        "FRM-005", "Invoice number present", "blocking", "1.0.0", True
    ),
    "FRM-006": ControlDefinition(
        "FRM-006", "Quantity/type of goods or scope/type of service described",
        "blocking", "1.0.0", True,
    ),
    "FRM-007": ControlDefinition(
        "FRM-007",
        "Delivery/service date or period present when applicable",
        "warning",
        "1.0.0",
        True,
    ),
    "CAL-001": ControlDefinition(
        "CAL-001", "Line net amounts arithmetically consistent", "blocking", "1.0.0", True
    ),
    "CAL-002": ControlDefinition(
        "CAL-002",
        "Tax bases and tax amounts consistent with rates and rounding rules",
        "blocking",
        "1.0.0",
        True,
    ),
    "CAL-003": ControlDefinition(
        "CAL-003",
        "Net, tax, gross, and payable totals reconcile",
        "blocking",
        "1.0.0",
        True,
    ),
    "CAL-004": ControlDefinition(
        "CAL-004", "Currency present and used consistently", "blocking", "1.0.0", True
    ),
    "ORG-001": ControlDefinition(
        "ORG-001",
        "Buyer data match approved organization master data",
        "blocking",
        "1.0.0",
        True,
    ),
}
