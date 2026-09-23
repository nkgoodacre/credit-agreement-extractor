"""Tests for cae.edgar.client: retry-on-transient-error and rate limiting.

Uses httpx.MockTransport throughout so these never touch the network.
"""

from __future__ import annotations

import time

import httpx
import pytest

from cae.edgar.client import EdgarClient


def test_retries_on_500_then_succeeds() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(500, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    client = EdgarClient(user_agent="test test@example.com", transport=httpx.MockTransport(handler))
    response = client.get("https://example.com/x")
    assert response.status_code == 200
    assert attempts["n"] == 3


def test_does_not_retry_on_404() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(404, request=request)

    client = EdgarClient(user_agent="test test@example.com", transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        client.get("https://example.com/missing")
    assert attempts["n"] == 1


def test_sends_configured_user_agent() -> None:
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers["user-agent"] = request.headers.get("user-agent", "")
        return httpx.Response(200, json={}, request=request)

    client = EdgarClient(
        user_agent="credit-agreement-extractor alias@mozmail.com",
        transport=httpx.MockTransport(handler),
    )
    client.get("https://example.com/x")
    assert seen_headers["user-agent"] == "credit-agreement-extractor alias@mozmail.com"


def test_throttles_between_requests() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={}, request=request)

    client = EdgarClient(user_agent="test test@example.com", transport=httpx.MockTransport(handler))
    start = time.monotonic()
    for _ in range(3):
        client.get("https://example.com/x")
    elapsed = time.monotonic() - start
    # 3 requests at <=8 req/s must take at least 2 intervals (~0.25s).
    assert elapsed >= 0.2
