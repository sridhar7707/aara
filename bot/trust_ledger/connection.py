"""Connection helper for the Phase 1A Trust Ledger integration.

The ledger DB is a separate SQLite file from bot/trades.db, matching Phase
0's own standalone-DB design (phase0_data_model.md Section 9) -- keeps the
hash-chained tables isolated from the dashboard's WAL contention on the
operational DB.
"""
from __future__ import annotations

import sqlite3

import ledger.db as _ledger_db

DEFAULT_LEDGER_DB_PATH = "data/trust_ledger.db"


def get_ledger_conn(db_path: str = DEFAULT_LEDGER_DB_PATH) -> sqlite3.Connection:
    """Open (creating + initializing schema if needed) the Trust Ledger DB."""
    return _ledger_db.init_db(db_path)
