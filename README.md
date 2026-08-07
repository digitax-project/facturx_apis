# Factur-X API

API for Factur-X PDF generation, XML extraction and validation.

## Setup and Installation

1. Make sure you have Python 3.7 or higher installed.

2. Install the package and its dependencies:

   ```bash
   # Navigate to the project directory
   cd c:\Agentic\synthetic_invoice\factur-x-master

   # Create and activate a virtual environment (recommended)
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   source .venv/bin/activate  # On Linux/Mac

   # Install in development mode
   pip install -e .
   ```

3. Run the API server:

   ```bash
   # Using the convenience script
   python run.py
   
   # Or directly
   python -m facturx.api
   ```

4. Access the API documentation:
   
   Open your browser and navigate to http://localhost:6969/docs

## API Endpoints

### Legacy Factur-X/Order-X endpoints

- `/facturx-pdfgen` - Generate a Factur-X or Order-X PDF
- `/facturx-pdfextractxml` - Extract XML from a Factur-X or Order-X PDF
- `/facturx-xmlcheck` - Validate Factur-X or Order-X XML

### DigiTax Phase 1 invoice-preprocessing endpoints

See `docs/invoice_phase1/` for the full specification. These endpoints
inspect, validate, and normalize a Factur-X/ZUGFeRD or plain-PDF invoice into
a shared canonical contract, run the same starter control profile against
both, and return a schema-valid control report. They never approve, reject,
book, pay, or contact a supplier -- Phase 1 ends at a report for human
review.

- `GET /health`
- `GET /capabilities` - supported formats/versions, the active control
  profile, and known limitations (see below)
- `POST /v1/invoices/inspect` - detect source type, format, and version
- `POST /v1/invoices/normalize` - extract/normalize into `canonicalInvoice`
  only, no controls run, no organization context required
- `POST /v1/invoices/validate` - XSD findings for a structured document
  (`applicable: false` for a plain PDF); Schematron reported as
  `"not_implemented"`, never silently omitted
- `POST /v1/invoices/process` - the full pipeline; multipart form with
  `file`, plus either `organizationId=unternehmen-x-demo` or
  `demoMode=true` (there is no silent fallback to demo master data).
  Returns `{"canonicalInvoice": ..., "phase1ControlReport": ...}` on success.
  400/422 for a malformed request (including missing organization context),
  415 if the file isn't recognizable as a PDF or XML at all, 200 with a
  classified report (which may itself be `nicht_pruefbar`) for every
  anticipated content outcome, and 5xx with a stable `error_code` only for a
  genuinely unexpected technical failure.

```bash
curl -X POST "http://localhost:6969/v1/invoices/process" \
  -F "file=@invoice.pdf" \
  -F "organizationId=unternehmen-x-demo"
```

#### Known limitations (also reported by `/capabilities`)

- **XSD baseline is Factur-X 1.07.2 / ZUGFeRD 2.3.2**, not the current
  ZUGFeRD 2.5 / Factur-X 1.09 package. `/capabilities` flags this
  explicitly as `legacyBaseline: true`. The upgrade is tracked as a
  separate follow-up issue (see `docs/invoice_phase1/service_gap_analysis.md`).
- **Schematron/official business-rule validation is not implemented.** No
  Schematron artifacts are bundled or fetched. The corresponding control
  (`STR-004`) is defined in the candidate catalog but deliberately left out
  of the starter control profile, not reported as passed or run.
- **Plain-PDF extraction uses a mock adapter**, not real OCR/LLM. It exists
  to prove the field-evidence/confidence contract a real adapter must
  satisfy (`facturx/phase1/normalize/pdf_adapter.py`), and is swappable via
  FastAPI dependency injection.
- **CAL-002/CAL-003 (arithmetic controls) assume a simple invoice.**
  `CAL-002` becomes `not_applicable` whenever a document-level charge or
  allowance is present, rather than silently computing a wrong verdict.
- **Only one organization context is supported**: the fictional
  `unternehmen-x-demo` snapshot. Real multi-tenant master-data loading is
  future work.
- **`examples/n8n/digitax_invoice_intake.json`** is a sanitized reference
  export of the existing DigiTax draft workflow, real-import-verified via
  the official `n8nio/n8n` Docker image -- see `examples/n8n/README.md`. It
  is not yet rewired to call the endpoints above.

## Features

### Flexible XML Extraction

The XML extraction endpoint now supports extracting XML from PDFs regardless of the XML filename. This is useful for handling:

- Non-standard implementations of Factur-X
- Custom XML files embedded in PDFs
- Variations of standard names

By default, the API will:
1. First try to extract XML using standard filenames (factur-x.xml, zugferd-invoice.xml, etc.)
2. If nothing is found, it will try to find any embedded XML file

## Testing the API

### Using the Web Interface

1. Start the API server: `python run.py`
2. Open http://localhost:6969/docs in your browser
3. Use the interactive Swagger UI to test the endpoints

### Extracting XML from PDF

1. Go to http://localhost:6969/docs
2. Expand the `/facturx-pdfextractxml` endpoint
3. Click "Try it out"
4. Upload a PDF file with embedded XML
5. Set `accept_any_filename` to `true` to extract any XML regardless of filename
6. Choose whether to validate the XML (check_xsd)
7. Choose whether to return as file or text (return_xml_file)
8. Click "Execute"

### Using cURL

```bash
# Extract XML from a PDF with any XML filename
curl -X POST "http://localhost:6969/facturx-pdfextractxml" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "pdf_file=@path/to/invoice.pdf" \
  -F "check_xsd=true" \
  -F "accept_any_filename=true" \
  > extracted.xml
```

## Running tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

CI runs the same suite on every push/PR (`.github/workflows/test.yaml`).

## Troubleshooting

### No XML found in PDF

If you get a message saying "No XML found in the PDF", ensure that:
- The PDF actually contains an embedded XML file
- The PDF isn't password-protected or encrypted
- Try setting `accept_any_filename` to `true` to extract any embedded XML

For technical support, please file an issue on the project repository.
