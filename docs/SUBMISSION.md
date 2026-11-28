# InvoiceFlow — Zyrelyx Global AI Hackathon 2026 submission

InvoiceFlow is an open-source (MIT), explainable multi-agent accounts-payable platform.
It ingests an invoice (PDF or image), runs it through a pipeline of specialized agents,
and prints the reason behind every decision: the agent's natural-language reasoning, a
confidence score, and the exact rule that fired — exportable as JSON and PDF.

Live instance (running while you read this, no signup): **<https://hermes-vm.tailfd1655.ts.net>**
Source: **<https://github.com/DawnofGenX/invoiceflow>**

## What it does

Upload an invoice PDF. Within seconds the pipeline classifies the document, extracts
vendor/number/amount/dates/PO/line items, runs five validation checks (PO match,
line-item compare, duplicate detection, amount math, anomaly scan), applies approval
thresholds, and schedules a mock payment — or halts the invoice for review. Each step
writes an audit row: `agent_name`, `action`, `reasoning`, `rule_fired`, `confidence`,
`input_data`/`output_data`, `duration_ms`. The UI streams those decisions live over SSE
and renders them on the invoice's confirmation slip, verbatim.

## Why it's different

AP incumbents (BILL, Stampli, Ramp, Melio, Rossum) log *what* happened — approved,
held, paid. An auditor reviewing an automated control needs *why*: the control has to
be documented and testable, and an unexplained output is not sufficient evidence.
InvoiceFlow makes the reason a first-class, stored, exportable artifact on every single
decision. That is the wedge: not more automation, auditable automation. Payments are
deliberately out of scope — money movement is regulated and is where incumbents make
their margin; explainability is where the gap is.

## How it's built

Backend: FastAPI + LangGraph `StateGraph` (`backend/app/agents/orchestrator.py`) with
four pipeline agents and an orchestrator that finalizes status. SQLAlchemy 2.x over
SQLite; Tesseract for OCR; sse-starlette for the live feed; reportlab for PDF export.
LLM calls route through one OpenAI-compatible gateway with per-agent model overrides
(`LLM_CLASSIFY_MODEL` → intake, `LLM_REASONING_MODEL` → extraction, `LLM_VISION_MODEL`),
and a deterministic offline stub (`LLM_STUB=1`) runs the whole pipeline with no network
and no key — which is why the test suite and CI are reproducible by anyone.
Frontend: Next.js 16 + React 19 + Tailwind 4, five screens (Register, Intake, Held,
Evidence, Record). Deployment: docker-compose (backend + frontend + nginx) on one VM,
public ingress through a Tailscale Funnel because the Azure NSG exposes only SSH.

| Agent | Decides | Audit artifact |
|---|---|---|
| intake | is this an invoice? | `classify_document` + confidence |
| extraction | vendor, number, amount, dates, PO, line items | `extract_fields` + per-field confidence |
| validation | `po_match` → `line_item_compare` → `duplicate_check` → `amount_verification` → `anomaly_check` | one entry per check, each with `rule_fired` |
| approval | auto-approve / route by threshold / force new-vendor review | `route_approval` + rule name |
| orchestrator | final status | `finalize` (`not_an_invoice`, `validation_failed`, `auto_approve`, …) |

## Try it live (2 minutes)

1. Open <https://hermes-vm.tailfd1655.ts.net> — no signup; the ledger ships with
   history (3 POs, 3 invoices).
2. Go to **Intake** (`/upload`) and upload `backend/demo-data/sample_invoices/sample-clean.pdf`
   from the repo — watch the agents stream, then read the confirmation slip on the
   record page: reasoning, rule, confidence, duration, in order.
3. Upload `sample-duplicate.pdf` → held with `duplicate_detected`;
   `sample-new-vendor.pdf` → forced manual review; `sample-contract.pdf` → rejected
   `not_an_invoice`. Five fixtures, five predictable outcomes.
4. Hit **Evidence** (`/audit`) for the same data aggregated across the ledger —
   decisions logged, automation rate, rules fired — and export any record as JSON
   or PDF.

Prove it yourself instead: `docker compose up -d --build`, then
`python3 scripts/e2e_smoke.py --base-url <url> --verbose` → 63 checks (64 with the
harness reset enabled) asserting the explainability contract end to end. Backend suite:
31 tests, offline, `31 passed`.

## Built during the sprint

Repo history starts 2026-11-24 (skeleton) through the final e2e-idempotency fix on
2026-11-28; the full obstacle log — what broke in production and how each fix was
proven — is `docs/FRICTION_LOG.md`. The full architecture reference is
`docs/ARCHITECTURE.md`.

## Deliberately out of scope

- **Payment execution** — status stops at `payment_scheduled` against a mock row.
- **Email-forwarding inbox** — cut; upload is the demo path.
- **Multi-tenant auth** — single-workspace demo deployment for judging.
- **Compliance certification** — InvoiceFlow provides documented, testable controls;
  it does not claim any certification.
