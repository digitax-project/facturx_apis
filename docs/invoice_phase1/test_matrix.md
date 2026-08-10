# Synthetic acceptance matrix

All fixtures use fictional `Unternehmen X` or `Unternehmen Y` data. No real
invoices, VAT IDs, bank data, addresses, or free text may be committed.

| ID | Input | Expected path | Expected status |
|---|---|---|---|
| FX-01 | valid Factur-X 1.09 / ZUGFeRD 2.5 EN16931 | embedded XML, official validation, normalize, selected starter profile | unauffaellig |
| FX-02 | valid recognized but not processable Factur-X profile, currently MINIMUM | detect profile, stop before unreviewed content controls | nicht_pruefbar / UNSUPPORTED_PROFILE |
| FX-03 | PDF without an accepted embedded XML filename | classify as plain PDF; current mock adapter result is test-only and not production evidence | adapter-dependent; must not be presented as structured validation |
| FX-04 | XML with XSD or Schematron failure | structured findings retained | klaerung_erforderlich |
| FX-05 | valid XML with buyer master-data mismatch | ORG-001 finding | klaerung_erforderlich |
| FX-06 | valid XML for Unternehmen Y with an unapproved supplier identifier | operating profile and ORG-002 | klaerung_erforderlich |
| FX-07 | valid XML for Unternehmen Y with several independent mismatches | retain all applicable standard, content, and master-data findings | klaerung_erforderlich |
| PDF-01 | readable PDF with all fields selected by the starter profile | OCR/LLM, confidence evidence, normalize, shared selected controls | unauffaellig |
| PDF-02 | PDF missing invoice number | FRM-005 finding | klaerung_erforderlich |
| PDF-03 | PDF with low-confidence totals | applicable CAL control not reliable | nicht_pruefbar |
| PDF-04 | scanned or encrypted unreadable PDF | DOC-001 failure | nicht_pruefbar |
| PDF-05 | PDF with buyer master-data mismatch | ORG-001 finding | klaerung_erforderlich |
| SYS-01 | duplicate source hash/run retry | idempotent result, no duplicate report | original status |
| SYS-02 | Factur-X service unavailable | retry then controlled technical result | nicht_pruefbar |
| SYS-03 | unknown aggregation value | safe fallback | nicht_pruefbar |

Every test asserts the canonical schema, report schema, catalog/profile ID,
stable reason codes, source hash, rule/standard version, and absence of booking
or approval actions.
