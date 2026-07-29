"""data_quality_events writer -- REQ-1001 (Failure Recovery).

The table has existed in ledger/schema.sql since Phase 0 (HEALTHY / DEGRADED /
DOWN per source) but nothing wrote to it -- broker/data/DB failures were only
ever logged to loguru, with no queryable record of degradation over time.
Not part of the Group A hash chain (no record_hash/previous_record_hash
columns, not in ledger._LEDGER_TABLES) -- this is an operational health log,
not an immutable decision-evidence record, so a plain insert is correct here.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

_VALID_STATUSES = {"HEALTHY", "DEGRADED", "DOWN"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_data_quality_event(
    trust_conn: sqlite3.Connection,
    source: str,
    status: str,
    detail: str | None = None,
) -> None:
    """Append one row to data_quality_events. Insert-only, like every other
    ledger table -- callers report a status as it's observed, they don't
    update a prior row."""
    if status not in _VALID_STATUSES:
        raise ValueError(f"record_data_quality_event: status must be one of {_VALID_STATUSES}, got {status!r}")
    from bot.trust_ledger.ids import new_data_quality_event_id
    trust_conn.execute(
        "INSERT INTO data_quality_events (event_id, timestamp, source, status, detail) "
        "VALUES (?, ?, ?, ?, ?)",
        (new_data_quality_event_id(), _utc_now(), source, status, detail),
    )
    trust_conn.commit()
