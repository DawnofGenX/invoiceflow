# InvoiceFlow

**The open-source, explainable multi-agent accounts payable platform.**

InvoiceFlow ingests invoices (PDF or image), routes them through a pipeline of specialized
agents, and — uniquely — shows you **why** every decision was made. Every approval, rejection
or flag ships with a full audit trail: the agent's natural-language reasoning, a calibrated
confidence score, and the exact rule or risk signal that fired.

Existing AP tools log *what* happened (approved / paid / rejected). InvoiceFlow explains *why* —
which is what auditors ask for before an automated control output is accepted as audit evidence
(an unexplained output is not sufficient evidence: the control has to be documented and testable).

---

## Live demo

Running right now on a small VM, deployed from this repo with `docker compose up -d --build`:

- **<https://hermes-vm.tailfd1655.ts.net>** — stable public HTTPS URL, served through a Tailscale
  Funnel (the VM's Azure NSG only exposes SSH, and the tenant blocks device-code auth, so the
  Funnel is the production ingress; it survives reconnects and reboots).

Verified end to end against that public URL: `python3 scripts/e2e_smoke.py --base-url
https://hermes-vm.tailfd1655.ts.net` → **64/64 checks passed** with the harness reset enabled
(`E2E_RESET_TOKEN` set) — 63 product checks plus the reset check itself; **63/63** on an instance
where the reset endpoint is disabled. All requests routed through the public Funnel ingress
(103.84.155.153), not the tailnet.

Start at **Transparency**, upload any file from `backend/demo-data/sample_invoices/`, and watch the
agents stream their decisions live. No signup, no seeding required — the DB ships with demo history.

---

## Why this exists

| | Incumbent AP suites (BILL, Stampli, Ramp, Melio) | InvoiceFlow |
|---|---|---|
| Invoice capture + approval | ✅ | ✅ |
| Payment execution | ✅ (their revenue) | ✗ (mock status — deliberately out of scope) |
| Per-decision natural-language reasoning | ✗ | ✅ |
| Confidence score per decision | ✗ | ✅ |
| `rule_fired` — the exact rule/risk signal | ✗ | ✅ (e.g. `po_match`, `duplicate_detected`, `new_vendor_verification`) |
| Audit export (JSON + PDF) | partial | ✅ |
| Open source | ✗ | ✅ MIT |

---

## Architecture

```
                 ┌──────────────────────────────────────────────────────────┐
  PDF / image ──▶│  FastAPI  POST /api/invoices/upload                      │
                 └───────────────────────────┬──────────────────────────────┘
                                             │ BackgroundTask
                                 ┌───────────▼────────────┐
                                 │ LangGraph StateGraph   │
                                 │  (app/agents/          │
                                 │   orchestrator.py)     │
                                 └───────────┬────────────┘
        ┌────────────────┬───────────────────┼───────────────────┬───────────────────┐
        ▼                ▼                   ▼                   ▼                   ▼
   ┌─────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   ┌──────────────┐
   │ intake  │───▶│  extraction  │───▶│  validation  │───▶│   approval   │──▶│  payment     │
   │ classify│    │ LLM → JSON   │    │ 5 rule       │    │ amount +     │   │ (mock status)│
   │ (LLM)   │    │ + line items │    │ checks       │    │ vendor rules │   │              │
   └────┬────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘   └──────────────┘
        │                │                   │                   │
        └────────────────┴───────────────────┴───────────────────┘
                             every node writes AuditLog
                    (reasoning, confidence, rule_fired, input/output, duration_ms)
                                             │
                             ┌───────────────▼────────────────┐
                             │  EventBus → SSE /stream        │  live agent feed in the UI
                             └────────────────────────────────┘
```

### Agents

| Agent | File | What it decides | Explainability artifact |
|---|---|---|---|
| Intake | `backend/app/agents/intake.py` | Is this even an invoice? | `classify_document` + confidence |
| Extraction | `backend/app/agents/extraction.py` | Vendor, number, amount, dates, PO, line items | `extract_fields` + per-field confidence |
| Validation | `backend/app/agents/validation.py` | PO match, line-item match, duplicate, amount math, anomalies | 5 separate audit entries, each with `rule_fired` |
| Approval | `backend/app/agents/approval.py` | Auto-approve / route by amount / force review for new vendors | `route_approval` + threshold rule name |
| Orchestrator | `backend/app/agents/orchestrator.py` | Graph control flow + final status | `finalize` |

Validation rules, in order: `po_match` → `line_item_compare` → `duplicate_check` →
`amount_verification` → `anomaly_check` (`new_vendor`, `amount_3x_average`).
Any `high`/`block` severity issue routes the invoice to `needs_review` instead of payment.

