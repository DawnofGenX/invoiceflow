"""Fuzzy PO matching and line-item comparison."""
import difflib
from decimal import Decimal
from typing import Any


def _norm(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


def match_po_number(invoice_po: str | None, po_numbers: list[str]) -> dict[str, Any]:
    """Fuzzy-match an invoice's PO number against known PO numbers.

    Returns a dict with `matched`, `po_number`, `similarity`, and `reason`.
    """
    if not invoice_po or not invoice_po.strip():
        return {
            "matched": False,
            "po_number": None,
            "similarity": 0.0,
            "reason": "No PO number present on the invoice",
        }

    target = _norm(invoice_po)
    best_po: str | None = None
    best_ratio = 0.0
    for po in po_numbers:
        ratio = difflib.SequenceMatcher(None, target, _norm(po)).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_po = po

    if best_po is not None and best_ratio >= 0.8:
        return {
            "matched": True,
            "po_number": best_po,
            "similarity": round(best_ratio, 3),
            "reason": f"Invoice PO '{invoice_po}' fuzzy-matches '{best_po}' ({best_ratio:.0%})",
        }
    return {
        "matched": False,
        "po_number": best_po,
        "similarity": round(best_ratio, 3),
        "reason": (
            f"No PO matched '{invoice_po}'"
            + (f" (closest '{best_po}' at {best_ratio:.0%})" if best_po else "")
        ),
    }


def compare_line_items(
    invoice_items: list[dict[str, Any]],
    po_items: list[dict[str, Any]],
    tolerance: Decimal = Decimal("0.05"),
) -> dict[str, Any]:
    """Compare invoice line items to PO line items within a price tolerance.

    invoice_items / po_items: list of {description, quantity, unit_price, total}.
    """
    if not po_items:
        return {
            "ok": False,
            "reason": "PO has no line items to compare against",
            "mismatches": [],
        }

    mismatches: list[dict[str, Any]] = []
    matched = 0
    for inv in invoice_items:
        best = None
        for poi in po_items:
            if _norm(inv.get("description", "")) == _norm(poi.get("description", "")):
                best = poi
                break
        if best is None:
            mismatches.append(
                {"description": inv.get("description"), "issue": "No matching PO line item"}
            )
            continue

        # Price tolerance check on unit price (and total where comparable).
        inv_price = _to_decimal(inv.get("unit_price"))
        po_price = _to_decimal(best.get("unit_price"))
        inv_qty = _to_decimal(inv.get("quantity"))
        po_qty = _to_decimal(best.get("quantity"))
        price_ok = inv_price is not None and po_price is not None and _within_tol(
            inv_price, po_price, tolerance
        )
        qty_ok = inv_qty is not None and po_qty is not None and _within_tol(
            inv_qty, po_qty, tolerance
        )
        if price_ok and qty_ok:
            matched += 1
        else:
            mismatches.append(
                {
                    "description": inv.get("description"),
                    "issue": (
                        f"Price/quantity differs from PO "
                        f"(invoice {inv_qty}x${inv_price} vs PO {po_qty}x${po_price})"
                    ),
                }
            )

    if not mismatches:
        return {"ok": True, "reason": f"All {matched} line items match the PO", "mismatches": []}
    return {
        "ok": False,
        "reason": f"{matched} matched, {len(mismatches)} line-item mismatch(es)",
        "mismatches": mismatches,
    }


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", "").replace("$", "").strip())
    except Exception:
        return None


def _within_tol(a: Decimal, b: Decimal, tol: Decimal) -> bool:
    if b == 0:
        return a == 0
    return abs(a - b) / abs(b) <= tol
