"""Tests for database.trade_journal."""
import sqlite3
import pytest
from database.trade_journal import (
    _ensure_table, open_entry, close_entry, query_pattern_stats, recent_entries,
    _auto_lesson,
)


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    _ensure_table(con)
    return con


def test_open_entry_creates_row(db):
    jid = open_entry(db, "AAPL", 42, "XGB 0.65 entry", {"xgb_prob": 0.65}, 0.65, ["Trending"])
    assert jid is not None and jid > 0
    row = db.execute("SELECT symbol, buy_trade_id, entry_confidence, closed_at FROM trade_journal WHERE id=?", (jid,)).fetchone()
    assert row[0] == "AAPL"
    assert row[1] == 42
    assert abs(row[2] - 0.65) < 1e-6
    assert row[3] is None  # open


def test_close_entry_updates_existing(db):
    jid = open_entry(db, "MSFT", 1, "reason", {}, 0.70, [])
    close_entry(db, "MSFT", 2, "take-profit", 0.08, 5)
    row = db.execute(
        "SELECT exit_reason, outcome_pct, holding_days, lesson, closed_at FROM trade_journal WHERE id=?",
        (jid,),
    ).fetchone()
    assert row[0] == "take-profit"
    assert abs(row[1] - 0.08) < 1e-6
    assert row[2] == 5
    assert "Take-profit" in row[3]
    assert row[4] is not None


def test_close_entry_orphan_creates_row(db):
    # No open entry — should still log a closed record
    close_entry(db, "TSLA", 99, "stop-loss", -0.04, 2)
    rows = db.execute("SELECT symbol, exit_reason FROM trade_journal WHERE symbol='TSLA'").fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "stop-loss"


def test_close_entry_picks_most_recent_open(db):
    jid1 = open_entry(db, "GOOG", 10, "first", {}, 0.60, [])
    jid2 = open_entry(db, "GOOG", 20, "second", {}, 0.70, [])
    close_entry(db, "GOOG", 30, "signal", 0.05, 7)
    row1 = db.execute("SELECT closed_at FROM trade_journal WHERE id=?", (jid1,)).fetchone()
    row2 = db.execute("SELECT closed_at FROM trade_journal WHERE id=?", (jid2,)).fetchone()
    assert row1[0] is None      # first entry still open
    assert row2[0] is not None  # second (most recent) was closed


def test_query_pattern_stats_empty(db):
    assert query_pattern_stats(db) == []


def test_query_pattern_stats_aggregates(db):
    open_entry(db, "AAPL", 1, "r", {}, 0.6, [])
    close_entry(db, "AAPL", 2, "take-profit", 0.07, 5)
    open_entry(db, "MSFT", 3, "r", {}, 0.55, [])
    close_entry(db, "MSFT", 4, "stop-loss", -0.04, 3)
    open_entry(db, "TSLA", 5, "r", {}, 0.62, [])
    close_entry(db, "TSLA", 6, "take-profit", 0.09, 8)
    stats = query_pattern_stats(db)
    tp = next((s for s in stats if s["exit_reason"] == "take-profit"), None)
    sl = next((s for s in stats if s["exit_reason"] == "stop-loss"), None)
    assert tp is not None and tp["n"] == 2 and tp["wins"] == 2
    assert sl is not None and sl["n"] == 1 and sl["wins"] == 0


def test_recent_entries(db):
    open_entry(db, "AAPL", 1, "reason", {"xgb_prob": 0.6}, 0.6, ["Trending"])
    close_entry(db, "AAPL", 2, "signal", 0.03, 4)
    rows = recent_entries(db, limit=10)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["exit_reason"] == "signal"


@pytest.mark.parametrize("reason,pct,days,expected_fragment", [
    ("take-profit",   0.08,  5,  "Take-profit"),
    ("stop-loss",    -0.04,  1,  "quickly"),
    ("stop-loss",    -0.04, 20,  "Long hold"),
    ("stop-loss",    -0.04,  7,  "Stop-loss triggered"),
    ("trailing-stop", 0.02,  6,  "gain"),
    ("time-exit",     0.01, 22,  "could have held"),
    ("time-exit",    -0.01, 22,  "did not develop"),
    ("signal",        0.05,  9,  "correctly"),
    ("signal",       -0.03,  9,  "false positive"),
])
def test_auto_lesson(reason, pct, days, expected_fragment):
    lesson = _auto_lesson(reason, pct, days)
    assert expected_fragment in lesson
