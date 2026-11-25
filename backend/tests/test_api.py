"""API-level tests: batch upload, filters, audit report, vendors, error handling.

These run the real FastAPI app through TestClient against the offline LLM stub, so
they cover routing, serialization, persistence and the background pipeline without
touching the network.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

SAMPLES = Path(__file__).resolve().parent.parent / "demo-data" / "sample_invoices"


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        c.post("/api/seed/")
        yield c
    Base.metadata.drop_all(engine)


def _pdf(name: str) -> tuple[str, bytes, str]:
    return (name, (SAMPLES / name).read_bytes(), "application/pdf")


def _upload(client: TestClient, name: str) -> dict:
    res = client.post("/api/invoices/upload", files={"file": _pdf(name)})
    assert res.status_code == 201, res.text
    return res.json()


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_upload_runs_pipeline_and_schedules_payment(client):
    body = _upload(client, "sample-clean.pdf")
    detail = client.get(f"/api/invoices/{body['invoice_id']}").json()
    assert detail["status"] == "payment_scheduled"
    assert detail["vendor_name"] == "Acme Industrial Supply"
    assert detail["amount"] == 450.0
    assert len(detail["audit_entries"]) >= 5


def test_upload_rejects_unsupported_type(client):
    res = client.post(
        "/api/invoices/upload", files={"file": ("notes.txt", b"hello", "text/plain")}
    )
    assert res.status_code == 400
    assert "Unsupported file type" in res.json()["detail"]


def test_upload_rejects_empty_file(client):
    res = client.post(
        "/api/invoices/upload", files={"file": ("blank.pdf", b"", "application/pdf")}
    )
    assert res.status_code == 422


def test_batch_upload_partial_success(client):
    files = [
        ("files", _pdf("sample-clean.pdf")),
        ("files", ("bad.txt", b"not a pdf", "text/plain")),
        ("files", _pdf("sample-new-vendor.pdf")),
    ]
    res = client.post("/api/invoices/upload-batch", files=files)
    assert res.status_code == 201, res.text
    payload = res.json()
    assert payload["accepted"] == 2
    assert payload["failed"] == 1
    statuses = {item["filename"]: item["status"] for item in payload["results"]}
    assert statuses["bad.txt"] == "failed"
    assert statuses["sample-clean.pdf"] == "pending"


def test_list_filters_by_status_and_query(client):
    _upload(client, "sample-clean.pdf")
    _upload(client, "sample-new-vendor.pdf")

    scheduled = client.get("/api/invoices/", params={"status": "payment_scheduled"}).json()
    assert [inv["invoice_number"] for inv in scheduled] == ["INV-2024-001"]

    by_vendor = client.get("/api/invoices/", params={"q": "nova"}).json()
    assert len(by_vendor) == 1
    assert by_vendor[0]["vendor_name"] == "Nova Robotics LLC"

    by_po = client.get("/api/invoices/", params={"q": "po-1042"}).json()
    assert len(by_po) == 1
    assert by_po[0]["invoice_number"] == "INV-2024-001"


def test_audit_summary_reports_explainability(client):
    _upload(client, "sample-clean.pdf")
    _upload(client, "sample-new-vendor.pdf")
    summary = client.get("/api/audit/summary").json()

    assert summary["total_decisions"] >= 10
    assert summary["decisions_per_invoice"] > 1
    assert summary["avg_confidence"] is not None
    assert 0.0 <= summary["automation_rate"] <= 1.0
    rules = {row["rule"] for row in summary["rules_fired"]}
    assert "po_match" in rules
    assert "new_vendor_verification" in rules
    assert len(summary["recent"]) > 0
    # every decision shown to a reviewer must carry human-readable reasoning
    assert all(row["reasoning"].strip() for row in summary["recent"])


def test_vendors_aggregate_history(client):
    _upload(client, "sample-clean.pdf")
    _upload(client, "sample-new-vendor.pdf")
    vendors = client.get("/api/vendors/").json()

    names = {row["vendor_name"] for row in vendors}
    assert {"Acme Industrial Supply", "Nova Robotics LLC"} <= names
    acme = next(row for row in vendors if row["vendor_name"] == "Acme Industrial Supply")
    assert acme["has_history"] is True
    assert acme["invoice_count"] >= 1  # seed ships settled history for Acme
    nova = next(row for row in vendors if row["vendor_name"] == "Nova Robotics LLC")
    assert nova["has_history"] is False


def test_audit_export_json_and_pdf(client):
    body = _upload(client, "sample-clean.pdf")
    invoice_id = body["invoice_id"]

    js = client.get(f"/api/invoices/{invoice_id}/audit/export", params={"format": "json"})
    assert js.status_code == 200
    payload = js.json()
    assert payload["invoice_number"] == "INV-2024-001"
    assert len(payload["audit_trail"]) >= 5

    pdf = client.get(f"/api/invoices/{invoice_id}/audit/export", params={"format": "pdf"})
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    bad = client.get(f"/api/invoices/{invoice_id}/audit/export", params={"format": "csv"})
    assert bad.status_code == 400


def test_approval_decision_flow(client):
    body = _upload(client, "sample-new-vendor.pdf")
    invoice_id = body["invoice_id"]
    queue = client.get("/api/approvals/").json()
    request = next(item for item in queue if item["invoice_id"] == invoice_id)

    res = client.post(
        f"/api/approvals/{request['id']}/decide",
        json={"decision": "approve", "comment": "vendor verified by phone"},
    )
    assert res.status_code == 200
    assert res.json()["invoice_status"] == "payment_scheduled"

    detail = client.get(f"/api/invoices/{invoice_id}").json()
    assert detail["status"] == "payment_scheduled"
    actions = [entry["action"] for entry in detail["audit_entries"]]
    assert "approval_decision" in actions or "route_approval" in actions
