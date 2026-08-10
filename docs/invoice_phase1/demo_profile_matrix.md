# Demo profile and mock-invoice matrix

## Purpose

The synthetic invoices demonstrate how one Phase 1 API applies a shared
technical and invoice-content baseline while selecting additional controls from
the organization's versioned profile. They are not legal test certificates and
do not demonstrate booking, payment, approval, or supplier communication.

## Organization profiles

| Organization | Profile | Additional context |
| --- | --- | --- |
| `unternehmen-x-demo` | `inbound-starter-de-v1` 0.2.0 | Buyer master-data match through `ORG-001` |
| `unternehmen-y-demo` | `inbound-operating-de-v1` 0.1.0 | Buyer match plus approved-supplier match through `ORG-002` |

Both organizations and every invoice are fictional. Profile selection is based
on the explicit `organizationId`; an unknown ID is rejected rather than mapped
to demo data.

## Core cases and profile comparison

| Order | File | Organization | Injected mismatch | Main evidence | Intended message |
| --- | --- | --- | --- | --- | --- |
| 1 | `demo_invoice_valid_unternehmen_x.pdf` | X | none | all applicable controls pass | The starter profile processes a valid structured invoice and still routes it to human standard review. |
| 2 | `demo_invoice_missing_supplier_identifier_unternehmen_x.pdf` | X | one missing supplier identifier | `FRM-003` and `STR-004` | One underlying defect can be detected independently by a DigiTax field control and official Schematron rules. |
| 3 | `demo_invoice_incorrect_payable_unternehmen_x.pdf` | X | one wrong payable amount | `CAL-003` and official `BR-CO-16` through `STR-004` | The report explains the formula, expected amount, actual amount, difference, and tolerance instead of returning only red/green. |
| 3a | `demo_invoice_shared_supplier_unternehmen_x.pdf` | X | supplier not approved by Y | no finding | X does not select `ORG-002`; the same supplier, service, and amounts are therefore not checked against supplier master data. |
| 4 | `demo_invoice_valid_unternehmen_y.pdf` | Y | none | `ORG-002` also passes | The same API can select a richer organization profile without changing the invoice format or n8n workflow. |
| 5 | `demo_invoice_unapproved_supplier_unternehmen_y.pdf` | Y | one unknown supplier identifier | `ORG-002 / SUPPLIER_NOT_APPROVED` | Standards-valid invoice data can still require clarification against organization-specific master data. |
| 6 | `demo_invoice_multiple_mismatches_unternehmen_y.pdf` | Y | wrong buyer city, missing supplier identifier, wrong payable amount | `ORG-001`, `ORG-002`, `FRM-003`, `CAL-003`, `STR-004` | The API retains several independent findings and evidence paths in one report rather than hiding them behind one status. |

## Recommended five-minute demonstration

1. Open the upload page and state the boundary: automated pre-check followed by
   human review, not autonomous approval.
2. Upload case 1 with Unternehmen X to establish the baseline and show the
   profile ID in the report.
3. Upload case 3 to show one arithmetic defect and its concrete explanation.
4. Upload case 4 with Unternehmen Y to show profile selection and `ORG-002`.
5. Upload case 5 to distinguish standard validation from organization-specific
   supplier validation. Compare it with case 3a: recipient-specific fields
   differ, while supplier, service, and amounts remain the same.
6. Upload case 6 only if time permits; use it to show multiple findings grouped
   in one traceable control report.

Generate the files with:

```bash
python examples/demo/generate_demo_invoices.py --output-dir .demo-output
```

The generated manifest records the organization, profile, injected mismatches,
expected routing, file hash, and embedded XML hash for every case.

## Software and artifact provenance

- Hybrid-PDF generation uses the open-source `factur-x` Python project by
  Alexis de Lattre/Akretion: <https://github.com/akretion/factur-x>.
- The pinned upstream package and publisher provenance are recorded on PyPI:
  <https://pypi.org/project/factur-x/>.
- Offline XSLT 2.0 execution uses Saxonica's SaxonC Python binding:
  <https://www.saxonica.com/html/download/c.html>.
- The vendored XSD/Schematron file sources, hashes, and licenses are recorded in
  `facturx/phase1/resources/facturx-1.09-en16931/PROVENANCE.json`.
