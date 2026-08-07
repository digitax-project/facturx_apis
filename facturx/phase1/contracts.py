"""Loads and validates the Phase 1 JSON Schema contracts.

The authoritative, documentation copy of the schemas lives in
docs/invoice_phase1/contracts/*.schema.json. The runtime copy this module
actually loads is packaged inside facturx/phase1/schemas/ (shipped with the
wheel, same pattern as the XSD files under facturx/xsd/ in facturx.py) so
this works from a real pip install, not just from a source checkout.
tests/test_contracts.py asserts the two stay byte-identical.
"""
import importlib.resources
import json
from functools import lru_cache
from typing import Any

import jsonschema

CANONICAL_INVOICE_SCHEMA_FILENAME = "canonical_invoice.schema.json"
PHASE1_CONTROL_REPORT_SCHEMA_FILENAME = "phase1_control_report.schema.json"


@lru_cache(maxsize=None)
def _load_schema(filename: str) -> dict:
    resource = importlib.resources.files(__package__).joinpath("schemas", filename)
    with resource.open("r", encoding="utf-8") as f:
        return json.load(f)


_FORMAT_CHECKER = jsonschema.FormatChecker()


def validate_canonical_invoice(payload: dict[str, Any]) -> None:
    """Raises jsonschema.ValidationError if payload does not match the contract."""
    jsonschema.validate(
        payload,
        _load_schema(CANONICAL_INVOICE_SCHEMA_FILENAME),
        format_checker=_FORMAT_CHECKER,
    )


def validate_phase1_control_report(payload: dict[str, Any]) -> None:
    """Raises jsonschema.ValidationError if payload does not match the contract."""
    jsonschema.validate(
        payload,
        _load_schema(PHASE1_CONTROL_REPORT_SCHEMA_FILENAME),
        format_checker=_FORMAT_CHECKER,
    )
