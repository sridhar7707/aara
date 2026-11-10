"""Tests for the heartbeat snapshot writer (ADR-088, revised 2026-11-08).

The value is always recorded, so the drawdown series is not biased by dropped points.
"""
import sqlite3

import bot._main_prep as prep


def _db(open_positions: int) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE position_state (symbol TEXT PRIMARY KEY)")
    for i in range(open_positions):
        con.execute("INSERT INTO position_state VALUES (?)", (f"SYM{i}",))
    return con


def _recorder(monkeypatch):
    written = []
    monkeypatch.setattr(prep, "_record_snapshot", lambda con, v, c, n: written.append((v, c, n)))
    return written


def test_records_live_count_when_positions_present(monkeypatch):
    written = _recorder(monkeypatch)
    prep.write_heartbeat_if_consistent(_db(1), None, {"AAPL": object()}, 100.0, 40.0)
    assert written == [(100.0, 40.0, 1)]


def test_records_zero_when_nothing_held_and_nothing_expected(monkeypatch):
    written = _recorder(monkeypatch)
    prep.write_heartbeat_if_consistent(_db(0), None, {}, 100.0, 100.0)
    assert written == [(100.0, 100.0, 0)]


def test_empty_read_still_records_the_value_with_database_count(monkeypatch):
    written = _recorder(monkeypatch)
    # A deep-drawdown reading must not be dropped (the quant review's point 3).
    prep.write_heartbeat_if_consistent(_db(2), None, {}, 35479.0, 35479.0)
    assert written == [(35479.0, 35479.0, 2)]


def test_never_calls_the_broker(monkeypatch):
    _recorder(monkeypatch)

    class NoCalls:
        def get_positions(self):
            raise AssertionError("snapshot writer must not re-query the broker")

    assert prep.write_heartbeat_if_consistent(_db(1), NoCalls(), {}, 90.0, 10.0) is True
