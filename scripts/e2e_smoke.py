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
import os
import sys
import time
import urllib.error
import urllib.parse
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

# Upload-name prefix owned by this harness. The maintenance endpoint deletes only
# rows whose stored upload name starts with it, so the smoke test can clean up
# after itself without touching real uploads or the seeded demo data.
OWNED_PREFIX = "e2e-"

# Legacy fixture names uploaded before the prefix existed. They are harness
# artifacts too, and are cleaned up by the same reset.
LEGACY_FIXTURE_NAMES = (
    "sample-clean.pdf",
    "sample-new-vendor.pdf",
    "sample-duplicate.pdf",
    "sample-high-value.pdf",
    "sample-contract.pdf",
)

# Token for POST /api/maintenance/reset-e2e. Read from the environment so the
# secret never lives in the repo.
RESET_TOKEN_ENV = "INVOICEFLOW_E2E_RESET_TOKEN"


def _owned_name(filename: str) -> str:
    """Return the upload name used for a fixture — always harness-owned."""
    return f"{OWNED_PREFIX}{filename}"

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
            (
                f'Content-Disposition: form-data; name="file"; '
                f'filename="{_owned_name(path.name)}"\r\n'
            ).encode(),
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


def upload_many(base: str, paths: list[Path]) -> tuple[int, dict | None]:
    """POST several files to /api/invoices/upload-batch in one multipart body."""
    boundary = "----invoiceflow-smoke-batch"
    chunks: list[bytes] = []
    for path in paths:
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            (
                f'Content-Disposition: form-data; name="files"; '
                f'filename="{_owned_name(path.name)}"\r\n'
            ).encode()
        )
        chunks.append(b"Content-Type: application/pdf\r\n\r\n")
        chunks.append(path.read_bytes())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    status, raw = req(
        base,
        "/api/invoices/upload-batch",
        method="POST",
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        return status, json.loads(raw)
    except Exception:
        return status, None


def reset_harness_artifacts(base: str, timeout: int = 60) -> tuple[int, str]:
    """Ask the server to delete artifacts left by previous smoke runs.

    Without this, each run's fixtures collide with the previous run's copies and
    the duplicate-detection rule fires on the fixture itself. Returns
    (http_status, detail) — a 404 means the endpoint is disabled on that
    instance, which is a legitimate configuration, not an error.
    """
    token = os.environ.get(RESET_TOKEN_ENV, "")
    if not token:
        return 0, f"no token in ${RESET_TOKEN_ENV}; skipping reset"
    status, raw = req(
        base,
        "/api/maintenance/reset-e2e",
        method="POST",
        headers={"X-E2E-Token": token},
        timeout=timeout,
    )
    return status, raw[:300].decode("utf-8", "replace")


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

    print("\n[0] reset harness artifacts")
    status, detail = reset_harness_artifacts(base)
    if status == 200:
        check("POST /api/maintenance/reset-e2e", True, detail)
    elif status == 404:
        print(f"  [skip] reset endpoint disabled on this instance ({detail})")
    elif status == 0:
        print(f"  [skip] {detail}")
    else:
        check("POST /api/maintenance/reset-e2e", False, f"HTTP {status} {detail}")

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

    print("\n[7] batch upload")
    batch_files = [samples / "sample-clean.pdf", samples / "sample-contract.pdf"]
    if all(f.exists() for f in batch_files):
        st, payload = upload_many(base, batch_files)
        ok_shape = (
            st in (200, 201)
            and isinstance(payload, dict)
            and isinstance(payload.get("results"), list)
            and len(payload["results"]) == len(batch_files)  # type: ignore[arg-type]
        )
        check(
            "POST /api/invoices/upload-batch",
            ok_shape,
            f"HTTP {st} {json.dumps(payload)[:300] if payload else 'no body'}",
        )
        if ok_shape and isinstance(payload, dict):
            raw_results = payload.get("results") or []
            results_list: list[dict] = [r for r in raw_results if isinstance(r, dict)]
            check(
                "batch reports accepted + failed counts",
                isinstance(payload.get("accepted"), int)
                and isinstance(payload.get("failed"), int)
                and payload["accepted"] + payload["failed"] == len(batch_files),  # type: ignore[index]
                f"accepted={payload.get('accepted')} failed={payload.get('failed')}",  # type: ignore[union-attr]
            )
            check(
                "every batch row names its file and status",
                all(r.get("filename") and r.get("status") for r in results_list),
                str(results_list)[:200],
            )
            first_id = next((r["invoice_id"] for r in results_list if r.get("invoice_id")), None)
            check("batch rows carry invoice ids", bool(first_id), str(first_id))
            if first_id:
                d = wait_terminal(base, first_id)
                check(
                    "batched invoice reaches a terminal state",
                    bool(d) and d.get("status") in TERMINAL,  # type: ignore[union-attr]
                    str(d.get("status") if d else None),  # type: ignore[union-attr]
                )
    else:
        check("batch upload samples present", False, str(batch_files))

    print("\n[8] transparency report (/api/audit/summary)")
    st, summary = get_json(base, "/api/audit/summary", timeout=60)
    if not (st == 200 and isinstance(summary, dict)):
        check("GET /api/audit/summary", False, f"HTTP {st}")
    else:
        check("GET /api/audit/summary", True, "")
        check(
            "summary counts every decision",
            isinstance(summary.get("total_decisions"), int) and summary["total_decisions"] > 0,  # type: ignore[operator]
            f"total_decisions={summary.get('total_decisions')}",
        )
        check(
            "summary reports rules that fired",
            isinstance(summary.get("rules_fired"), list) and len(summary["rules_fired"]) > 0,  # type: ignore[arg-type]
            str(summary.get("rules_fired"))[:200],
        )
        check(
            "every fired rule carries a count",
            all(
                isinstance(r.get("rule"), str) and isinstance(r.get("count"), int) and r["count"] > 0
                for r in summary.get("rules_fired", [])  # type: ignore[union-attr]
            ),
            "",
        )
        avg = summary.get("avg_confidence")
        check(
            "avg confidence in [0,1]",
            isinstance(avg, (int, float)) and 0.0 <= float(avg) <= 1.0,
            str(avg),
        )
        rate = summary.get("automation_rate")
        check(
            "automation rate in [0,1]",
            isinstance(rate, (int, float)) and 0.0 <= float(rate) <= 1.0,
            str(rate),
        )
        recent = summary.get("recent") or []
        check("recent decisions returned", isinstance(recent, list) and len(recent) > 0, str(len(recent)))
        check(
            "recent decisions explain themselves",
            all(
                (r.get("reasoning") or "").strip()
                and isinstance(r.get("confidence"), (int, float))
                and r.get("invoice_id")
                for r in recent
            ),
            "",
        )
        check(
            "decisions grouped by agent",
            isinstance(summary.get("by_agent"), dict) and len(summary["by_agent"]) > 0,  # type: ignore[arg-type]
            str(summary.get("by_agent")),
        )

    print("\n[9] vendors (/api/vendors/)")
    st, vendors = get_json(base, "/api/vendors/", timeout=60)
    if not (st == 200 and isinstance(vendors, list)):
        check("GET /api/vendors/", False, f"HTTP {st}")
    else:
        check("GET /api/vendors/", len(vendors) > 0, f"{len(vendors)} vendors")
        check(
            "vendor rows carry counts and totals",
            all(
                v.get("vendor_name")
                and isinstance(v.get("invoice_count"), int)
                and isinstance(v.get("total_amount"), (int, float))
                for v in vendors
            ),
            "",
        )
        check(
            "seeded vendor has settled history",
            any(v.get("has_history") is True for v in vendors),
            str([(v.get("vendor_name"), v.get("has_history")) for v in vendors])[:250],
        )

    print("\n[10] list filters")
    st, listing = get_json(base, "/api/invoices/?limit=200", timeout=60)
    ref_vendor = None
    if st == 200 and isinstance(listing, list) and listing:
        # rejected documents legitimately have a blank vendor; pick a real one
        ref_vendor = next(
            (i.get("vendor_name") for i in listing if i.get("vendor_name")), None
        )
    if not ref_vendor:
        check("invoice list populated", False, f"HTTP {st}")
    else:
        check("GET /api/invoices/?limit=200", True, f"{len(listing)} invoices")  # type: ignore[arg-type]
        st, filtered = get_json(
            base, f"/api/invoices/?q={urllib.parse.quote(ref_vendor)}", timeout=60
        )
        check(
            "q filter returns only matching vendors",
            st == 200
            and isinstance(filtered, list)
            and len(filtered) > 0
            and all(ref_vendor.lower() in (i.get("vendor_name") or "").lower() for i in filtered),  # type: ignore[union-attr]
            f"vendor={ref_vendor} n={len(filtered) if isinstance(filtered, list) else None}",
        )
        st, filtered = get_json(base, "/api/invoices/?status=definitely-not-a-status", timeout=60)
        check(
            "status filter narrows the list",
            st == 200 and isinstance(filtered, list) and len(filtered) == 0,  # type: ignore[arg-type]
            f"HTTP {st} n={len(filtered) if isinstance(filtered, list) else None}",
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
