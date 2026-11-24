"""Validation agent — PO match, duplicate, fraud, and amount verification.

All checks are rule-based (not LLM) so every decision is exactly reproducible —
the core of the explainability wedge. Each check writes its own audit entry so
the audit-trail UI shows precisely which rule fired and why.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Invoice, PurchaseOrder
from app.services import duplicate_detector, fraud_detector, po_matcher
from app.services.audit import record_audit
from app.services.events import bus


def _vendor_history(db: Session, vendor_name: str, invoice_id: str) -> tuple[bool, Decimal | None]:
    """Return (is_new_vendor, avg_amount) from previously stored invoices.

    Excludes the current invoice (its vendor_name is already persisted by the
    extraction agent) so a first-time vendor is correctly seen as new.
    """
    rows = db.execute(
        select(Invoice.amount).where(
            Invoice.vendor_name == vendor_name, Invoice.id != invoice_id
        )
    ).scalars().all()
    if not rows:
        return True, None
    amounts = [Decimal(str(a)) for a in rows]
    return False, sum(amounts, Decimal("0")) / len(amounts)


def run(state: dict, db: Session) -> dict:
    invoice_id = state["invoice_id"]
    invoice = db.get(Invoice, invoice_id)
    invoice.status = "validating"

    vendor_name = invoice.vendor_name or ""
    amount = invoice.amount or Decimal("0")
    invoice_number = invoice.invoice_number or ""
    po_number = invoice.po_number
    line_items = (invoice.extracted_data or {}).get("line_items") or []

    bus.publish(
        invoice_id,
        {
            "type": "agent_started",
            "agent": "validation",
            "action": "validate",
            "status": "running",
            "invoice_status": "validating",
        },
    )

    issues: list[dict] = []
    checks: dict = {}

    # 1. PO match
    po_numbers = list(db.execute(select(PurchaseOrder.po_number)).scalars())
    po_match = po_matcher.match_po_number(po_number, po_numbers)
    checks["po_match"] = po_match
    record_audit(
        db,
        invoice_id=invoice_id,
        agent_name="validation",
        action="po_match",
        reasoning=po_match["reason"],
        rule_fired="po_match" if po_match["matched"] else ("po_mismatch" if po_number else None),
        confidence=po_match["similarity"] if po_match["matched"] else 1.0,
        input_data={"po_number": po_number},
        output_data={"matched": po_match["matched"], "matched_po": po_match.get("po_number")},
    )
    if po_number and not po_match["matched"]:
        issues.append({"check": "po_match", "severity": "high", "reason": po_match["reason"]})

    # 1b. Line-item comparison when a PO matched
    if po_match["matched"]:
        po = db.execute(
            select(PurchaseOrder).where(PurchaseOrder.po_number == po_match["po_number"])
        ).scalar_one_or_none()
        po_items = [
            {
                "description": li.description,
                "quantity": str(li.quantity),
                "unit_price": str(li.unit_price),
                "total": str(li.total),
            }
            for li in (po.line_items if po else [])
        ]
        li_compare = po_matcher.compare_line_items(line_items, po_items)
        checks["line_item_compare"] = li_compare
        record_audit(
            db,
            invoice_id=invoice_id,
            agent_name="validation",
            action="line_item_compare",
            reasoning=li_compare["reason"],
            rule_fired="line_items_match" if li_compare["ok"] else "line_item_mismatch",
            confidence=1.0 if li_compare["ok"] else 0.0,
            input_data={"invoice_items": line_items, "po_items": po_items},
            output_data={"mismatches": li_compare["mismatches"]},
        )
        if not li_compare["ok"]:
            issues.append(
                {"check": "line_item_compare", "severity": "high", "reason": li_compare["reason"]}
            )

    # 2. Duplicate detection
    existing = [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "vendor_name": inv.vendor_name,
            "amount": inv.amount,
        }
        for inv in db.execute(select(Invoice).where(Invoice.id != invoice_id)).scalars()
    ]
    dup = duplicate_detector.find_duplicates(invoice_number, vendor_name, amount, existing)
    checks["duplicate"] = dup
    record_audit(
        db,
        invoice_id=invoice_id,
        agent_name="validation",
        action="duplicate_check",
        reasoning=dup["reason"],
        rule_fired="duplicate_detected" if dup["duplicate"] else None,
        confidence=1.0,
        input_data={"invoice_number": invoice_number, "vendor_name": vendor_name, "amount": str(amount)},
        output_data={"matches": dup["matches"]},
    )
    if dup["duplicate"]:
        issues.append({"check": "duplicate", "severity": "block", "reason": dup["reason"]})

    # 3. Amount verification (line-item sum vs invoice total)
    if line_items:
        line_sum = sum(
            (po_matcher._to_decimal(li.get("total")) or Decimal("0")) for li in line_items
        )
        diff = abs(amount - line_sum)
        amt_ok = diff <= Decimal("0.01")
        checks["amount_verification"] = {
            "ok": amt_ok,
            "line_sum": str(line_sum),
            "total": str(amount),
            "diff": str(diff),
        }
        record_audit(
            db,
            invoice_id=invoice_id,
            agent_name="validation",
            action="amount_verification",
            reasoning=(
                f"Line items sum to ${line_sum} vs invoice total ${amount} "
                + ("(match)" if amt_ok else f"(mismatch by ${diff})")
            ),
            rule_fired=None if amt_ok else "line_sum_mismatch",
            confidence=1.0 if amt_ok else 0.0,
            input_data={"line_items": line_items, "total": str(amount)},
            output_data={"line_sum": str(line_sum), "difference": str(diff)},
        )
        if not amt_ok:
            issues.append(
                {
                    "check": "amount_verification",
                    "severity": "high",
                    "reason": f"Line items sum ${line_sum} != total ${amount}",
                }
            )

    # 4. Anomaly detection (new vendor, amount spikes)
    is_new_vendor, vendor_avg = _vendor_history(db, vendor_name, invoice_id)
    anomaly = fraud_detector.detect_anomalies(
        amount, vendor_name, vendor_avg_amount=vendor_avg, is_new_vendor=is_new_vendor
    )
    checks["anomalies"] = anomaly
    if anomaly["anomalies"]:
        for flag in anomaly["anomalies"]:
            record_audit(
                db,
                invoice_id=invoice_id,
                agent_name="validation",
                action="anomaly_check",
                reasoning=flag["reason"],
                rule_fired=flag["rule"],
                confidence=1.0,
                input_data={
                    "vendor_name": vendor_name,
                    "amount": str(amount),
                    "vendor_avg": str(vendor_avg) if vendor_avg else None,
                },
                output_data={"severity": flag["severity"]},
            )
            if flag["severity"] == "high":
                issues.append({"check": "anomaly", "severity": "high", "reason": flag["reason"]})
    else:
        record_audit(
            db,
            invoice_id=invoice_id,
            agent_name="validation",
            action="anomaly_check",
            reasoning=anomaly["reason"],
            rule_fired=None,
            confidence=1.0,
            input_data={"vendor_name": vendor_name, "amount": str(amount)},
        )

    blocking = [i for i in issues if i["severity"] in ("high", "block")]
    valid = not blocking
    validation_result = {"valid": valid, "issues": issues, "checks": checks, "new_vendor": is_new_vendor}

    bus.publish(
        invoice_id,
        {
            "type": "agent_done",
            "agent": "validation",
            "action": "validate",
            "status": "done",
            "valid": valid,
            "reasoning": (
                f"{len(blocking)} blocking issue(s), {len(issues) - len(blocking)} informational"
                if issues
                else "All validation checks passed"
            ),
            "issues": issues,
        },
    )

    return {"validation_result": validation_result, "current_step": "validation"}
