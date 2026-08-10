"""Static capability descriptor for GET /capabilities.

Reports what this service actually supports right now -- including what it
deliberately does NOT support yet -- rather than implying completeness.
Per AGENTS.md: never describe XSD/Schematron validity as proof of legal or
tax compliance, and be explicit when a baseline is outdated.
"""
from .controls.profiles import STARTER_PROFILE

CATALOG_VERSION = "0.2.0"

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
            # Per level, since they are genuinely on different XSD baselines
            # right now -- reporting one blanket "xsdVersion" would be
            # dishonest once en16931 moved ahead of the others. See
            # facturx/phase1/resources/facturx-1.09-en16931/PROVENANCE.json
            # for full source/hash/license provenance of the en16931 XSD.
            "xsdBaselines": {
                "en16931": {
                    "version": "1.09",
                    "legacyBaseline": False,
                    "source": (
                        "Vendored from the pinned, PyPI-hash-verified factur-x==6.6 "
                        "wheel (facturx/xsd_and_schematron/facturx-en16931/); "
                        "content-verified as Factur-X 1.09, not 1.09.2 -- see "
                        "PROVENANCE.json."
                    ),
                },
                "minimum": {"version": "1.07.2", "legacyBaseline": True},
                "basicwl": {"version": "1.07.2", "legacyBaseline": True},
                "basic": {"version": "1.07.2", "legacyBaseline": True},
                "extended": {"version": "1.07.2", "legacyBaseline": True},
            },
            "note": (
                "Only en16931 has been upgraded to the current Factur-X 1.09 "
                "XSD baseline; minimum/basicwl/basic/extended remain on the "
                "legacy ZUGFeRD 2.3.2 / Factur-X 1.07.2 package (see "
                "xsdBaselines above) because only en16931 has reviewed "
                "content controls and a reviewed Schematron artifact so far. "
                "The true ZUGFeRD 2.5.2 / Factur-X 1.09.2 corrigendum "
                "(2026-08-04, primarily affecting EXTENDED) is NOT what is "
                "vendored here -- that official package is gated behind a "
                "personal-data registration form with no direct download; "
                "acquiring it is a separate follow-up. Only en16931 is "
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
        "status": "implemented",
        "scope": ["en16931"],
        "artifactVersion": "1.09",
        "engine": "saxonche 13.0.0 (SaxonC-HE, offline execution, no network/Java at runtime)",
        "note": (
            "STR-004 executes the official, vendored, hash-verified Factur-X "
            "1.09 EN16931 compiled Schematron business rules (427 assertions: "
            "424 blocking BR-*/BR-CO-*/BR-S-*/BR-DEC-* rules, 3 advisory "
            "flag=warning PEPPOL-EN16931-R00x recommendations) against "
            "POST /v1/invoices/process and POST /v1/invoices/validate for "
            "en16931 documents only -- not yet reviewed for minimum/basicwl/"
            "basic/extended, where it reports not_applicable/"
            "UNSUPPORTED_PROFILE rather than running unreviewed. If Saxon or "
            "its bundled resources fail, time out, or the output can't be "
            "parsed, STR-004 reports not_reliable (forcing nicht_pruefbar), "
            "never passed."
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
