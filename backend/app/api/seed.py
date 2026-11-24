"""Seed demo data: purchase orders + prior vendor history."""
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Invoice, InvoiceStatus, POLineItem, PurchaseOrder

router = APIRouter()


def seed_demo_data(db: Session) -> dict:
    if db.execute(select(PurchaseOrder).limit(1)).first() is not None:
        return {"seeded": False, "reason": "already seeded"}

    po_acme = PurchaseOrder(
        po_number="PO-1042",
        vendor_name="Acme Industrial Supply",
        total_amount=Decimal("450.00"),
        status="open",
    )
    po_acme.line_items = [
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

    po_baker = PurchaseOrder(
        po_number="PO-2210",
        vendor_name="Baker Manufacturing",
        total_amount=Decimal("1200.50"),
        status="open",
    )
    po_baker.line_items = [
        POLineItem(
            description="Aluminum Sheet 4x8",
            quantity=Decimal("5"),
            unit_price=Decimal("240.10"),
            total=Decimal("1200.50"),
        ),
    ]

    po_cobalt = PurchaseOrder(
        po_number="PO-3301",
        vendor_name="Cobalt Logistics",
        total_amount=Decimal("8750.00"),
        status="open",
    )
    po_cobalt.line_items = [
        POLineItem(
            description="Freight - LTL shipment",
            quantity=Decimal("1"),
            unit_price=Decimal("8750.00"),
            total=Decimal("8750.00"),
        ),
    ]

    prior_acme = Invoice(
        invoice_number="INV-2024-000",
        vendor_name="Acme Industrial Supply",
        vendor_email="billing@acmeindustrial.com",
        amount=Decimal("400.00"),
        status=InvoiceStatus.PAID.value,
    )
    prior_baker = Invoice(
        invoice_number="INV-2024-010",
        vendor_name="Baker Manufacturing",
        vendor_email="ap@bakermfg.com",
        amount=Decimal("980.00"),
        status=InvoiceStatus.PAID.value,
    )
    prior_cobalt = Invoice(
        invoice_number="INV-2024-020",
        vendor_name="Cobalt Logistics",
        vendor_email="invoices@cobaltlogistics.com",
        amount=Decimal("7000.00"),
        status=InvoiceStatus.PAID.value,
    )

    db.add_all(
        [po_acme, po_baker, po_cobalt, prior_acme, prior_baker, prior_cobalt]
    )
    db.commit()
    return {"seeded": True, "purchase_orders": 3, "prior_invoices": 3}


@router.post("/")
def seed(db: Session = Depends(get_db)) -> dict:
    return seed_demo_data(db)
