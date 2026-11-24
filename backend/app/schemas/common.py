"""Shared/aggregate schemas."""
from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_invoices: int
    by_status: dict[str, int]
    total_amount: float
    pending_approvals: int
    needs_review: int
    auto_approved: int
