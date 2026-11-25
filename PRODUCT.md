# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: an accounts-payable clerk who works a queue of incoming supplier invoices all day, in an
office, in daylight, on a desktop monitor. Their job: get every invoice through validation and
approval correctly and quickly, and be able to justify each decision afterwards to a controller or
auditor. Chosen explicitly in the design interview (2026-11-25): "AP clerk grinding a queue all day
in an office, daylight, needs density". Secondary: a finance lead spot-checking exceptions; a hackathon
judge who sees the product for under a minute.

## Product Purpose

InvoiceFlow ingests invoices (PDF or image), runs them through a multi-agent pipeline
(intake → extraction → validation → approval), and records why every decision was made. Success =
a clerk can process a stack of invoices knowing which ones were handled automatically, which need a
human, and exactly which rule or risk signal caused each outcome — without re-reading the document.

## Positioning

Per-decision explainability as the product, not a feature: every decision carries the agent's
natural-language reasoning, a confidence score, and the exact `rule_fired` (`po_match`,
`duplicate_detected`, `new_vendor_verification`, `auto_approve`, …). Incumbent AP suites log what
happened; InvoiceFlow shows why, which is what makes an automated control defensible as audit
evidence. Open source (MIT) is part of the position, not decoration.

## Operating Context

Desktop browser at a desk in daylight. Repeated, high-frequency task with a real queue. Users live
in tables and detail views, compare amounts against purchase orders, and need to move through many
invoices without losing their place. Monitoring/audit reading happens after the fact, often printed or
exported (JSON + PDF audit export). Demo mode is a clean seeded database with sample documents.

## Capabilities and Constraints

Shipped: single + batch upload (PDF/image, Tesseract OCR), 5-stage agent pipeline with SSE live
streaming of each agent's reasoning, validation rules in fixed order (po_match → line_item_compare →
duplicate_check → amount_verification → anomaly_check), approval thresholds (<$500 auto, $500–5,000
manager, $5,000–10,000 admin, >$10,000 dual, new vendor always human), approvals queue, transparency
report (rules fired, decisions per agent, confidence), invoice list with search + status filter,
JSON/PDF audit export. Deliberate non-goals: no payment execution (mock status only), no email
forwarding, no multi-tenant auth. Stack: Next.js 16 App Router + Tailwind 4 + FastAPI/SQLite.

## Brand Commitments

Name: InvoiceFlow. Claims must stay true to what ships — no payment execution, no compliance
certifications, no customer logos, no invented benchmarks. Every seeded figure is illustrative demo
data and is labeled as such.

## Evidence on Hand

Live deployment https://hermes-vm.tailfd1655.ts.net with seeded demo invoices (Acme Industrial Supply,
Baker Manufacturing, Cobalt Logistics), five sample PDFs in `backend/demo-data/sample_invoices/`, and a
63-check acceptance suite (`scripts/e2e_smoke.py`) that asserts the explainability contract.
