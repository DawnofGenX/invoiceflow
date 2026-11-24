"""Approval agent — routes the invoice to an approver based on amount thresholds.

Thresholds (from plan): <$500 auto-approve; $500-$5,000 manager; $5,000-$10,000
admin; >$10,000 dual. Rules live in the ApprovalRule table (seeded on first run)
so they're configurable rather than hard-coded. New vendors force a manager
review regardless of amount.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApprovalRequest, ApprovalRule, Invoice
from app.services.audit import record_audit
from app.services.events import bus

_DEFAULT_RULES = [
    ("auto-approve", "0", "499.99", "auto", 0),
    ("manager", "500", "4999.99", "manager", 1),
    ("admin", "5000", "9999.99", "admin", 2),
    ("dual", "10000", None, "dual", 3),
]


def _ensure_rules(db: Session) -> list[ApprovalRule]:
    rules = list(db.execute(select(ApprovalRule).order_by(ApprovalRule.priority)).scalars())
    if rules:
        return rules
    for name, mn, mx, role, pri in _DEFAULT_RULES:
        rule = ApprovalRule(
            name=name,
            min_amount=Decimal(mn),
            max_amount=Decimal(mx) if mx else None,
            approver_role=role,
            priority=pri,
        )
        db.add(rule)
        rules.append(rule)
    db.flush()
    return rules


def run(state: dict, db: Session) -> dict:
    invoice_id = state["invoice_id"]
    invoice = db.get(Invoice, invoice_id)
    amount = invoice.amount or Decimal("0")
    validation = state.get("validation_result") or {}
    is_new_vendor = bool(validation.get("new_vendor"))

    bus.publish(
        invoice_id,
        {
            "type": "agent_started",
            "agent": "approval",
            "action": "route_approval",
            "status": "running",
            "invoice_status": "awaiting_approval",
        },
    )

    if is_new_vendor:
        decision = {
            "decision": "routed",
            "approver_role": "manager",
            "rule": "new_vendor_verification",
            "reason": f"New vendor '{invoice.vendor_name}' requires manual verification before payment",
        }
        db.add(
            ApprovalRequest(
                invoice_id=invoice_id,
                status="pending",
                amount_threshold=amount,
                reason=decision["reason"],
            )
        )
        record_audit(
            db,
            invoice_id=invoice_id,
            agent_name="approval",
            action="route_approval",
            reasoning=decision["reason"],
            rule_fired="new_vendor_verification",
            confidence=1.0,
            input_data={"vendor_name": invoice.vendor_name, "amount": str(amount)},
            output_data={"decision": "routed", "approver_role": "manager"},
        )
    else:
        rules = _ensure_rules(db)
        matched = None
        for rule in rules:
            mn = Decimal(str(rule.min_amount))
            mx = None if rule.max_amount is None else Decimal(str(rule.max_amount))
            if amount >= mn and (mx is None or amount <= mx):
                matched = rule
                break
        if matched is None:
            matched = rules[-1]

        if matched.approver_role == "auto":
            decision = {
                "decision": "auto_approve",
                "approver_role": "auto",
                "rule": matched.name,
                "reason": f"Amount ${amount} is within auto-approval threshold '{matched.name}'",
            }
            record_audit(
                db,
                invoice_id=invoice_id,
                agent_name="approval",
                action="route_approval",
                reasoning=decision["reason"],
                rule_fired=matched.name,
                confidence=1.0,
                input_data={"amount": str(amount)},
                output_data={"decision": "auto_approve"},
            )
        else:
            decision = {
                "decision": "routed",
                "approver_role": matched.approver_role,
                "rule": matched.name,
                "reason": f"Amount ${amount} requires '{matched.approver_role}' approval (rule '{matched.name}')",
            }
            db.add(
                ApprovalRequest(
                    invoice_id=invoice_id,
                    status="pending",
                    amount_threshold=amount,
                    reason=decision["reason"],
                )
            )
            record_audit(
                db,
                invoice_id=invoice_id,
                agent_name="approval",
                action="route_approval",
                reasoning=decision["reason"],
                rule_fired=matched.name,
                confidence=1.0,
                input_data={"amount": str(amount)},
                output_data={"decision": "routed", "approver_role": matched.approver_role},
            )

    bus.publish(
        invoice_id,
        {
            "type": "agent_done",
            "agent": "approval",
            "action": "route_approval",
            "status": "done",
            "decision": decision["decision"],
            "reasoning": decision["reason"],
            "approver_role": decision["approver_role"],
        },
    )

    return {"approval_decision": decision, "current_step": "approval"}
