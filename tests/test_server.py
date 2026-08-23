"""
Tests for hardcover.server — tool definitions, dispatch logic, and error formatting.

Tests call _dispatch() directly (the pure sync dispatch function) and
patch _get_client() to avoid any real HTTP calls or MCP transport setup.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from hardcover.client import (
    AuthError,
    ForbiddenError,
    GraphQLError,
    HardcoverError,
    QueryTimeoutError,
    RateLimitError,
)
import hardcover.server as server_module
from hardcover.server import TOOLS, _dispatch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _first_text(contents: list) -> str:
    return contents[0].text


def _parse(contents: list) -> Any:
    return json.loads(_first_text(contents))


def _is_error(contents: list) -> bool:
    return _first_text(contents).startswith("Error:")


def _call(name: str, args: dict[str, Any] | None = None) -> list:
    """Thin wrapper so tests read naturally."""
    return _dispatch(name, args or {})


# ---------------------------------------------------------------------------
# Tool listing
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    def test_tools_list_is_not_empty(self):
        assert len(TOOLS) > 0

    def test_all_tools_have_name(self):
        for tool in TOOLS:
            assert tool.name

    def test_all_tools_have_description(self):
        for tool in TOOLS:
            assert tool.description

    def test_all_tools_have_input_schema(self):
        for tool in TOOLS:
            assert tool.input_schema is not None

    def test_expected_tools_present(self):
        names = {t.name for t in TOOLS}
        expected = {
            "get_me", "search",
            "get_book_by_id", "get_book_by_slug",
            "get_editions_by_title", "get_edition_by_id", "get_editions_by_isbn",
            "get_author_by_id", "get_author_by_slug", "get_author_books",
            "get_series_by_id", "get_books_in_series",
            "get_my_library", "get_library_by_status",
            "get_reading_progress", "get_user_book", "get_my_reading_journal",
            "get_user_by_username", "get_user_library",
            "get_list_by_id",
        }
        assert expected.issubset(names), f"Missing tools: {expected - names}"

    def test_tool_names_are_unique(self):
        names = [t.name for t in TOOLS]
        assert len(names) == len(set(names))

    def test_required_fields_are_lists(self):
        for tool in TOOLS:
            required = tool.input_schema.get("required", [])
            assert isinstance(required, list), f"{tool.name}: 'required' must be a list"


# ---------------------------------------------------------------------------
# Dispatch — happy path
# ---------------------------------------------------------------------------


class TestDispatchHappyPath:
    def test_get_me(self):
        mock_data = {"me": {"id": 1, "username": "alice"}}
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = mock_data
            result = _call("get_me")
        assert _parse(result) == mock_data

    def test_search_defaults(self):
        mock_data = {"search": {"results": [], "query": "dune"}}
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = mock_data
            _call("search", {"query": "dune"})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars["query"] == "dune"
        assert call_vars["query_type"] == "book"
        assert call_vars["per_page"] == 25
        assert call_vars["page"] == 1

    def test_search_custom_type_and_pagination(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"search": {"results": []}}
            _call("search", {"query": "rowling", "query_type": "author", "per_page": 10, "page": 2})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars["query_type"] == "author"
        assert call_vars["per_page"] == 10
        assert call_vars["page"] == 2

    def test_get_book_by_id(self):
        mock_data = {"books": [{"id": 42, "title": "Dune"}]}
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = mock_data
            result = _call("get_book_by_id", {"id": 42})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"id": 42}
        assert _parse(result) == mock_data

    def test_get_book_by_slug(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"books": []}
            _call("get_book_by_slug", {"slug": "dune"})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"slug": "dune"}

    def test_get_editions_by_title(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"editions": []}
            _call("get_editions_by_title", {"title": "Oathbringer"})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"title": "Oathbringer"}

    def test_get_edition_by_id(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"editions": []}
            _call("get_edition_by_id", {"id": 21953653})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"id": 21953653}

    def test_get_editions_by_isbn(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"editions": []}
            _call("get_editions_by_isbn", {"isbn": "9780765326355"})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"isbn": "9780765326355"}

    def test_get_author_by_id(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"authors": []}
            _call("get_author_by_id", {"id": 7})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"id": 7}

    def test_get_author_by_slug(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"authors": []}
            _call("get_author_by_slug", {"slug": "brandon-sanderson"})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"slug": "brandon-sanderson"}

    def test_get_author_books_defaults(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"books": []}
            _call("get_author_books", {"author_id": 7})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"author_id": 7, "limit": 20, "offset": 0}

    def test_get_author_books_custom_pagination(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"books": []}
            _call("get_author_books", {"author_id": 7, "limit": 5, "offset": 10})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars["limit"] == 5
        assert call_vars["offset"] == 10

    def test_get_series_by_id(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"series": []}
            _call("get_series_by_id", {"id": 100})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"id": 100}

    def test_get_books_in_series(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"book_series": []}
            _call("get_books_in_series", {"series_id": 100})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"series_id": 100}

    def test_get_my_library_defaults(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"me": {"user_books": []}}
            _call("get_my_library")
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"limit": 25, "offset": 0}

    def test_get_library_by_status(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"me": {"user_books": []}}
            _call("get_library_by_status", {"status_id": 3})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars["status_id"] == 3
        assert call_vars["limit"] == 25

    def test_get_reading_progress(self):
        mock_data = {"me": {"user_books": []}}
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = mock_data
            result = _call("get_reading_progress")
        assert _parse(result) == mock_data

    def test_get_user_book(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"me": {"user_books": []}}
            _call("get_user_book", {"book_id": 99})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"book_id": 99}

    def test_get_my_reading_journal(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"me": {"user_books": []}}
            _call("get_my_reading_journal", {"book_id": 55})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"book_id": 55}

    def test_get_user_by_username(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"users": []}
            _call("get_user_by_username", {"username": "alice"})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"username": "alice"}

    def test_get_user_library(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"user_books": []}
            _call("get_user_library", {"user_id": 10, "status_id": 2})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars["user_id"] == 10
        assert call_vars["status_id"] == 2

    def test_get_list_by_id(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"lists": []}
            _call("get_list_by_id", {"id": 77})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars == {"id": 77}


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------


class TestUnknownTool:
    def test_unknown_tool_returns_error(self):
        result = _call("nonexistent_tool")
        assert _is_error(result)
        assert "nonexistent_tool" in _first_text(result)


# ---------------------------------------------------------------------------
# Error formatting (_run converts exceptions → error TextContent)
# ---------------------------------------------------------------------------


class TestErrorFormatting:
    def test_auth_error(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.side_effect = AuthError("bad token")
            result = _call("get_me")
        assert _is_error(result)
        assert "Authentication failed" in _first_text(result)

    def test_rate_limit_with_retry_hint(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.side_effect = RateLimitError("429", retry_after=30)
            result = _call("get_me")
        assert _is_error(result)
        assert "30s" in _first_text(result)

    def test_rate_limit_without_retry_hint(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.side_effect = RateLimitError("429", retry_after=None)
            result = _call("get_me")
        assert _is_error(result)
        assert "Retry after" not in _first_text(result)

    def test_forbidden_error(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.side_effect = ForbiddenError("insufficient_scope")
            result = _call("get_me")
        assert _is_error(result)
        assert "Forbidden" in _first_text(result)

    def test_timeout_error(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.side_effect = QueryTimeoutError("timeout")
            result = _call("get_me")
        assert _is_error(result)
        assert "timed out" in _first_text(result).lower()

    def test_graphql_error(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.side_effect = GraphQLError(
                "GraphQL errors: Field not found",
                errors=[{"message": "Field not found"}],
            )
            result = _call("get_me")
        assert _is_error(result)
        assert "GraphQL error" in _first_text(result)

    def test_generic_hardcover_error(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.side_effect = HardcoverError("something broke")
            result = _call("get_me")
        assert _is_error(result)
        assert "something broke" in _first_text(result)


# ---------------------------------------------------------------------------
# Response format
# ---------------------------------------------------------------------------


class TestResponseFormat:
    def test_result_is_valid_json(self):
        mock_data = {"me": {"id": 1, "username": "bob"}}
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = mock_data
            result = _call("get_me")
        parsed = json.loads(_first_text(result))
        assert parsed == mock_data

    def test_content_type_is_text(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"me": {"id": 1}}
            result = _call("get_me")
        assert result[0].type == "text"

    def test_returns_exactly_one_content_block(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"me": {"id": 1}}
            result = _call("get_me")
        assert len(result) == 1

    def test_error_also_returns_one_content_block(self):
        result = _call("nonexistent_tool")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# New tools added in v0.2
# ---------------------------------------------------------------------------


class TestNewTools:
    def test_get_me_uses_full_query(self):
        """get_me should return rich profile fields."""
        mock_data = {"me": [{"id": 1, "username": "alice", "books_count": 33, "flair": "Supporter", "pro": True}]}
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = mock_data
            result = _call("get_me")
        assert _parse(result) == mock_data

    def test_get_reading_stats_passes_user_id_and_since(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"all_time": {}, "filtered": {}}
            _call("get_reading_stats", {"user_id": 42, "since": "2026-01-01"})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars["user_id"] == 42
        assert call_vars["since"] == "2026-01-01"

    def test_get_reading_stats_since_optional(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"all_time": {}, "filtered": {}}
            _call("get_reading_stats", {"user_id": 42})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars["since"] is None

    def test_get_books_read_between(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"user_books": []}
            _call("get_books_read_between", {
                "user_id": 42, "since": "2026-01-01", "until": "2026-12-31"
            })
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars["user_id"] == 42
        assert call_vars["since"] == "2026-01-01"
        assert call_vars["until"] == "2026-12-31"
        assert call_vars["limit"] == 25
        assert call_vars["offset"] == 0

    def test_get_books_read_between_custom_pagination(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"user_books": []}
            _call("get_books_read_between", {
                "user_id": 42, "since": "2026-08-01", "until": "2026-08-31",
                "limit": 10, "offset": 5
            })
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars["limit"] == 10
        assert call_vars["offset"] == 5

    def test_get_my_goals(self):
        mock_data = {"me": [{"goals": [{"id": 1, "goal": 52, "progress": 33, "state": "active"}]}]}
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = mock_data
            result = _call("get_my_goals")
        assert _parse(result) == mock_data
        mock_get.return_value.execute.assert_called_once()
        # no variables — second positional arg should be None
        call_args = mock_get.return_value.execute.call_args[0]
        assert call_args[1] is None

    def test_get_my_activities_passes_user_id(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"activities": []}
            _call("get_my_activities", {"user_id": 139179})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars["user_id"] == 139179
        assert call_vars["limit"] == 20
        assert call_vars["offset"] == 0

    def test_get_my_activities_custom_pagination(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"activities": []}
            _call("get_my_activities", {"user_id": 1, "limit": 5, "offset": 10})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars["limit"] == 5
        assert call_vars["offset"] == 10

    def test_get_book_activities(self):
        with patch.object(server_module, "_get_client") as mock_get:
            mock_get.return_value.execute.return_value = {"activities": []}
            _call("get_book_activities", {"book_id": 375699})
            call_vars = mock_get.return_value.execute.call_args[0][1]
        assert call_vars["book_id"] == 375699
        assert call_vars["limit"] == 20

    def test_new_tools_all_in_tools_list(self):
        names = {t.name for t in TOOLS}
        new_tools = {
            "get_reading_stats",
            "get_books_read_between",
            "get_my_goals",
            "get_my_activities",
            "get_book_activities",
        }
        assert new_tools.issubset(names), f"Missing: {new_tools - names}"
