"""Rate-limited, retrying HTTP client for SEC EDGAR.

EDGAR requires a descriptive User-Agent and enforces a request-rate limit.
Centralising both here means every module that talks to EDGAR (search,
downloads) gets the same throttling and retry behaviour for free, and
nothing else in the codebase needs to know about EDGAR's access etiquette.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from types import TracebackType

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

# SEC's documented ceiling is 10 requests/second; stay under it with margin.
MAX_REQUESTS_PER_SECOND = 8.0
_MIN_INTERVAL_SECONDS = 1.0 / MAX_REQUESTS_PER_SECOND


def _is_transient(exc: BaseException) -> bool:
    """Network errors and 429/5xx responses are worth retrying; anything
    else (404, malformed request) will not succeed on a retry."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


@dataclass
class EdgarClient:
    """Thin wrapper over ``httpx.Client`` enforcing EDGAR's access rules.

    ``transport`` is an injection point for tests (an ``httpx.MockTransport``)
    so the retry and throttling logic can be exercised without a live
    network call.
    """

    user_agent: str
    timeout: float = 30.0
    transport: httpx.BaseTransport | None = field(default=None, repr=False)
    _client: httpx.Client = field(init=False, repr=False)
    _last_request_at: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"},
            timeout=self.timeout,
            transport=self.transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> EdgarClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
        self._last_request_at = time.monotonic()

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    def get(self, url: str, params: dict[str, str] | None = None) -> httpx.Response:
        self._throttle()
        response = self._client.get(url, params=params)
        response.raise_for_status()
        return response
