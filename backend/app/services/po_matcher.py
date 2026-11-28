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
            "matches": [],
        }

    mismatches: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    matched = 0
    for index, inv in enumerate(invoice_items):
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

        # The invoice must agree with ITSELF before it can agree with the PO:
        # quantity x unit price must equal the printed line total. Without this
        # a tampered line total (10 x $15.00 printed as $190.00) sailed through
        # every check, because only the unit price and quantity were compared.
        inv_qty = _to_decimal(inv.get("quantity"))
        inv_price = _to_decimal(inv.get("unit_price"))
        inv_total = _to_decimal(inv.get("total"))
        if inv_qty is not None and inv_price is not None and inv_total is not None:
            expected_total = inv_qty * inv_price
            if not _within_tol(inv_total, expected_total, tolerance):
                mismatches.append(
                    {
                        "description": inv.get("description"),
                        "issue": (
                            f"Line total ${_fmt(inv_total)} does not equal "
                            f"{_fmt(inv_qty)} x ${_fmt(inv_price)} (${_fmt(expected_total)})"
                        ),
                    }
                )
                continue

        # Price tolerance check on unit price (and total where comparable).
        po_price = _to_decimal(best.get("unit_price"))
        po_qty = _to_decimal(best.get("quantity"))
        price_ok = inv_price is not None and po_price is not None and _within_tol(
            inv_price, po_price, tolerance
        )
        qty_ok = inv_qty is not None and po_qty is not None and _within_tol(
            inv_qty, po_qty, tolerance
        )
        if price_ok and qty_ok:
            matched += 1
            matches.append(
                {
                    "index": index,
                    "description": inv.get("description"),
                    "po_line_id": best.get("id"),
                }
            )
        else:
            mismatches.append(
                {
                    "description": inv.get("description"),
                    "issue": (
                        f"Price/quantity differs from PO "
                        f"(invoice {_fmt(inv_qty)}x${_fmt(inv_price)} vs PO "
                        f"{_fmt(po_qty)}x${_fmt(po_price)})"
                    ),
                }
            )

    if not mismatches:
        return {
            "ok": True,
            "reason": f"All {matched} line items match the PO",
            "mismatches": [],
            "matches": matches,
        }
    # Name the specific problems: "1 line-item mismatch(es)" tells a reviewer
    # nothing about which line and why, which is the whole point of the trail.
    detail = "; ".join(
        f"{m.get('description')}: {m.get('issue')}" for m in mismatches[:3]
    )
    return {
        "ok": False,
        "reason": (
            f"{matched} matched, {len(mismatches)} line-item mismatch(es) — {detail}"
        ),
        "mismatches": mismatches,
        "matches": matches,
    }


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", "").replace("$", "").strip())
    except Exception:
        return None


def _fmt(value: Decimal | None) -> str:
    """Render a number as money with two decimals.

    Money reaches the matcher as a float (the extractor parses "15.00" out of
    the document), so plain str() would print "$190.0" - money without its
    cents, in the one message a reviewer actually reads.
    """
    if value is None:
        return "?"
    return f"{value:.2f}"


def _within_tol(a: Decimal, b: Decimal, tol: Decimal) -> bool:
    if b == 0:
        return a == 0
    return abs(a - b) / abs(b) <= tol
