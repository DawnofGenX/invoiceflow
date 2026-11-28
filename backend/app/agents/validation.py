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


def _money(value: Decimal | int) -> str:
    """Render money with two decimals.

    Money reaches the validator as a float (the extractor parses "150.00" out
    of the document), so `Decimal("150.0") + Decimal("300.0")` renders as
    "$450.0" - money printed without its cents.
    """
    return f"{value:.2f}"


def _line_key(item: dict) -> tuple:
    """Content key for an invoice line, used to pair it with its stored row.

    The matcher works on the extracted list (authoritative order); the record
    renders the stored LineItem rows. Pairing them by content rather than by
    position means a re-ordered relationship can never mislabel a line.

    Numbers are compared as Decimals: the extractor yields floats (10.0) while
    the stored rows hold Decimals (Decimal("10.00")).
    """
    return (
        po_matcher._norm(str(item.get("description") or "")),
        _num_key(item.get("quantity")),
        _num_key(item.get("unit_price")),
        _num_key(item.get("total")),
    )


def _num_key(value) -> str:
    """Normalise a number for content comparison (150.0 == 150.00)."""
    if value is None:
        return ""
    decimal = po_matcher._to_decimal(value)
    if decimal is None:
        return str(value).strip()
    return f"{decimal.normalize():f}"


def _stored_line_key(item) -> tuple:
    return (
        po_matcher._norm(item.description or ""),
        _num_key(item.quantity),
        _num_key(item.unit_price),
        _num_key(item.total),
    )


def _apply_po_line_matches(invoice: Invoice, li_compare: dict) -> None:
    """Write the PO line reference onto each matched invoice line item.

    `compare_line_items` returns the index of every invoice line that matched
    a PO line within tolerance. The record's MATCH column reads
    `LineItem.matched_po_line_id`, so without this the record always said
    "unmatched". Line items that did not match are explicitly cleared, so a
    stale reference can never survive a re-run.
    """
    matched_by_index = {m["index"]: m.get("po_line_id") for m in li_compare.get("matches") or []}
    extracted = (invoice.extracted_data or {}).get("line_items") or []

    # Pair stored rows with extracted lines by content, not by position.
    rows_by_key: dict[tuple, list] = {}
    for row in invoice.line_items:
        rows_by_key.setdefault(_stored_line_key(row), []).append(row)

    for index, item in enumerate(extracted):
        pool = rows_by_key.get(_line_key(item))
        row = pool.pop(0) if pool else None
        if row is None:
            continue
        row.matched_po_line_id = matched_by_index.get(index)

    # Any stored row with no extracted counterpart stays unmatched.
    for row in invoice.line_items:
        if not row.matched_po_line_id:
            row.matched_po_line_id = None


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
                "id": li.id,
                "description": li.description,
                "quantity": str(li.quantity),
                "unit_price": str(li.unit_price),
                "total": str(li.total),
            }
            for li in (po.line_items if po else [])
        ]
        li_compare = po_matcher.compare_line_items(line_items, po_items)
        checks["line_item_compare"] = li_compare
        # Persist the match onto the invoice's own line-item rows so the record
        # and the decision trail agree. Without this the record rendered every
        # row as "unmatched" while the trail said "All 2 line items match the
        # PO" - two contradictory statements about the same invoice.
        _apply_po_line_matches(invoice, li_compare)
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
                f"Line items sum to ${_money(line_sum)} vs invoice total ${_money(amount)} "
                + ("(match)" if amt_ok else f"(mismatch by ${_money(diff)})")
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
                    "reason": f"Line items sum ${_money(line_sum)} != total ${_money(amount)}",
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
