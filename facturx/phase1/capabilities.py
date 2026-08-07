"""Static capability descriptor for GET /capabilities.

Reports what this service actually supports right now -- including what it
deliberately does NOT support yet -- rather than implying completeness.
Per AGENTS.md: never describe XSD/Schematron validity as proof of legal or
tax compliance, and be explicit when a baseline is outdated.
"""
from .controls.profiles import STARTER_PROFILE

CATALOG_VERSION = "0.1.0"

CAPABILITIES = {
    "structuredFormats": {
        "factur-x": {
            # "Recognized" = detectable and XSD-checkable via /inspect and
            # /validate (all five levels have bundled XSDs). "Processable" =
            # what POST /v1/invoices/process will actually run the starter
            # control profile against. These are deliberately different: a
            # recognized-but-not-processable profile (minimum/basicwl/basic/
            # extended) is legitimately valid Factur-X, just not yet tested
            # against our content controls, and /process reports it as
            # nicht_pruefbar with reason UNSUPPORTED_PROFILE (DOC-001) --
            # distinct from an unrecognized format entirely (UNSUPPORTED_FORMAT).
            "recognizedLevels": [
                "minimum",
                "basicwl",
                "basic",
                "en16931",
                "extended",
            ],
            "processableLevels": ["en16931"],
            "xsdVersion": "1.07.2",
            "legacyBaseline": True,
            "note": (
                "This is the ZUGFeRD 2.3.2 / Factur-X 1.07.2 XSD package, not "
                "the current ZUGFeRD 2.5 / Factur-X 1.09 package. Upgrading is "
                "tracked separately, see the follow-up issue referenced in "
                "docs/invoice_phase1/service_gap_analysis.md. Only en16931 is "
                "processable by POST /v1/invoices/process; other recognized "
                "levels route to nicht_pruefbar/UNSUPPORTED_PROFILE."
            ),
        },
        "xrechnung": {
            "supported": False,
            "note": "Not implemented. Treated as an unsupported detected format.",
        },
    },
    "schematron": {
        "status": "not_implemented",
        "note": (
            "No official Schematron/business-rule artifacts are bundled or "
            "fetched. STR-004 is defined in the control catalog but is not "
            "part of the current starter control profile -- it is never "
            "reported as passed or run."
        ),
    },
    "pdfExtraction": {
        "status": "mock_adapter",
        "note": (
            "Plain-PDF field extraction uses a pluggable, dependency-injected "
            "adapter. The shipped default is a deterministic mock, not a real "
            "OCR/LLM service. It exists to prove the field-evidence/confidence "
            "contract a real adapter must satisfy."
        ),
    },
    "controlProfile": {
        "id": STARTER_PROFILE.id,
        "version": STARTER_PROFILE.version,
        "catalogVersion": CATALOG_VERSION,
        "controlIds": list(STARTER_PROFILE.control_ids),
    },
    "organizationMasterData": {
        "status": "single_demo_snapshot",
        "note": (
            "Only one built-in fictional organization ('unternehmen-x-demo') "
            "is supported. Callers must opt in explicitly; there is no "
            "fallback to demo data for unrecognized organization context."
        ),
    },
}
