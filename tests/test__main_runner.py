"""Tests for bot/_main_runner.py. No existing test scaffold for this file
before this ADR (same "no scaffold yet" situation TD-020 already noted for
run_loop in this same file) -- these are new, narrowly scoped to the one
function this ADR touches, using mocked init_db/push_db so no real DB file
or HuggingFace upload is ever touched."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import os
os.environ.setdefault("_BOT_LOG_HANDLER_ADDED", "1")

from bot._main_runner import _do_clean_db

_ALL_TABLES = (
    "trades", "position_state", "risk_state", "portfolio_snapshots",
    "signal_log", "screener_log", "capital_pools", "capital_ledger",
)


def _seed_db(path: str) -> None:
    con = sqlite3.connect(path)
    for table in _ALL_TABLES:
        con.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, val TEXT)")
        con.execute(f"INSERT INTO {table} (val) VALUES ('x')")
    con.commit()
    con.close()


def test_clean_db_wipes_capital_pools_and_capital_ledger_too(tmp_path):
    """ADR-075: a full reset must also clear capital_pools/capital_ledger --
    before this fix, a reset Alpaca account would size its first post-reset
    trades against the stale pre-reset pool balance, since _do_clean_db's
    table list didn't include either table. _do_clean_db() closes its own
    connection internally, so this re-opens the same file afterward rather
    than querying the (by-then-closed) connection it was given."""
    db_path = str(tmp_path / "clean_db_test.db")
    _seed_db(db_path)

    with patch("bot._main_runner.init_db", return_value=sqlite3.connect(db_path)), \
         patch("bot.monitor.sync_db.push_db", return_value=True):
        _do_clean_db()

    con = sqlite3.connect(db_path)
    for table in _ALL_TABLES:
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count == 0, f"{table} was not cleared"
    con.close()
