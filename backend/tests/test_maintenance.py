"""Tests for the maintenance reset endpoint.

The smoke test uploads the same fixtures on every run. Without a reset, the
next run's fixtures collide with the previous run's copies and the
duplicate-detection rule fires on the fixture itself — the product behaves
correctly but the test fails. These tests pin that behaviour down.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import AuditLog, Invoice

SAMPLES = Path(__file__).resolve().parent.parent / "demo-data" / "sample_invoices"


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        c.post("/api/seed/")
        yield c
    Base.metadata.drop_all(engine)


def _upload(client: TestClient, name: str, as_name: str | None = None) -> str:
    data = (SAMPLES / name).read_bytes()
    res = client.post(
        "/api/invoices/upload",
        files={"file": (as_name or name, data, "application/pdf")},
    )
    assert res.status_code == 201, res.text
    return res.json()["invoice_id"]


def test_reset_endpoint_disabled_without_token(client):
    """No configured token -> the endpoint must not exist."""
    assert settings.e2e_reset_token == ""
    res = client.post("/api/maintenance/reset-e2e")
    assert res.status_code == 404


def test_reset_requires_matching_token(client, monkeypatch):
    monkeypatch.setattr(settings, "e2e_reset_token", "s3cret")
    assert client.post("/api/maintenance/reset-e2e").status_code == 403
    assert (
        client.post(
            "/api/maintenance/reset-e2e", headers={"X-E2E-Token": "wrong"}
        ).status_code
        == 403
    )


def test_reset_removes_only_harness_artifacts(client, monkeypatch):
    monkeypatch.setattr(settings, "e2e_reset_token", "s3cret")

    seeded = client.get("/api/invoices/?limit=200").json()
    seeded_ids = {i["id"] for i in seeded}
    assert seeded_ids, "seed should provide invoices to protect"

    harness_id = _upload(client, "sample-clean.pdf", as_name="e2e-sample-clean.pdf")
    legacy_id = _upload(client, "sample-new-vendor.pdf", as_name="sample-new-vendor.pdf")
    # A real user upload that merely starts with "sample-" must survive.
    keep_id = _upload(client, "sample-high-value.pdf", as_name="sample-custom.pdf")

    res = client.post(
        "/api/maintenance/reset-e2e", headers={"X-E2E-Token": "s3cret"}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reset"] is True
    assert body["removed"]["invoices"] == 2

    remaining = {i["id"] for i in client.get("/api/invoices/?limit=200").json()}
    assert harness_id not in remaining
    assert legacy_id not in remaining
    assert keep_id in remaining
    assert seeded_ids <= remaining, "seeded demo data must never be deleted"

    # Audit rows for deleted invoices are gone too (no orphaned explainability rows).
    with SessionLocal() as db:
        orphan = db.execute(
            select(AuditLog.id).where(AuditLog.invoice_id == harness_id)
        ).all()
    assert not orphan


def test_second_run_after_reset_does_not_collide(client, monkeypatch):
    """The core regression.

    A fixture uploaded twice *without* a reset is a genuine duplicate and the
    detector is right to flag it. But the smoke test re-uploads the same
    fixtures on every run, so the second *run* must not look like a duplicate
    of the first run's leftovers — the reset in between is what guarantees it.
    """
    monkeypatch.setattr(settings, "e2e_reset_token", "s3cret")

    first = _upload(client, "sample-clean.pdf", as_name="e2e-sample-clean.pdf")
    first_detail = client.get(f"/api/invoices/{first}").json()
    first_rules = [e["rule_fired"] for e in first_detail["audit_entries"] if e["rule_fired"]]

    # Reset between runs — this is what the harness does at startup.
    res = client.post("/api/maintenance/reset-e2e", headers={"X-E2E-Token": "s3cret"})
    assert res.status_code == 200, res.text
    assert res.json()["removed"]["invoices"] == 1

    second = _upload(client, "sample-clean.pdf", as_name="e2e-sample-clean.pdf")
    second_detail = client.get(f"/api/invoices/{second}").json()
    second_rules = [e["rule_fired"] for e in second_detail["audit_entries"] if e["rule_fired"]]

    assert "duplicate_detected" not in first_rules, first_rules
    assert "duplicate_detected" not in second_rules, second_rules
    assert second_detail["status"] == "payment_scheduled", second_detail["status"]


def test_genuine_duplicate_upload_is_still_flagged(client):
    """Guard against over-correcting: without a reset, the same invoice really
    is a duplicate and the product must still say so."""
    _upload(client, "sample-clean.pdf", as_name="e2e-sample-clean.pdf")
    second = _upload(client, "sample-clean.pdf", as_name="e2e-sample-clean.pdf")
    detail = client.get(f"/api/invoices/{second}").json()
    rules = [e["rule_fired"] for e in detail["audit_entries"] if e["rule_fired"]]
    assert "duplicate_detected" in rules, rules
    assert detail["status"] == "needs_review", detail["status"]
