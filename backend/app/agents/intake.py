"""Intake agent — classifies the document type and routes accordingly."""
from sqlalchemy.orm import Session

from app.config import settings
from app.services import llm
from app.services.audit import record_audit
from app.services.events import bus

_SYSTEM = (
    "You are the Intake Agent of an accounts-payable system. "
    "Classify the document type of the provided text and return JSON only."
)


def run(state: dict, db: Session) -> dict:
    invoice_id = state["invoice_id"]
    raw_text = state.get("raw_text", "")

    bus.publish(
        invoice_id,
        {
            "type": "agent_started",
            "agent": "intake",
            "action": "classify_document",
            "status": "running",
            "invoice_status": "extracting",
        },
    )

    snippet = raw_text[:2000]
    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                'Return a JSON object: {"document_type": "invoice|receipt|po|contract|other", '
                '"confidence": 0.0-1.0, "reasoning": "short explanation"}. '
                f"Document text:\n{snippet}"
            ),
        },
    ]

    try:
        result, duration_ms = llm.complete_json(settings.llm_classify_model, messages)
    except llm.LLMError as e:
        # Deterministic degradation for ANY upstream failure (retries already
        # exhausted for transient ones): classify from the text itself, low
        # confidence, explicit llm_unavailable marker in the audit trail.
        # The request still completes — it never 500s on an upstream outage.
        result = llm.fallback_classify(snippet)
        duration_ms = 0
        result["reasoning"] = f"{result['reasoning']} (upstream: {e})"

    doc_type = str(result.get("document_type", "other")).lower()
    confidence = float(result.get("confidence", 0.0))
    reasoning = str(result.get("reasoning", ""))

    record_audit(
        db,
        invoice_id=invoice_id,
        agent_name="intake",
        action="classify_document",
        reasoning=reasoning,
        rule_fired=result.get("rule_fired"),
        confidence=confidence,
        input_data={"raw_text_preview": snippet[:500]},
        output_data={"document_type": doc_type},
        duration_ms=duration_ms,
    )

    bus.publish(
        invoice_id,
        {
            "type": "agent_done",
            "agent": "intake",
            "action": "classify_document",
            "status": "done",
            "reasoning": reasoning,
            "confidence": confidence,
            "document_type": doc_type,
        },
    )

    return {
        "document_type": doc_type,
        "current_step": "intake",
        "confidence_scores": {**state.get("confidence_scores", {}), "intake": confidence},
    }
