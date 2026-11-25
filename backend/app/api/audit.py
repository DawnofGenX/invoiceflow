"""Portfolio-level explainability endpoints.

These power the Transparency report: they aggregate the audit trail across every
invoice so a reviewer can see *what the agents decided and why* at a glance, rather
than one invoice at a time.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AuditLog, Invoice, InvoiceStatus

router = APIRouter()


@router.get("/summary")
def audit_summary(
    recent: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregate explainability metrics plus the most recent decisions."""
    total_decisions = db.execute(
        select(func.count()).select_from(AuditLog)
    ).scalar_one()

    by_agent = {
        agent: count
        for agent, count in db.execute(
            select(AuditLog.agent_name, func.count())
            .group_by(AuditLog.agent_name)
            .order_by(func.count().desc())
        ).all()
    }

    rules_fired = [
        {"rule": rule, "count": int(count)}
        for rule, count in db.execute(
            select(AuditLog.rule_fired, func.count().label("n"))
            .where(AuditLog.rule_fired.is_not(None))
            .group_by(AuditLog.rule_fired)
            .order_by(func.count().desc())
        ).all()
    ]

    avg_confidence = db.execute(select(func.avg(AuditLog.confidence))).scalar()
    low_confidence = db.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.confidence < settings.low_confidence_threshold)
    ).scalar_one()

    statuses = {
        status: int(count)
        for status, count in db.execute(
            select(Invoice.status, func.count()).group_by(Invoice.status)
        ).all()
    }
    total_invoices = sum(statuses.values())
    automated = statuses.get(InvoiceStatus.PAYMENT_SCHEDULED.value, 0) + statuses.get(
        InvoiceStatus.PAID.value, 0
    )
    human = statuses.get(InvoiceStatus.AWAITING_APPROVAL.value, 0) + statuses.get(
        InvoiceStatus.NEEDS_REVIEW.value, 0
    )

    recent_rows = db.execute(
        select(AuditLog, Invoice.invoice_number, Invoice.vendor_name)
        .join(Invoice, Invoice.id == AuditLog.invoice_id)
        .order_by(AuditLog.created_at.desc())
        .limit(recent)
    ).all()

    return {
        "total_decisions": int(total_decisions),
        "decisions_per_invoice": round(total_decisions / total_invoices, 2)
        if total_invoices
        else 0.0,
        "by_agent": by_agent,
        "rules_fired": rules_fired,
        "avg_confidence": round(float(avg_confidence), 3) if avg_confidence is not None else None,
        "low_confidence_threshold": settings.low_confidence_threshold,
        "low_confidence_count": int(low_confidence),
        "total_invoices": total_invoices,
        "automated_invoices": automated,
        "human_review_invoices": human,
        "automation_rate": round(automated / total_invoices, 3) if total_invoices else 0.0,
        "by_status": statuses,
        "recent": [
            {
                "id": entry.id,
                "invoice_id": entry.invoice_id,
                "invoice_number": number,
                "vendor_name": vendor,
                "agent": entry.agent_name,
                "action": entry.action,
                "reasoning": entry.reasoning,
                "rule_fired": entry.rule_fired,
                "confidence": entry.confidence,
                "duration_ms": entry.duration_ms,
                "created_at": entry.created_at.isoformat(),
            }
            for entry, number, vendor in recent_rows
        ],
    }
