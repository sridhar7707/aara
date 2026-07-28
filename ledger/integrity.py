"""Scheduled integrity check: hash-chain verification + active_deployment_pointer
drift detection (phase0_implementation_spec.md Section 8).

Building and scheduling the actual cron/task-runner wiring is a deployment
concern outside Phase 0's scope (no UI, no capital, infrastructure only) --
this module provides the check function itself, ready to be invoked by
whatever scheduler runs it (daily is reasonable at the documented event
volume, per the implementation spec).
"""
from __future__ import annotations

import sqlite3

from ledger.ledger import rebuild_active_pointer, verify_all_chains


def get_active_pointer(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT active_manifest_id FROM active_deployment_pointer WHERE id=1").fetchone()
    return row[0] if row else None


def run_integrity_check(conn: sqlite3.Connection) -> dict:
    """Returns {"broken_chains": {table: breaks}, "pointer_drift": bool,
    "rebuilt_pointer": str|None, "stored_pointer": str|None}.

    A broken chain is never auto-repaired -- it's evidence something
    bypassed the application layer (direct DB edit, restore from a stale
    backup, disk corruption). The correct response is to halt and
    investigate, which is why this function only reports, never patches.
    """
    results = verify_all_chains(conn)
    broken = {table: breaks for table, breaks in results.items() if breaks}

    rebuilt = rebuild_active_pointer(conn)
    stored = get_active_pointer(conn)

    return {
        "broken_chains": broken,
        "pointer_drift": rebuilt != stored,
        "rebuilt_pointer": rebuilt,
        "stored_pointer": stored,
    }
