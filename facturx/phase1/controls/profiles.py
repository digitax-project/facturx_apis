"""Versioned control profiles.

docs/invoice_phase1/control_catalog.md: "an organization selects a versioned
control profile based on invoice type, tax case, risk, available master
data, and implementation maturity." This slice ships a starter profile and
one operating demo profile. The starter profile includes
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


OPERATING_PROFILE = ControlProfile(
    id="inbound-operating-de-v1",
    version="0.1.0",
    control_ids=STARTER_PROFILE.control_ids + ("ORG-002",),
)


PROFILES = {
    STARTER_PROFILE.id: STARTER_PROFILE,
    OPERATING_PROFILE.id: OPERATING_PROFILE,
}


def get_control_profile(profile_id: str) -> ControlProfile:
    return PROFILES[profile_id]
