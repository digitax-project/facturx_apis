"""FastAPI router for the Phase 1 endpoints.

See docs/invoice_phase1/service_gap_analysis.md "Proposed API additions" and
examples/n8n/invoice_phase1_node_plan.md for the contract these implement.
HTTP status rules are centralized here: UnsupportedInputError from the
pipeline becomes 400/415/422, TechnicalProcessingError becomes 5xx, and a
completed classification (including one whose *result* is nicht_pruefbar)
is always a normal 200 response.
"""
import logging
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from .capabilities import CAPABILITIES
from .document_intake import MAX_UPLOAD_BYTES, inspect_document
from .demo_support import build_results_xlsx
from .errors import TechnicalProcessingError, UnsupportedInputError
from .normalize.pdf_adapter import MockPdfExtractionAdapter, PdfExtractionAdapter
from .pipeline import normalize_invoice, process_invoice, validate_invoice

logger = logging.getLogger("facturx-phase1-api")

router = APIRouter(tags=["phase1"])

_default_pdf_extraction_adapter = MockPdfExtractionAdapter()


def get_pdf_extraction_adapter() -> PdfExtractionAdapter:
    """FastAPI dependency seam. Overridden in tests with adapters seeded for
    specific scenarios; the production default is the mock adapter until a
    real OCR/LLM adapter is integrated (see capabilities.py)."""
    return _default_pdf_extraction_adapter


_READ_CHUNK_BYTES = 64 * 1024


def _require_demo_endpoints() -> None:
    if os.getenv("FACTURX_ENABLE_DEMO_ENDPOINTS", "").lower() != "true":
        raise HTTPException(status_code=404, detail="Demo endpoints are disabled.")


def _load_demo_generator():
    try:
        from examples.demo.generate_demo_invoices import SCENARIOS, build_hybrid_pdf
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=501,
            detail=(
                "Synthetic generator assets are not installed. Use the repository's "
                "isolated Docker demo setup, which includes examples/demo."
            ),
        ) from exc
    return SCENARIOS, build_hybrid_pdf


async def _read_upload_bounded(file: UploadFile, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    """Reads at most `max_bytes + 1` bytes from an UploadFile in chunks.

    document_intake.inspect_document() rejects anything over MAX_UPLOAD_BYTES
    -- but only after `await file.read()` had already pulled the entire
    body into memory, which is itself an unbounded-memory exposure for a
    request that was going to be rejected anyway. This stops reading as
    soon as the limit is exceeded, so a hostile multi-gigabyte upload never
    fully lands in memory; inspect_document() still does the authoritative
    size check and produces the same FILE_TOO_LARGE/413 result.
    """
    chunks = []
    total = 0
    while total <= max_bytes:
        chunk = await file.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")


def _validate_correlation_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not _CORRELATION_ID_PATTERN.match(value):
        raise UnsupportedInputError(
            "INVALID_CORRELATION_ID",
            "correlationId must be 1-200 characters from [A-Za-z0-9._:-].",
            status_code=400,
        )
    return value


def _error_response(exc: Exception, correlation_id: Optional[str] = None) -> HTTPException:
    if isinstance(exc, (UnsupportedInputError, TechnicalProcessingError)):
        detail = {"error_code": exc.error_code, "detail": exc.detail}
        if correlation_id is not None:
            detail["correlationId"] = correlation_id
        return HTTPException(status_code=exc.status_code, detail=detail)
    raise exc


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/capabilities")
async def capabilities():
    return CAPABILITIES


@router.get("/demo/batch", include_in_schema=False)
async def batch_demo_page():
    _require_demo_endpoints()
    return FileResponse(Path(__file__).parent / "static" / "batch_demo.html")


@router.get("/v1/demo/mock-invoices")
async def list_mock_invoices():
    _require_demo_endpoints()
    scenarios, _build_hybrid_pdf = _load_demo_generator()

    return {
        "generator": "deterministic-template-v1",
        "llmUsed": False,
        "scenarios": [
            {
                "id": scenario["id"],
                "organizationId": scenario["organizationId"],
                "filename": f"{scenario['outputBasename']}.pdf",
                "category": scenario["category"],
                "description": scenario["scenario"],
            }
            for scenario in scenarios
        ],
    }


@router.get("/v1/demo/mock-invoices/{scenario_id}")
async def generate_mock_invoice(scenario_id: str):
    _require_demo_endpoints()
    scenarios, build_hybrid_pdf = _load_demo_generator()

    scenario = next((item for item in scenarios if item["id"] == scenario_id), None)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Unknown synthetic invoice scenario.")
    pdf_bytes, _xml_bytes, _invoice = build_hybrid_pdf(scenario)
    filename = f"{scenario['outputBasename']}.pdf"
    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-DigiTax-Synthetic-Generator": "deterministic-template-v1",
        },
    )


