# InvoiceFlow — Architecture Reference

Every route, table, field, and env var below was grepped from the source at
`backend/app/` and `frontend/app/` on 2026-11-28. Where this page and the code
disagree, the code is right; fix this page.

- Backend: FastAPI (`backend/app/main.py`, title `InvoiceFlow`, version `0.1.0`),
  SQLAlchemy 2.x mapped columns over SQLite, LangGraph `StateGraph`, Tesseract OCR,
  `sse-starlette`, `reportlab`.
- Frontend: Next.js 16.4.6 / React 19.3.0 / Tailwind 4.3.3.
- Deploy: docker-compose — `backend` (:8000), `frontend` (:3000), `nginx` (:80) —
  behind a Tailscale Funnel in production (`DEPLOY.md`).

## The five agents and what each decides

| Agent | Source | Decision | Audit `action` |
|---|---|---|---|
| intake | `agents/intake.py` | Is the uploaded document an invoice? LLM classification over OCR text. | `classify_document` + confidence |
| extraction | `agents/extraction.py` | Vendor, invoice number, amount, currency, dates, PO number, line items — from the first 6000 chars of OCR text via LLM JSON mode. | `extract_fields` + confidence |
| validation | `agents/validation.py` | Five sequential checks (below); collects `issues` with `severity` (`info`/`high`/`block`). | one entry per check |
| approval | `agents/approval.py` | Auto-approve / route to a role / force review for a new vendor, from `ApprovalRule` rows. | `route_approval` + `rule_fired = matched.name` |
| orchestrator | `agents/orchestrator.py` | Graph control flow + final `Invoice.status`. | `finalize` |

Validation checks, in execution order, with the `rule_fired` values actually emitted
(`agents/validation.py`, `services/fraud_detector.py`):

| Check | `rule_fired` on pass | on fail | severity on fail |
|---|---|---|---|
| `po_match` | `po_match` | `po_mismatch` (only when a PO number was present) | `high` |
| `line_item_compare` | `line_items_match` | `line_item_mismatch` | `high` |
| `duplicate_check` | — (null when clean) | `duplicate_detected` | `block` |
| `amount_verification` | — (null when math ok) | `line_sum_mismatch` | — |
| `anomaly_check` | `new_vendor` (`info`), `amount_3x_average` (`high`) | — | per flag |

Anomaly flags are deliberately rule-based, not LLM (`services/fraud_detector.py`):
`new_vendor` = no prior invoice for the vendor name; `amount_3x_average` = amount > 3×
the vendor's stored average. New-vendor status comes from `validation.py::_vendor_history`
(prior stored invoices).

Approval thresholds live in `ApprovalRule` rows (seeded on first run in
`agents/approval.py`): `auto` <$500 · `manager` $500–4,999.99 · `admin` $5,000–9,999.99 ·
`dual` ≥$10,000. A new vendor always forces manual review regardless of amount.

## LangGraph graph shape

`orchestrator.py::build_graph()` — `StateGraph(InvoiceState)`:

```
entry: intake
intake      → (conditional) document_type == "invoice" ? extraction : END
extraction  → validation
validation  → (conditional) validation_result.valid ? approval : END
approval    → END
```

`process_invoice()` streams `values` mode and calls `db.commit()` after every node, so
a mid-pipeline failure still leaves completed steps persisted and explainable.
`_finalize()` then maps state → status: non-invoice → `rejected` (`not_an_invoice`);
invalid → `needs_review` (`validation_failed`); valid + `auto_approve` → `approved`
then `schedule_mock_payment` → `payment_scheduled`; anything else keeps the approval
agent's routed status. Errors finalize as `error`.

`InvoiceStatus` values (`models/invoice.py`): `pending`, `extracting`, `validating`,
`needs_review`, `awaiting_approval`, `approved`, `payment_scheduled`, `paid`,
`rejected`, `error`.

## Audit trail — the explainability core

`AuditLog` → table `audit_logs` (`models/audit.py`). One row per decision:

