"""Dashboard aggregate stats."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ApprovalRequest, ApprovalStatus, Invoice, InvoiceStatus
from app.schemas import DashboardStats

router = APIRouter()


@router.get("/", response_model=DashboardStats)
def dashboard(db: Session = Depends(get_db)) -> DashboardStats:
    statuses = list(db.execute(select(Invoice.status)).scalars())
    by_status: dict[str, int] = {}
    for s in statuses:
        by_status[s] = by_status.get(s, 0) + 1

    total_amount = db.execute(
        select(func.coalesce(func.sum(Invoice.amount), 0))
    ).scalar_one()
    pending = db.execute(
        select(func.count())
        .select_from(ApprovalRequest)
        .where(ApprovalRequest.status == ApprovalStatus.PENDING.value)
    ).scalar_one()

    return DashboardStats(
        total_invoices=len(statuses),
        by_status=by_status,
        total_amount=float(total_amount or 0),
        pending_approvals=int(pending),
        needs_review=by_status.get(InvoiceStatus.NEEDS_REVIEW.value, 0),
        auto_approved=by_status.get(InvoiceStatus.PAYMENT_SCHEDULED.value, 0)
        + by_status.get(InvoiceStatus.APPROVED.value, 0),
    )
