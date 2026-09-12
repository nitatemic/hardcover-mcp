# hardcover-mcp

> **⚠️ Beta v0.1.2** — This is an early release. The API surface, tool names, and query structure may change. Please report issues and feedback via [GitHub Issues](https://github.com/nitatemic/hardcover-mcp/issues).

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for the [Hardcover](https://hardcover.app) API — the book-tracking platform that uses the same GraphQL API for its website, iOS, and Android apps.

Connect any MCP-compatible AI assistant (Claude Desktop, Cursor, Kiro, or any MCP client) directly to your Hardcover library, reading history, goals, and the full Hardcover book catalogue.

---

## Contents

- [Features](#features)
- [Tools Reference](#tools-reference)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Claude Desktop](#claude-desktop)
  - [Kiro CLI](#kiro-cli)
  - [Other MCP Clients](#other-mcp-clients)
- [Rate Limits & API Policy](#rate-limits--api-policy)
- [Disclaimer](#disclaimer)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- 🔍 **Search** books, authors, series, users, lists, characters, publishers, and prompts
- 📚 **Browse your library** — all statuses, filtered views, and paginated results
- 📖 **Reading progress** — currently-reading books with page-level progress
- 📊 **Reading statistics** — books read this month, this year, all time, with average ratings
- 🎯 **Reading goals** — progress, state, and target for all your goals
- 🗓️ **Books by date range** — list every book you finished between two dates
- 📓 **Reading journal** — per-book session history
- 👤 **User profiles** — your profile and other users' libraries
- 📋 **Lists** — retrieve any Hardcover list with its books
- 🏃 **Activity feed** — your recent activity and activity on specific books
- 🔖 **Editions** — look up by title, ID, or ISBN-10/13
- ✍️ **Authors** — profiles and bibliography
- 📖 **Series** — ordered, deduplicated book lists

---

## Tools Reference

### Identity

| Tool | Description |
|------|-------------|
| `get_me` | Authenticated user's profile: id, username, name, bio, location, books count, followers, flair, pro status |

### Search

| Tool | Arguments | Description |
|------|-----------|-------------|
| `hardcover_search` | `query`, `query_type?`, `per_page?`, `page?` | Search books, authors, series, users, lists, characters, publishers, or prompts |

### Books

| Tool | Arguments | Description |
|------|-----------|-------------|
| `get_book_by_id` | `id` | Full book details by Hardcover ID |
| `get_book_by_slug` | `slug` | Full book details by URL slug (e.g. `the-name-of-the-wind`) |
| `get_editions_by_title` | `title` | All editions matching an exact title |
| `get_edition_by_id` | `id` | Single edition details |
| `get_editions_by_isbn` | `isbn` | Look up edition by ISBN-10 or ISBN-13 (digits only) |

### Authors

| Tool | Arguments | Description |
|------|-----------|-------------|
| `get_author_by_id` | `id` | Author profile by ID |
| `get_author_by_slug` | `slug` | Author profile by slug (e.g. `brandon-sanderson`) |
| `get_author_books` | `author_id`, `limit?`, `offset?` | Books by an author, ordered by popularity |

### Series

| Tool | Arguments | Description |
|------|-----------|-------------|
| `get_series_by_id` | `id` | Series metadata: name, description, book count |
| `get_books_in_series` | `series_id` | Ordered, deduplicated book list — excludes partial books and compilations |

### My Library

| Tool | Arguments | Description |
|------|-----------|-------------|
| `get_my_library` | `limit?`, `offset?` | Full library, all statuses, paginated |
| `get_library_by_status` | `status_id`, `limit?`, `offset?` | Library filtered by reading status |
| `get_reading_progress` | — | Currently-reading books with page progress |
| `get_user_book` | `book_id` | Your relationship with a book: status, rating, review, read sessions |
| `get_my_reading_journal` | `book_id` | Reading journal and session history for a book |

**Status IDs:** `1` Want to Read · `2` Currently Reading · `3` Read · `4` Paused · `5` Did Not Finish · `6` Ignored

### Reading Statistics

| Tool | Arguments | Description |
|------|-----------|-------------|
| `get_reading_stats` | `user_id`, `since?` | All-time count + avg rating, and filtered count since a date (`YYYY-MM-DD`). Use `since=2026-01-01` for this year, `since=2026-08-01` for this month |
| `get_books_read_between` | `user_id`, `since`, `until`, `limit?`, `offset?` | Books finished between two dates, ordered newest first |

### Goals

| Tool | Arguments | Description |
|------|-----------|-------------|
| `get_my_goals` | — | All reading goals with progress, target, state, and dates |

### Activities

| Tool | Arguments | Description |
|------|-----------|-------------|
| `get_my_activities` | `user_id`, `limit?`, `offset?` | Your activity feed (books added, rated, reviewed, goals, lists) |
| `get_book_activities` | `book_id`, `limit?`, `offset?` | Community activity for a specific book |

### Other Users

| Tool | Arguments | Description |
|------|-----------|-------------|
| `get_user_library` | `user_id`, `status_id`, `limit?`, `offset?` | Another user's library filtered by reading status |

### Lists

| Tool | Arguments | Description |
|------|-----------|-------------|
| `get_list_by_id` | `id` | List details and its books (up to 50) |

---

## Requirements

- Python **3.10** or later
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- A **Hardcover API key** — get yours at [hardcover.app/account/api](https://hardcover.app/account/api)

---

## Installation

### With uv (recommended)

```bash
git clone https://github.com/muhyousri/hardcover-mcp
cd hardcover-mcp
uv sync
```

### With pip

```bash
git clone https://github.com/muhyousri/hardcover-mcp
cd hardcover-mcp
pip install -e .
```

### From PyPI (once published)

```bash
uv pip install hardcover-mcp
# or
pip install hardcover-mcp
```

---

## Configuration

Copy `.env.example` to `.env` and add your API key:

```bash
cp .env.example .env
```

```env
HARDCOVER_API_KEY=your_api_key_here
```

> **Keep your token private.** Your Personal Access Token has access to your Hardcover account. Never commit it to version control, share it publicly, or embed it in client-side code.

---

## Usage

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "hardcover": {
      "command": "uv",
      "args": [
        "run",
        "--with-editable",
        "/path/to/hardcover-mcp",
        "hardcover-mcp"
      ],
      "env": {
        "HARDCOVER_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

Or if installed via pip/uv into a virtualenv:

```json
{
  "mcpServers": {
    "hardcover": {
      "command": "/path/to/venv/bin/hardcover-mcp",
      "env": {
        "HARDCOVER_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

### Kiro CLI

Add to `~/.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "hardcover": {
      "command": "/path/to/uv",
      "args": [
        "run",
        "--with-editable",
        "/path/to/hardcover-mcp",
        "hardcover-mcp"
      ],
      "env": {
        "HARDCOVER_API_KEY": "your_api_key_here"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

### Other MCP Clients

Point your client at the `hardcover-mcp` entrypoint (or `python -m hardcover.server`) with `HARDCOVER_API_KEY` set in the environment. The server communicates over stdio and is compatible with any MCP 1.0+ client.

---

## Rate Limits & API Policy

> **Please read before building with this server.** Hardcover's API is free to use but has firm limits. Hitting them unexpectedly can disrupt your workflow.

### Rate Limits

| Plan | Daily | Burst | Per Minute |
|------|-------|-------|-----------|
| **Free** | 5,000 req/day | 10 req | 60 req/min |
| **Supporter** | 50,000 req/day | 15 req | 60 req/min |

- **Daily limit**: hard cap. Once reached, all requests return `429` until midnight UTC.
- **Burst limit**: how many requests you can fire back-to-back before throttling. Refills continuously at the per-minute rate.
- **Per-minute limit**: 60 req/min for all plans (token bucket).
- **Per-request limit**: a single GraphQL request may contain at most **5 top-level queries**. Exceeding this returns `403`, not `429`.
- **Personal Access Tokens** get double the burst capacity vs. legacy JWT auth on the same plan.

This MCP server surfaces `retry_after` hints when a `429` is returned, so your AI assistant can back off gracefully.

### Commercial Use

Per [Hardcover's API policy](https://docs.hardcover.app/api/getting-started#commercial-api-use):

- **User-owned data** (libraries, ratings, reviews, journal entries, lists, goals) **may not be used in commercial products** unless you are acting on behalf of a user who has explicitly granted access.
- Aggregate, anonymised data (e.g. number of Hardcover readers, average Hardcover rating) may be used commercially if credited to Hardcover.
- Images served from Hardcover are user-uploaded. If you display them publicly, you **must** have a [DMCA takedown policy](https://hardcover.app/pages/dmca).

### Prohibited Query Patterns

The following GraphQL operators are **disabled** by the API:

`_like`, `_nlike`, `_ilike`, `_niregex`, `_nregex`, `_iregex`, `_regex`, `_nsimilar`, `_similar`

### Queries must run server-side

The Hardcover API may **not** be called from a browser. Your API key must be kept in a secure server environment.

For more details see the official [Getting Started guide](https://docs.hardcover.app/api/getting-started).

---

## Disclaimer

> **This is a beta release (v0.1.2).** It is independent, community-built software and is **not** affiliated with, endorsed by, or supported by Hardcover.
>
> - The Hardcover API is itself in beta and subject to breaking changes.
> - Tool names, query structure, and response shapes in this MCP server may change between versions.
> - Use in production or commercial contexts is entirely at your own risk.
> - By using the Hardcover API via this server, you agree to [Hardcover's policies](https://hardcover.app/pages/policies).

---

## Development

```bash
git clone https://github.com/muhyousri/hardcover-mcp
cd hardcover-mcp

# Create virtualenv and install with dev deps
uv sync --extra dev
# or: pip install -e ".[dev]"

# Run tests
uv run pytest
# or: python -m pytest

# Run the server locally (needs HARDCOVER_API_KEY in environment)
HARDCOVER_API_KEY=your_key hardcover-mcp
```

### Project structure

```
hardcover-mcp/
├── hardcover/
│   ├── __init__.py
│   ├── client.py      # GraphQL HTTP client, rate-limit handling, error mapping
│   ├── queries.py     # All GraphQL query strings
│   └── server.py      # MCP server, tool definitions, dispatch
├── tests/
│   ├── conftest.py    # Shared fixtures
│   ├── test_client.py # 30 client tests (HTTP errors, rate limits, response parsing)
│   └── test_server.py # 51 server tests (tool dispatch, error formatting)
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

### Running tests

```bash
pytest                  # all tests
pytest tests/test_client.py   # client only
pytest tests/test_server.py   # server only
pytest -v               # verbose
```

---

## Contributing

Contributions are welcome. Please:

1. Open an issue first to discuss significant changes
2. Follow the existing code style
3. Add or update tests for any changed behaviour
4. Keep PRs focused — one feature or fix per PR

---

## License

MIT — see [LICENSE](LICENSE) for details.
