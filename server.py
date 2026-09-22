"""Job Application Tracker MCP server.

Domain: Data Analysis -- tracks job applications in a local SQLite
database and exposes a statistical-analysis tool over that data.

Tools:
    add_application         -- record a new application (write path)
    get_application_stats   -- aggregate / filter application data (analysis path)
Prompt:
    job_search_review       -- prompt template that guides the LLM through
                                reviewing the stats and suggesting next actions

Best practices implemented (see auth.py / errors.py / db.py for detail,
and demo_exploits.py for exploit checks that prove each one holds):
    1. Input sanitization  -- parameterized SQL queries + whitelisted/validated
                               fields, so injected SQL or bad values can't do damage.
    2. Error disclosure     -- every tool call is wrapped so only a fixed,
                               generic message ever reaches the caller; full
                               detail goes to server.log only.

MCP server scaffolding (server class, @mcp.tool()/@mcp.prompt() decorators,
mcp.run()) follows the pattern in the official MCP Python SDK README:
https://github.com/modelcontextprotocol/python-sdk
"""
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

import db
import errors
from auth import is_valid

load_dotenv(Path(__file__).parent / ".env")

API_KEY = os.getenv("APP_API_KEY")
if not API_KEY:
    raise RuntimeError(
        "APP_API_KEY is not set. Copy .env.example to .env and set a value before starting the server."
    )

db.init_db()

# The instructions string is sent to the client as part of server metadata,
# so the LLM automatically knows which key to pass -- the user never has to
# paste a secret into chat.
mcp = MCPServer(
    "job-application-tracker",
    instructions=(
        "This server tracks job applications. Every tool call requires an "
        f"api_key argument; always pass exactly this value: {API_KEY}"
    ),
)


def _unauthorized() -> dict:
    return {"success": False, "error": errors.UNAUTHORIZED_ERROR}


@mcp.tool()
def add_application(
    api_key: str,
    company: str,
    role: str,
    date_applied: str,
    status: str = "applied",
    notes: str = "",
) -> dict:
    """Record a new job application.

    Args:
        api_key: server access token (see server instructions).
        company: company name.
        role: job title / role applied for.
        date_applied: date in YYYY-MM-DD format.
        status: one of applied, interview, offer, rejected, withdrawn.
        notes: free-text notes.
    """
    if not is_valid(api_key):
        return _unauthorized()

    try:
        if status not in db.ALLOWED_STATUSES:
            return {
                "success": False,
                "error": f"status must be one of: {', '.join(sorted(db.ALLOWED_STATUSES))}",
            }
        try:
            datetime.strptime(date_applied, "%Y-%m-%d")
        except ValueError:
            return {"success": False, "error": "date_applied must be in YYYY-MM-DD format"}

        if not company.strip() or not role.strip():
            return {"success": False, "error": "company and role are required"}

        new_id = db.insert_application(company.strip(), role.strip(), date_applied, status, notes.strip())
        return {"success": True, "id": new_id}
    except Exception as exc:  # noqa: BLE001 -- deliberate: never leak internals to the caller
        return {"success": False, "error": errors.log_and_hide(exc, "add_application")}


@mcp.tool()
def get_application_stats(api_key: str, status_filter: str | None = None) -> dict:
    """Compute summary statistics over stored job applications.

    Args:
        api_key: server access token (see server instructions).
        status_filter: optional status to filter the returned application
            list by. It does not need to be one of the known statuses --
            an unrecognized value simply matches zero rows (see
            demo_exploits.py for why this is safe against SQL injection).
    """
    if not is_valid(api_key):
        return _unauthorized()

    try:
        matching_count, breakdown, rows = db.fetch_stats(status_filter)
        grand_total = db.count_rows()
        responses = breakdown.get("interview", 0) + breakdown.get("offer", 0)
        response_rate = round(responses / grand_total * 100, 1) if grand_total else 0.0

        return {
            "success": True,
            "grand_total_applications": grand_total,
            "status_breakdown": breakdown,
            "response_rate_percent": response_rate,
            "matching_filter": status_filter,
            "matching_count": matching_count,
            "matching_applications": [
                {"company": c, "role": r, "date_applied": d, "status": s} for c, r, d, s in rows
            ],
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": errors.log_and_hide(exc, "get_application_stats")}


@mcp.prompt()
def job_search_review(focus_area: str = "overall") -> str:
    """Prompt template: guide the LLM through reviewing job-search stats.

    Args:
        focus_area: what to focus the review on, e.g. "overall", "response
            rate", "stale applications".
    """
    return (
        "Call get_application_stats to pull my current job application data, "
        f"then review it with a focus on: {focus_area}.\n\n"
        "In your response:\n"
        "1. Summarize the key numbers (total applications, breakdown by status, response rate).\n"
        "2. Call out any concerning patterns (e.g. low response rate, too few applications, "
        "many stuck in 'applied' status).\n"
        "3. Suggest two or three concrete next actions I should take this week."
    )


if __name__ == "__main__":
    mcp.run()
