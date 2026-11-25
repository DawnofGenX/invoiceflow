#!/usr/bin/env python3
"""End-to-end smoke test for a running InvoiceFlow instance.

Runs against any base URL (local, Docker, or public deployment) and asserts not just
that invoices flow, but that the *explainability* contract holds: every agent decision
must carry natural-language reasoning, a confidence in [0, 1], and — for rule-based
steps — the exact rule that fired.

Usage:
    python scripts/e2e_smoke.py --base-url http://localhost
    python scripts/e2e_smoke.py --base-url https://invoiceflow.example.com --verbose

Exit code 0 = every check passed, 1 = at least one failure.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAMPLES = ROOT / "backend" / "demo-data" / "sample_invoices"

TERMINAL = {
    "needs_review",
    "awaiting_approval",
    "approved",
    "payment_scheduled",
    "paid",
    "rejected",
    "error",
}

# file -> (expected terminal status, substring expected in rule_fired/action, min audit entries)
EXPECTATIONS = {
    "sample-clean.pdf": ("payment_scheduled", None, 5),
    "sample-new-vendor.pdf": ("awaiting_approval", "new_vendor", 5),
    "sample-duplicate.pdf": ("needs_review", "duplicate", 5),
    "sample-high-value.pdf": ("awaiting_approval", None, 5),
    # a non-invoice is short-circuited by intake: fewer entries is correct, not a bug
    "sample-contract.pdf": ("rejected", "not_an_invoice", 2),
}

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, ok, detail))
    if not ok or VERBOSE:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}{(' — ' + detail) if detail else ''}")
    return ok


def req(
    base: str,
    path: str,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> tuple[int, bytes]:
    url = base.rstrip("/") + path
    r = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def get_json(
    base: str, path: str, timeout: int = 120, method: str = "GET"
) -> tuple[int, dict | list | None]:
    status, body = req(base, path, method=method, timeout=timeout)
    try:
        return status, json.loads(body)
    except Exception:
        return status, None


def upload(base: str, path: Path) -> dict | None:
    boundary = "----invoiceflow-smoke"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode(),
            b"Content-Type: application/pdf\r\n\r\n",
            path.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    status, raw = req(
        base,
        "/api/invoices/upload",
        method="POST",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        payload = json.loads(raw)
    except Exception:
        return {"_error": f"HTTP {status}: {raw[:200]!r}"}
    if status >= 400:
        return {"_error": f"HTTP {status}: {payload}"}
    return payload


def wait_terminal(base: str, invoice_id: str, timeout: float = 180.0) -> dict | None:
    deadline = time.time() + timeout
    last: dict | None = None
    while time.time() < deadline:
        status, detail = get_json(base, f"/api/invoices/{invoice_id}", timeout=60)
        if status == 200 and isinstance(detail, dict):
            last = detail
            if detail.get("status") in TERMINAL:
                return detail
        time.sleep(2)
    return last


def run(base: str, samples: Path) -> int:
    print(f"InvoiceFlow E2E smoke → {base}")

    print("\n[1] health")
    status, health = get_json(base, "/api/health", timeout=30)
    check("GET /api/health", status == 200 and isinstance(health, dict), str(health))

    print("\n[2] seed")
    status, seeded = get_json(base, "/api/seed/", timeout=180, method="POST")
    check("POST /api/seed/", status in (200, 201) and isinstance(seeded, dict), str(seeded))

    print("\n[3] dashboard")
    status, dash = get_json(base, "/api/dashboard/", timeout=60)
    ok = status == 200 and isinstance(dash, dict) and "total_invoices" in dash
    check("GET /api/dashboard/", ok, json.dumps(dash) if isinstance(dash, dict) else str(dash))

    print("\n[4] pipeline + explainability contract")
    for fname, (expected_status, expected_rule, min_entries) in EXPECTATIONS.items():
        path = samples / fname
        if not path.exists():
            check(f"{fname}: file present", False, f"missing {path}")
            continue

        up = upload(base, path)
        if not up or "_error" in up:
            check(f"{fname}: upload", False, str(up))
            continue
        invoice_id = str(up.get("invoice_id") or "")
        check(f"{fname}: upload accepted", bool(invoice_id), f"id={invoice_id}")
        if not invoice_id:
            continue

        detail = wait_terminal(base, invoice_id)
        if not detail:
            check(f"{fname}: pipeline reached terminal state", False, "no detail returned")
            continue

        got_status = detail.get("status")
        check(
            f"{fname}: status == {expected_status}",
            got_status == expected_status,
            f"got {got_status}",
        )

        entries = detail.get("audit_entries") or []
        check(
            f"{fname}: audit trail recorded",
            len(entries) >= min_entries,
            f"{len(entries)} entries (min {min_entries})",
        )

        bad_reasoning = [e["action"] for e in entries if not (e.get("reasoning") or "").strip()]
        check(f"{fname}: every entry has reasoning", not bad_reasoning, str(bad_reasoning))

        bad_conf = [
            e["action"]
            for e in entries
            if not isinstance(e.get("confidence"), (int, float))
            or not (0.0 <= float(e["confidence"]) <= 1.0)
        ]
        check(f"{fname}: confidence in [0,1]", not bad_conf, str(bad_conf))

        rules = [e.get("rule_fired") for e in entries if e.get("rule_fired")]
        check(f"{fname}: rule_fired present", bool(rules), f"rules={rules}")

        if expected_rule:
            blob = " ".join(str(r) for r in rules + [e.get("action", "") for e in entries]).lower()
            check(
                f"{fname}: rule '{expected_rule}' fired",
                expected_rule.lower() in blob,
                f"rules={rules}",
            )

        print("\n[5] audit export")
        status, raw = req(base, f"/api/invoices/{invoice_id}/audit/export?format=json", timeout=60)
        exported: object = None
        try:
            exported = json.loads(raw)
        except Exception:
            pass
        ok = status == 200 and isinstance(exported, dict)
        trail = exported.get("audit_trail") if isinstance(exported, dict) else None
        n = len(trail) if isinstance(trail, list) else 0
        check(
            f"{fname}: JSON audit export",
            ok and n >= min_entries,
            f"HTTP {status}, {n} entries (min {min_entries})",
        )

    print("\n[6] approval round-trip")
    status, queue = get_json(base, "/api/approvals/", timeout=60)
    pending = []
    if status == 200:
        pending = queue if isinstance(queue, list) else queue.get("items", [])  # type: ignore[union-attr]
    if not pending:
        check("approval queue populated", False, "no pending approvals (duplicate seed run?)")
    else:
        first = pending[0]
        aid = first.get("id") if isinstance(first, dict) else None
        body = json.dumps({"decision": "approve", "comment": "e2e smoke"}).encode()
        st, raw2 = req(
            base,
            f"/api/approvals/{aid}/decide",
            method="POST",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        res = None
        try:
            res = json.loads(raw2)
        except Exception:
            pass
        check(
            "POST /api/approvals/{id}/decide",
            st in (200, 201) and isinstance(res, dict),
            f"HTTP {st} {res}",
        )
        if isinstance(res, dict):
            check(
                "approved invoice moves to payment_scheduled",
                res.get("invoice_status") == "payment_scheduled",
                str(res.get("invoice_status")),
            )

    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{'=' * 60}\n{passed}/{total} checks passed")
    if failed:
        print(f"\n{len(failed)} FAILURE(S):")
        for name, _, detail in failed:
            print(f"  - {name}{(' — ' + detail) if detail else ''}")
        return 1
    print("All checks passed.")
    return 0


def main() -> int:
    global VERBOSE
    p = argparse.ArgumentParser(description="InvoiceFlow end-to-end smoke test")
    p.add_argument("--base-url", default="http://localhost", help="instance root URL")
    p.add_argument("--samples", default=str(DEFAULT_SAMPLES), help="sample invoice directory")
    p.add_argument("--verbose", action="store_true", help="print every check, not just failures")
    args = p.parse_args()
    VERBOSE = args.verbose
    samples = Path(args.samples)
    if not samples.is_dir():
        print(f"sample directory not found: {samples}", file=sys.stderr)
        return 1
    try:
        return run(args.base_url, samples)
    except urllib.error.URLError as e:
        print(f"cannot reach {args.base_url}: {e}", file=sys.stderr)
        return 1


VERBOSE = False

if __name__ == "__main__":
    sys.exit(main())
