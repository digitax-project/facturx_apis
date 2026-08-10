# Factur-X API

API for Factur-X PDF generation, XML extraction and validation.

## DigiTax Phase 1 API v1.0.1

`v1.0.0` introduced the first stable DigiTax Phase 1 invoice-preprocessing API
and its n8n demonstration. `v1.0.1` corrects the dated official-standard
baseline and adds the complete generated Schematron assertion inventory. The
service release is independent of the embedded upstream `factur-x` Python
library version `3.6` and the invoice validation baseline
`Factur-X 1.09 EN16931`.

### What is new

- A fail-safe pipeline for inspecting, normalizing, validating, and checking
  structured invoices before human review.
- Hardened PDF/XML intake with explicit size limits and entity/network-safe XML
  parsing.
- Factur-X 1.09 EN16931 XSD validation plus offline execution of the official
  Schematron business rules.
- A versioned DigiTax control report with stable control IDs, reason codes,
  rule versions, source hash, evidence references, and detailed calculations.
- Reproducible valid and incorrect-payable hybrid Factur-X demo invoices.
- An isolated n8n 2.33.7 upload workflow with browser-readable results and
  explicit `standard_review`, `prioritized_review`, and `technical_review`
  routes.

Phase 1 only produces findings for human review. It does not approve or reject
an invoice and does not perform booking, payment, delegation, or supplier
communication.

## Setup and Installation

