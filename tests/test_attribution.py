"""Tests for dashboard.components.attribution."""
import pytest

import dashboard.data as ddata
from bot._main_db import init_db, log_trade
from dashboard.components.attribution import (
    _query_closed_trades, _query_closed_trades_by_reason, render_exit_attribution,
)


@pytest.fixture
def dash_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "attribution_test.db")
    con = init_db(db_path)
    monkeypatch.setattr(ddata, "DB_PATH", db_path)
    return con


def test_query_closed_trades_excludes_sell_reconcile(dash_db):
    log_trade(dash_db, "AAPL", "SELL_STOP", 5.0, 100.0, 500.0, "TRENDING_UP", 10000.0, -0.05)
    log_trade(dash_db, "MSFT", "SELL_RECONCILE", 3.0, 200.0, 600.0, "reconcile", 10000.0, 0.99)
    rows = _query_closed_trades()
    symbols = [r[0] for r in rows]
    assert "AAPL" in symbols
    assert "MSFT" not in symbols


def test_query_closed_trades_by_reason_excludes_sell_reconcile(dash_db):
    log_trade(dash_db, "AAPL", "SELL_STOP", 5.0, 100.0, 500.0, "TRENDING_UP", 10000.0, -0.05)
    log_trade(dash_db, "MSFT", "SELL_RECONCILE", 3.0, 200.0, 600.0, "reconcile", 10000.0, 0.99)
    rows = _query_closed_trades_by_reason()
    actions = [r[0] for r in rows]
    assert "SELL_STOP" in actions
    assert "SELL_RECONCILE" not in actions


def test_render_exit_attribution_empty_state(dash_db):
    html = render_exit_attribution()
    assert "No closed trades yet" in html


def test_render_exit_attribution_groups_by_reason(dash_db):
    log_trade(dash_db, "AAPL", "SELL_STOP", 5.0, 100.0, 500.0, "TRENDING_UP", 10000.0, -0.05)
    log_trade(dash_db, "MSFT", "SELL_STOP", 3.0, 200.0, 600.0, "TRENDING_UP", 10000.0, -0.03)
    log_trade(dash_db, "BAC", "SELL_TIME_EXIT", 10.0, 60.0, 600.0, "TRENDING_UP", 10000.0, 0.02)
    html = render_exit_attribution()
    assert "Stop-Loss" in html
    assert "Time Exit" in html
    # 2 stop-loss trades, both losses -> 0% win rate
    assert "0%" in html
    # 1 time-exit trade, a win -> 100% win rate
    assert "100%" in html


def test_render_exit_attribution_ignores_sell_reconcile(dash_db):
    log_trade(dash_db, "AAPL", "SELL_STOP", 5.0, 100.0, 500.0, "TRENDING_UP", 10000.0, -0.05)
    log_trade(dash_db, "MSFT", "SELL_RECONCILE", 3.0, 200.0, 600.0, "reconcile", 10000.0, 0.99)
    html = render_exit_attribution()
    assert "Stop-Loss" in html
    assert "1 closed trades" in html  # only the real SELL_STOP counts


def test_render_exit_attribution_unmapped_reason_falls_back_gracefully(dash_db):
    """A brand-new exit action not yet in _EXIT_LABELS must still render
    sensibly (not crash), so a future exit type doesn't break the page."""
    log_trade(dash_db, "AAPL", "SELL_NEW_REASON", 5.0, 100.0, 500.0, "TRENDING_UP", 10000.0, 0.03)
    html = render_exit_attribution()
    assert "New Reason" in html
