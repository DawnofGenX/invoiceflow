"""Duplicate invoice detection."""
from decimal import Decimal
from typing import Any


def _norm(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


def find_duplicates(
    invoice_number: str,
    vendor_name: str,
    amount: Decimal,
    existing: list[dict[str, Any]],
) -> dict[str, Any]:
    """Detect a duplicate invoice among previously stored invoices.

    `existing` is a list of {invoice_number, vendor_name, amount, id}.
    """
    target_num = _norm(invoice_number)
    target_vendor = _norm(vendor_name)
    dupes: list[dict[str, Any]] = []
    for inv in existing:
        same_number = _norm(inv.get("invoice_number", "")) == target_num
        same_vendor = _norm(inv.get("vendor_name", "")) == target_vendor
        same_amount = _amounts_equal(inv.get("amount"), amount)

        # Strong duplicate: identical invoice number (+ vendor and/or amount).
        if same_number and (same_vendor or same_amount):
            dupes.append(
                {
                    "id": inv.get("id"),
                    "invoice_number": inv.get("invoice_number"),
                    "vendor_name": inv.get("vendor_name"),
                    "amount": str(inv.get("amount")),
                    "signal": "same invoice number + vendor/amount",
                }
            )
        # Weaker duplicate: same vendor + amount but different number.
        elif same_vendor and same_amount:
            dupes.append(
                {
                    "id": inv.get("id"),
                    "invoice_number": inv.get("invoice_number"),
                    "vendor_name": inv.get("vendor_name"),
                    "amount": str(inv.get("amount")),
                    "signal": "same vendor + amount, different invoice number",
                }
            )

    if dupes:
        return {
            "duplicate": True,
            "reason": f"Found {len(dupes)} possible duplicate(s) of this invoice",
            "matches": dupes,
        }
    return {"duplicate": False, "reason": "No duplicate found", "matches": []}


def _amounts_equal(a: Any, b: Decimal) -> bool:
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except Exception:
        return False
