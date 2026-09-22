# Job Application Tracker MCP Server

An MCP (Model Context Protocol) server that tracks job applications in a
local SQLite database and exposes statistical analysis over that data to
any MCP client (e.g. Claude Desktop).

**Domain:** Data Analysis (database queries + statistical analysis).

## What it exposes

| Type | Name | Purpose |
|---|---|---|
| Tool | `add_application` | Record a new job application (company, role, date, status, notes). |
| Tool | `get_application_stats` | Compute totals, a status breakdown, response rate, and an optional filtered list. |
| Prompt | `job_search_review` | Prompt template that guides the LLM to pull the stats and give a structured progress review. |

Both tools require an `api_key` argument, described below.

## Project layout

```
server.py          MCP server: tool/prompt definitions, wiring
db.py              SQLite persistence (parameterized queries only)
auth.py            Shared-secret access-token check
errors.py          Central error handling / logging (sanitized responses)
demo_exploits.py   Exploit checks for the two best practices (see below)
requirements.txt
.env.example       Template for the required secret
claude_desktop_config.json   Example Claude Desktop MCP config
data/              SQLite DB file (created at runtime, gitignored)
server.log         Full error/exception log (created at runtime, gitignored)
```

## Setup

Requires Python 3.10+. This project uses [`uv`](https://github.com/astral-sh/uv)
for the virtual environment.

```bash
cd Apllied_AI_MCP
uv venv                       # creates .venv (skip if it already exists)
uv pip install -r requirements.txt

cp .env.example .env
python -c "import secrets; print(secrets.token_hex(16))"   # generate a token
# paste the generated token into .env as APP_API_KEY=...
```

Run the server directly (for local testing over stdio):

```bash
.venv/bin/python server.py
```

It will block waiting for an MCP client on stdio -- that's expected; connect
a client (see below) rather than running it standalone in a terminal.

### Run the exploit checks

```bash
.venv/bin/python demo_exploits.py
```

This proves both best practices (see below) actually hold, and exits
non-zero if either one is broken.

## Secret management

The server requires a single secret, `APP_API_KEY`, loaded from a local
`.env` file via `python-dotenv` and `pathlib` (never `os.environ` set at
the system level, and never hardcoded). `.env` is listed in `.gitignore`
and is never committed; `.env.example` documents the variable without a
real value. The server refuses to start if `APP_API_KEY` is missing.

## Authentication

Both tools take an `api_key` parameter and check it against `APP_API_KEY`
using a constant-time comparison (`secrets.compare_digest`, in `auth.py`)
before doing anything else. This simulates how you'd gate access if this
server were deployed as a shared/remote MCP server instead of run locally
by a single user: every caller has to present a valid credential, and the
credential is never hardcoded in source. The server's `instructions` field
(set in `server.py` when constructing `MCPServer(...)`) tells the connecting
LLM which key to pass, so a human never has to paste it into chat.

## Best practices (Part 2A)

### 1. Input sanitization -- SQL injection prevention

All database access goes through `db.py`, and every query uses `sqlite3`
parameter placeholders (`?`) with values passed as a bound-parameter tuple,
never string-interpolated into the SQL text. Additionally, `status` values
on `add_application` are validated against a fixed whitelist
(`db.ALLOWED_STATUSES`) and `date_applied` is validated with
`datetime.strptime`.

**Exploit:** `demo_exploits.py::demo_sql_injection` calls
`get_application_stats` with `status_filter = "x'; DROP TABLE applications; --"`.
Because the value is bound as a parameter, SQLite treats the whole string as
a literal value to match against the `status` column -- it can't terminate
the query or inject a second statement. The check asserts the table still
exists, the row count is unchanged, and the payload matches zero rows.

### 2. Error disclosure -- generic error messages

Every tool body is wrapped in `try/except Exception`. On failure,
`errors.log_and_hide()` logs the full exception (with traceback, file paths,
and line numbers) to `server.log` and returns a single fixed string,
`"Request could not be completed. Please check your input and try again."`,
to the caller. Authentication failures similarly return a fixed
`"Unauthorized."` rather than saying *why* the key was rejected.

**Exploit:** `demo_exploits.py::demo_error_disclosure` triggers a real crash
(passing a non-string `company`, which fails deep inside `add_application`)
and captures, for comparison, what a raw uncaught exception at the DB layer
would reveal (absolute file paths, line numbers, the SQLite exception type).
The check asserts none of that appears anywhere in the tool's actual
response -- only the fixed generic message does.

## Claude Desktop configuration

See [`claude_desktop_config.json`](./claude_desktop_config.json). Copy its
contents into your Claude Desktop config (`~/Library/Application
Support/Claude/claude_desktop_config.json` on macOS), adjusting the paths
if your checkout lives somewhere other than
`/Users/nishithabodipati/Apllied_AI_MCP`. No secret is stored in this file
-- the server reads `APP_API_KEY` from its own local `.env` at startup.
Restart Claude Desktop after editing the config.

## Code citations

The MCP server scaffolding (`MCPServer` class construction, `@mcp.tool()`
and `@mcp.prompt()` decorators, `mcp.run()`) follows the pattern shown in
the official MCP Python SDK README and example servers:
- https://github.com/modelcontextprotocol/python-sdk
- https://github.com/modelcontextprotocol/servers

All business logic (SQLite schema/queries, auth check, error wrapping,
tool/prompt bodies) is original to this project.
