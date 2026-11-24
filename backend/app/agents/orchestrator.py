"""Orchestrator — LangGraph state machine wiring the agent pipeline.

Each agent is a LangGraph node that reads its DB session from
config["configurable"]["db"]. The pipeline commits after every node so the audit
trail is persisted incrementally (a mid-pipeline failure still leaves completed
steps visible and explainable).
"""
from typing import Any

from langgraph.graph import END, StateGraph
from langchain_core.runnables import RunnableConfig

from app.agents import approval, extraction, intake, validation
from app.agents.state import InvoiceState
from app.models import Invoice, InvoiceStatus
from app.services.audit import record_audit
from app.services.events import bus
from app.services.payment import schedule_mock_payment


def _db(config: RunnableConfig) -> Any:
    return config["configurable"]["db"]


def _intake_node(state: InvoiceState, config: RunnableConfig) -> dict:
    return intake.run(state, _db(config))


def _extraction_node(state: InvoiceState, config: RunnableConfig) -> dict:
    return extraction.run(state, _db(config))


def _validation_node(state: InvoiceState, config: RunnableConfig) -> dict:
    return validation.run(state, _db(config))


def _approval_node(state: InvoiceState, config: RunnableConfig) -> dict:
    return approval.run(state, _db(config))


def _route_after_intake(state: InvoiceState) -> str:
    return "extraction" if state.get("document_type") == "invoice" else "end"


def _route_after_validation(state: InvoiceState) -> str:
    vr = state.get("validation_result") or {}
    return "approval" if vr.get("valid") else "end"


def build_graph():
    g = StateGraph(InvoiceState)
    g.add_node("intake", _intake_node)
    g.add_node("extraction", _extraction_node)
    g.add_node("validation", _validation_node)
    g.add_node("approval", _approval_node)
    g.set_entry_point("intake")
    g.add_conditional_edges("intake", _route_after_intake, {"extraction": "extraction", "end": END})
    g.add_edge("extraction", "validation")
    g.add_conditional_edges("validation", _route_after_validation, {"approval": "approval", "end": END})
    g.add_edge("approval", END)
    return g.compile()


_graph = build_graph()


def process_invoice(db: Any, invoice_id: str, file_path: str, raw_text: str) -> dict:
    """Run the full pipeline synchronously. Returns the final InvoiceState."""
    initial: InvoiceState = {
        "invoice_id": invoice_id,
        "file_path": file_path,
        "raw_text": raw_text,
        "errors": [],
        "confidence_scores": {},
    }
    config = {"configurable": {"db": db}}

    final_state: dict = dict(initial)
    for full_state in _graph.stream(initial, config, stream_mode="values"):
        db.commit()
        final_state = full_state

    _finalize(db, invoice_id, final_state)
    return final_state


def _finalize(db: Any, invoice_id: str, state: dict) -> None:
    invoice = db.get(Invoice, invoice_id)
    doc_type = state.get("document_type")
    validation = state.get("validation_result") or {}
    decision = state.get("approval_decision") or {}

    if doc_type != "invoice":
        invoice.status = InvoiceStatus.REJECTED.value
        record_audit(
            db,
            invoice_id=invoice_id,
            agent_name="orchestrator",
            action="finalize",
            reasoning=f"Document classified as '{doc_type}', not an invoice — rejected",
            rule_fired="not_an_invoice",
            confidence=1.0,
        )
    elif not validation.get("valid"):
        invoice.status = InvoiceStatus.NEEDS_REVIEW.value
        record_audit(
            db,
            invoice_id=invoice_id,
            agent_name="orchestrator",
            action="finalize",
            reasoning=(
                f"{len(validation.get('issues', []))} validation issue(s) — flagged for review"
            ),
            rule_fired="validation_failed",
            confidence=1.0,
            output_data={"issues": validation.get("issues")},
        )
    elif decision.get("decision") == "auto_approve":
        invoice.status = InvoiceStatus.APPROVED.value
        record_audit(
            db,
            invoice_id=invoice_id,
            agent_name="orchestrator",
            action="finalize",
            reasoning="Auto-approved within threshold",
            rule_fired="auto_approve",
            confidence=1.0,
        )
        schedule_mock_payment(db, invoice)
    elif decision.get("decision") == "routed":
        invoice.status = InvoiceStatus.AWAITING_APPROVAL.value
        record_audit(
            db,
            invoice_id=invoice_id,
            agent_name="orchestrator",
            action="finalize",
            reasoning=f"Routed to {decision.get('approver_role')} for approval",
            rule_fired=decision.get("rule"),
            confidence=1.0,
        )
    else:
        invoice.status = InvoiceStatus.ERROR.value
        record_audit(
            db,
            invoice_id=invoice_id,
            agent_name="orchestrator",
            action="finalize",
            reasoning="Pipeline finished without a decision — marked error",
            confidence=0.0,
        )

    scores = state.get("confidence_scores") or {}
    invoice.confidence_score = min(scores.values()) if scores else None
    db.commit()

    bus.publish(
        invoice_id,
        {"type": "invoice_completed", "status": "done", "invoice_status": invoice.status},
    )
