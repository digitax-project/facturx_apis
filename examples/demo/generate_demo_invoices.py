"""Generates readable, synthetic hybrid Factur-X 1.09 EN16931 demo PDFs from
the already-accepted XML fixtures in tests/fixtures/ -- for the 2026-08-10
afternoon demo (see coordination/claude-codex/2026-08-10_afternoon-demo-plan.md,
workstream A).

Does NOT invent any new standard rule or fixture content: every visible field
on the generated PDF page is read directly from the same
normalize_structured_invoice() parse of the accepted XML fixture that gets
embedded into the same PDF, via facturx.facturx.generate_from_binary() (the
same library call already used by this repo's own tests, e.g.
tests/conftest.py's valid_hybrid_pdf_bytes fixture). This means the visible
page and the embedded machine-readable XML are structurally guaranteed to
agree -- there is no separate hand-transcribed copy of the invoice data that
could silently drift from the XML.

Usage:
    python examples/demo/generate_demo_invoices.py

Requires `reportlab` (not a runtime API dependency -- see requirements-dev.txt).

Output: writes PDFs, source XML copies, and a manifest.json into
C:/Users/Tyto/Desktop/diss/ResearchAssistant/output/demo/invoice_phase1/2026-08-10/
(a shared, non-repo output area used across this afternoon's demo workstreams
-- NOT part of the facturx_apis git repository). The XML fixtures and this
generator, in tests/fixtures/ and here, remain the reproducible source; the
files under output/ are regenerable review copies, not the source of truth.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Force THIS worktree's facturx package to win over any stale editable
# install registered elsewhere on this machine (confirmed necessary: a
# plain `import facturx` here resolved to an unrelated C:\Agentic\facturx
# checkout without facturx.phase1 at all, via pip's PEP 660 editable-install
# finder, until this repo root was placed first on sys.path).
sys.path.insert(0, str(REPO_ROOT))

from pypdf import PdfWriter  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from facturx.facturx import generate_from_binary  # noqa: E402
from facturx.phase1.document_intake import _parse_untrusted_xml  # noqa: E402
from facturx.phase1.normalize.structured import normalize_structured_invoice  # noqa: E402
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
OUTPUT_DIR = Path(
    r"C:\Users\Tyto\Desktop\diss\ResearchAssistant\output\demo\invoice_phase1\2026-08-10"
)

FACTURX_LABEL = "Factur-X 1.09 EN16931"  # never "1.09.2" -- see PROVENANCE.json

SCENARIOS = [
    {
        "id": "valid",
        "xmlFixture": "facturx_valid_en16931.xml",
        "outputBasename": "demo_invoice_valid_unternehmen_x",
        "scenario": "Valid EN16931 invoice, all totals reconcile.",
        "expectedStatus": "unauffaellig",
        "expectedRouting": "standard_review",
        "expectedFindings": "None -- all applicable controls (incl. STR-003 XSD and STR-004 Schematron) pass.",
    },
    {
        "id": "incorrect_payable",
        "xmlFixture": "facturx_incorrect_payable.xml",
        "outputBasename": "demo_invoice_incorrect_payable_unternehmen_x",
        "scenario": (
            "XSD-valid, grossAmount correct, but DuePayableAmount does not "
            "equal grossAmount - prepaidAmount + roundingAmount (isolates "
            "the payable-reconciliation step, BR-CO-16)."
        ),
        "expectedStatus": "klaerung_erforderlich",
        "expectedRouting": "prioritized_review",
        "expectedFindings": (
            "STR-004 (official EN16931 Schematron) fails with rule FX-SCH-A-000122 "
            "(BR-CO-16), and DigiTax CAL-003 independently fails with "
            "formula/expected/actual/difference -- two independent mechanisms "
            "agreeing this invoice is wrong."
        ),
    },
]


def _fmt_amount(value) -> str:
    if value is None:
        return "-"
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")  # de-DE style: 1 234,56


def _draw_readable_invoice_page(invoice: dict) -> bytes:
    """Draws a plain, readable A4 invoice page from a canonical_invoice
    'invoice' dict (as returned by normalize_structured_invoice()). Every
    value drawn here is read from that same dict -- nothing is
    hand-transcribed separately, so the visible page cannot drift from the
    embedded XML it was parsed from."""
    buf = BytesIO()
    # invariant=1: fixed creation timestamp/document ID so re-running this
    # generator against unchanged fixtures produces a reproducible base page,
    # not a new timestamp-dependent one every run.
    # pageCompression=0: keeps the content stream uncompressed so the
    # generated PDF's visible text is plain-text-inspectable (grep/strings),
    # not just visually readable -- an extra transparency property for a
    # demo asset, and lets tests/test_demo_assets.py assert the visible
    # invoice number is literally present in the PDF bytes.
    c = canvas.Canvas(buf, pagesize=A4, invariant=1, pageCompression=0)
    width, height = A4
    left = 20 * mm
    right = width - 20 * mm
    y = height - 20 * mm

    def line(text, size=10, font="Helvetica", dy=6 * mm, x=None):
        nonlocal y
        c.setFont(font, size)
        c.drawString(x if x is not None else left, y, text)
        y -= dy

    supplier = invoice["supplier"]
    buyer = invoice["buyer"]
    supply = invoice["supply"]
    totals = invoice["totals"]
    line_items = invoice.get("lineItems") or []

    line("RECHNUNG / INVOICE", size=16, font="Helvetica-Bold", dy=10 * mm)
    line(f"Rechnungsnummer / Invoice No.: {invoice['invoiceNumber']}", size=10)
    line(f"Rechnungsdatum / Issue date: {invoice['issueDate']}", size=10)
    if supply.get("deliveryDate"):
        line(f"Lieferdatum / Delivery date: {supply['deliveryDate']}", size=10)
    line(f"Waehrung / Currency: {invoice['currency']}", size=10, dy=10 * mm)

    block_top = y
    line("Verkaeufer / Seller:", size=10, font="Helvetica-Bold", dy=5 * mm)
    line(supplier["name"], size=10)
    line(supplier["address"]["street"], size=10)
    line(f"{supplier['address']['postalCode']} {supplier['address']['city']}", size=10)
    line(f"{supplier['address']['countryCode']}", size=10)
    if supplier.get("vatId"):
        line(f"USt-IdNr. / VAT ID: {supplier['vatId']}", size=10)
    seller_bottom = y

    y = block_top
    line("Kaeufer / Buyer:", size=10, font="Helvetica-Bold", dy=5 * mm, x=width / 2)
    line(buyer["name"], size=10, x=width / 2)
    line(buyer["address"]["street"], size=10, x=width / 2)
    line(f"{buyer['address']['postalCode']} {buyer['address']['city']}", size=10, x=width / 2)
    line(f"{buyer['address']['countryCode']}", size=10, x=width / 2)
    y = min(y, seller_bottom) - 10 * mm

    if supply.get("description"):
        line(f"Leistungsbeschreibung / Supply: {supply['description']}", size=10, dy=10 * mm)

    # Line items table
    table_top = y
    c.setFont("Helvetica-Bold", 9)
    headers = ["Pos.", "Beschreibung / Description", "Menge / Qty", "Netto / Net", "USt % / VAT %"]
    col_x = [left, left + 15 * mm, right - 65 * mm, right - 45 * mm, right - 20 * mm]
    for header, x in zip(headers, col_x):
        c.drawString(x, y, header)
    y -= 5 * mm
    c.line(left, y, right, y)
    y -= 5 * mm
    c.setFont("Helvetica", 9)
    for idx, item in enumerate(line_items, start=1):
        c.drawString(col_x[0], y, str(idx))
        c.drawString(col_x[1], y, str(item.get("description") or "")[:45])
        c.drawRightString(col_x[3] - 2 * mm, y, str(item.get("quantity") if item.get("quantity") is not None else "-"))
        c.drawRightString(col_x[3] + 18 * mm, y, _fmt_amount(item.get("netAmount")))
        c.drawRightString(right, y, f"{item.get('vatRate')}" if item.get("vatRate") is not None else "-")
        y -= 6 * mm
    y -= 4 * mm
    c.line(left, y, right, y)
    y -= 10 * mm

    def total_row(label, value, bold=False):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        c.drawString(right - 70 * mm, y, label)
        c.drawRightString(right, y, f"{_fmt_amount(value)} {invoice['currency']}")
        y -= 6 * mm

    total_row("Nettosumme / Net total:", totals["lineNet"])
    total_row("USt-Basis / Tax basis:", totals["taxBasis"])
    total_row("USt-Betrag / VAT amount:", totals["taxAmount"])
    total_row("Bruttosumme / Gross total:", totals["grossAmount"], bold=True)
    if totals.get("prepaidAmount"):
        total_row("Anzahlung / Prepaid:", totals["prepaidAmount"])
    if totals.get("roundingAmount"):
        total_row("Rundung / Rounding:", totals["roundingAmount"])
    total_row("Zahlbetrag / Payable amount:", totals["payableAmount"], bold=True)

    y -= 10 * mm
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(
        left, y,
        "Fiktive Testdaten -- kein echtes Geschaeftsdokument / Synthetic test data -- not a real business document.",
    )
    y -= 5 * mm
    c.drawString(
        left, y,
        f"Automatische Vorpruefung ({FACTURX_LABEL}); keine Freigabe, Buchung, Zahlung oder Lieferantenkommunikation.",
    )

    c.showPage()
    c.save()
    return buf.getvalue()


def _blank_a4_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=A4[0], height=A4[1])
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_hybrid_pdf(scenario: dict) -> tuple:
    """Reusable by both this CLI generator and tests/test_demo_assets.py --
    the single place that turns an accepted XML fixture into a readable
    hybrid PDF, so both the demo-asset files and the automated regression
    test exercise the exact same code path. Returns
    (hybrid_pdf_bytes, xml_bytes, invoice_dict)."""
    xml_path = FIXTURES_DIR / scenario["xmlFixture"]
    xml_bytes = xml_path.read_bytes()
    xml_etree = _parse_untrusted_xml(xml_bytes)
    invoice, field_evidence, warnings = normalize_structured_invoice(xml_etree)
    assert not warnings, f"unexpected normalization warnings for {scenario['xmlFixture']}: {warnings}"

    readable_page_pdf = _draw_readable_invoice_page(invoice)
    hybrid_pdf_bytes = generate_from_binary(
        readable_page_pdf, xml_bytes, flavor="factur-x", level="en16931", check_xsd=True
    )
    return hybrid_pdf_bytes, xml_bytes, invoice


def generate() -> list:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_entries = []

    for scenario in SCENARIOS:
        hybrid_pdf_bytes, xml_bytes, invoice = build_hybrid_pdf(scenario)

        pdf_out_path = OUTPUT_DIR / f"{scenario['outputBasename']}.pdf"
        xml_out_path = OUTPUT_DIR / f"{scenario['outputBasename']}.xml"
        pdf_out_path.write_bytes(hybrid_pdf_bytes)
        xml_out_path.write_bytes(xml_bytes)

        manifest_entries.append(
            {
                "scenarioId": scenario["id"],
                "scenario": scenario["scenario"],
                "sourceXmlFixture": f"tests/fixtures/{scenario['xmlFixture']}",
                "generatedPdf": pdf_out_path.name,
                "generatedPdfSha256": _sha256(hybrid_pdf_bytes),
                "embeddedXmlCopy": xml_out_path.name,
                "embeddedXmlSha256": _sha256(xml_bytes),
                "standardsLabel": FACTURX_LABEL,
                "visibleInvoiceNumber": invoice["invoiceNumber"],
                "visibleTotals": {
                    "lineNet": invoice["totals"]["lineNet"],
                    "taxAmount": invoice["totals"]["taxAmount"],
                    "grossAmount": invoice["totals"]["grossAmount"],
                    "payableAmount": invoice["totals"]["payableAmount"],
                },
                "expectedStatus": scenario["expectedStatus"],
                "expectedRouting": scenario["expectedRouting"],
                "expectedFindings": scenario["expectedFindings"],
            }
        )
        print(f"Wrote {pdf_out_path} ({len(hybrid_pdf_bytes)} bytes)")

    return manifest_entries


if __name__ == "__main__":
    entries = generate()
    generated_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "$comment": (
            "Generated demo assets for the 2026-08-10 afternoon DigiTax Phase 1 "
            "demo (workstream A). Regenerate with "
            "`python examples/demo/generate_demo_invoices.py` from the accepted "
            "XML fixtures in tests/fixtures/ -- this file and its PDFs are "
            "regenerable review copies, not the source of truth."
        ),
        "generatedAt": generated_at,
        "standardsLabel": FACTURX_LABEL,
        "entries": entries,
    }
    manifest_path = OUTPUT_DIR / "generated_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {manifest_path}")
