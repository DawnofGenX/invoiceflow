"""Vendor view: what the system knows about each supplier.

The approval agent forces manual verification for vendors with no history, so the
vendor table is the other half of that story — it shows exactly which suppliers are
established and which are new.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Invoice, InvoiceStatus

router = APIRouter()


@router.get("/")
def list_vendors(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(
            Invoice.vendor_name,
            func.count().label("invoice_count"),
            func.sum(Invoice.amount).label("total_amount"),
            func.avg(Invoice.confidence_score).label("avg_confidence"),
            func.max(Invoice.created_at).label("last_seen"),
        )
        .where(Invoice.vendor_name.is_not(None), Invoice.vendor_name != "")
        .group_by(Invoice.vendor_name)
        .order_by(func.sum(Invoice.amount).desc())
    ).all()

    paid = {
        vendor: int(count)
        for vendor, count in db.execute(
            select(Invoice.vendor_name, func.count())
            .where(
                Invoice.status.in_(
                    [
                        InvoiceStatus.PAYMENT_SCHEDULED.value,
                        InvoiceStatus.PAID.value,
                    ]
                )
            )
            .group_by(Invoice.vendor_name)
        ).all()
    }

    return [
        {
            "vendor_name": vendor,
            "invoice_count": int(count),
            "settled_count": paid.get(vendor, 0),
            "total_amount": float(total or 0),
            "avg_confidence": round(float(conf), 3) if conf is not None else None,
            "last_seen": last_seen.isoformat() if last_seen else None,
            "has_history": paid.get(vendor, 0) > 0,
        }
        for vendor, count, total, conf, last_seen in rows
    ]
