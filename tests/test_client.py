"""
Tests for hardcover.client.HardcoverClient and related helpers.

All tests mock httpx.post so no real network calls are made.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from hardcover.client import (
    AuthError,
    ForbiddenError,
    GraphQLError,
    HardcoverClient,
    HardcoverError,
    QueryTimeoutError,
    RateLimitError,
    RateLimitState,
)
from tests.conftest import graphql_error_response, make_response, ok_response

DUMMY_KEY = "test-key-abc123"
DUMMY_QUERY = "query { me { id } }"


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestClientConstruction:
    def test_accepts_explicit_api_key(self):
        c = HardcoverClient(api_key=DUMMY_KEY)
        assert c._api_key == DUMMY_KEY

    def test_reads_key_from_env(self, monkeypatch):
        monkeypatch.setenv("HARDCOVER_API_KEY", "env-key-xyz")
        c = HardcoverClient()
        assert c._api_key == "env-key-xyz"

    def test_raises_auth_error_with_no_key(self, monkeypatch):
        monkeypatch.delenv("HARDCOVER_API_KEY", raising=False)
        with pytest.raises(AuthError, match="No API key"):
            HardcoverClient()

    def test_default_rate_limit_state_is_empty(self):
        c = HardcoverClient(api_key=DUMMY_KEY)
        assert c.rate_limit.remaining_burst is None
        assert c.rate_limit.remaining_daily is None


# ---------------------------------------------------------------------------
# Successful responses
# ---------------------------------------------------------------------------


class TestSuccessfulExecute:
    def test_returns_data_dict(self, client):
        response = ok_response({"me": {"id": 42, "username": "alice"}})
        with patch("httpx.post", return_value=response):
            result = client.execute(DUMMY_QUERY)
        assert result == {"me": {"id": 42, "username": "alice"}}

    def test_passes_variables(self, client):
        response = ok_response({"books": []})
        with patch("httpx.post", return_value=response) as mock_post:
            client.execute(DUMMY_QUERY, {"id": 99})
        call_kwargs = mock_post.call_args
        sent_body = call_kwargs.kwargs["json"]
        assert sent_body["variables"] == {"id": 99}

    def test_omits_variables_key_when_none(self, client):
        response = ok_response({"me": {"id": 1}})
        with patch("httpx.post", return_value=response) as mock_post:
            client.execute(DUMMY_QUERY)
        sent_body = mock_post.call_args.kwargs["json"]
        assert "variables" not in sent_body

    def test_authorization_header_is_bearer(self, client):
        response = ok_response({"me": {"id": 1}})
        with patch("httpx.post", return_value=response) as mock_post:
            client.execute(DUMMY_QUERY)
        sent_headers = mock_post.call_args.kwargs["headers"]
        assert sent_headers["Authorization"] == f"Bearer {DUMMY_KEY}"

    def test_content_type_is_json(self, client):
        response = ok_response({"me": {"id": 1}})
        with patch("httpx.post", return_value=response) as mock_post:
            client.execute(DUMMY_QUERY)
        sent_headers = mock_post.call_args.kwargs["headers"]
        assert sent_headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# Rate-limit header parsing
# ---------------------------------------------------------------------------


class TestRateLimitParsing:
    def test_parses_headers_after_200(self, client, rate_limit_headers):
        response = ok_response({"me": {"id": 1}}, headers=rate_limit_headers)
        with patch("httpx.post", return_value=response):
            client.execute(DUMMY_QUERY)
        assert client.rate_limit.remaining_burst == 7
        assert client.rate_limit.remaining_daily == 4983
        assert client.rate_limit.burst_reset == 1724412000
        assert client.rate_limit.daily_reset == 1724457600

    def test_no_headers_leaves_state_empty(self, client):
        response = ok_response({"me": {"id": 1}})
        with patch("httpx.post", return_value=response):
            client.execute(DUMMY_QUERY)
        assert client.rate_limit.remaining_burst is None

    def test_partial_headers_handled_gracefully(self, client):
        response = ok_response({"me": {"id": 1}}, headers={"x-ratelimit-remaining": "3"})
        with patch("httpx.post", return_value=response):
            client.execute(DUMMY_QUERY)
        assert client.rate_limit.remaining_burst == 3
        assert client.rate_limit.remaining_daily is None


class TestRateLimitStateFromHeaders:
    def test_parses_all_fields(self):
        headers = httpx.Headers({
            "x-ratelimit-limit": "10",
            "x-ratelimit-remaining": "5",
            "x-ratelimit-reset": "1000",
            "x-ratelimit-daily-limit": "5000",
            "x-ratelimit-daily-remaining": "4500",
            "x-ratelimit-daily-reset": "2000",
        })
        state = RateLimitState.from_headers(headers)
        assert state.remaining_burst == 5
        assert state.remaining_daily == 4500
        assert state.burst_reset == 1000
        assert state.daily_reset == 2000

    def test_returns_none_for_missing_fields(self):
        state = RateLimitState.from_headers(httpx.Headers({}))
        assert state.remaining_burst is None
        assert state.remaining_daily is None
        assert state.burst_reset is None
        assert state.daily_reset is None


# ---------------------------------------------------------------------------
# HTTP error codes → exceptions
# ---------------------------------------------------------------------------


class TestHttpErrorMapping:
    def test_401_raises_auth_error(self, client):
        with patch("httpx.post", return_value=make_response(401)):
            with pytest.raises(AuthError, match="Invalid or expired"):
                client.execute(DUMMY_QUERY)

    def test_403_raises_forbidden_error(self, client):
        with patch("httpx.post", return_value=make_response(403, {"error": "insufficient_scope"})):
            with pytest.raises(ForbiddenError, match="insufficient_scope"):
                client.execute(DUMMY_QUERY)

    def test_403_forbidden_without_body(self, client):
        with patch("httpx.post", return_value=make_response(403)):
            with pytest.raises(ForbiddenError, match="forbidden"):
                client.execute(DUMMY_QUERY)

    def test_408_raises_query_timeout_error(self, client):
        with patch("httpx.post", return_value=make_response(408, {"error": "Request timeout"})):
            with pytest.raises(QueryTimeoutError):
                client.execute(DUMMY_QUERY)

    def test_429_raises_rate_limit_error(self, client):
        with patch("httpx.post", return_value=make_response(429, {"error": "Too Many Requests", "message": "daily limit"})):
            with pytest.raises(RateLimitError, match="daily limit"):
                client.execute(DUMMY_QUERY)

    def test_429_exposes_retry_after(self, client):
        resp = make_response(429, {"error": "Too Many Requests"}, headers={"Retry-After": "42"})
        with patch("httpx.post", return_value=resp):
            with pytest.raises(RateLimitError) as exc_info:
                client.execute(DUMMY_QUERY)
        assert exc_info.value.retry_after == 42

    def test_429_retry_after_none_when_missing(self, client):
        with patch("httpx.post", return_value=make_response(429, {"error": "Too Many Requests"})):
            with pytest.raises(RateLimitError) as exc_info:
                client.execute(DUMMY_QUERY)
        assert exc_info.value.retry_after is None

    def test_500_raises_hardcover_error(self, client):
        with patch("httpx.post", return_value=make_response(500, {"error": "An unknown error occurred"})):
            with pytest.raises(HardcoverError, match="Unexpected HTTP 500"):
                client.execute(DUMMY_QUERY)

    def test_503_retries_then_raises(self, client):
        """503 should retry once then raise."""
        resp_503 = make_response(503, {"error": "Service temporarily unavailable"})
        with patch("httpx.post", return_value=resp_503) as mock_post:
            with patch("time.sleep"):  # skip actual sleep
                with pytest.raises(HardcoverError, match="Unexpected HTTP 503"):
                    client.execute(DUMMY_QUERY, retries=1)
        # called twice: initial attempt + 1 retry
        assert mock_post.call_count == 2

    def test_503_no_retry_when_retries_zero(self, client):
        resp_503 = make_response(503)
        with patch("httpx.post", return_value=resp_503) as mock_post:
            with pytest.raises(HardcoverError):
                client.execute(DUMMY_QUERY, retries=0)
        assert mock_post.call_count == 1


# ---------------------------------------------------------------------------
# GraphQL-level errors (HTTP 200 with errors array)
# ---------------------------------------------------------------------------


class TestGraphQLErrors:
    def test_raises_graphql_error_on_errors_array(self, client):
        with patch("httpx.post", return_value=graphql_error_response("Field not found")):
            with pytest.raises(GraphQLError, match="Field not found"):
                client.execute(DUMMY_QUERY)

    def test_graphql_error_carries_errors_list(self, client):
        body = {"errors": [{"message": "err1"}, {"message": "err2"}]}
        with patch("httpx.post", return_value=make_response(200, body)):
            with pytest.raises(GraphQLError) as exc_info:
                client.execute(DUMMY_QUERY)
        assert len(exc_info.value.errors) == 2

    def test_empty_errors_array_does_not_raise(self, client):
        """An empty errors list should be treated as success if data is present."""
        body = {"data": {"me": {"id": 1}}, "errors": []}
        with patch("httpx.post", return_value=make_response(200, body)):
            result = client.execute(DUMMY_QUERY)
        assert result == {"me": {"id": 1}}

    def test_missing_data_field_raises(self, client):
        with patch("httpx.post", return_value=make_response(200, {"something": "else"})):
            with pytest.raises(HardcoverError, match="missing 'data'"):
                client.execute(DUMMY_QUERY)

    def test_invalid_json_raises(self, client):
        response = httpx.Response(200, content=b"not json", headers={})
        with patch("httpx.post", return_value=response):
            with pytest.raises(HardcoverError, match="Could not parse JSON"):
                client.execute(DUMMY_QUERY)


# ---------------------------------------------------------------------------
# Timeout (client-side)
# ---------------------------------------------------------------------------


class TestClientSideTimeout:
    def test_httpx_timeout_raises_query_timeout_error(self, client):
        with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
            with pytest.raises(QueryTimeoutError, match="timed out"):
                client.execute(DUMMY_QUERY)
