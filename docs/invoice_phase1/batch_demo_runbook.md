# Batch demo runbook

## Start

```powershell
powershell -ExecutionPolicy Bypass -File examples/n8n/scripts/Manage-Phase1UploadDemo.ps1 -Action Start
```

Open <http://localhost:6970/demo/batch>. The stack should remain running during
the presentation. The dashboard sends every invoice through n8n and the Phase 1
API; it performs no invoice controls in the browser.

## 1. Unternehmen X batch

Select these files together from `.demo-output`:

- `demo_invoice_valid_unternehmen_x.pdf`
- `demo_invoice_missing_supplier_identifier_unternehmen_x.pdf`
- `demo_invoice_incorrect_payable_unternehmen_x.pdf`

Click **Run X batch**. Explain that the three rows use the same starter profile
but produce a baseline, a required-information finding, and an arithmetic
finding. The report retains concrete reason codes and evidence instead of only
showing a red/green result.

## 2. Unternehmen Y batch

Select these files together:

- `demo_invoice_valid_unternehmen_y.pdf`
- `demo_invoice_unapproved_supplier_unternehmen_y.pdf`
- `demo_invoice_multiple_mismatches_unternehmen_y.pdf`

Click **Run Y batch**. Point out that the profile column changes to
`inbound-operating-de-v1`. This profile adds `ORG-002`, so the service can use
approved supplier master data in addition to the shared baseline.

## 3. Consolidated table and Excel

Explain the table from left to right:

1. **Input/context:** batch, file and organization.
2. **Applied logic:** the exact versioned control profile.
3. **Invoice facts:** number, supplier and payable amount.
4. **Review result:** status, routing, finding count and finding families.

Click a row to show complete findings. Then click **Export to Excel**. The API
creates a real `.xlsx` workbook containing the visible result columns.

## 4. Paired profile comparison

Click **Run paired profile comparison**. The generator creates two invoices
with the same supplier, service, line items and amounts. Recipient-specific
fields differ because each valid invoice must identify its actual buyer.

- Unternehmen X: `unauffaellig`, because its starter profile does not select
  supplier-master-data control `ORG-002`.
- Unternehmen Y: `klaerung_erforderlich`, because `ORG-002` reports
  `SUPPLIER_NOT_APPROVED`.

The intended conclusion is not that one invoice is universally correct and the
other wrong. The conclusion is that an organization's selected controls and
available reference data determine which additional mismatches can be found.

## 5. Synthetic X batch

Click **Generate and run X batch**. The current generator is deterministic and
template-based. It creates a valid invoice, one missing a supplier identifier,
and one with an incorrect payable amount, then sends them through the same n8n
and API path as manually uploaded files.

This demonstrates the future experiment boundary: an LLM may later select or
construct synthetic scenarios, but the generated Factur-X document must still
pass technical generation checks, and expected findings must still be verified
against the deterministic control report.

## Claims and boundaries

- The demo shows automated pre-checking and explainable routing to human review.
- It does not approve, reject, book, pay, or contact a supplier.
- Synthetic generation is not evidence of legal correctness.
- Unternehmen X and Y are fictional in-memory contexts, not a production
  multi-tenant master-data implementation.
