"""Audit-log recording helper — every agent decision is written here."""
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_audit(
    db: Session,
    *,
    invoice_id: str,
    agent_name: str,
    action: str,
    reasoning: str,
    rule_fired: str | None = None,
    confidence: float = 0.0,
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    duration_ms: int = 0,
) -> AuditLog:
    """Create (but do not commit) an audit entry for an agent decision."""
    entry = AuditLog(
        invoice_id=invoice_id,
        agent_name=agent_name,
        action=action,
        reasoning=reasoning,
        rule_fired=rule_fired,
        confidence=confidence,
        input_data=input_data,
        output_data=output_data,
        duration_ms=duration_ms,
    )
    db.add(entry)
    return entry
