"""Tests for bot/trust_ledger/data_quality.py (REQ-1001 Failure Recovery).

data_quality_events has existed in ledger/schema.sql since Phase 0 but had no
writer -- these tests prove the writer works and that the two real failure
points that now use it (account compliance check, position-fetch ambiguity)
log correctly without ever raising into the caller.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import ledger.db as ledger_db  # noqa: E402
import bot._main_db as main_db  # noqa: E402
import bot.trust_ledger.data_quality as dq  # noqa: E402
from bot._main_trust_decisions import record_data_quality_safe  # noqa: E402
from bot._main_reconcile import _fetch_positions_for_reconcile  # noqa: E402
from bot._main_positions import _upsert_position_state  # noqa: E402


@pytest.fixture
def trust_conn():
    con = ledger_db.init_db(":memory:")
    yield con
    con.close()


@pytest.fixture
def trades_conn():
    con = main_db.init_db(":memory:")
    yield con
    con.close()


def _rows(trust_conn):
    return trust_conn.execute(
        "SELECT event_id, source, status, detail FROM data_quality_events ORDER BY timestamp"
    ).fetchall()


class _CountingClient:
    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    def get_positions(self):
        self.calls += 1
        return self._results[min(self.calls, len(self._results)) - 1]


def test_record_data_quality_event_writes_row(trust_conn):
    dq.record_data_quality_event(trust_conn, "alpaca_account", "DOWN", "test detail")
    rows = _rows(trust_conn)
    assert len(rows) == 1
    event_id, source, status, detail = rows[0]
    assert event_id.startswith("DQ-")
    assert source == "alpaca_account"
    assert status == "DOWN"
    assert detail == "test detail"


def test_record_data_quality_event_rejects_invalid_status(trust_conn):
    with pytest.raises(ValueError):
        dq.record_data_quality_event(trust_conn, "alpaca_account", "SOMEWHAT_OK")


def test_record_data_quality_safe_never_raises(trust_conn, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("db exploded")
    monkeypatch.setattr(dq, "record_data_quality_event", _boom)
    record_data_quality_safe(trust_conn, "alpaca_account", "DOWN", "detail")  # must not raise


def test_record_data_quality_safe_writes_through(trust_conn):
    record_data_quality_safe(trust_conn, "alpaca_account", "DEGRADED", "compliance check raised: boom")
    rows = _rows(trust_conn)
    assert len(rows) == 1
    assert rows[0][1:3] == ("alpaca_account", "DEGRADED")


def test_fetch_positions_logs_nothing_when_healthy(trades_conn, trust_conn, monkeypatch):
    monkeypatch.setattr("bot._main_reconcile.time.sleep", lambda s: None)
    client = _CountingClient([{"AAPL": object()}])
    _fetch_positions_for_reconcile(client, trades_conn, trust_conn)
    assert _rows(trust_conn) == []


def test_fetch_positions_logs_degraded_on_recovery(trades_conn, trust_conn, monkeypatch):
    monkeypatch.setattr("bot._main_reconcile.time.sleep", lambda s: None)
    _upsert_position_state(trades_conn, "AAPL", 100.0, 100.0, 1.0, 5.0)
    client = _CountingClient([{}, {"AAPL": object()}])
    result = _fetch_positions_for_reconcile(client, trades_conn, trust_conn)
    assert "AAPL" in result
    rows = _rows(trust_conn)
    assert len(rows) == 1
    assert rows[0][1:3] == ("alpaca_positions", "DEGRADED")


def test_fetch_positions_logs_degraded_on_exhausted_reverify(trades_conn, trust_conn, monkeypatch):
    monkeypatch.setattr("bot._main_reconcile.time.sleep", lambda s: None)
    _upsert_position_state(trades_conn, "AAPL", 100.0, 100.0, 1.0, 5.0)
    client = _CountingClient([{}])  # stays empty every call
    result = _fetch_positions_for_reconcile(client, trades_conn, trust_conn)
    assert result == {}
    rows = _rows(trust_conn)
    assert len(rows) == 1
    assert rows[0][1:3] == ("alpaca_positions", "DEGRADED")
    assert "genuinely closed" in rows[0][3]


def test_fetch_positions_without_trust_conn_skips_logging(trades_conn, monkeypatch):
    """trust_conn=None (the default) must not attempt any ledger write."""
    monkeypatch.setattr("bot._main_reconcile.time.sleep", lambda s: None)
    _upsert_position_state(trades_conn, "AAPL", 100.0, 100.0, 1.0, 5.0)
    client = _CountingClient([{}])
    result = _fetch_positions_for_reconcile(client, trades_conn)
    assert result == {}
