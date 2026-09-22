"""Access-token gate for the tracker's tools.

A real deployment of this server as a shared/remote MCP server (rather
than run locally by one user) would need to authenticate each caller.
We simulate that here with a shared-secret token loaded from ``.env``
(never hardcoded, never logged) so the same pattern -- validate a
caller-supplied credential against a server-side secret -- carries
over directly to a real deployment.
"""
import os
import secrets


def get_expected_key() -> str | None:
    return os.getenv("APP_API_KEY")


def is_valid(supplied_key: str | None) -> bool:
    expected = get_expected_key()
    if not expected or not supplied_key:
        return False
    # Constant-time comparison so a mistyped key can't be brute-forced
    # faster by timing how quickly the comparison fails.
    return secrets.compare_digest(supplied_key, expected)
