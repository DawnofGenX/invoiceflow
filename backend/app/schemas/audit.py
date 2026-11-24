"""Pydantic response schemas for the audit trail."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_name: str
    action: str
    reasoning: str
    rule_fired: str | None = None
    confidence: float
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    duration_ms: int
    created_at: datetime
