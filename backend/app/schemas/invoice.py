"""Pydantic schemas for invoices and line items."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.audit import AuditLogOut


class LineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    description: str
    quantity: float
    unit_price: float
    total: float
    matched_po_line_id: str | None = None


class InvoiceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    invoice_number: str
    vendor_name: str
    vendor_email: str | None = None
    amount: float
    currency: str
    tax_amount: float | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    po_number: str | None = None
    status: str
    confidence_score: float | None = None
    created_at: datetime


class InvoiceDetail(InvoiceSummary):
    raw_text: str | None = None
    file_path: str | None = None
    line_items: list[LineItemOut] = []
    audit_entries: list[AuditLogOut] = []


class InvoiceUploadResponse(BaseModel):
    invoice_id: str
    status: str