Approval thresholds (seeded on first run in `ApprovalRule`):
`< $500` auto-approve · `$500–$5,000` manager · `$5,000–$10,000` admin · `> $10,000` dual.
A new vendor always forces manual verification regardless of amount.

---

## Quick start (Docker)

```bash
git clone https://github.com/DawnofGenX/invoiceflow.git
cd invoiceflow
cp .env.example .env          # add your OPENCODE_API_KEY
docker compose up -d --build
curl -X POST http://localhost/api/seed/     # 3 POs + 3 historical invoices
open http://localhost
```

Three containers: `backend` (FastAPI :8000), `frontend` (Next.js :3000), `nginx` (:80,
`/api` → backend, `/` → frontend, SSE-safe: `proxy_buffering off`).

### Local dev (no Docker)

```bash
# backend
cd backend
uv venv --python 3.12 && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env          # add your OPENCODE_API_KEY
.venv/bin/uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
npm install
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
npm run dev                   # http://localhost:3000
```

### Tests and CI

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
```

25 tests, all offline (OCR is real; the LLM is a deterministic stub via `LLM_STUB=1`, which
`tests/conftest.py` sets automatically):

- 4 pipeline tests — happy path auto-approve, new-vendor escalation, duplicate → review, non-invoice → rejected
- 10 API tests — health, upload validation (bad type, empty file), batch partial success,
  list filters, audit-summary explainability assertions, vendor aggregation,
  JSON/PDF audit export, approval decision round-trip
- 5 maintenance tests — reset endpoint gating (disabled → 404, wrong token → 403), harness-only
  deletion, second-run idempotency, genuine duplicates still flagged after a reset

`scripts/e2e_smoke.py` is the end-to-end proof against a *running* instance. It checks the
explainability contract, not just status codes — every audit entry must carry non-empty
reasoning, a confidence in `[0,1]` and the rule that fired:

```bash
python scripts/e2e_smoke.py --base-url http://localhost --verbose   # 63 checks (+1 with the reset enabled)
```

The smoke test re-uploads the same fixtures on every run, so it cleans up after itself
first: fixtures are uploaded under an `e2e-` prefixed name and the harness calls
`POST /api/maintenance/reset-e2e` before its first upload. That endpoint only exists
when `E2E_RESET_TOKEN` is set (it then requires the same token in the `X-E2E-Token`
header); without it the endpoint returns `404` and the reset is skipped. Set
`INVOICEFLOW_E2E_RESET_TOKEN` in your shell to the same value to enable it. It deletes
only harness-owned rows — never seeded demo data, never real uploads. See `DEPLOY.md`.

CI (`.github/workflows/ci.yml`) runs the pytest suite, `npm run build`, and builds both
Docker images on every push.

### Reproduce it yourself

A judge with a clean machine and ~10 minutes, in order:

```bash
git clone https://github.com/DawnofGenX/invoiceflow.git
cd invoiceflow
cp .env.example .env                      # OPENCODE_API_KEY is the only required value
docker compose up -d --build              # backend :8000, frontend :3000, nginx :80
curl -X POST http://localhost/api/seed/   # 3 POs + 3 historical invoices
python3 scripts/e2e_smoke.py --base-url http://localhost --verbose
```

Expect `63/63 checks passed` (64 with `E2E_RESET_TOKEN` set — see the reset note above).
Then open <http://localhost>, upload `backend/demo-data/sample_invoices/sample-clean.pdf`,
and read the confirmation slip on the invoice record. To run the test suite without Docker,
without network and without a key: `cd backend && LLM_STUB=1 ./.venv/bin/python -m pytest tests/ -q`
(25 passed). Commands verified against `docker-compose.yml`, `scripts/e2e_smoke.py`
(`--base-url`, `--samples`, `--verbose`) and `DEPLOY.md`.

---

## Why this wins (rubric alignment)

Every claim below points at something a judge can run or read, not at a metric.

| Rubric criterion | Evidence in this repo |
|---|---|
| Technical Architecture & Engineering Depth (35%) | A LangGraph `StateGraph` with conditional routing (`backend/app/agents/orchestrator.py`), per-node commits so a mid-pipeline failure still leaves an explainable trail, SSE streaming through an in-memory event bus with replay (`backend/app/services/events.py`), per-agent model routing over one OpenAI-compatible gateway, and a deterministic offline stub so the whole pipeline is testable with no key. `docs/ARCHITECTURE.md` is the full reference. |
| Innovation & Originality (25%) | The audit trail is the product: `agent_name`, `action`, `reasoning`, `rule_fired`, `confidence`, `input_data`/`output_data`, `duration_ms` per decision (`backend/app/models/audit.py`) — exportable as JSON/PDF. The incumbents in the comparison table above log outcomes; they do not log reasons. |
| Real-World Utility & Scalability (25%) | The validation rules mirror a real AP control sequence (PO match → line-item compare → duplicate → amount math → anomaly), approval thresholds are data (`ApprovalRule` rows, not code), and new-vendor detection keys off stored invoice history. Payments are deliberately out of scope — the wedge is explainability, not money movement. |
| Execution & Demo Clarity (15%) | A live URL with no signup, pre-seeded history, five fixture PDFs with five distinct predictable outcomes, and `scripts/e2e_smoke.py` — 63 checks asserting the explainability contract, not just status codes. `docs/FRICTION_LOG.md` records what broke and how each fix was proven. |

---

## Try the explainability

Sample invoices are in `backend/demo-data/sample_invoices/` (regenerate with
`python backend/demo-data/generate_samples.py`):

| File | Expected outcome |
|---|---|
| `sample-clean.pdf` | $450 Acme, PO-1042 matches → auto-approve → `payment_scheduled` |
| `sample-new-vendor.pdf` | Nova Robotics, unseen vendor → `awaiting_approval` (manual verification) |
| `sample-duplicate.pdf` | Repeats INV-2024-000 → `needs_review` (`duplicate_detected`) |
| `sample-high-value.pdf` | Cobalt $8,750 → routed to admin approval |
| `sample-contract.pdf` | Not an invoice → `rejected` (`not_an_invoice`) |

Then open the record: the confirmation slip prints each agent's decision line in order —
agent, action, the rule that fired, confidence, duration and the reasoning sentence
verbatim. Export it as JSON or PDF from the same page.

The **Evidence** page (`/audit`) aggregates the same data across the whole ledger:
decisions logged, automation rate, average confidence, which rules fired and how often,
decisions per agent, the newest decisions verbatim, and every vendor stamped
`established` or `new — verify`.

## Design

The interface is built as a confirmation register rather than a KPI dashboard: a pale
print ground under an ink-green rail, 1px rules instead of cards, and disposition shown
as a stamped token (SETTLED / HELD / VOID) instead of a coloured pill. Archivo sets
labels and prose; Sometype Mono sets every reference, amount, timestamp and confidence.
`DESIGN.md` records the tokens and rules (with `.impeccable/design.json` as the
machine-readable sidecar); read it before adding a screen so new surfaces stay in the
same world.

---

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/invoices/upload` | Upload PDF/image → runs the pipeline |
| POST | `/api/invoices/upload-batch` | Multi-file upload (`files[]`) → per-file accepted/failed results |
| GET | `/api/invoices/?status=&q=&limit=&offset=` | List invoices, filtered by status or free-text (vendor / invoice no. / PO) |
| GET | `/api/audit/summary` | Transparency report: decisions, rules fired, automation rate, recent decisions |
| GET | `/api/vendors/` | Vendor aggregation incl. `has_history` (why new vendors get reviewed) |
| GET | `/api/invoices/{id}` | Invoice + line items + audit entries |
| GET | `/api/invoices/{id}/audit` | Audit trail only |
| GET | `/api/invoices/{id}/audit/export?format=json\|pdf` | Audit-ready export |
| GET | `/api/invoices/{id}/stream` | SSE live agent events |
| GET | `/api/approvals/` | Pending approval queue |
| POST | `/api/approvals/{id}/decide` | `{"decision":"approve"\|"reject","comment":"..."}` |
| GET | `/api/dashboard/` | Totals, by-status counts, pending/needs-review |
| POST | `/api/seed/` | Idempotent demo seed |
| GET | `/api/health` | Health probe |

---

## Model routing

All LLM calls go through one OpenAI-compatible endpoint (`opencode-go`), configurable per agent:

| Env | Agent | Default |
|---|---|---|
| `LLM_CLASSIFY_MODEL` | intake classification | `qwen3.8-flash` |
| `LLM_REASONING_MODEL` | extraction | `deepseek-v4-pro` |
| `LLM_VISION_MODEL` | future vision OCR | `deepseek-v4.1-flash` |

The client (`backend/app/services/llm.py`) sends `x-opencode-session` (required by the
gateway) and requests `response_format={"type":"json_object"}` with a `{...}` fallback parse.

---

## Deliberate non-goals

- **No payment execution.** Status goes to `payment_scheduled` against a mock `Payment` row.
  Real money movement is regulated and is where incumbents make their margin.
- **No email-forwarding inbox.** Cut on purpose; upload is the demo path.
- **No multi-tenant auth.** Single-workspace demo deployment for judging.

## License

MIT — see `LICENSE`.
