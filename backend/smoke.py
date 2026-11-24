"""Smoke test: seed a PO + known vendor, run one clean invoice through the pipeline."""
from decimal import Decimal

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import (
    AuditLog,
    Invoice,
    InvoiceStatus,
    POLineItem,
    Payment,
    PurchaseOrder,
)


def main() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()

    # Seed a PO with two line items.
    po = PurchaseOrder(
        po_number="PO-1042",
        vendor_name="Acme Industrial Supply",
        total_amount=Decimal("450.00"),
        status="open",
    )
    po.line_items.append(
        POLineItem(description="Steel Bracket", quantity=Decimal("10"), unit_price=Decimal("15.00"), total=Decimal("150.00"))
    )
    po.line_items.append(
        POLineItem(description="Hex Bolts M8", quantity=Decimal("200"), unit_price=Decimal("1.50"), total=Decimal("300.00"))
    )
    db.add(po)

    # Prior invoice from the same vendor (establishes history, so this is NOT a new vendor).
    prior = Invoice(
        invoice_number="INV-2024-000",
        vendor_name="Acme Industrial Supply",
        vendor_email="acme@acmeindustrial.com",
        amount=Decimal("400.00"),
        currency="USD",
        status=InvoiceStatus.PAID.value,
    )
    db.add(prior)
    db.commit()

    # The invoice under test.
    inv = Invoice(invoice_number="INV-2024-001", vendor_name="", amount=Decimal("0"), status=InvoiceStatus.PENDING.value)
    db.add(inv)
    db.commit()
    invoice_id = inv.id

    raw_text = """INVOICE
Acme Industrial Supply
123 Main Street, Chicago, IL 60601
acme@acmeindustrial.com

Invoice Number: INV-2024-001
Invoice Date: 2024-11-15
Due Date: 2024-12-15
PO Number: PO-1042

Bill To: InvoiceFlow Inc., 456 Market Street, San Francisco, CA 94105

Item             Qty   Unit Price   Total
Steel Bracket    10    15.00        150.00
Hex Bolts M8     200   1.50         300.00

Total: $450.00
"""

    from app.agents.orchestrator import process_invoice

    process_invoice(db, invoice_id, "sample.pdf", raw_text)

    inv = db.get(Invoice, invoice_id)
    print("=== FINAL STATE ===")
    print("status:", inv.status)
    print("vendor:", inv.vendor_name)
    print("invoice_number:", inv.invoice_number)
    print("amount:", inv.amount)
    print("po_number:", inv.po_number)
    print("confidence:", inv.confidence_score)
    print("line items:", [(li.description, str(li.quantity), str(li.total)) for li in inv.line_items])

    print("\n=== AUDIT TRAIL ===")
    for a in db.execute(
        select(AuditLog).where(AuditLog.invoice_id == invoice_id).order_by(AuditLog.created_at)
    ).scalars():
        print(f"[{a.agent_name}] {a.action} | rule={a.rule_fired} | conf={a.confidence:.2f} | {a.reasoning[:90]}")

    print("\n=== PAYMENTS ===")
    for p in db.execute(select(Payment).where(Payment.invoice_id == invoice_id)).scalars():
        print(p.status, p.payment_reference, p.amount)

    db.close()


if __name__ == "__main__":
    main()
