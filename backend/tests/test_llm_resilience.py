"""Resilience tests for the LLM client: bounded retries, fallback marker.

All offline. The single raw HTTP attempt lives at the `llm._http_post` seam;
the retry/fallback wrapper above it is what these tests exercise. `time.sleep`
is recorded, never slept.
"""
import httpx
import pytest

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import AuditLog, Invoice, InvoiceStatus
from app.services import llm
from sqlalchemy import select


@pytest.fixture
def _fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _stub_off(monkeypatch):
    """These tests exercise the live client path, not the deterministic stub."""
    monkeypatch.setattr(settings, "llm_stub", False)


def _status_error(code: int, body: str = "boom", headers: dict | None = None) -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "http://fake.test/chat/completions")
    resp = httpx.Response(code, request=req, text=body, headers=headers or {})
    return httpx.HTTPStatusError(f"{code}", request=req, response=resp)


_OK = ({"choices": [{"message": {"content": '{"ok": true}'}}]}, 5)


# ---------------------------------------------------------------------------
# (1) bounded retry on transient failures
# ---------------------------------------------------------------------------

def test_retries_429_then_succeeds_within_bound(monkeypatch):
    """429, 429, then 200 => result returned after exactly 3 raw attempts."""
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(settings, "llm_backoff_base_seconds", 0.01)
    calls: list[int] = []

    def flaky(payload, timeout):
        n = len(calls)
        calls.append(n)
        if n < 2:
            raise _status_error(429)
        return _OK

    monkeypatch.setattr(llm, "_http_post", flaky)
    text, ms = llm.complete_json("m", [{"role": "user", "content": "x"}])
    assert text == {"ok": True}
    assert len(calls) == 3, "429 twice then success must take exactly 3 attempts"


def test_no_retry_on_400(monkeypatch):
    """A non-429 4xx is permanent: exactly one attempt, LLMError raised."""
    sleeps: list[float] = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: sleeps.append(s))
    calls: list[int] = []

    def bad_request(payload, timeout):
        calls.append(1)
        raise _status_error(400, "MissingSessionID")

    monkeypatch.setattr(llm, "_http_post", bad_request)
    with pytest.raises(llm.LLMError):
        llm.complete_json("m", [{"role": "user", "content": "x"}])
    assert len(calls) == 1, "400 must not be retried"
    assert sleeps == [], "no backoff sleep for a permanent error"


def test_backoff_is_exponential_and_retry_after_is_honored(monkeypatch):
    """500 -> backoff; 429 with Retry-After -> exact header value; capped sleeps."""
    delays: list[float] = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: delays.append(s))
    monkeypatch.setattr(settings, "llm_backoff_base_seconds", 0.01)
    monkeypatch.setattr(settings, "llm_max_attempts", 4)

    def flaky(payload, timeout):
        n = len(delays)
        if n == 0:
            raise _status_error(500)
        if n == 1:
            raise _status_error(429, headers={"Retry-After": "7"})
        if n == 2:
            raise _status_error(503)
        return _OK

    monkeypatch.setattr(llm, "_http_post", flaky)
    llm.complete_json("m", [{"role": "user", "content": "x"}])
    assert len(delays) == 3, "3 transient failures => 3 backoff sleeps"
    assert delays[1] == pytest.approx(7.0), "Retry-After header overrides backoff exactly"
    assert delays[0] < delays[2], "exponential schedule: later backoff is larger"
    assert all(0 < d <= 30.0 for d in delays), "sleeps are capped"


def test_connection_error_is_retried_then_gives_up_bounded(monkeypatch):
    """Persistent transport failure: exactly llm_max_attempts tries, then raise."""
    calls: list[int] = []
    delays: list[float] = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: delays.append(s))
    monkeypatch.setattr(settings, "llm_max_attempts", 3)
    monkeypatch.setattr(settings, "llm_backoff_base_seconds", 0.01)

    def down(payload, timeout):
        calls.append(1)
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(llm, "_http_post", down)
    with pytest.raises(llm.LLMError):
        llm.complete_json("m", [{"role": "user", "content": "x"}])
    assert len(calls) == 3, "bounded: exactly max_attempts raw calls"
    assert len(delays) == 2, "sleep only between attempts"


# ---------------------------------------------------------------------------
# (2) deterministic fallback with llm_unavailable marker in the audit trail
# ---------------------------------------------------------------------------

_INVOICE_TEXT = """INVOICE
Acme Industrial Supply
Invoice Number: INV-2024-900
Invoice Date: 2024-11-15
Due Date: 2024-12-15

Item             Qty   Unit Price   Total
Steel Bracket    10    15.00        150.00
Hex Bolts M8     200   1.50         300.00

Total: $450.00
"""


def test_fallback_completes_invoice_with_llm_unavailable_marker(monkeypatch, _fresh_db):
    """Upstream dead => pipeline COMPLETES (no raise) and audit shows llm_unavailable."""
    from app.agents.orchestrator import process_invoice

    sleeps: list[float] = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(settings, "llm_stub", False)
    monkeypatch.setattr(settings, "llm_max_attempts", 2)
    monkeypatch.setattr(settings, "llm_backoff_base_seconds", 0.01)

    def dead(payload, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(llm, "_http_post", dead)

    db = SessionLocal()
    inv = Invoice(invoice_number="TMP-DEAD", vendor_name="", amount=0, status=InvoiceStatus.PENDING.value)
    db.add(inv)
    db.commit()
    process_invoice(db, inv.id, "x.pdf", _INVOICE_TEXT)  # must NOT raise

    row = db.get(Invoice, inv.id)
    assert row.status not in (InvoiceStatus.PENDING.value, InvoiceStatus.ERROR.value, None)
    assert float(row.amount) == 450.0, "deterministic fallback still reads the stated total"

    entries = list(db.execute(select(AuditLog).where(AuditLog.invoice_id == inv.id)).scalars())
    markers = [e for e in entries if e.rule_fired == "llm_unavailable"]
    assert markers, "audit trail must carry an explicit llm_unavailable marker"
    assert all(e.confidence < 0.5 for e in markers), "fallback decisions carry low confidence"
    db.close()


# ---------------------------------------------------------------------------
# (4) settings knobs
# ---------------------------------------------------------------------------

def test_timeout_knob_drives_http_timeout(monkeypatch):
    """llm_timeout_seconds drives the httpx timeout (sane default, env-overridable)."""
    assert 0 < settings.llm_timeout_seconds <= 120
    assert settings.llm_max_attempts >= 1
    seen: dict = {}

    def spy(payload, timeout):
        seen["timeout"] = timeout
        return _OK

    monkeypatch.setattr(settings, "llm_stub", False)
    monkeypatch.setattr(llm, "_http_post", spy)
    llm.complete_json("m", [{"role": "user", "content": "x"}])
    assert seen["timeout"] == settings.llm_timeout_seconds
