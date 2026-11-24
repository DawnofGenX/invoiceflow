"""Pydantic schemas for approval requests."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApprovalRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    invoice_id: str
    approver_id: str | None = None
    status: str
    amount_threshold: float | None = None
    reason: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class ApprovalDecisionIn(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    comment: str | None = None
