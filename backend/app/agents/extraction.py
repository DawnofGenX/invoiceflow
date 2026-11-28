"""Extraction agent — pulls structured invoice fields out of the raw text and
persists them to the Invoice row so validation/approval read consistent state.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Invoice, LineItem
from app.services import llm
from app.services.audit import record_audit
from app.services.events import bus

_SYSTEM = (
    "You are the Extraction Agent of an accounts-payable system. "
    "Extract structured invoice data from the document text. "
    "Return JSON only. Use null for any field not present."
)

_SCHEMA_HINT = """Return a JSON object with exactly these keys:
{
  "vendor_name": string,
  "vendor_email": string or null,
  "invoice_number": string,
  "amount": number,
  "currency": string (default "USD"),
  "tax_amount": number or null,
  "invoice_date": "YYYY-MM-DD" or null,
  "due_date": "YYYY-MM-DD" or null,
  "po_number": string or null,
  "line_items": [{"description": string, "quantity": number, "unit_price": number, "total": number}],
  "confidence": 0.0-1.0,
  "reasoning": string
}"""


def _dec(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "").replace("$", "").strip())
    except Exception:
        return None


def _date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def run(state: dict, db: Session) -> dict:
    invoice_id = state["invoice_id"]
    raw_text = state.get("raw_text", "")
    doc_type = state.get("document_type", "invoice")
    invoice = db.get(Invoice, invoice_id)

    bus.publish(
        invoice_id,
        {
            "type": "agent_started",
            "agent": "extraction",
            "action": "extract_fields",
            "status": "running",
            "invoice_status": "extracting",
        },
    )

    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"{_SCHEMA_HINT}\n\nDocument text:\n{raw_text[:6000]}"},
    ]

    try:
        result, duration_ms = llm.complete_json(settings.llm_reasoning_model, messages)
    except llm.LLMError as e:
        # Deterministic degradation for ANY upstream failure (retries already
        # exhausted for transient ones): recover labelled fields from the text
        # itself (same parsing semantics as the stub, so duplicate/fraud
        # checks stay consistent), low confidence, llm_unavailable marker.
        # The request still completes — it never 500s on an upstream outage.
        result = llm.fallback_extract(raw_text)
        duration_ms = 0
        result["reasoning"] = f"{result['reasoning']} (upstream: {e})"

    confidence = float(result.get("confidence", 0.0))
    reasoning = str(result.get("reasoning", ""))

    # Persist extracted fields to the Invoice row (validation reads these).
    invoice.vendor_name = str(result.get("vendor_name") or "")[:255]
    invoice.vendor_email = result.get("vendor_email")
    invoice.invoice_number = str(result.get("invoice_number") or "")[:64]
    invoice.amount = _dec(result.get("amount")) or Decimal("0")
    invoice.currency = str(result.get("currency") or "USD")[:8]
    invoice.tax_amount = _dec(result.get("tax_amount"))
    invoice.invoice_date = _date(result.get("invoice_date"))
    invoice.due_date = _date(result.get("due_date"))
    invoice.po_number = result.get("po_number")
    invoice.extracted_data = result
    invoice.confidence_score = confidence

    # Persist line items (fresh invoice — clear guards against re-run duplicates).
    invoice.line_items.clear()
    for li in result.get("line_items") or []:
        invoice.line_items.append(
            LineItem(
                description=str(li.get("description") or "")[:255],
                quantity=_dec(li.get("quantity")) or Decimal("0"),
                unit_price=_dec(li.get("unit_price")) or Decimal("0"),
                total=_dec(li.get("total")) or Decimal("0"),
            )
        )

    record_audit(
        db,
        invoice_id=invoice_id,
        agent_name="extraction",
        action="extract_fields",
        reasoning=reasoning,
        rule_fired=result.get("rule_fired"),
        confidence=confidence,
        input_data={"document_type": doc_type, "raw_text_preview": raw_text[:500]},
        output_data={
            "vendor_name": result.get("vendor_name"),
            "invoice_number": result.get("invoice_number"),
            "amount": result.get("amount"),
            "po_number": result.get("po_number"),
        },
        duration_ms=duration_ms,
    )

    bus.publish(
        invoice_id,
        {
            "type": "agent_done",
            "agent": "extraction",
            "action": "extract_fields",
            "status": "done",
            "reasoning": reasoning,
            "confidence": confidence,
            "vendor_name": result.get("vendor_name"),
            "amount": result.get("amount"),
        },
    )

    return {
        "extracted_data": result,
        "current_step": "extraction",
        "confidence_scores": {**state.get("confidence_scores", {}), "extraction": confidence},
    }
