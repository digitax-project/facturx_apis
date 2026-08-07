# Synthetic acceptance matrix

All fixtures use a fictional `Unternehmen X`. No real invoices, VAT IDs, bank
data, addresses, or free text may be committed.

| ID | Input | Expected path | Expected status |
|---|---|---|---|
| FX-01 | valid ZUGFeRD 2.5 / Factur-X 1.09 EN16931 | embedded XML, official validation, normalize, C01-C08 | unauffaellig |
| FX-02 | valid older explicitly supported Factur-X fixture | version-specific validation and normalize | unauffaellig or hinweis |
| FX-03 | hybrid PDF without embedded XML | no silent PDF fallback unless workflow explicitly allows it | nicht_pruefbar |
| FX-04 | XML with XSD or Schematron failure | structured findings retained | klaerung_erforderlich |
| FX-05 | valid XML with buyer master-data mismatch | C08 finding | klaerung_erforderlich |
| PDF-01 | readable PDF with all minimum fields | OCR/LLM, confidence evidence, normalize, C01 and C03-C08 | unauffaellig |
| PDF-02 | PDF missing invoice number | C03 finding | klaerung_erforderlich |
| PDF-03 | PDF with low-confidence totals | C07 not reliable | nicht_pruefbar |
| PDF-04 | scanned or encrypted unreadable PDF | C01 failure | nicht_pruefbar |
| PDF-05 | PDF with buyer master-data mismatch | C08 finding | klaerung_erforderlich |
| SYS-01 | duplicate source hash/run retry | idempotent result, no duplicate report | original status |
| SYS-02 | Factur-X service unavailable | retry then controlled technical result | nicht_pruefbar |
| SYS-03 | unknown aggregation value | safe fallback | nicht_pruefbar |

Every test asserts the canonical schema, report schema, stable reason codes,
source hash, rule/standard version, and absence of booking or approval actions.
