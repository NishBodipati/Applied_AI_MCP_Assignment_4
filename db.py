"""SQLite persistence for the job application tracker.

All queries use parameterized placeholders (``?``) instead of string
interpolation, so user-supplied values are always passed as bound
parameters and can never change the shape of the executed SQL. This
is what blocks SQL injection -- see demo_exploits.py for a live check.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "applications.db"

ALLOWED_STATUSES = {"applied", "interview", "offer", "rejected", "withdrawn"}


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                role TEXT NOT NULL,
                date_applied TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


def table_exists() -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='applications'"
        ).fetchone()
        return row is not None


def insert_application(company: str, role: str, date_applied: str, status: str, notes: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO applications (company, role, date_applied, status, notes) VALUES (?, ?, ?, ?, ?)",
            (company, role, date_applied, status, notes),
        )
        return cur.lastrowid


def count_rows() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]


def fetch_stats(status_filter: str | None):
    """Return (matching_count, status_breakdown, matching_rows).

    ``status_filter`` is passed as a bound parameter, never concatenated
    into the SQL string, so it can only ever match a literal status value
    -- it cannot alter the query's structure.
    """
    with _connect() as conn:
        breakdown = dict(conn.execute("SELECT status, COUNT(*) FROM applications GROUP BY status").fetchall())

        if status_filter is None:
            rows = conn.execute("SELECT company, role, date_applied, status FROM applications").fetchall()
        else:
            rows = conn.execute(
                "SELECT company, role, date_applied, status FROM applications WHERE status = ?",
                (status_filter,),
            ).fetchall()

    return len(rows), breakdown, rows
