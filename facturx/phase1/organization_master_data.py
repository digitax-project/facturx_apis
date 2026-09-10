"""Built-in synthetic organization contexts for the reproducible demo.

These are fixtures, not a multi-tenant persistence implementation. Callers must
select a known fictional organization explicitly; ``demoMode=true`` selects
Unternehmen X only. There is no fallback for an unknown organization ID.
"""

from .controls.profiles import OPERATING_PROFILE, STARTER_PROFILE

DEMO_ORGANIZATION_ID = "unternehmen-x-demo"
UNTERNEHMEN_Y_ID = "unternehmen-y-demo"

UNTERNEHMEN_X_CONTEXT = {
    "organizationId": DEMO_ORGANIZATION_ID,
    "controlProfileId": STARTER_PROFILE.id,
    "buyer": {
        "name": "Unternehmen X",
        "street": "Musterweg 10",
        "postalCode": "04109",
        "city": "Leipzig",
        "countryCode": "DE",
    },
    "approvedSuppliers": [],
}

UNTERNEHMEN_Y_CONTEXT = {
    "organizationId": UNTERNEHMEN_Y_ID,
    "controlProfileId": OPERATING_PROFILE.id,
    "buyer": {
        "name": "Unternehmen Y",
        "street": "Industriestrasse 20",
        "postalCode": "01067",
        "city": "Dresden",
        "countryCode": "DE",
    },
    "approvedSuppliers": [
        {
            "supplierId": "SUP-DE-001",
            "name": "Beispiel Lieferant GmbH",
            "vatId": "DE111111111",
            "taxId": None,
        }
    ],
}

ORGANIZATION_CONTEXTS = {
    DEMO_ORGANIZATION_ID: UNTERNEHMEN_X_CONTEXT,
    UNTERNEHMEN_Y_ID: UNTERNEHMEN_Y_CONTEXT,
}


def resolve_master_data(organization_id: str | None, demo_mode: bool) -> dict | None:
    """Return a known synthetic context without silently accepting unknown IDs."""
    resolved_id = DEMO_ORGANIZATION_ID if demo_mode and not organization_id else organization_id
    return ORGANIZATION_CONTEXTS.get(resolved_id)


def build_buyer_master_data_context(
    organization_id: str | None,
    control_profile_id: str,
    buyer_master_data: dict,
) -> dict:
    """Builds the same organization-context shape `resolve_master_data`
    returns, directly from a real caller's own data instead of a hardcoded
    fixture -- the path any real (non-demo) organization goes through.
    `approvedSuppliers` has no TCMS-side data model yet, so it always
    defaults to empty here; a control profile that requires ORG-002 for a
    real organization is out of scope until that data model exists.
    """
    return {
        "organizationId": organization_id,
        "controlProfileId": control_profile_id,
        "buyer": {
            "name": buyer_master_data["name"],
            "street": buyer_master_data["street"],
            "postalCode": buyer_master_data["postalCode"],
            "city": buyer_master_data["city"],
            "countryCode": buyer_master_data["countryCode"],
            "alternateAddresses": buyer_master_data.get("alternateAddresses", []),
        },
        "approvedSuppliers": [],
    }
