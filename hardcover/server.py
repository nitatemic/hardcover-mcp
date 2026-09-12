"""
Hardcover MCP Server

Exposes the following tools:

  Identity / profile
  ─────────────────
  • get_me                  — current authenticated user

  Search
  ──────
  • search                  — search books, authors, series, users, lists, …

  Books
  ─────
  • get_book_by_id          — book details by Hardcover ID
  • get_book_by_slug        — book details by slug
  • get_editions_by_title   — all editions matching a title
  • get_edition_by_id       — single edition details
  • get_editions_by_isbn    — look up edition by ISBN-10 or ISBN-13

  Authors
  ───────
  • get_author_by_id        — author profile by ID
  • get_author_by_slug      — author profile by slug
  • get_author_books        — books by an author

  Series
  ──────
  • get_series_by_id        — series info by ID
  • get_books_in_series     — ordered, deduplicated book list for a series

  My library
  ──────────
  • get_my_library          — all user_books (paginated)
  • get_library_by_status   — filter library by reading status
  • get_reading_progress    — currently-reading books with page progress
  • get_user_book           — my relationship with a specific book
  • get_my_reading_journal  — reading journal for a specific book

  Other users
  ───────────
  • get_user_library        — another user's library filtered by status

  Lists
  ─────
  • get_list_by_id          — list details and its books
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import mcp_types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types as mcp_sdk_types

from hardcover import queries as Q
from hardcover.client import (
    AuthError,
    ForbiddenError,
    GraphQLError,
    HardcoverClient,
    HardcoverError,
    QueryTimeoutError,
    RateLimitError,
)

# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_client: HardcoverClient | None = None


def _get_client() -> HardcoverClient:
    global _client
    if _client is None:
        _client = HardcoverClient()
    return _client


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


def _error(message: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=f"Error: {message}")]


def _run(query: str, variables: dict[str, Any] | None = None) -> list[types.TextContent]:
    """Execute a GraphQL query and return formatted content, handling all known errors."""
    try:
        data = _get_client().execute(query, variables)
        return _text(data)
    except AuthError as exc:
        return _error(f"Authentication failed: {exc}")
    except RateLimitError as exc:
        hint = f" Retry after {exc.retry_after}s." if exc.retry_after else ""
        return _error(f"Rate limit exceeded.{hint}")
    except ForbiddenError as exc:
        return _error(f"Forbidden: {exc}")
    except QueryTimeoutError:
        return _error("Query timed out (30s server limit). Try a more specific query.")
    except GraphQLError as exc:
        return _error(f"GraphQL error: {exc}")
    except HardcoverError as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[types.Tool] = [
    types.Tool(
        name="get_me",
        description="Get the currently authenticated Hardcover user's profile (id, username, name, book counts).",
        input_schema={"type": "object", "properties": {}, "required": []},
    ),
    types.Tool(
        name="hardcover_search",
        description=(
            "Search Hardcover for books, authors, series, users, lists, characters, "
            "publishers, or prompts. Returns rich result objects from Typesense. "
            "query_type defaults to 'book'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
                "query_type": {
                    "type": "string",
                    "description": "One of: book, author, series, user, list, character, publisher, prompt",
                    "enum": ["book", "author", "series", "user", "list", "character", "publisher", "prompt"],
                    "default": "book",
                },
                "per_page": {"type": "integer", "description": "Results per page (default 25)", "default": 25},
                "page": {"type": "integer", "description": "Page number (default 1)", "default": 1},
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="get_book_by_id",
        description="Get full book details by Hardcover book ID.",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "Hardcover book ID"}},
            "required": ["id"],
        },
    ),
    types.Tool(
        name="get_book_by_slug",
        description="Get full book details by Hardcover URL slug (e.g. 'the-name-of-the-wind').",
        input_schema={
            "type": "object",
            "properties": {"slug": {"type": "string", "description": "Book URL slug"}},
            "required": ["slug"],
        },
    ),
    types.Tool(
        name="get_editions_by_title",
        description="Get all known editions of a book by exact title match.",
        input_schema={
            "type": "object",
            "properties": {"title": {"type": "string", "description": "Exact edition title to look up"}},
            "required": ["title"],
        },
    ),
    types.Tool(
        name="get_edition_by_id",
        description="Get detailed information about a specific edition by its ID.",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "Edition ID"}},
            "required": ["id"],
        },
    ),
    types.Tool(
        name="get_editions_by_isbn",
        description="Look up an edition by ISBN-10 or ISBN-13.",
        input_schema={
            "type": "object",
            "properties": {"isbn": {"type": "string", "description": "ISBN-10 or ISBN-13 (digits only, no dashes)"}},
            "required": ["isbn"],
        },
    ),
    types.Tool(
        name="get_author_by_id",
        description="Get an author's profile by Hardcover author ID.",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "Author ID"}},
            "required": ["id"],
        },
    ),
    types.Tool(
        name="get_author_by_slug",
        description="Get an author's profile by URL slug (e.g. 'brandon-sanderson').",
        input_schema={
            "type": "object",
            "properties": {"slug": {"type": "string", "description": "Author URL slug"}},
            "required": ["slug"],
        },
    ),
    types.Tool(
        name="get_author_books",
        description="Get books written by a specific author, ordered by popularity.",
        input_schema={
            "type": "object",
            "properties": {
                "author_id": {"type": "integer", "description": "Author ID"},
                "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
                "offset": {"type": "integer", "description": "Pagination offset (default 0)", "default": 0},
            },
            "required": ["author_id"],
        },
    ),
    types.Tool(
        name="get_series_by_id",
        description="Get series metadata (name, description, book count) by series ID.",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "Series ID"}},
            "required": ["id"],
        },
    ),
    types.Tool(
        name="get_books_in_series",
        description=(
            "Get the ordered, deduplicated list of books in a series. "
            "Merges duplicates, excludes partial books and compilations."
        ),
        input_schema={
            "type": "object",
            "properties": {"series_id": {"type": "integer", "description": "Series ID"}},
            "required": ["series_id"],
        },
    ),
    types.Tool(
        name="get_my_library",
        description="Get the authenticated user's full library (all statuses), paginated.",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results (default 25)", "default": 25},
                "offset": {"type": "integer", "description": "Pagination offset (default 0)", "default": 0},
            },
            "required": [],
        },
    ),
    types.Tool(
        name="get_library_by_status",
        description=(
            "Get the authenticated user's books filtered by reading status. "
            "Status IDs: 1=Want to Read, 2=Currently Reading, 3=Read, 4=Did Not Finish, 5=Owned."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "status_id": {
                    "type": "integer",
                    "description": "1=Want to Read, 2=Currently Reading, 3=Read, 4=DNF, 5=Owned",
                    "enum": [1, 2, 3, 4, 5],
                },
                "limit": {"type": "integer", "description": "Max results (default 25)", "default": 25},
                "offset": {"type": "integer", "description": "Pagination offset (default 0)", "default": 0},
            },
            "required": ["status_id"],
        },
    ),
    types.Tool(
        name="get_reading_progress",
        description="Get all books currently being read with their page-level progress.",
        input_schema={"type": "object", "properties": {}, "required": []},
    ),
    types.Tool(
        name="get_user_book",
        description="Get the authenticated user's relationship with a specific book (status, rating, review, read sessions).",
        input_schema={
            "type": "object",
            "properties": {"book_id": {"type": "integer", "description": "Hardcover book ID"}},
            "required": ["book_id"],
        },
    ),
    types.Tool(
        name="get_my_reading_journal",
        description="Get reading journal entries and session history for a specific book.",
        input_schema={
            "type": "object",
            "properties": {"book_id": {"type": "integer", "description": "Hardcover book ID"}},
            "required": ["book_id"],
        },
    ),
    types.Tool(
        name="get_user_library",
        description=(
            "Get another user's library filtered by reading status. "
            "Status IDs: 1=Want to Read, 2=Currently Reading, 3=Read, 4=Did Not Finish, 5=Owned."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "Hardcover user ID"},
                "status_id": {
                    "type": "integer",
                    "description": "1=Want to Read, 2=Currently Reading, 3=Read, 4=DNF, 5=Owned",
                    "enum": [1, 2, 3, 4, 5],
                },
                "limit": {"type": "integer", "description": "Max results (default 25)", "default": 25},
                "offset": {"type": "integer", "description": "Pagination offset (default 0)", "default": 0},
            },
            "required": ["user_id", "status_id"],
        },
    ),
    types.Tool(
        name="get_list_by_id",
        description="Get a Hardcover list's details and its books (up to 50 books).",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "List ID"}},
            "required": ["id"],
        },
    ),
    # ── Reading stats ────────────────────────────────────────────────────
    types.Tool(
        name="get_reading_stats",
        description=(
            "Get reading statistics: total books read all-time AND since an optional "
            "date (e.g. '2026-01-01' for this year, '2026-08-01' for this month), "
            "plus average rating for each window. Requires the user's numeric ID "
            "(use get_me to find it)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "Hardcover numeric user ID"},
                "since": {
                    "type": "string",
                    "description": "Optional YYYY-MM-DD start date to filter the 'filtered' count (e.g. 2026-01-01)",
                },
            },
            "required": ["user_id"],
        },
    ),
    types.Tool(
        name="get_books_read_between",
        description="List books marked as Read with a finish date between two dates, ordered most-recent first.",
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "Hardcover numeric user ID"},
                "since": {"type": "string", "description": "Start date YYYY-MM-DD (inclusive)"},
                "until": {"type": "string", "description": "End date YYYY-MM-DD (inclusive)"},
                "limit": {"type": "integer", "description": "Max results (default 25)", "default": 25},
                "offset": {"type": "integer", "description": "Pagination offset (default 0)", "default": 0},
            },
            "required": ["user_id", "since", "until"],
        },
    ),
    # ── Goals ────────────────────────────────────────────────────────────
    types.Tool(
        name="get_my_goals",
        description="Get the authenticated user's reading goals (progress, target, state, dates).",
        input_schema={"type": "object", "properties": {}, "required": []},
    ),
    # ── Activities ───────────────────────────────────────────────────────
    types.Tool(
        name="get_my_activities",
        description=(
            "Get a user's recent activity feed (books added, rated, reviewed, "
            "goals, lists). Requires the user's numeric ID."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "Hardcover numeric user ID"},
                "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
                "offset": {"type": "integer", "description": "Pagination offset (default 0)", "default": 0},
            },
            "required": ["user_id"],
        },
    ),
    types.Tool(
        name="get_book_activities",
        description="Get recent user activity for a specific book (ratings, reviews, status changes).",
        input_schema={
            "type": "object",
            "properties": {
                "book_id": {"type": "integer", "description": "Hardcover book ID"},
                "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
                "offset": {"type": "integer", "description": "Pagination offset (default 0)", "default": 0},
            },
            "required": ["book_id"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Core dispatch — pure function, easy to unit-test directly
# ---------------------------------------------------------------------------


def _dispatch(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    match name:
        case "get_me":
            return _run(Q.ME_FULL)

        case "hardcover_search":
            return _run(Q.SEARCH, {
                "query": arguments["query"],
                "query_type": arguments.get("query_type", "book"),
                "per_page": arguments.get("per_page", 25),
                "page": arguments.get("page", 1),
            })

        case "get_book_by_id":
            return _run(Q.GET_BOOK_BY_ID, {"id": arguments["id"]})

        case "get_book_by_slug":
            return _run(Q.GET_BOOK_BY_SLUG, {"slug": arguments["slug"]})

        case "get_editions_by_title":
            return _run(Q.GET_EDITIONS_BY_TITLE, {"title": arguments["title"]})

        case "get_edition_by_id":
            return _run(Q.GET_EDITION_BY_ID, {"id": arguments["id"]})

        case "get_editions_by_isbn":
            return _run(Q.GET_EDITIONS_BY_ISBN, {"isbn": arguments["isbn"]})

        case "get_author_by_id":
            return _run(Q.GET_AUTHOR_BY_ID, {"id": arguments["id"]})

        case "get_author_by_slug":
            return _run(Q.GET_AUTHOR_BY_SLUG, {"slug": arguments["slug"]})

        case "get_author_books":
            return _run(Q.GET_AUTHOR_BOOKS, {
                "author_id": arguments["author_id"],
                "limit": arguments.get("limit", 20),
                "offset": arguments.get("offset", 0),
            })

        case "get_series_by_id":
            return _run(Q.GET_SERIES_BY_ID, {"id": arguments["id"]})

        case "get_books_in_series":
            return _run(Q.GET_BOOKS_IN_SERIES, {"series_id": arguments["series_id"]})

        case "get_my_library":
            return _run(Q.GET_MY_LIBRARY, {
                "limit": arguments.get("limit", 25),
                "offset": arguments.get("offset", 0),
            })

        case "get_library_by_status":
            return _run(Q.GET_LIBRARY_BY_STATUS, {
                "status_id": arguments["status_id"],
                "limit": arguments.get("limit", 25),
                "offset": arguments.get("offset", 0),
            })

        case "get_reading_progress":
            return _run(Q.GET_READING_PROGRESS)

        case "get_user_book":
            return _run(Q.GET_USER_BOOK, {"book_id": arguments["book_id"]})

        case "get_my_reading_journal":
            return _run(Q.GET_MY_READING_JOURNAL, {"book_id": arguments["book_id"]})

        case "get_user_library":
            return _run(Q.GET_USER_LIBRARY_BY_STATUS, {
                "user_id": arguments["user_id"],
                "status_id": arguments["status_id"],
                "limit": arguments.get("limit", 25),
                "offset": arguments.get("offset", 0),
            })

        case "get_list_by_id":
            return _run(Q.GET_LIST_BY_ID, {"id": arguments["id"]})

        case "get_reading_stats":
            if arguments.get("since"):
                return _run(Q.GET_READING_STATS, {
                    "user_id": arguments["user_id"],
                    "since": arguments["since"],
                })
            return _run(Q.GET_READING_STATS_ALL_TIME, {
                "user_id": arguments["user_id"],
            })

        case "get_books_read_between":
            return _run(Q.GET_BOOKS_READ_BETWEEN, {
                "user_id": arguments["user_id"],
                "since": arguments["since"],
                "until": arguments["until"],
                "limit": arguments.get("limit", 25),
                "offset": arguments.get("offset", 0),
            })

        case "get_my_goals":
            return _run(Q.GET_MY_GOALS)

        case "get_my_activities":
            return _run(Q.GET_MY_ACTIVITIES, {
                "user_id": arguments["user_id"],
                "limit": arguments.get("limit", 20),
                "offset": arguments.get("offset", 0),
            })

        case "get_book_activities":
            return _run(Q.GET_BOOK_ACTIVITIES, {
                "book_id": arguments["book_id"],
                "limit": arguments.get("limit", 20),
                "offset": arguments.get("offset", 0),
            })

        case _:
            return _error(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# MCP handler functions (wired into Server via constructor)
# ---------------------------------------------------------------------------
# Tool filtering via environment variables
# ---------------------------------------------------------------------------
#   HARDCOVER_ENABLED_TOOLS  - comma-separated allowlist; if set, ONLY these register
#   HARDCOVER_DISABLED_TOOLS - comma-separated denylist; ignored if an allowlist is set
# Tool names are case-insensitive.

def _parse_tool_set(value: str | None) -> set[str]:
    if not value:
        return set()
    return {name.strip().lower() for name in value.split(",") if name.strip()}

_enabled_tools = _parse_tool_set(os.getenv("HARDCOVER_ENABLED_TOOLS"))
_disabled_tools = _parse_tool_set(os.getenv("HARDCOVER_DISABLED_TOOLS"))

def _filter_tools(tools: list[types.Tool]) -> list[types.Tool]:
    if _enabled_tools:
        return [t for t in tools if t.name.lower() in _enabled_tools]
    if _disabled_tools:
        return [t for t in tools if t.name.lower() not in _disabled_tools]
    return tools

FILTERED_TOOLS = _filter_tools(TOOLS)

# ---------------------------------------------------------------------------


def build_server() -> Server:
    """Create and return the configured MCP server instance."""
    server = Server("hardcover-mcp")

    @server.list_tools()
    async def handle_list_tools() -> list[mcp_sdk_types.Tool]:
        # Convert from mcp_types.Tool to mcp.types.Tool (different Pydantic models)
        return [
            mcp_sdk_types.Tool(
                name=t.name,
                description=t.description,
                inputSchema=t.input_schema,
            )
            for t in FILTERED_TOOLS
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[mcp_sdk_types.TextContent | mcp_sdk_types.ImageContent | mcp_sdk_types.EmbeddedResource]:
        results = _dispatch(name, arguments or {})
        # Convert from mcp_types content to mcp.types content
        converted = []
        for r in results:
            if hasattr(r, 'text'):
                converted.append(mcp_sdk_types.TextContent(type="text", text=r.text))
            else:
                converted.append(r)
        return converted

    return server


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import asyncio

    async def _run_server() -> None:
        server = build_server()
        try:
            async with stdio_server() as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
        except Exception as exc:
            print(f"Server error: {exc}", file=sys.stderr)
            sys.exit(1)

    asyncio.run(_run_server())


if __name__ == "__main__":
    main()
