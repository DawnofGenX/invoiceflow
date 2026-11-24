"""Invoice endpoints: upload, list, detail, audit, export, SSE stream."""
import asyncio
import json
import os
import queue
import tempfile
from decimal import Decimal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import SessionLocal, get_db
from app.models import AuditLog, Invoice, InvoiceStatus
from app.schemas import (
    AuditLogOut,
    InvoiceDetail,
    InvoiceSummary,
    InvoiceUploadResponse,
)
from app.services.audit import record_audit
from app.services.audit_export import export_json, export_pdf
from app.services.events import bus
from app.services.ocr import OCRError, extract_document_text

router = APIRouter()

_ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def _run_pipeline(invoice_id: str, file_path: str, raw_text: str) -> None:
    from app.agents.orchestrator import process_invoice

    db = SessionLocal()
    try:
        process_invoice(db, invoice_id, file_path, raw_text)
    except Exception as exc:  # noqa: BLE001
        try:
            invoice = db.get(Invoice, invoice_id)
            if invoice is not None:
                invoice.status = InvoiceStatus.ERROR.value
            record_audit(
                db,
                invoice_id=invoice_id,
                agent_name="orchestrator",
                action="pipeline_error",
                reasoning=f"Unhandled pipeline error: {exc}",
                confidence=0.0,
            )
            db.commit()
            bus.publish(
                invoice_id, {"type": "error", "status": "error", "message": str(exc)}
            )
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()


@router.post("/upload", response_model=InvoiceUploadResponse, status_code=201)
async def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> InvoiceUploadResponse:
    filename = file.filename or "upload.pdf"
    suffix = os.path.splitext(filename)[1].lower() or ".pdf"
    if suffix not in _ALLOWED:
        raise HTTPException(
            status_code=400, detail=f"Unsupported file type: {suffix or 'unknown'}"
        )

    content = await file.read()
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        try:
            raw_text = extract_document_text(path)
        except OCRError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    if not raw_text.strip():
        raise HTTPException(
            status_code=422, detail="No text could be extracted from the document"
        )

    invoice = Invoice(
        invoice_number="",
        vendor_name="",
        amount=Decimal("0"),
        status=InvoiceStatus.PENDING.value,
        raw_text=raw_text,
        file_path=filename,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    background_tasks.add_task(_run_pipeline, invoice.id, filename, raw_text)
    return InvoiceUploadResponse(invoice_id=invoice.id, status="pending")


@router.get("/", response_model=list[InvoiceSummary])
def list_invoices(db: Session = Depends(get_db)) -> list[Invoice]:
    return list(db.execute(select(Invoice).order_by(Invoice.created_at.desc())).scalars())


@router.get("/{invoice_id}", response_model=InvoiceDetail)
def get_invoice(invoice_id: str, db: Session = Depends(get_db)) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/{invoice_id}/audit", response_model=list[AuditLogOut])
def get_audit(invoice_id: str, db: Session = Depends(get_db)) -> list[AuditLog]:
    if db.get(Invoice, invoice_id) is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return list(
        db.execute(
            select(AuditLog)
            .where(AuditLog.invoice_id == invoice_id)
            .order_by(AuditLog.created_at)
        ).scalars()
    )


@router.get("/{invoice_id}/audit/export")
def export_audit(
    invoice_id: str, format: str = "json", db: Session = Depends(get_db)
) -> Response:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    entries = list(
        db.execute(
            select(AuditLog)
            .where(AuditLog.invoice_id == invoice_id)
            .order_by(AuditLog.created_at)
        ).scalars()
    )
    if format == "json":
        return Response(
            content=export_json(invoice, entries),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="audit-{invoice_id}.json"'},
        )
    if format == "pdf":
        return Response(
            content=export_pdf(invoice, entries),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="audit-{invoice_id}.pdf"'},
        )
    raise HTTPException(status_code=400, detail="format must be 'json' or 'pdf'")


@router.get("/{invoice_id}/stream")
async def stream_invoice(invoice_id: str) -> EventSourceResponse:
    async def event_stream():
        q = bus.subscribe(invoice_id)
        try:
            while True:
                try:
                    event = await asyncio.to_thread(q.get, timeout=300)
                except queue.Empty:
                    yield {"event": "timeout", "data": "{}"}
                    break
                yield {"event": "agent_event", "data": json.dumps(event, default=str)}
                if event.get("type") in ("invoice_completed", "error"):
                    break
        finally:
            bus.unsubscribe(invoice_id, q)

    return EventSourceResponse(event_stream())
