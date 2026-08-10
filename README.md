# Factur-X API

API for Factur-X PDF generation, XML extraction and validation.

## Setup and Installation

1. Make sure you have Python 3.10 or higher installed (the `facturx/phase1/`
   package uses PEP 604 union syntax, which raises the floor from the core
   library's historical 3.7+).

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
- `POST /v1/invoices/validate` - XSD and (for EN16931) Schematron findings
  for a structured document (`applicable: false` for a plain PDF); the
  `schematron` field is an object (`status`, and `findings`/`errorDetail`
  depending on status), never silently omitted
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

- **EN16931 XSD baseline is Factur-X 1.09**; `minimum`/`basicwl`/`basic`/
  `extended` remain on the legacy Factur-X 1.07.2 / ZUGFeRD 2.3.2 XSDs, since
  only EN16931 has reviewed content controls and a reviewed Schematron
  artifact so far (see `/capabilities`' `structuredFormats["factur-x"]
  .xsdBaselines`, per level, and
  `facturx/phase1/resources/facturx-1.09-en16931/PROVENANCE.json` for full
  source/hash/license provenance). This is Factur-X **1.09**, not the true
  ZUGFeRD 2.5.2 / Factur-X 1.09.2 corrigendum (published 2026-08-04,
  primarily affecting EXTENDED) -- that official package is gated behind a
  personal-data registration form on ferd-net.de/fnfe-mpe.org with no direct
  download; acquiring it is a separate follow-up, not done here.
- **Official EN16931 Schematron business-rule validation (`STR-004`) is
  implemented**, executed offline via pinned `saxonche` (SaxonC-HE 13.0, no
  Java, no network at runtime) against the vendored 1.09 stylesheet. It only
  runs on an already-XSD-valid EN16931 document (Schematron's arithmetic
  assumes XSD-conformant types -- verified directly that running it against
  XSD-invalid content makes the engine raise a type error, not a meaningful
  finding); it is not yet reviewed for the other recognized profiles, where
  it reports `not_applicable`/`UNSUPPORTED_PROFILE` rather than running
  unreviewed. A Saxon/resource failure, timeout, or unparseable output
  reports `not_reliable` (forcing `nicht_pruefbar`), never `passed`.
- **Plain-PDF extraction uses a mock adapter**, not real OCR/LLM. It exists
  to prove the field-evidence/confidence contract a real adapter must
  satisfy (`facturx/phase1/normalize/pdf_adapter.py`), and is swappable via
  FastAPI dependency injection.
- **CAL-002/CAL-003 (arithmetic controls) assume a simple invoice.**
  `CAL-002`'s tax-consistency formula does not account for document-level
  charges/allowances. When a reliable non-zero charge or allowance is
  present, it returns `not_reliable` with reason `CONTROL_SCOPE_UNSUPPORTED`
  (forcing the run to `nicht_pruefbar`) rather than silently computing a
  wrong verdict or reporting `not_applicable` (which would aggregate as a
  false green result).
- **Only one organization context is supported**: the fictional
  `unternehmen-x-demo` snapshot. Real multi-tenant master-data loading is
  future work.
- **`examples/n8n/digitax_invoice_intake.json`** is a sanitized reference
  export of the existing DigiTax draft workflow, real-import-verified via
  the official `n8nio/n8n` Docker image -- see `examples/n8n/README.md`. It
  is not yet rewired to call the endpoints above.
- **Deployment risk: the legacy `/facturx-*` routes are not hardened to the
  same standard as the Phase 1 endpoints.** They share this FastAPI app
  (see `facturx/api.py`) and still use the unhardened XML parsing path
  described in `facturx/facturx.py`'s `xml_check_xsd()` (see the Phase 1
  `/v1/invoices/*` endpoints' own hardening in `facturx/phase1/
  document_intake.py` and `facturx/phase1/validate/structured.py` for
  contrast). This doesn't block local development or the Phase 1 endpoints
  themselves, but the legacy routes should be disabled or independently
  hardened before this service is deployed publicly.

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