| Column | Type | Notes |
|---|---|---|
| `id` | String(36) PK | uuid |
| `invoice_id` | FK → `invoices.id`, indexed | |
| `agent_name` | String(64) | `intake`/`extraction`/`validation`/`approval`/`orchestrator` |
| `action` | String(128) | e.g. `classify_document`, `po_match`, `route_approval`, `finalize` |
| `reasoning` | Text | natural language, verbatim in the UI confirmation slip |
| `rule_fired` | String(255), nullable | null when no rule decided |
| `confidence` | Float, default 0.0 | contract: within `[0,1]`; e2e asserts it |
| `input_data` / `output_data` | JSON, nullable | what the agent saw / produced |
| `duration_ms` | Integer | |
| `created_at` | DateTime | |

Exports: `services/audit_export.py` — `export_json` (payload bytes) and `export_pdf`
(reportlab). Route below.

## SSE event flow

`services/events.py` — in-memory `EventBus`, singleton `bus`. Events keyed by
`invoice_id`, bounded replay history (`_MAX_HISTORY = 200` deque) so a late SSE
subscriber still gets the full run. Agents `bus.publish()` progress and error lines
during the run; `GET /api/invoices/{id}/stream` subscribes and yields each as SSE
event `agent_event`, terminating on `type` `invoice_completed` or `error`, with a
`timeout` event after 300s idle (`api/invoices.py::stream_invoice`). nginx keeps it
alive with `proxy_buffering off` and `proxy_read_timeout 3600s`.

## Data model (tables)

| Table | Model · file | Role |
|---|---|---|
| `invoices` | `Invoice` · `models/invoice.py` | `invoice_number`, `vendor_name`, `amount` Numeric(12,2), `currency`, `po_number`, `status`, `confidence_score`, `raw_text`, `extracted_data` JSON, `file_path`, timestamps |
| `line_items` | `LineItem` · `models/invoice.py` | invoice-side extracted items |
| `purchase_orders` | `PurchaseOrder` · `models/purchase_order.py` | seeded POs for matching |
| `po_line_items` | `POLineItem` · same file | PO-side items for `line_item_compare` |
| `audit_logs` | `AuditLog` · `models/audit.py` | above |
| `approval_requests` | `ApprovalRequest` · `models/approval.py` | human queue for routed invoices |
| `approval_rules` | `ApprovalRule` · same file | `name`, min/max amount, `approver_role` |
| `payments` | `Payment` · `models/payment.py` | mock `payment_scheduled` rows only |
| `users` | `User` · `models/user.py` | single-workspace demo, no auth flow |

Schema is created at app startup (`Base.metadata.create_all`, `main.py` lifespan);
SQLite file at `database_url` (compose volume `invoiceflow-data` →
`/app/data/invoiceflow.db`).

## API surface

Exactly the routes mounted in `main.py` + the api modules (prefixes from
`include_router`):

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/invoices/upload` | single PDF/image → 201, pipeline runs, returns invoice |
| POST | `/api/invoices/upload-batch` | `files[]` multi-upload → per-file accepted/failed |
| GET | `/api/invoices/` | list; `status`, `q` (vendor/number/PO), `limit`, `offset` |
| GET | `/api/invoices/{invoice_id}` | invoice + line items + audit entries |
| GET | `/api/invoices/{invoice_id}/audit` | audit entries only |
| GET | `/api/invoices/{invoice_id}/audit/export` | `?format=json\|pdf` |
| GET | `/api/invoices/{invoice_id}/stream` | SSE `agent_event` feed |
| GET | `/api/approvals/` | pending approval queue |
| POST | `/api/approvals/{request_id}/decide` | `{"decision":"approve"\|"reject","comment":…}` |
| GET | `/api/dashboard/` | totals, by-status counts, pending/needs-review |
| GET | `/api/audit/summary` | transparency report: decisions, rules fired, automation rate |
| GET | `/api/vendors/` | vendor aggregation incl. `has_history` |
| POST | `/api/seed/` | idempotent demo seed (3 POs + 3 invoices) |
| POST | `/api/maintenance/reset-e2e` | harness cleanup; 404 unless `E2E_RESET_TOKEN` set, 403 on bad `X-E2E-Token` |
| GET | `/api/health` | `{"status":"ok","service":"invoiceflow"}` |

## LLM routing

One OpenAI-compatible gateway (`services/llm.py`, chat/completions dialect). Every
request carries `x-opencode-session` (gateway returns 400 `MissingSessionID` without
it) and requests `response_format={"type":"json_object"}` with a brace-extraction
fallback parse.

| Env var | Setting | Used by | Default |
|---|---|---|---|
| `OPENCODE_BASE_URL` | gateway root | all calls | `https://opencode.ai/zen/go/v1` |
| `OPENCODE_API_KEY` | bearer token | all calls | — (required to boot under compose) |
| `OPENCODE_SESSION` | `x-opencode-session` | all calls | `invoiceflow-dev` |
| `LLM_CLASSIFY_MODEL` | `llm_classify_model` | intake | `qwen3.8-flash` |
| `LLM_REASONING_MODEL` | `llm_reasoning_model` | extraction | `deepseek-v4-pro` |
| `LLM_VISION_MODEL` | `llm_vision_model` | reserved (vision OCR) | `deepseek-v4.1-flash` |
| `LLM_STUB` | `llm_stub` | offline deterministic stub, tests/CI | `false` |

