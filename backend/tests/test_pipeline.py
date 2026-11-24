"""End-to-end pipeline tests across all routing branches."""
from decimal import Decimal

import pytest

from app.database import Base, SessionLocal, engine
from app.models import Invoice, InvoiceStatus
from app.agents.orchestrator import process_invoice


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def _create_invoice(db, number="TMP-PENDING"):
    inv = Invoice(invoice_number=number, vendor_name="", amount=Decimal("0"), status=InvoiceStatus.PENDING.value)
    db.add(inv)
    db.commit()
    return inv


def _run(db, inv, text):
    process_invoice(db, inv.id, "sample.pdf", text)
    return db.get(Invoice, inv.id)


def test_happy_path_auto_approve():
    db = SessionLocal()
    prior = Invoice(
        invoice_number="INV-2024-000",
        vendor_name="Acme Industrial Supply",
        vendor_email="acme@acmeindustrial.com",
        amount=Decimal("400.00"),
        status=InvoiceStatus.PAID.value,
    )
    db.add(prior)
    db.commit()

    inv = _create_invoice(db)
    text = """INVOICE
Acme Industrial Supply
123 Main Street, Chicago, IL 60601

Invoice Number: INV-2024-001
Invoice Date: 2024-11-15
Due Date: 2024-12-15

Item             Qty   Unit Price   Total
Steel Bracket    10    15.00        150.00
Hex Bolts M8     200   1.50         300.00

Total: $450.00
"""
    inv = _run(db, inv, text)
    assert inv.status == InvoiceStatus.PAYMENT_SCHEDULED.value
    assert inv.vendor_name == "Acme Industrial Supply"
    assert inv.amount == Decimal("450.00")
    assert inv.invoice_number == "INV-2024-001"
    db.close()


def test_new_vendor_routes_to_manager():
    db = SessionLocal()
    inv = _create_invoice(db)
    text = """INVOICE
Brand New Co
Invoice Number: INV-2024-001
Item              Qty  Unit Price   Total
Widget           2    100.00        200.00
Total: $200.00
"""
    inv = _run(db, inv, text)
    assert inv.status == InvoiceStatus.AWAITING_APPROVAL.value
    db.close()


def test_duplicate_flagged_for_review():
    db = SessionLocal()
    existing = Invoice(
        invoice_number="INV-2024-001",
        vendor_name="Acme Industrial Supply",
        amount=Decimal("450.00"),
        status=InvoiceStatus.PAID.value,
    )
    db.add(existing)
    db.commit()

    inv = _create_invoice(db)
    text = """INVOICE
Acme Industrial Supply
Invoice Number: INV-2024-001
Item              Qty   Unit Price   Total
Steel Bracket    10    15.00        150.00
Hex Bolts M8     200   1.50         300.00
Total: $450.00
"""
    inv = _run(db, inv, text)
    assert inv.status == InvoiceStatus.NEEDS_REVIEW.value
    db.close()


def test_not_an_invoice_rejected():
    db = SessionLocal()
    inv = _create_invoice(db)
    text = """CONTRACT AGREEMENT
This agreement is entered into between Party A and Party B.
Terms and conditions apply. This is a legal contract, not an invoice.
"""
    inv = _run(db, inv, text)
    assert inv.status == InvoiceStatus.REJECTED.value
    db.close()
