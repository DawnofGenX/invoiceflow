"""Line-item PO matching must survive into the persisted record.

The invoice record renders a MATCH column from `LineItem.matched_po_line_id`,
but nothing in the pipeline ever wrote that column: the validation agent
compared the line items and threw the result away. The record therefore said
"unmatched" on every row while the decision trail said "All 2 line items match
the PO" - two contradictory statements about the same invoice.

These tests pin the behaviour that closes that gap, plus the rule-token
consistency the audit trail depends on.
"""
from decimal import Decimal

import pytest

from app.agents.orchestrator import process_invoice
from app.database import Base, SessionLocal, engine
from app.models import (
    AuditLog,
    Invoice,
    InvoiceStatus,
    POLineItem,
    PurchaseOrder,
)


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def _seed_po(db) -> PurchaseOrder:
    po = PurchaseOrder(
        po_number="PO-1042",
        vendor_name="Acme Industrial Supply",
        total_amount=Decimal("450.00"),
        status="open",
    )
    po.line_items = [
        POLineItem(
            description="Steel Bracket",
            quantity=Decimal("10"),
            unit_price=Decimal("15.00"),
            total=Decimal("150.00"),
        ),
        POLineItem(
            description="Hex Bolts M8",
            quantity=Decimal("200"),
            unit_price=Decimal("1.50"),
            total=Decimal("300.00"),
        ),
    ]
    db.add(po)
    db.commit()
    return po


def _seed_prior_vendor(db) -> None:
    db.add(
        Invoice(
            invoice_number="INV-2024-000",
            vendor_name="Acme Industrial Supply",
            vendor_email="acme@acmeindustrial.com",
            amount=Decimal("400.00"),
            status=InvoiceStatus.PAID.value,
        )
    )
    db.commit()


INVOICE_TEXT = """INVOICE
Acme Industrial Supply
123 Main Street, Chicago, IL 60601

Invoice Number: INV-2024-001
Invoice Date: 2024-11-15
Due Date: 2024-12-15
PO Number: PO-1042

Item             Qty   Unit Price   Total
Steel Bracket    10    15.00        150.00
Hex Bolts M8     200   1.50         300.00

Total: $450.00
"""


def _run(db, text: str) -> Invoice:
    inv = Invoice(
        invoice_number="TMP-PENDING",
        vendor_name="",
        amount=Decimal("0"),
        status=InvoiceStatus.PENDING.value,
    )
    db.add(inv)
    db.commit()
    process_invoice(db, inv.id, "sample.pdf", text)
    return db.get(Invoice, inv.id)


def test_matched_line_items_are_marked_on_the_record():
    """A line item that matched a PO line must not render as unmatched."""
    db = SessionLocal()
    _seed_po(db)
    _seed_prior_vendor(db)

    inv = _run(db, INVOICE_TEXT)

    assert inv.status == InvoiceStatus.PAYMENT_SCHEDULED.value
    items = list(inv.line_items)
    assert len(items) == 2
    assert all(item.matched_po_line_id for item in items), (
        f"expected both line items to carry a PO line reference, got "
        f"{[(i.description, i.matched_po_line_id) for i in items]}"
    )
    db.close()


def test_mismatched_line_item_is_left_unmatched():
    """A price that differs from the PO must not be marked as matched."""
    db = SessionLocal()
    _seed_po(db)
    _seed_prior_vendor(db)

    text = INVOICE_TEXT.replace("150.00", "190.00").replace("Total: $450.00", "Total: $490.00")
    inv = _run(db, text)

    assert inv.status == InvoiceStatus.NEEDS_REVIEW.value
    items = list(inv.line_items)
    bracket = next(i for i in items if "Steel" in i.description)
    assert bracket.matched_po_line_id is None
    db.close()


def test_line_total_that_contradicts_its_own_quantity_is_rejected():
    """10 x $15.00 printed as $190.00 is a tampered line, not a match.

    Only the unit price and quantity were compared against the PO, so a line
    whose own arithmetic was wrong passed every check - while the invoice
    total was quietly inflated by $40.
    """
    db = SessionLocal()
    _seed_po(db)
    _seed_prior_vendor(db)

    text = INVOICE_TEXT.replace("150.00", "190.00")
    inv = _run(db, text)

    assert inv.status == InvoiceStatus.NEEDS_REVIEW.value
    entries = (
        db.query(AuditLog)
        .filter(AuditLog.invoice_id == inv.id, AuditLog.action == "line_item_compare")
        .all()
    )
    assert entries, "expected a line_item_compare decision entry"
    assert "does not equal" in entries[0].reasoning
    db.close()


def test_auto_approval_uses_one_canonical_rule_token():
    """The audit trail must not split one rule across two spellings.

    `auto-approve` (the seeded rule name) and `auto_approve` (the orchestrator's
    token) used to both appear, so the "rules that fired" table counted the
    same rule twice.
    """
    db = SessionLocal()
    _seed_po(db)
    _seed_prior_vendor(db)

    inv = _run(db, INVOICE_TEXT)

    fired = [
        e.rule_fired
        for e in db.query(AuditLog).filter(AuditLog.invoice_id == inv.id).all()
        if e.rule_fired
    ]
    assert "auto_approve" in fired
    assert "auto-approve" not in fired, f"kebab-case duplicate rule token in {fired}"
    db.close()


def test_amount_verification_reasoning_uses_two_decimals():
    """Money in the decision trail must not read as $450.0."""
    db = SessionLocal()
    _seed_po(db)
    _seed_prior_vendor(db)

    inv = _run(db, INVOICE_TEXT)

    entry = (
        db.query(AuditLog)
        .filter(AuditLog.invoice_id == inv.id, AuditLog.action == "amount_verification")
        .one()
    )
    assert "$450.00" in entry.reasoning
    assert "$450.0 " not in entry.reasoning
    db.close()


def test_tampered_line_message_shows_money_with_cents():
    """The mismatch message is the one line a reviewer reads - it must be $190.00, not $190.0."""
    db = SessionLocal()
    _seed_po(db)
    _seed_prior_vendor(db)

    text = INVOICE_TEXT.replace("150.00", "190.00")
    inv = _run(db, text)

    entry = (
        db.query(AuditLog)
        .filter(AuditLog.invoice_id == inv.id, AuditLog.action == "line_item_compare")
        .one()
    )
    assert "$190.00" in entry.reasoning
    assert "$190.0 " not in entry.reasoning
    assert "$15.00" in entry.reasoning
    db.close()
