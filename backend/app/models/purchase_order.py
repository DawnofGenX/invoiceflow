"""Purchase-order and PO line-item models."""
import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, new_uuid, utcnow


class POStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    po_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    vendor_name: Mapped[str] = mapped_column(String(255))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(32), default=POStatus.OPEN.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    line_items: Mapped[list["POLineItem"]] = relationship(
        back_populates="po", cascade="all, delete-orphan"
    )


class POLineItem(Base):
    __tablename__ = "po_line_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    po_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_orders.id"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    po: Mapped["PurchaseOrder"] = relationship(back_populates="line_items")
