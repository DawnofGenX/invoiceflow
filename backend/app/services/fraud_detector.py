"""Fraud / anomaly detection.

Checks that are deliberately rule-based (not LLM) so the reasoning is exact and
reproducible — the whole point of the explainability wedge.
"""
from decimal import Decimal
from typing import Any


def detect_anomalies(
    amount: Decimal,
    vendor_name: str,
    *,
    vendor_avg_amount: Decimal | None,
    is_new_vendor: bool,
) -> dict[str, Any]:
    """Return a list of anomaly flags with the exact rule that fired."""
    flags: list[dict[str, Any]] = []

    # New vendor: no prior history with this vendor.
    if is_new_vendor:
        flags.append(
            {
                "severity": "info",
                "rule": "new_vendor",
                "reason": f"First invoice from vendor '{vendor_name}' — no transaction history",
            }
        )

    # Amount > 3x the vendor's historical average.
    if vendor_avg_amount is not None and vendor_avg_amount > 0:
        ratio = amount / vendor_avg_amount
        if ratio > 3:
            flags.append(
                {
                    "severity": "high",
                    "rule": "amount_3x_average",
                    "reason": (
                        f"Amount ${amount} is {ratio:.1f}x the vendor's "
                        f"average of ${vendor_avg_amount}"
                    ),
                }
            )

    if not flags:
        return {"anomalies": [], "reason": "No anomalies detected"}

    return {
        "anomalies": flags,
        "reason": f"{len(flags)} anomaly flag(s) raised",
    }
