"""Maintenance endpoints — operational reset helpers for the smoke test.

The end-to-end smoke test uploads the same fixtures on every run. Each run
therefore leaves behind invoices whose invoice numbers collide with the next
run's fixtures, so the duplicate-detection rule fires on the fixture itself and
the test fails even though the product is behaving correctly.

`POST /api/maintenance/reset-e2e` removes exactly those test artifacts — rows
whose stored upload name starts with `e2e-` (the name the smoke test uploads
under) or the legacy `sample-` prefix — and never touches the seeded demo data
or any real upload.

Safety: the endpoint is disabled entirely unless `E2E_RESET_TOKEN` is
configured, and every call must present that token in the `X-E2E-Token`
header. Comparison is constant-time.
"""
from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ApprovalRequest, AuditLog, Invoice, LineItem, Payment

router = APIRouter()

# Upload-name prefixes owned by the test harness. Seeded rows have file_path
# NULL and real uploads keep their own names, so neither is matched here.
_OWNED_PREFIXES = ("e2e-",)

# Exact names uploaded by the smoke test before the `e2e-` prefix existed.
# Matched exactly (not by prefix) so an unrelated user upload that happens to
# start with "sample-" is never touched.
_LEGACY_FIXTURE_NAMES = (
    "sample-clean.pdf",
    "sample-new-vendor.pdf",
    "sample-duplicate.pdf",
    "sample-high-value.pdf",
    "sample-contract.pdf",
)


def _owned_invoice_ids(db: Session) -> list[str]:
    clauses = [Invoice.file_path.like(f"{prefix}%") for prefix in _OWNED_PREFIXES]
    clauses += [Invoice.file_path == name for name in _LEGACY_FIXTURE_NAMES]
    # `or_` is required: `where(*clauses)` would AND them together and match
    # nothing, since a row can never satisfy both a prefix match and an exact
    # name match at the same time.
    return list(db.execute(select(Invoice.id).where(or_(*clauses))).scalars())


def _count(db: Session, model: Any, column: Any, ids: list[str]) -> int:
    """Count rows of `model` whose `column` is in `ids`."""
    return int(
        db.execute(select(func.count()).select_from(model).where(column.in_(ids))).scalar_one()
    )


@router.post("/reset-e2e")
def reset_e2e(
    db: Session = Depends(get_db),
    x_e2e_token: str = Header(default="", alias="X-E2E-Token"),
) -> dict:
    """Delete smoke-test artifacts. Requires E2E_RESET_TOKEN to be configured."""
    expected = settings.e2e_reset_token
    if not expected:
        raise HTTPException(
            status_code=404, detail="maintenance endpoints are not enabled"
        )
    if not x_e2e_token or not secrets.compare_digest(x_e2e_token, expected):
        raise HTTPException(
            status_code=403, detail="missing or invalid X-E2E-Token"
        )

    invoice_ids = _owned_invoice_ids(db)
    removed = {
        "invoices": 0,
        "audit_logs": 0,
        "line_items": 0,
        "payments": 0,
        "approval_requests": 0,
    }
    if invoice_ids:
        # Count before deleting: the ORM result object does not expose rowcount
        # in a type-safe way, and the counts are part of the response contract.
        removed["audit_logs"] = _count(db, AuditLog, AuditLog.invoice_id, invoice_ids)
        removed["line_items"] = _count(db, LineItem, LineItem.invoice_id, invoice_ids)
        removed["payments"] = _count(db, Payment, Payment.invoice_id, invoice_ids)
        removed["approval_requests"] = _count(
            db, ApprovalRequest, ApprovalRequest.invoice_id, invoice_ids
        )
        removed["invoices"] = _count(db, Invoice, Invoice.id, invoice_ids)

        db.execute(delete(AuditLog).where(AuditLog.invoice_id.in_(invoice_ids)))
        db.execute(delete(LineItem).where(LineItem.invoice_id.in_(invoice_ids)))
        db.execute(delete(Payment).where(Payment.invoice_id.in_(invoice_ids)))
        db.execute(delete(ApprovalRequest).where(ApprovalRequest.invoice_id.in_(invoice_ids)))
        db.execute(delete(Invoice).where(Invoice.id.in_(invoice_ids)))
    db.commit()
    return {"reset": True, "removed": removed}
