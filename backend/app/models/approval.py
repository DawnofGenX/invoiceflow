"""Approval request and rule models."""
import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, new_uuid, utcnow


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id"), index=True)
    approver_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=ApprovalStatus.PENDING.value)
    amount_threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApprovalRule(Base):
    __tablename__ = "approval_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(128))
    min_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    approver_role: Mapped[str] = mapped_column(String(64))
    priority: Mapped[int] = mapped_column(Integer, default=0)
