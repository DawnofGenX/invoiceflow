"""Audit log model — the explainability core.

Every agent decision writes a row here carrying: natural-language reasoning,
a confidence score, the exact rule/risk-signal that fired, and the input/output
data the agent saw/produced. This is the product's moat.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING

from app.database import Base, new_uuid, utcnow

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(128))
    reasoning: Mapped[str] = mapped_column(Text)
    rule_fired: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    invoice: Mapped["Invoice"] = relationship(back_populates="audit_entries")