@router.post("/v1/demo/results.xlsx")
async def export_demo_results(payload: dict = Body(...)):
    _require_demo_endpoints()
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows or len(rows) > 500:
        raise HTTPException(status_code=422, detail="rows must contain between 1 and 500 results.")
    if any(not isinstance(row, dict) for row in rows):
        raise HTTPException(status_code=422, detail="Every result row must be an object.")
    workbook = build_results_xlsx(rows)
    return Response(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="digitax-phase1-results.xlsx"'},
    )


@router.post("/v1/invoices/inspect")
async def inspect(file: UploadFile):
    content = await _read_upload_bounded(file)
    try:
        inspection = inspect_document(content, file.filename or "upload", file.content_type or "")
    except UnsupportedInputError as exc:
        raise _error_response(exc)
    return {
        "sourceType": inspection.source_type,
        "filename": inspection.filename,
        "mimeType": inspection.mime_type,
        "sha256": inspection.sha256,
        "detectedFormat": inspection.detected_format,
        "formatVersion": inspection.format_version,
        "profile": inspection.profile,
        "readable": inspection.readable,
        "encrypted": inspection.encrypted,
        "warnings": inspection.warnings,
    }


@router.post("/v1/invoices/normalize")
async def normalize(
    file: UploadFile,
    adapter: PdfExtractionAdapter = Depends(get_pdf_extraction_adapter),
):
    content = await _read_upload_bounded(file)
    try:
        canonical_invoice = normalize_invoice(
            file_bytes=content,
            filename=file.filename or "upload",
            content_type=file.content_type or "",
            pdf_extraction_adapter=adapter,
        )
    except (UnsupportedInputError, TechnicalProcessingError) as exc:
        logger.warning("Phase 1 normalize request rejected: %s %s", exc.error_code, exc.detail)
        raise _error_response(exc)
    return {"canonicalInvoice": canonical_invoice}


@router.post("/v1/invoices/validate")
async def validate(file: UploadFile):
    content = await _read_upload_bounded(file)
    try:
        result = validate_invoice(
            file_bytes=content,
            filename=file.filename or "upload",
            content_type=file.content_type or "",
        )
    except (UnsupportedInputError, TechnicalProcessingError) as exc:
        logger.warning("Phase 1 validate request rejected: %s %s", exc.error_code, exc.detail)
        raise _error_response(exc)
    return result


@router.post(
    "/v1/invoices/process",
    responses={
        400: {
            "description": (
                "Missing/unrecognized organization context "
                "(error_code ORGANIZATION_CONTEXT_REQUIRED), or an invalid "
                "X-Correlation-ID header (error_code INVALID_CORRELATION_ID, "
                "checked before the upload is read by the application)."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "error_code": "INVALID_CORRELATION_ID",
                            "detail": "correlationId must be 1-200 characters from [A-Za-z0-9._:-].",
                        }
                    }
                }
            },
        },
    },
)
async def process(
    file: UploadFile,
    organizationId: Optional[str] = Form(None),
    demoMode: bool = Form(False),
    x_correlation_id: Optional[str] = Header(
        None,
        alias="X-Correlation-ID",
        description=(
            "Optional caller-supplied correlation identifier, echoed "
            "verbatim into the response report's correlationId when valid. "
            "Must be 1-200 characters from [A-Za-z0-9._:-]; an invalid "
            "value is rejected with 400 INVALID_CORRELATION_ID before the "
            "application reads the upload. This constraint is documented "
            "here for API consumers -- it is enforced by application code "
            "in the route body, not by this parameter declaration itself, "
            "so an invalid value never produces FastAPI's automatic 422."
        ),
        json_schema_extra={
            "pattern": "^[A-Za-z0-9._:-]{1,200}$",
            "minLength": 1,
            "maxLength": 200,
        },
    ),
    adapter: PdfExtractionAdapter = Depends(get_pdf_extraction_adapter),
):
    correlation_id = None
    try:
        correlation_id = _validate_correlation_id(x_correlation_id)
        content = await _read_upload_bounded(file)
        canonical_invoice, report = process_invoice(
            file_bytes=content,
            filename=file.filename or "upload",
            content_type=file.content_type or "",
            organization_id=organizationId,
            demo_mode=demoMode,
            correlation_id=correlation_id,
            pdf_extraction_adapter=adapter,
        )
    except (UnsupportedInputError, TechnicalProcessingError) as exc:
        logger.warning(
            "Phase 1 process request rejected: %s %s correlationId=%s",
            exc.error_code, exc.detail, correlation_id,
        )
        raise _error_response(exc, correlation_id=correlation_id)
    return {"canonicalInvoice": canonical_invoice, "phase1ControlReport": report}
