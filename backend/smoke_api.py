"""API smoke test via FastAPI TestClient (full HTTP path, all routing branches)."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

SAMPLES = Path(__file__).resolve().parent / "demo-data" / "sample_invoices"


def _upload(client: TestClient, name: str) -> str:
    with open(SAMPLES / name, "rb") as f:
        r = client.post(
            "/api/invoices/upload",
            files={"file": (name, f, "application/pdf")},
        )
    assert r.status_code == 201, r.text
    return r.json()["invoice_id"]


def main() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with TestClient(app) as client:
        # health
        r = client.get("/api/health")
        assert r.status_code == 200, r.text
        print("health:", r.json())

        # seed
        r = client.post("/api/seed/")
        print("seed:", r.json())

        # 1. clean invoice -> auto-approve -> payment_scheduled
        inv_id = _upload(client, "sample-clean.pdf")
        inv = client.get(f"/api/invoices/{inv_id}").json()
        print(f"[clean] status={inv['status']} vendor={inv['vendor_name']} amount={inv['amount']}")
        assert inv["status"] == "payment_scheduled", inv
        assert inv["vendor_name"] == "Acme Industrial Supply"
        assert inv["amount"] == 450.0

        audit = client.get(f"/api/invoices/{inv_id}/audit").json()
        print(f"[clean] audit entries: {len(audit)}")
        assert len(audit) >= 5
        for a in audit:
            print(f"    {a['agent_name']:<12} {a['action']:<20} rule={a['rule_fired']} conf={a['confidence']}")

        # export json + pdf
        rj = client.get(f"/api/invoices/{inv_id}/audit/export?format=json")
        assert rj.status_code == 200 and rj.headers["content-type"].startswith("application/json")
        print(f"[export] json OK ({len(rj.content)} bytes)")

        rp = client.get(f"/api/invoices/{inv_id}/audit/export?format=pdf")
        assert rp.status_code == 200 and rp.content[:4] == b"%PDF"
        print(f"[export] pdf OK ({len(rp.content)} bytes)")

        # 2. new vendor -> awaiting_approval (manager)
        nv_id = _upload(client, "sample-new-vendor.pdf")
        nv = client.get(f"/api/invoices/{nv_id}").json()
        print(f"[new-vendor] status={nv['status']}")
        assert nv["status"] == "awaiting_approval", nv

        # 3. high value (known vendor, admin threshold) -> awaiting_approval
        hv_id = _upload(client, "sample-high-value.pdf")
        hv = client.get(f"/api/invoices/{hv_id}").json()
        print(f"[high-value] status={hv['status']}")
        assert hv["status"] == "awaiting_approval", hv

        # approvals list + approve the new vendor
        approvals = client.get("/api/approvals/").json()
        print("approvals:", [(a["id"][:8], a["status"]) for a in approvals])
        pending = [a for a in approvals if a["status"] == "pending"]
        assert len(pending) == 2, f"expected 2 pending, got {len(pending)}"
        req_id = pending[0]["id"]
        r = client.post(
            f"/api/approvals/{req_id}/decide",
            json={"decision": "approve", "comment": "vendor verified"},
        )
        print("decide:", r.json())
        assert r.json()["approval_status"] == "approved"

        # 4. duplicate -> needs_review
        dup_id = _upload(client, "sample-duplicate.pdf")
        dup = client.get(f"/api/invoices/{dup_id}").json()
        print(f"[duplicate] status={dup['status']}")
        assert dup["status"] == "needs_review", dup

        # 5. non-invoice contract -> rejected
        con_id = _upload(client, "sample-contract.pdf")
        con = client.get(f"/api/invoices/{con_id}").json()
        print(f"[contract] status={con['status']}")
        assert con["status"] == "rejected", con

        # dashboard
        dash = client.get("/api/dashboard/").json()
        print("dashboard:", dash)

    print("\nALL API SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
