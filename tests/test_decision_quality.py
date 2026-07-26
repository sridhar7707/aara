"""Tests for dashboard.components.decision_quality."""
import pytest

import dashboard.data as ddata
from bot._main_db import init_db, log_trade
from bot._main_decisions import create_buy_decision
from database.services.decision_service import mark_executed, complete_decision
import dashboard.components.decision_quality as dq


@pytest.fixture
def dash_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "dq_test.db")
    con = init_db(db_path)
    monkeypatch.setattr(ddata, "DB_PATH", db_path)
    monkeypatch.setattr(dq, "_get_sym_hist", lambda symbol: None)  # no network in tests
    return con


def _completed_decision(con, symbol, price, pnl_pct):
    trade_id = log_trade(con, symbol, "BUY", 5.0, price, price * 5, "TRENDING_UP", 10000.0, 0.0)
    did = create_buy_decision(con, symbol, price, 10000.0, None, 0.7, 0.6, 0.3, 0.55, "TRENDING_UP")
    mark_executed(con, did, trade_id=trade_id)
    complete_decision(con, did, realized_pnl_pct=pnl_pct)
    return did


def test_empty_state_when_no_completed_decisions(dash_db):
    html = dq.render_decision_quality_summary()
    assert "No completed decisions yet" in html


def test_counts_completed_decisions(dash_db):
    _completed_decision(dash_db, "AAPL", 100.0, 0.05)
    _completed_decision(dash_db, "MSFT", 200.0, -0.03)
    html = dq.render_decision_quality_summary()
    assert "Based on 2 completed decisions" in html


def test_excludes_decisions_without_known_outcome(dash_db):
    _completed_decision(dash_db, "AAPL", 100.0, 0.05)
    # BAC is executed but never completed — must not count
    trade_id = log_trade(dash_db, "BAC", "BUY", 5.0, 60.0, 300.0, "TRENDING_UP", 10000.0, 0.0)
    did = create_buy_decision(dash_db, "BAC", 60.0, 10000.0, None, 0.7, 0.6, 0.3, 0.55, "TRENDING_UP")
    mark_executed(dash_db, did, trade_id=trade_id)
    html = dq.render_decision_quality_summary()
    assert "Based on 1 completed decisions" in html


def test_trend_shows_early_evidence_below_minimum(dash_db):
    for i in range(3):  # below _MIN_FOR_TREND (6)
        _completed_decision(dash_db, f"SYM{i}", 100.0, 0.05)
    html = dq.render_decision_quality_summary()
    assert "Early evidence" in html


def test_trend_shows_improving_when_second_half_wins_more(dash_db):
    for i in range(3):
        _completed_decision(dash_db, f"LOSER{i}", 100.0, -0.05)  # first half: all losses
    for i in range(3):
        _completed_decision(dash_db, f"WINNER{i}", 100.0, 0.05)  # second half: all wins
    html = dq.render_decision_quality_summary()
    assert "Improving" in html


def test_trend_shows_declining_when_second_half_loses_more(dash_db):
    for i in range(3):
        _completed_decision(dash_db, f"WINNER{i}", 100.0, 0.05)
    for i in range(3):
        _completed_decision(dash_db, f"LOSER{i}", 100.0, -0.05)
    html = dq.render_decision_quality_summary()
    assert "Declining" in html


def test_strength_hidden_when_no_sector_has_enough_decisions(dash_db):
    """Each symbol below _MIN_FOR_DIMENSION (3) per sector -> no claim made."""
    _completed_decision(dash_db, "AAPL", 100.0, 0.05)   # Tech
    _completed_decision(dash_db, "JPM", 100.0, 0.03)    # Finance
    html = dq.render_decision_quality_summary()
    assert "No sector stands out" in html
    assert "Strength:" not in html


def test_strength_shown_when_a_sector_has_enough_decisions(dash_db):
    for i in range(3):
        # AAPL/MSFT/NVDA are all Technology in SECTOR_MAP, all wins -> 100% WR
        _completed_decision(dash_db, ["AAPL", "MSFT", "NVDA"][i], 100.0, 0.05)
    html = dq.render_decision_quality_summary()
    assert "Strength:" in html


def test_sole_qualifying_sector_with_poor_win_rate_is_weakness_not_strength(dash_db):
    """The exact bug this caught: being the ONLY sector with enough decisions
    must not make it a "Strength" just by default. 1 win, 2 losses = 33% win
    rate is genuinely poor (below the 45% bar) — it should show as a
    Weakness, never mislabeled as a Strength."""
    _completed_decision(dash_db, "AAPL", 100.0, 0.05)    # Tech, win
    _completed_decision(dash_db, "MSFT", 100.0, -0.03)   # Tech, loss
    _completed_decision(dash_db, "NVDA", 100.0, -0.02)   # Tech, loss
    html = dq.render_decision_quality_summary()
    assert "Strength:" not in html
    assert "Weakness:" in html


def test_sole_qualifying_sector_with_middling_win_rate_shows_neither(dash_db):
    """A win rate that's neither clearly good (>=60%) nor clearly bad (<45%)
    — e.g. 50% — must not be forced into either bucket."""
    _completed_decision(dash_db, "AAPL", 100.0, 0.05)    # Tech, win
    _completed_decision(dash_db, "MSFT", 100.0, 0.04)    # Tech, win
    _completed_decision(dash_db, "NVDA", 100.0, -0.03)   # Tech, loss
    _completed_decision(dash_db, "AMD",  100.0, -0.02)   # Tech, loss
    html = dq.render_decision_quality_summary()
    assert "Strength:" not in html
    assert "Weakness:" not in html
    assert "No sector stands out" in html
