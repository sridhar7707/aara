"""Connection + schema loading for the Phase 0 ledger database.

Standalone by design (Section 9 of phase0_data_model.md): its own SQLite
file, no import dependency on bot/ or database/services/decision_service.py,
so Phase 0 can be built and tested in isolation before anything wires into
it. Supersedes decision_log at the Phase 1A cutover, not before.
"""
from __future__ import annotations

import os
import sqlite3

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_conn(db_path: str) -> sqlite3.Connection:
    """New connection with foreign keys enforced. Caller owns lifecycle
    (close it, or use as a context manager via contextlib.closing)."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Load schema.sql. Uses executescript() rather than a naive split on
    ';' -- the append-only triggers' BEGIN...END bodies contain their own
    internal semicolons, which a split-and-execute-one-statement-at-a-time
    loader would cut apart into invalid fragments."""
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def init_db(db_path: str) -> sqlite3.Connection:
    """Open (creating if needed) and fully initialize a ledger database."""
    conn = get_conn(db_path)
    init_schema(conn)
    return conn
