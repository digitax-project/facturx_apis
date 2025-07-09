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

- `/facturx-pdfgen` - Generate a Factur-X or Order-X PDF
- `/facturx-pdfextractxml` - Extract XML from a Factur-X or Order-X PDF
- `/facturx-xmlcheck` - Validate Factur-X or Order-X XML

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

## Troubleshooting

### No XML found in PDF

If you get a message saying "No XML found in the PDF", ensure that:
- The PDF actually contains an embedded XML file
- The PDF isn't password-protected or encrypted
- Try setting `accept_any_filename` to `true` to extract any embedded XML

For technical support, please file an issue on the project repository.
