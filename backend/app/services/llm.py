"""LLM client for the opencode-go collection (OpenAI-compatible chat dialect).

CRITICAL: opencode-go requires an `x-opencode-session` header (any non-empty
string). Without it every request returns HTTP 400 "MissingSessionID".
"""
import json
import re
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.config import settings

_CHAT_ENDPOINT = "/chat/completions"



class LLMError(Exception):
    """Raised when the LLM call fails or returns an unusable payload."""


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.opencode_api_key}",
        "x-opencode-session": settings.opencode_session,
        "Content-Type": "application/json",
    }


def _post(payload: dict[str, Any], timeout: float) -> tuple[dict, int]:
    url = settings.opencode_base_url.rstrip("/") + _CHAT_ENDPOINT
    t0 = time.time()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=_headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        body = e.response.text[:500]
        raise LLMError(f"LLM HTTP {e.response.status_code}: {body}") from e
    except httpx.HTTPError as e:
        raise LLMError(f"LLM request failed: {e}") from e
    elapsed_ms = int((time.time() - t0) * 1000)
    return data, elapsed_ms


def _extract_content(data: dict) -> str:
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"Unexpected LLM response shape: {str(data)[:500]}") from e


# ---------------------------------------------------------------------------
# Offline deterministic stub (LLM_STUB=1)
#
# Used by the test suite and CI so the whole pipeline can be exercised with no
# network and no API key. It is NOT a language model: it parses the
# well-formed sample documents with regexes. Anything outside tests should run
# against the real gateway.
# ---------------------------------------------------------------------------

_CONTRACT_MARKERS = ("AGREEMENT", "CONTRACT", "TERMS AND CONDITIONS", "STATEMENT OF WORK")


def _first_match(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip() if m else None


def _money(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(Decimal(value.replace(",", "").replace("$", "").strip()))
    except (InvalidOperation, ValueError):
        return None


def _stub_classify(text: str) -> dict[str, Any]:
    upper = text.upper()
    has_total = "TOTAL:" in upper
    if "INVOICE" in upper and has_total:
        return {
            "document_type": "invoice",
            "confidence": 0.97,
            "reasoning": "The document is titled INVOICE and carries a line-item table with a "
            "grand Total, which is the structural signature of a bill.",
        }
    if any(marker in upper for marker in _CONTRACT_MARKERS):
        return {
            "document_type": "contract",
            "confidence": 0.93,
            "reasoning": "The document contains agreement/contract language and no billed totals, "
            "so it is a legal document rather than an invoice.",
        }
    if has_total:
        return {
            "document_type": "receipt",
            "confidence": 0.72,
            "reasoning": "A total is present but the document is not titled INVOICE; the closest "
            "classification is a receipt.",
        }
    return {
        "document_type": "other",
        "confidence": 0.6,
        "reasoning": "No invoice title, billed total or contract language was found.",
    }


def _stub_extract(text: str) -> dict[str, Any]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    vendor = None
    for index, line in enumerate(lines):
        if line.upper().startswith("INVOICE") and index + 1 < len(lines):
            vendor = lines[index + 1]
            break

    items: list[dict[str, Any]] = []
    for line in lines:
        m = re.match(
            r"^(?P<desc>.+?)\s{2,}(?P<qty>\d+(?:\.\d+)?)\s+(?P<unit>\d+(?:\.\d+)?)\s+"
            r"(?P<total>\d+(?:\.\d+)?)$",
            line,
        )
        if m and "unit price" not in line.lower():
            items.append(
                {
                    "description": m.group("desc").strip(),
                    "quantity": float(m.group("qty")),
                    "unit_price": float(m.group("unit")),
                    "total": float(m.group("total")),
                }
            )

    return {
        "vendor_name": vendor,
        "vendor_email": _first_match(r"([\w.+-]+@[\w-]+\.[\w.-]+)", text),
        "invoice_number": _first_match(r"Invoice Number:\s*(\S+)", text),
        "amount": _money(_first_match(r"Total:\s*\$?([\d,]+(?:\.\d{2})?)", text)),
        "currency": "USD",
        "tax_amount": None,
        "invoice_date": _first_match(r"Invoice Date:\s*(\d{4}-\d{2}-\d{2})", text),
        "due_date": _first_match(r"Due Date:\s*(\d{4}-\d{2}-\d{2})", text),
        "po_number": _first_match(r"PO Number:\s*(\S+)", text),
        "line_items": items,
        "confidence": 0.94 if items else 0.78,
        "reasoning": (
            f"Read the vendor name, invoice number, dates and {len(items)} line item(s) directly "
            "from the labelled fields; the amount is the stated grand total."
        ),
    }


def _stub_json(messages: list[dict[str, str]]) -> dict[str, Any]:
    blob = "\n".join(str(m.get("content", "")) for m in messages)
    if '"document_type"' in blob:
        return _stub_classify(blob)
    return _stub_extract(blob)


def complete(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    timeout: float = 120.0,
) -> tuple[str, int]:
    """Single-turn chat completion. Returns (text, duration_ms)."""
    if settings.llm_stub:
        return json.dumps(_stub_json(messages)), 3
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data, elapsed_ms = _post(payload, timeout)
    return _extract_content(data), elapsed_ms


def complete_json(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    timeout: float = 120.0,
) -> tuple[dict, int]:
    """Chat completion constrained to JSON. Returns (parsed_dict, duration_ms)."""
    if settings.llm_stub:
        return _stub_json(messages), 3
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    data, elapsed_ms = _post(payload, timeout)
    text = _extract_content(data)

    try:
        return json.loads(text), elapsed_ms
    except json.JSONDecodeError:
        # Fallback: pull the first {...} block out of a chatty response.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1]), elapsed_ms
            except json.JSONDecodeError as e:
                raise LLMError(f"LLM returned invalid JSON: {text[:500]}") from e
        raise LLMError(f"LLM returned no JSON object: {text[:500]}")
