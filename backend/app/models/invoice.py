"""Invoice and line-item models."""
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING

from app.database import Base, new_uuid, utcnow

if TYPE_CHECKING:
    from app.models.audit import AuditLog


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    NEEDS_REVIEW = "needs_review"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    PAYMENT_SCHEDULED = "payment_scheduled"
    PAID = "paid"
    REJECTED = "rejected"
    ERROR = "error"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    invoice_number: Mapped[str] = mapped_column(String(64), index=True)
    vendor_name: Mapped[str] = mapped_column(String(255))
    vendor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    po_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default=InvoiceStatus.PENDING.value)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    line_items: Mapped[list["LineItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    audit_entries: Mapped[list["AuditLog"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    matched_po_line_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="line_items")
