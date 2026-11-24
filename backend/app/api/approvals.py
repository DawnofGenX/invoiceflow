"""Approval endpoints: list requests, approve/reject a routed invoice."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db, utcnow
from app.models import ApprovalRequest, ApprovalStatus, Invoice, InvoiceStatus
from app.schemas import ApprovalDecisionIn, ApprovalRequestOut
from app.services.audit import record_audit
from app.services.payment import schedule_mock_payment

router = APIRouter()


@router.get("/", response_model=list[ApprovalRequestOut])
def list_approvals(db: Session = Depends(get_db)) -> list[ApprovalRequest]:
    return list(
        db.execute(select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())).scalars()
    )


@router.post("/{request_id}/decide")
def decide_approval(
    request_id: str, body: ApprovalDecisionIn, db: Session = Depends(get_db)
) -> dict:
    req = db.get(ApprovalRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    invoice = db.get(Invoice, req.invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    comment = f": {body.comment}" if body.comment else ""
    if body.decision == "approve":
        req.status = ApprovalStatus.APPROVED.value
        invoice.status = InvoiceStatus.APPROVED.value
        schedule_mock_payment(db, invoice)
        record_audit(
            db,
            invoice_id=invoice.id,
            agent_name="manager",
            action="approve",
            reasoning=f"Human manager approved the invoice{comment}",
            rule_fired="human_approval",
            confidence=1.0,
            output_data={"decision": "approve"},
        )
    else:
        req.status = ApprovalStatus.REJECTED.value
        invoice.status = InvoiceStatus.REJECTED.value
        record_audit(
            db,
            invoice_id=invoice.id,
            agent_name="manager",
            action="reject",
            reasoning=f"Human manager rejected the invoice{comment}",
            rule_fired="human_rejection",
            confidence=1.0,
            output_data={"decision": "reject"},
        )

    req.resolved_at = utcnow()
    db.commit()
    return {"approval_status": req.status, "invoice_status": invoice.status}
