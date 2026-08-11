from facturx.phase1.controls.executor import evaluate_org_002
from facturx.phase1.controls.profiles import OPERATING_PROFILE, STARTER_PROFILE
from facturx.phase1.organization_master_data import resolve_master_data


def _supplier_invoice() -> dict:
    return {
        "supplier": {
            "name": "Beispiel Lieferant GmbH",
            "vatId": "DE111111111",
            "taxId": None,
        }
    }


def test_demo_organizations_select_distinct_versioned_profiles():
    x = resolve_master_data("unternehmen-x-demo", False)
    y = resolve_master_data("unternehmen-y-demo", False)

    assert x["controlProfileId"] == STARTER_PROFILE.id
    assert y["controlProfileId"] == OPERATING_PROFILE.id
    assert "ORG-002" not in STARTER_PROFILE.control_ids
    assert "ORG-002" in OPERATING_PROFILE.control_ids


def test_org_002_matches_the_approved_supplier_for_unternehmen_y():
    context = resolve_master_data("unternehmen-y-demo", False)
    result = evaluate_org_002(_supplier_invoice(), {}, context["approvedSuppliers"])

    assert result.outcome == "passed"


def test_org_002_never_accepts_a_low_confidence_identifier():
    context = resolve_master_data("unternehmen-y-demo", False)
    evidence = {
        "invoice.supplier.name": {"confidence": 1.0},
        "invoice.supplier.vatId": {"confidence": 0.4},
    }
    result = evaluate_org_002(
        _supplier_invoice(), evidence, context["approvedSuppliers"]
    )

    assert result.outcome == "not_reliable"
    assert result.reason_codes == ["LOW_CONFIDENCE_EXTRACTION"]
