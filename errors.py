"""Central error handling that keeps tool responses free of internal detail.

Full exception detail (stack trace, file paths, SQL text, exception
type) is written to a local log file for debugging. The caller only
ever sees a short, fixed, generic message. This is the "Error
Disclosure" best practice: an attacker who deliberately triggers an
error learns nothing about our schema, file layout, or query
structure -- see demo_exploits.py for a live check.
"""
import logging
from pathlib import Path

LOG_PATH = Path(__file__).parent / "server.log"

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("job_tracker")

GENERIC_ERROR = "Request could not be completed. Please check your input and try again."
UNAUTHORIZED_ERROR = "Unauthorized."


def log_and_hide(exc: Exception, context: str) -> str:
    """Log the real exception (with traceback) server-side, return a generic message."""
    logger.exception("Error in %s", context)
    return GENERIC_ERROR
