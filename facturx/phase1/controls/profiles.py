"""Versioned control profiles.

docs/invoice_phase1/control_catalog.md: "an organization selects a versioned
control profile based on invoice type, tax case, risk, available master
data, and implementation maturity." This slice ships exactly one: the
starter profile from automation_boundary.md's example table, now including
STR-004 (official EN16931 Schematron business rules, executed offline via
saxonche against the vendored Factur-X 1.09 artifacts -- see
facturx/phase1/validate/schematron.py and controls/executor.py's
evaluate_str_004()).
"""
from dataclasses import dataclass

from .catalog import CATALOG


@dataclass(frozen=True)
class ControlProfile:
    id: str
    version: str
    control_ids: tuple[str, ...]


STARTER_PROFILE = ControlProfile(
    id="inbound-starter-de-v1",
    # Bumped from 0.1.0: STR-004 (official EN16931 Schematron business rules)
    # is now selected and actually executed, changing which findings this
    # profile can produce for the same input compared to 0.1.0.
    version="0.2.0",
    control_ids=tuple(
        control_id
        for control_id, definition in CATALOG.items()
        if definition.selected_in_starter_profile
    ),
)
