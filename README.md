# InvoiceFlow

Open-source, explainable multi-agent accounts payable platform.

InvoiceFlow ingests invoices (PDF / image / email), routes them through a pipeline of specialized agents, and — uniquely — shows you **why** every decision was made. Every approval, rejection, or flag ships with a full audit trail: the natural-language reasoning, a confidence score, and the exact rule or risk signal that fired.

## What it is

- **Explainable by design** — the audit trail is the product, not an afterthought. Each agent decision is traceable and exportable (JSON + PDF) for audit-readiness.
- **Multi-agent architecture** — intake, extraction, validation, approval, and orchestration agents coordinate over a shared workflow.
- **Open-source** — MIT licensed. An open-source alternative to Stampli / BILL.

## Status

Built for the Zyrelyx Global AI Hackathon (Dec 1–7, 2026). All application code is written during the hackathon window.

## Stack (planned)

FastAPI + Next.js + PostgreSQL · LangGraph orchestration · Tesseract OCR · Docker Compose
