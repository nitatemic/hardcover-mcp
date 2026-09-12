"""
Hardcover GraphQL client with rate-limit awareness.

Rate limits (as of Aug 2026):
  Free:      5 000 req/day  |  10 burst  |  60 req/min
  Supporter: 50 000 req/day |  15 burst  |  60 req/min

The client reads the standard RateLimit response headers and raises
RateLimitError with a retry_after hint when throttled (HTTP 429).
A single request may contain at most 5 top-level queries; the server
layer is responsible for staying within that bound.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

HARDCOVER_API_URL = "https://api.hardcover.app/v1/graphql"
_DEFAULT_TIMEOUT = 30  # seconds — matches the API's own max timeout


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class HardcoverError(Exception):
    """Base exception for all Hardcover client errors."""


class AuthError(HardcoverError):
    """Raised on HTTP 401 — missing, invalid, or expired token."""


class ForbiddenError(HardcoverError):
    """Raised on HTTP 403 — missing scope, unsupported operation, or
    top-level query limit exceeded."""


class RateLimitError(HardcoverError):
    """Raised on HTTP 429 — daily or per-minute limit exceeded."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after  # seconds until bucket refills


class QueryTimeoutError(HardcoverError):
    """Raised on HTTP 408 — query exceeded the 30-second server timeout."""


class GraphQLError(HardcoverError):
    """Raised when the HTTP status is 200 but the body contains errors."""

    def __init__(self, message: str, errors: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.errors = errors


# ---------------------------------------------------------------------------
# Rate-limit state (in-process, per-client)
# ---------------------------------------------------------------------------


@dataclass
class RateLimitState:
    """Snapshot parsed from the last successful response's headers."""

    remaining_burst: int | None = None
    remaining_daily: int | None = None
    burst_reset: int | None = None   # unix timestamp
    daily_reset: int | None = None   # unix timestamp
    raw: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_headers(cls, headers: httpx.Headers) -> "RateLimitState":
        state = cls()
        state.raw = dict(headers)

        # Legacy X-RateLimit-* headers (more reliable to parse than the IETF draft)
        def _int(key: str) -> int | None:
            val = headers.get(key)
            return int(val) if val is not None else None

        state.remaining_burst = _int("x-ratelimit-remaining")
        state.remaining_daily = _int("x-ratelimit-daily-remaining")
        state.burst_reset = _int("x-ratelimit-reset")
        state.daily_reset = _int("x-ratelimit-daily-reset")
        return state


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class HardcoverClient:
    """
    Thin async-capable GraphQL client for the Hardcover API.

    Usage::

        client = HardcoverClient()          # reads HARDCOVER_API_KEY from env
        data = client.execute(QUERY, {"id": 123})
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        user_agent: str = "hardcover-mcp/0.1.2 (github.com/muhyousri/hardcover-mcp)",
    ) -> None:
        self._api_key = api_key or os.environ.get("HARDCOVER_API_KEY", "")
        if not self._api_key:
            raise AuthError(
                "No API key provided. Set HARDCOVER_API_KEY in your environment "
                "or pass api_key= to HardcoverClient()."
            )
        self._timeout = timeout
        self._user_agent = user_agent
        self.rate_limit: RateLimitState = RateLimitState()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        retries: int = 1,
    ) -> dict[str, Any]:
        """
        Execute a GraphQL query and return the ``data`` dict.

        Parameters
        ----------
        query:
            GraphQL query or mutation string.
        variables:
            Optional dict of GraphQL variables.
        retries:
            How many times to retry on transient 503 errors (default 1).

        Raises
        ------
        AuthError, ForbiddenError, RateLimitError, QueryTimeoutError,
        GraphQLError, HardcoverError
        """
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": self._user_agent,
        }

        attempt = 0
        while True:
            try:
                response = httpx.post(
                    HARDCOVER_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=self._timeout,
                )
            except httpx.TimeoutException as exc:
                raise QueryTimeoutError(
                    "Request timed out before the server responded."
                ) from exc

            # Always update rate-limit state from headers when present
            if response.headers:
                self.rate_limit = RateLimitState.from_headers(response.headers)

            status = response.status_code

            if status == 200:
                return self._parse_response(response)

            if status == 401:
                raise AuthError("Invalid or expired API token (HTTP 401).")

            if status == 403:
                body = self._safe_json(response)
                err = body.get("error", "forbidden")
                raise ForbiddenError(f"Access denied (HTTP 403): {err}")

            if status == 408:
                raise QueryTimeoutError("Query exceeded server timeout (HTTP 408).")

            if status == 429:
                retry_after: int | None = None
                ra = response.headers.get("Retry-After")
                if ra:
                    try:
                        retry_after = int(ra)
                    except ValueError:
                        pass
                body = self._safe_json(response)
                msg = body.get("message") or body.get("error") or "Too Many Requests"
                raise RateLimitError(
                    f"Rate limit exceeded (HTTP 429): {msg}",
                    retry_after=retry_after,
                )

            if status == 503 and attempt < retries:
                attempt += 1
                time.sleep(2**attempt)  # simple exponential back-off
                continue

            # Anything else
            raise HardcoverError(
                f"Unexpected HTTP {status}: {response.text[:200]}"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except Exception as exc:
            raise HardcoverError(
                f"Could not parse JSON response: {response.text[:200]}"
            ) from exc

        if "errors" in body and body["errors"]:
            errors = body["errors"]
            messages = "; ".join(
                e.get("message", str(e)) for e in errors
            )
            raise GraphQLError(f"GraphQL errors: {messages}", errors=errors)

        data = body.get("data")
        if data is None:
            raise HardcoverError(
                f"Response missing 'data' field: {body}"
            )
        return data

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any]:
        try:
            return response.json()
        except Exception:
            return {}
