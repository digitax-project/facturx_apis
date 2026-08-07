"""Versioned control profiles.

docs/invoice_phase1/control_catalog.md: "an organization selects a versioned
control profile based on invoice type, tax case, risk, available master
data, and implementation maturity." This slice ships exactly one: the
starter profile from automation_boundary.md's example table, minus STR-004
(see catalog.py for why it's excluded rather than selected-but-not-run).
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
    version="0.1.0",
    control_ids=tuple(
        control_id
        for control_id, definition in CATALOG.items()
        if definition.selected_in_starter_profile
    ),
)
