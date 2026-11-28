# FRICTION LOG — InvoiceFlow sprint

Every obstacle hit building InvoiceFlow, in the order it bit, with the fix that
actually shipped. Each entry points at a commit, a file, or a live behaviour you can
re-check. Nothing here is retrospective polish; this is the wound log.

## 1. The smoke test wasn't idempotent — the live demo read 59/63, not 63/63

`scripts/e2e_smoke.py` uploads the same five fixture PDFs on every run. Those rows
persisted, so run two's fixtures collided with run one's copies on
`invoice_number + vendor_name + amount`, the duplicate detector fired on the fixture
itself, and validation blocked invoices into `needs_review` instead of
`payment_scheduled` / `awaiting_approval`. The product was correct; the harness was
littering. The live instance reported 59/63 while the README claimed 63/63.

**Fix (commit `2e9d6cb`):** harness-owned cleanup, not product changes.
Fixtures upload under an `e2e-`-prefixed filename, and
`POST /api/maintenance/reset-e2e` (`backend/app/api/maintenance.py`) deletes only rows
whose `file_path` starts with `e2e-` (plus five exact legacy `sample-*.pdf` names) and
their audit/payment/approval children. The endpoint is disabled — returns 404 — unless
`E2E_RESET_TOKEN` is configured, and requires a constant-time
(`secrets.compare_digest`) `X-E2E-Token` match. Proof:
`backend/tests/test_maintenance.py` (5 tests: gating, wrong token, harness-only
deletion, second-run idempotency, genuine duplicates still flagged).

**Known open item:** ownership keys off the `file_path` prefix, so a real upload named
`e2e-something.pdf` would be swept. The durable fix is a dedicated origin column on
`Invoice`. The token must also be rotated before the hackathon window opens.

## 2. SQLAlchemy AND-ed a clause list that had to OR

The first cut of `_owned_invoice_ids` was `select(Invoice.id).where(*clauses)` mixing
`file_path.like("e2e-%")` with `file_path == "sample-clean.pdf"`. `where()` ANDs its
arguments, and no row can simultaneously carry a prefix match and a different exact
name — the delete matched nothing and the "fixed" reset silently reset zero rows.
Fixed with `or_(*clauses)`; the comment at `backend/app/api/maintenance.py:51` keeps
the trap documented in place.

## 3. Azure NSG exposes SSH only; `az` can't edit it from the guest

DEPLOY.md Path-B step 4 assumed opening TCP 80 in the NSG was routine. On this VM the
NSG exposes only TCP 22, and the tenant enforces security defaults (`AADSTS530035`),
so `az login --use-device-code` from inside the guest is dead — no inbound rule, no
device-code escape. Both standard paths were closed.

**Fix (commit `3491767`):** Tailscale Funnel as the production ingress —
`sudo tailscale funnel --bg 80` → stable public HTTPS with zero inbound ports and zero
cloud credentials, persisting across reconnects and reboots. Live URL:
`https://hermes-vm.tailfd1655.ts.net`. Documented in `DEPLOY.md` §7, with
Cloudflare quick tunnel noted as the no-account fallback (random hostname, dies with
the process — wrong for a submission URL).

## 4. Public-ingress tests silently rode the tailnet

From this VM, the system resolver returns the tailnet IP for
`hermes-vm.tailfd1655.ts.net`, so a "public" e2e run could quietly loop back through
the tailnet and prove nothing about the Funnel. `DEPLOY.md` §7 records the discipline:
resolve via `dig +short @1.1.1.1` to get the Funnel ingress IPs (e.g. 103.84.155.153)
and `curl --resolve` them explicitly; the README's verification claim states the same —
all checks routed through the Funnel ingress, not the tailnet.

## 5. Docker was believed missing on the VM. It was installed.

Initial setup notes assumed a bare VM, and the first install path spent time aiming
`apt-get` at a tool that was already there. `scripts/vm_setup.sh` now probes before it
installs (`command -v docker` + `docker compose version`, reporting
"already installed" with versions on `--check`), so the same wrong assumption can't
cost time twice.

## 6. nginx 502'd after every container recreation

`docker compose up -d --build` assigns the recreated backend a new container IP, but
nginx had baked the old upstream IP in at startup → 502 until nginx restarted, on the
URL judges were about to click. **Fix (commit `9eb170f`):** upstreams as variables
through Docker's embedded DNS with `resolver 127.0.0.11 valid=10s` (`nginx.conf`), so
every request re-resolves. Recorded in DEPLOY.md's troubleshooting table with
`docker compose restart nginx` as the manual escape hatch.

## 7. A status field is not an answer — the timeline became a confirmation slip

The first queue was a dark zinc KPI dashboard with an audit *timeline*. It looked
like every other AP tool and answered nothing: `approved` is a status, not a reason.
**Fix (commit `fec399a`):** rebuilt as a confirmation register — pale print ground,
ink-green rail, 1px rules instead of cards, disposition as stamped tokens
(SETTLED/HELD/VOID) instead of pills, and the record page printing numbered decision
lines with the reasoning sentence verbatim. The hold screen prints each hold's reason
sentence with Void/Approve stamps. The design system moved to `DESIGN.md` +
`.impeccable/design.json` so later screens can't drift.

## 8. Smaller cuts, kept honest

- The payment agent became a mock: `payment_scheduled` writes a `Payment` row and
  stops. Real money movement is regulated and is incumbents' margin — cutting it was
  strategy, not scope failure.
- Email forwarding was cut before it was written; upload is the demo path.
- `pytest-asyncio` warns about default fixture loop scope on every suite run
  (`_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET`). Cosmetic; 19/19 pass around it; not worth a
  dependency bump mid-sprint.
- The offline LLM stub (`LLM_STUB=1`, `backend/app/services/llm.py`) is not a model —
  it parses the prompt deterministically. It exists so CI, `pytest`, and a judge
  without an API key all run the same pipeline. Documented as a stub, never sold as AI.
