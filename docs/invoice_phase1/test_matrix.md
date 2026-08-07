# Synthetic acceptance matrix

All fixtures use a fictional `Unternehmen X`. No real invoices, VAT IDs, bank
data, addresses, or free text may be committed.

| ID | Input | Expected path | Expected status |
|---|---|---|---|
| FX-01 | valid ZUGFeRD 2.5 / Factur-X 1.09 EN16931 | embedded XML, official validation, normalize, selected starter profile | unauffaellig |
| FX-02 | valid older explicitly supported Factur-X fixture | version-specific validation and normalize | unauffaellig or hinweis |
| FX-03 | hybrid PDF without embedded XML | no silent PDF fallback unless workflow explicitly allows it | nicht_pruefbar |
| FX-04 | XML with XSD or Schematron failure | structured findings retained | klaerung_erforderlich |
| FX-05 | valid XML with buyer master-data mismatch | ORG-001 finding | klaerung_erforderlich |
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
