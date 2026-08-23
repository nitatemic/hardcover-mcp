"""
Shared pytest fixtures for hardcover-mcp tests.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from hardcover.client import HardcoverClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_response(
    status_code: int,
    body: Any = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Build a fake httpx.Response."""
    content = json.dumps(body).encode() if body is not None else b""
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers=headers or {},
    )


def ok_response(data: dict[str, Any], headers: dict[str, str] | None = None) -> httpx.Response:
    """HTTP 200 with a GraphQL data payload."""
    return make_response(200, {"data": data}, headers)


def graphql_error_response(message: str) -> httpx.Response:
    """HTTP 200 but GraphQL errors array."""
    return make_response(200, {"errors": [{"message": message}]})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> HardcoverClient:
    """A HardcoverClient with a dummy API key (no real HTTP calls)."""
    return HardcoverClient(api_key="test-key-abc123")


@pytest.fixture
def rate_limit_headers() -> dict[str, str]:
    """Typical rate-limit response headers (Free plan)."""
    return {
        "x-ratelimit-limit": "10",
        "x-ratelimit-remaining": "7",
        "x-ratelimit-reset": "1724412000",
        "x-ratelimit-daily-limit": "5000",
        "x-ratelimit-daily-remaining": "4983",
        "x-ratelimit-daily-reset": "1724457600",
    }
