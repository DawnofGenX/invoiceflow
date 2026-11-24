"""LangGraph state schema."""
from typing import Any, TypedDict


class InvoiceState(TypedDict, total=False):
    invoice_id: str
    file_path: str
    raw_text: str
    document_type: str
    extracted_data: dict[str, Any]
    validation_result: dict[str, Any]
    approval_decision: dict[str, Any]
    errors: list[str]
    current_step: str
    confidence_scores: dict[str, float]