Other settings (`config.py`): `DATABASE_URL` (`sqlite:///./invoiceflow.db`),
`TESSERACT_PATH` (`/usr/bin/tesseract`), `CORS_ORIGINS`, `SECRET_KEY`,
`LOW_CONFIDENCE_THRESHOLD` (0.7), `E2E_RESET_TOKEN` (empty → maintenance disabled),
`LLM_MAX_ATTEMPTS` (3), `LLM_BACKOFF_BASE_SECONDS` (0.5), `LLM_TIMEOUT_SECONDS` (60).
`.env.example` mirrors these for deployment.

## Failure and degradation

- LLM transient failure (429 / 5xx / timeout / connection error): the client retries
  with bounded exponential backoff + jitter (`LLM_MAX_ATTEMPTS`, default 3), honoring
  `Retry-After` exactly when the gateway sends it. A permanent 4xx (bad key, missing
  `x-opencode-session`) fails fast without a retry.
- LLM still unavailable after the retry budget: the agents **degrade instead of
  failing**. Intake and extraction fall back to the same deterministic parsing the
  offline stub uses, tagged `rule_fired="llm_unavailable"` with `confidence=0.2` and a
  reasoning line that says so. The request still returns 201, the pipeline still
  reaches a terminal status, and the audit trail carries the degradation — the
  low-confidence invoice is routed to review, never auto-approved.
- LLM error the fallback cannot cover (e.g. unusable payload): `LLMError` is caught
  per agent — an audit row is written with `confidence=0.0` and the error as
  reasoning, an `error` event is published, the reason is appended to
  `state["errors"]`, and the orchestrator finalizes `error`. The trail explains the
  failure itself; nothing fails silently.
- OCR with no text layer: pipeline surfaces it via extraction (empty text → low
  confidence / error path), not a crash.
- Mid-pipeline crash: committed audit rows survive (per-node commits).
- No network at all: `LLM_STUB=1` runs intake+extraction deterministically offline —
  the path CI and `pytest` use (`tests/conftest.py` sets it).

## Frontend

Five routes (`frontend/app/`): `/` Register · `/upload` Intake · `/approvals` Held ·
`/audit` Evidence · `/invoices/[id]` Record. Components
(`frontend/components/`): `Navbar`, `AgentStream`, `ConfirmationSlip`, `InvoiceDetail`,
`PipelineRoute`, `RegisterTable`, `StatusToken`. Visual system in `DESIGN.md`
(machine sidecar `.impeccable/design.json`).

## Run it locally

```bash
# Docker (needs OPENCODE_API_KEY in .env)
cp .env.example .env && docker compose up -d --build
curl -X POST http://localhost/api/seed/
python3 scripts/e2e_smoke.py --base-url http://localhost --verbose   # 63/64 checks

# No Docker, no network, no key
cd backend && uv venv --python 3.12 && uv pip install --python .venv/bin/python -r requirements.txt
LLM_STUB=1 ./.venv/bin/python -m pytest tests/ -q                    # 31 passed
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

`e2e_smoke.py` flags: `--base-url`, `--samples`, `--verbose`. The 64th check (the
`reset-e2e` call) fires only when the instance has `E2E_RESET_TOKEN` and the shell has
`INVOICEFLOW_E2E_RESET_TOKEN` — see `DEPLOY.md` §5.
