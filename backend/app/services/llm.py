"""LLM client for the opencode-go collection (OpenAI-compatible chat dialect).

CRITICAL: opencode-go requires an `x-opencode-session` header (any non-empty
string). Without it every request returns HTTP 400 "MissingSessionID".
"""
import json
import time
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


def complete(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    timeout: float = 120.0,
) -> tuple[str, int]:
    """Single-turn chat completion. Returns (text, duration_ms)."""
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
