"""Tests for bot/_main_signals.py: signal_history table + outcome resolution."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import bot._main_signals as sig


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    sig.init_signal_history(c)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _stub_telegram(monkeypatch):
    sent = []
    monkeypatch.setattr(sig.tg, "_send", lambda msg: sent.append(msg))
    return sent


def _meta(**overrides):
    m = {
        "entry_price": 100.0, "stop_price": 95.0, "target_price": 115.0,
        "rr_ratio": 3.0, "setup_type": "breakout_pullback",
        "volume_ratio": 1.8, "spy_today_pct": 0.004,
    }
    m.update(overrides)
    return m


def test_init_signal_history_creates_empty_table(con):
    rows = con.execute("SELECT * FROM signal_history").fetchall()
    assert rows == []


def test_record_signal_inserts_row_with_pending_outcome(con):
    sig.record_signal(con, "AAPL", _meta(), xgb_prob=0.7, lstm_prob=0.6, ensemble_score=0.65, macro_score=0.5)
    row = con.execute(
        "SELECT symbol, entry_price, stop_price, target_price, rr_ratio, setup_type, "
        "xgb_prob, lstm_prob, ensemble_score, macro_score, outcome FROM signal_history"
    ).fetchone()
    assert row == ("AAPL", 100.0, 95.0, 115.0, 3.0, "breakout_pullback", 0.7, 0.6, 0.65, 0.5, "pending")


def test_record_signal_sends_telegram_alert_with_key_fields(con, _stub_telegram):
    sig.record_signal(con, "AAPL", _meta(), xgb_prob=0.7, lstm_prob=0.6, ensemble_score=0.65, macro_score=0.5)
    assert len(_stub_telegram) == 1
    msg = _stub_telegram[0]
    assert "AAPL" in msg
    assert "$100.00" in msg
    assert "$95.00" in msg
    assert "$115.00" in msg
    assert "Breakout Pullback" in msg  # setup_type underscore->space, title-cased


def test_update_signal_outcomes_resolves_target_hit(con):
    sig.record_signal(con, "AAPL", _meta(), xgb_prob=0.7, lstm_prob=0.6, ensemble_score=0.65, macro_score=0.5)
    sig.update_signal_outcomes(con, {"AAPL": 120.0})
    outcome, price, pct = con.execute(
        "SELECT outcome, outcome_price, outcome_pct FROM signal_history WHERE symbol='AAPL'"
    ).fetchone()
    assert outcome == "target_hit"
    assert price == 120.0
    assert pct == pytest.approx((120.0 - 100.0) / 100.0)


def test_update_signal_outcomes_resolves_stop_hit(con):
    sig.record_signal(con, "AAPL", _meta(), xgb_prob=0.7, lstm_prob=0.6, ensemble_score=0.65, macro_score=0.5)
    sig.update_signal_outcomes(con, {"AAPL": 90.0})
    outcome, pct = con.execute(
        "SELECT outcome, outcome_pct FROM signal_history WHERE symbol='AAPL'"
    ).fetchone()
    assert outcome == "stop_hit"
    assert pct == pytest.approx((90.0 - 100.0) / 100.0)


def test_update_signal_outcomes_leaves_pending_when_between_stop_and_target(con):
    sig.record_signal(con, "AAPL", _meta(), xgb_prob=0.7, lstm_prob=0.6, ensemble_score=0.65, macro_score=0.5)
    sig.update_signal_outcomes(con, {"AAPL": 105.0})
    outcome = con.execute("SELECT outcome FROM signal_history WHERE symbol='AAPL'").fetchone()[0]
    assert outcome == "pending"


def test_update_signal_outcomes_skips_symbol_missing_from_prices(con):
    sig.record_signal(con, "AAPL", _meta(), xgb_prob=0.7, lstm_prob=0.6, ensemble_score=0.65, macro_score=0.5)
    sig.update_signal_outcomes(con, {"MSFT": 200.0})
    outcome = con.execute("SELECT outcome FROM signal_history WHERE symbol='AAPL'").fetchone()[0]
    assert outcome == "pending"


def test_update_signal_outcomes_expires_stale_unresolved_signal(con):
    old_ts = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    con.execute(
        "INSERT INTO signal_history (timestamp, symbol, entry_price, stop_price, target_price, outcome) "
        "VALUES (?, 'AAPL', 100.0, 95.0, 115.0, 'pending')", (old_ts,),
    )
    con.commit()
    sig.update_signal_outcomes(con, {"AAPL": 105.0})  # between stop and target, but stale
    outcome = con.execute("SELECT outcome FROM signal_history WHERE symbol='AAPL'").fetchone()[0]
    assert outcome == "expired"


def test_update_signal_outcomes_does_not_expire_recent_unresolved_signal(con):
    recent_ts = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    con.execute(
        "INSERT INTO signal_history (timestamp, symbol, entry_price, stop_price, target_price, outcome) "
        "VALUES (?, 'AAPL', 100.0, 95.0, 115.0, 'pending')", (recent_ts,),
    )
    con.commit()
    sig.update_signal_outcomes(con, {"AAPL": 105.0})
    outcome = con.execute("SELECT outcome FROM signal_history WHERE symbol='AAPL'").fetchone()[0]
    assert outcome == "pending"


def test_update_signal_outcomes_ignores_already_resolved_rows(con):
    con.execute(
        "INSERT INTO signal_history (timestamp, symbol, entry_price, stop_price, target_price, outcome) "
        "VALUES (?, 'AAPL', 100.0, 95.0, 115.0, 'target_hit')",
        (datetime.now(timezone.utc).isoformat(),),
    )
    con.commit()
    sig.update_signal_outcomes(con, {"AAPL": 90.0})  # would be stop_hit if re-evaluated
    outcome = con.execute("SELECT outcome FROM signal_history WHERE symbol='AAPL'").fetchone()[0]
    assert outcome == "target_hit"


def test_update_signal_outcomes_handles_malformed_timestamp_gracefully(con):
    con.execute(
        "INSERT INTO signal_history (timestamp, symbol, entry_price, stop_price, target_price, outcome) "
        "VALUES ('not-a-timestamp', 'AAPL', 100.0, 95.0, 115.0, 'pending')"
    )
    con.commit()
    sig.update_signal_outcomes(con, {"AAPL": 105.0})  # must not raise
    outcome = con.execute("SELECT outcome FROM signal_history WHERE symbol='AAPL'").fetchone()[0]
    assert outcome == "pending"
