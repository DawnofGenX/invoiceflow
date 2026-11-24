"""Audit-trail export: JSON (audit-ready) and PDF (human-readable)."""
import json
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

from app.models import AuditLog, Invoice


def _entry_dict(e: AuditLog) -> dict:
    return {
        "timestamp": e.created_at.isoformat(),
        "agent": e.agent_name,
        "action": e.action,
        "reasoning": e.reasoning,
        "rule_fired": e.rule_fired,
        "confidence": e.confidence,
        "input_data": e.input_data,
        "output_data": e.output_data,
        "duration_ms": e.duration_ms,
    }


def export_json(invoice: Invoice, entries: list[AuditLog]) -> bytes:
    payload = {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "vendor_name": invoice.vendor_name,
        "amount": str(invoice.amount),
        "currency": invoice.currency,
        "status": invoice.status,
        "audit_trail": [_entry_dict(e) for e in entries],
    }
    return json.dumps(payload, indent=2, default=str).encode("utf-8")


def export_pdf(invoice: Invoice, entries: list[AuditLog]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        title="InvoiceFlow Audit Trail",
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("Title", parent=styles["Title"], fontSize=18, spaceAfter=6)
    subtitle = ParagraphStyle(
        "Subtitle", parent=styles["Normal"], fontSize=10, textColor=colors.grey, spaceAfter=12
    )
    cell = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8, leading=10)
    head = ParagraphStyle(
        "Head",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        textColor=colors.white,
        fontName="Helvetica-Bold",
    )

    story: list = [
        Paragraph("InvoiceFlow — Audit Trail", title),
        Paragraph(
            f"Invoice {invoice.invoice_number} — {invoice.vendor_name} — "
            f"{invoice.currency} {invoice.amount} — status: {invoice.status}",
            subtitle,
        ),
    ]

    rows = [
        [
            Paragraph("Time (UTC)", head),
            Paragraph("Agent", head),
            Paragraph("Action", head),
            Paragraph("Rule Fired", head),
            Paragraph("Confidence", head),
            Paragraph("Reasoning", head),
        ]
    ]
    for e in entries:
        rows.append(
            [
                Paragraph(e.created_at.strftime("%H:%M:%S"), cell),
                Paragraph(e.agent_name, cell),
                Paragraph(e.action, cell),
                Paragraph(e.rule_fired or "—", cell),
                Paragraph(f"{e.confidence:.2f}", cell),
                Paragraph(e.reasoning, cell),
            ]
        )

    table = Table(
        rows,
        colWidths=[0.7 * inch, 0.9 * inch, 1.1 * inch, 1.1 * inch, 0.7 * inch, 3.0 * inch],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)

    doc.build(story)
    return buf.getvalue()
