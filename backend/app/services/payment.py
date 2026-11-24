"""Mock payment scheduling (no real payment rails — decision #1/#18)."""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Invoice, InvoiceStatus, Payment, PaymentStatus


def schedule_mock_payment(db: Session, invoice: Invoice) -> Payment:
    """Mark an approved invoice as payment-scheduled with a mock reference."""
    due = invoice.due_date
    scheduled = due if due is not None else date.today() + timedelta(days=3)
    payment = Payment(
        invoice_id=invoice.id,
        amount=invoice.amount,
        scheduled_date=scheduled,
        status=PaymentStatus.SCHEDULED.value,
        payment_reference=f"PAY-{invoice.invoice_number}",
    )
    db.add(payment)
    invoice.status = InvoiceStatus.PAYMENT_SCHEDULED.value
    return payment
