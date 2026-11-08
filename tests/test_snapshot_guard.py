"""Tests for the heartbeat snapshot guard (ADR-088): no snapshot may contradict the database."""
import sqlite3

import bot._main_prep as prep
import bot._main_reconcile as reconcile


class FakeClient:
    def __init__(self, reads):
        self._reads = list(reads)

    def get_positions(self):
        return self._reads.pop(0) if len(self._reads) > 1 else self._reads[0]


def _db(open_positions: bool) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE position_state (symbol TEXT PRIMARY KEY)")
    if open_positions:
        con.execute("INSERT INTO position_state VALUES ('AAPL')")
    return con


def _recorder(monkeypatch):
    written = []
    monkeypatch.setattr(prep, "_record_snapshot", lambda con, v, c, n: written.append((v, c, n)))
    monkeypatch.setattr(reconcile, "_RECONCILE_REVERIFY_DELAY_SECS", 0)
    return written


def test_records_when_positions_are_present(monkeypatch):
    written = _recorder(monkeypatch)
    con = _db(open_positions=True)
    ok = prep.write_heartbeat_if_consistent(con, FakeClient([{"AAPL": object()}]), {"AAPL": object()}, 100.0, 40.0)
    assert ok is True and written == [(100.0, 40.0, 1)]


def test_records_zero_positions_when_database_expects_none(monkeypatch):
    written = _recorder(monkeypatch)
    con = _db(open_positions=False)
    ok = prep.write_heartbeat_if_consistent(con, FakeClient([{}]), {}, 100.0, 100.0)
    assert ok is True and written == [(100.0, 100.0, 0)]


def test_skips_when_empty_read_contradicts_database(monkeypatch):
    written = _recorder(monkeypatch)
    con = _db(open_positions=True)
    ok = prep.write_heartbeat_if_consistent(con, FakeClient([{}, {}, {}, {}]), {}, 35479.0, 35479.0)
    assert ok is False and written == []


def test_recovers_when_reverify_finds_positions(monkeypatch):
    written = _recorder(monkeypatch)
    con = _db(open_positions=True)
    client = FakeClient([{}, {"AAPL": object()}])
    ok = prep.write_heartbeat_if_consistent(con, client, {}, 100.0, 40.0)
    assert ok is True and written == [(100.0, 40.0, 1)]
