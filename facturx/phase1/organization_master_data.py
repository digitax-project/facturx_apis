"""The one built-in synthetic organization master-data snapshot for this slice.

Real multi-tenant master-data loading (a lookup by organizationId against an
approved organization's own data) is wave-2 scope (control_catalog.md, ORG-002+).
This slice ships exactly one fictional demo snapshot ("Unternehmen X", matching
docs/invoice_phase1/examples/canonical_invoice.example.json) and requires callers
to opt into it explicitly -- there is no silent fallback to demo data for an
unrecognized or missing organization context. See ORGANIZATION_CONTEXT_REQUIRED
in facturx/phase1/errors.py / api.py.
"""

DEMO_ORGANIZATION_ID = "unternehmen-x-demo"

UNTERNEHMEN_X_SNAPSHOT = {
    "name": "Unternehmen X",
    "street": "Musterweg 10",
    "postalCode": "04109",
    "city": "Leipzig",
    "countryCode": "DE",
}


def resolve_master_data(organization_id: str | None, demo_mode: bool) -> dict | None:
    """Returns the master-data snapshot for the given context, or None if the
    caller did not explicitly opt into the one supported demo organization.
    """
    if demo_mode or organization_id == DEMO_ORGANIZATION_ID:
        return UNTERNEHMEN_X_SNAPSHOT
    return None
