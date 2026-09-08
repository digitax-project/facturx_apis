"""Text-structuring LLM adapter seam for digitally-born plain PDFs.

This is the `text_llm` counterpart to normalize/pdf_adapter.py's
`PdfExtractionAdapter` (the `ocr_llm` vision/OCR path). It exists because a
digitally-born plain PDF (real, meaningful embedded text -- see
document_intake.inspect_text_layer) never needs OCR or a vision model at
all: the real text is already available, cheaply and losslessly, from the
PDF's own text layer, so the only work left is asking an LLM to structure
that already-correct text into the canonical invoice shape. Calling this
adapter must therefore never call PdfExtractionAdapter.extract() (the
image/vision path) -- see pipeline.py's `_extract_and_normalize`, which
routes to exactly one of the two, never both.

Honest status, matching pdf_adapter.py's own docstring: like
`MockPdfExtractionAdapter`, `MockTextExtractionAdapter` is a deterministic
stand-in, not a real model call. This codebase's one actual, working
text-structuring LLM call today lives entirely in the external n8n Flow 1b
workflow (examples/n8n/digitax_invoice_phase1_flow1b_pdf_ocr_concept_v0_3_0.json,
nodes "02.0LT Extract PDF text" / "02.2LT Build local text extraction
request" / "02.3LT Run local text extraction"), which already implements
the project's local-model-first execution profile (an OpenAI-compatible
`$env.LOCAL_LLM_BASE_URL/chat/completions` call, escalating to the cloud
Gemini vision lane only when the text-layer gate finds no usable text) --
not in this Python service. `PdfExtractionAdapter.extract()` itself is the
same kind of intentional placeholder (see its own module docstring): there
is no real OCR/vision call in this Python service either, so there is no
existing "real" provider/config pattern in Python for this seam to bypass
or duplicate. A future real implementation of either adapter should follow
the n8n workflow's already-validated local-model-first pattern and plug in
through this same FastAPI dependency-injection seam (see
facturx/phase1/api.py's get_text_extraction_adapter), without pipeline.py
needing to change.
"""
import hashlib
from typing import Optional, Protocol

from .pdf_adapter import PdfExtractionResult


class TextExtractionAdapter(Protocol):
    def extract(self, text: str) -> PdfExtractionResult: ...


class MockTextExtractionAdapter:
    """Deterministic stand-in for a real text-structuring LLM call.

    Results are looked up by the sha256 of the extracted text passed in --
    NOT the original PDF's bytes, since this adapter (unlike
    MockPdfExtractionAdapter) never sees the PDF bytes at all, only the
    already-extracted text layer (see pipeline.py's `_extract_and_normalize`,
    which calls this instead of PdfExtractionAdapter.extract() whenever a
    usable text layer is present). Tests seed exactly the scenario they
    need by hashing the same text string they expect to be extracted; an
    unseeded text returns a "failed" extraction, the same anticipated
    outcome a real adapter failing to structure unfamiliar text would
    produce, rather than raising.
    """

    def __init__(
        self,
        canned: Optional[dict[str, PdfExtractionResult]] = None,
        default: Optional[PdfExtractionResult] = None,
    ):
        self._canned = canned or {}
        self._default = default

    def extract(self, text: str) -> PdfExtractionResult:
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if key in self._canned:
            return self._canned[key]
        if self._default is not None:
            return self._default
        return PdfExtractionResult(
            status="failed",
            overall_confidence=0.0,
            warnings=["NO_MOCK_RESULT_SEEDED_FOR_THIS_TEXT"],
        )