1. Make sure you have Python 3.10 or higher installed (the `facturx/phase1/`
   package uses PEP 604 union syntax, which raises the floor from the core
   library's historical 3.7+).

2. Install the package and its dependencies:

   ```bash
   git clone https://github.com/digitax-project/facturx_apis.git
   cd facturx_apis

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
a shared canonical contract, run the organization's selected versioned control
profile, and return a schema-valid control report. They never approve, reject,
book, pay, or contact a supplier -- Phase 1 ends at a report for human
review.

- `GET /health`
- `GET /capabilities` - supported formats/versions and available control
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

### Embedded starter controls

The API currently selects either `inbound-starter-de-v1` version `0.2.0` or
`inbound-operating-de-v1` version `0.1.0`; both use catalog version `0.3.0`.
The API returns every selected control with its outcome, severity, reason
codes, rule version, message, evidence references, and structured details
where applicable.

| Group | Controls currently executed |
| --- | --- |
| Document intake | `DOC-001`: readable, supported, unencrypted input; `DOC-007`: sufficient overall extraction confidence |
| Structured validation | `STR-003`: detected XSD validation; `STR-004`: official EN16931 Schematron business rules |
| Required invoice information | `FRM-001`: supplier/buyer names; `FRM-002`: addresses; `FRM-003`: supplier tax/VAT ID; `FRM-004`: issue date; `FRM-005`: invoice number; `FRM-006`: goods/service description; `FRM-007`: delivery/service date or period |
| Arithmetic and currency | `CAL-001`: line-net consistency; `CAL-002`: tax basis/rate/amount consistency; `CAL-003`: net, tax, gross, prepaid, rounding, and payable reconciliation; `CAL-004`: currency presence and consistency |
| Organization context | `ORG-001`: buyer data match the approved organization master-data snapshot; operating profile only: `ORG-002`, supplier identity matches approved supplier data |

`STR-004` is one DigiTax control boundary around the complete vendored
Schematron artifact. That artifact currently contains 427 contextual assertion
templates (302 unique technical IDs). The generated
[`Schematron rule inventory`](docs/invoice_phase1/schematron_rule_inventory.md)
documents every assertion and links to a machine-readable JSON inventory for
future control grouping, mock-invoice generation, and coverage tracking.

The complete candidate catalog, including controls not yet selected for the
starter profile, is documented in
[`docs/invoice_phase1/control_catalog.md`](docs/invoice_phase1/control_catalog.md).

### Run the six-case n8n demo

The isolated demo uses API port `6970`, n8n port `5679`, and the dedicated
Docker volume `digitax_n8n_phase1_data`. It does not change an existing n8n
instance on port `5678`.

```powershell
./examples/n8n/scripts/Manage-Phase1UploadDemo.ps1 -Action Start
./examples/n8n/scripts/Manage-Phase1UploadDemo.ps1 -Action SmokeTest
```

Open [`examples/n8n/phase1_upload_demo_page.html`](examples/n8n/phase1_upload_demo_page.html),
select Unternehmen X or Unternehmen Y, and upload these generated cases:

| Case | Profile | Expected result | Expected evidence |
| --- | --- | --- | --- |
| X: valid | starter | `unauffaellig / standard_review` | shared baseline passes |
| X: missing supplier identifier | starter | `klaerung_erforderlich / prioritized_review` | `FRM-003` and official Schematron findings |
| X: incorrect payable amount | starter | `klaerung_erforderlich / prioritized_review` | official `BR-CO-16` and independent `CAL-003` explanation |
| Y: valid approved supplier | operating | `unauffaellig / standard_review` | shared baseline plus `ORG-002` pass |
| Y: unapproved supplier | operating | `klaerung_erforderlich / prioritized_review` | `ORG-002 / SUPPLIER_NOT_APPROVED` |
| Y: multiple mismatches | operating | `klaerung_erforderlich / prioritized_review` | organization, required-information, arithmetic, and official-rule findings |

Generate portable demo files from the accepted XML fixtures:

```bash
python examples/demo/generate_demo_invoices.py --output-dir .demo-output
```

See [`examples/n8n/README.md`](examples/n8n/README.md) for workflow operation
and [`docs/invoice_phase1/demo_profile_matrix.md`](docs/invoice_phase1/demo_profile_matrix.md)
for the recommended demo sequence and exact meaning of each case.

### Upstream software and validation vendors

- Hybrid-PDF generation builds on the open-source [`factur-x` Python
  project](https://github.com/akretion/factur-x) by Alexis de Lattre/Akretion;
  package publisher, release provenance, and license metadata are available on
  [PyPI](https://pypi.org/project/factur-x/).
- Offline Schematron execution uses Saxonica's
  [`saxonche`/SaxonC Python binding](https://www.saxonica.com/html/download/c.html).
- The exact vendored XSD/Schematron sources, SHA-256 hashes, and licenses are
  retained in
  [`PROVENANCE.json`](facturx/phase1/resources/facturx-1.09-en16931/PROVENANCE.json).

#### Known limitations (also reported by `/capabilities`)

- **EN16931 XSD baseline is Factur-X 1.09**; `minimum`/`basicwl`/`basic`/
  `extended` remain on the legacy Factur-X 1.07.2 / ZUGFeRD 2.3.2 XSDs, since
  only EN16931 has reviewed content controls and a reviewed Schematron
  artifact so far (see `/capabilities`' `structuredFormats["factur-x"]
  .xsdBaselines`, per level, and
  `facturx/phase1/resources/facturx-1.09-en16931/PROVENANCE.json` for full
  source/hash/license provenance). The official FeRD and FNFE-MPE pages
  checked on 2026-08-10 identify Factur-X 1.09 / ZUGFeRD 2.5, published on
  2026-06-10, as the current release. No official Factur-X 1.09.2 / ZUGFeRD
  2.5.2 release was identified in those sources. This is a dated factual
  snapshot, not a permanent assumption; see
  [`docs/invoice_phase1/standard_baseline.md`](docs/invoice_phase1/standard_baseline.md)
  for sources and the update procedure.
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
- **Only two synthetic organization contexts are supported**:
  `unternehmen-x-demo` selects the starter profile and `unternehmen-y-demo`
  selects the operating demo profile with `ORG-002`. These in-memory fixtures
  demonstrate profile selection; real multi-tenant master-data loading remains
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
