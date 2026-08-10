"""DigiTax Phase 1 invoice-preprocessing vertical slice.

See docs/invoice_phase1/ for the specification this package implements:
inspect/normalize/validate structured and plain-PDF invoices into the shared
canonical_invoice contract, run the same starter control profile against
both, and return a schema-valid phase1_control_report. This package never
approves, rejects, books, pays, or contacts a supplier.
"""
