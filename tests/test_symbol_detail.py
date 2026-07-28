"""Tests for dashboard.components.symbol_detail.

Regression coverage for a confirmed production bug: selecting SNOW in the
Symbol Detail dropdown showed GOOGL's full AI-analysis panel instead. The
render function itself turned out to be correctly parameterized by `symbol`
throughout -- the real bug was an architectural race between two Gradio
event handlers writing to the same output (fixed in dashboard/timers.py).
These tests lock in that render_symbol_detail() stays symbol-pure so a
future change can't reintroduce cross-symbol contamination at this layer.
"""
from __future__ import annotations

import pandas as pd
import pytest

import dashboard.components.symbol_detail as sd

_TRADES_COLUMNS = [
    "timestamp", "symbol", "action", "shares", "price", "notional",
    "pnl_pct", "regime", "ensemble_score", "xgb_prob", "lstm_prob",
    "sentiment_score", "feature_drivers",
]


def _fake_data(open_pos: dict, prices: dict, trades_rows: list | None = None) -> dict:
    df = pd.DataFrame(trades_rows or [], columns=_TRADES_COLUMNS)
    return {
        "trades_df": df,
        "prices": prices,
        "open_pos": open_pos,
        "regime_raw": "trending_up",
    }


@pytest.fixture
def two_symbol_positions(monkeypatch):
    """SNOW and GOOGL both open positions, each with distinct entry data --
    exactly the shape of the real "ghost position" scenario that surfaced
    the bug (see project memory: SELL_RECONCILE pollution left both as
    live open positions)."""
    open_pos = {
        "SNOW":  {"shares": 10.0, "invested": 1500.0},
        "GOOGL": {"shares": 5.0,  "invested": 900.0},
    }
    prices = {"SNOW": 160.0, "GOOGL": 190.0}
    trades_rows = [
        {"timestamp": "2026-07-01T10:00:00", "symbol": "SNOW", "action": "BUY",
         "shares": 10.0, "price": 150.0, "notional": 1500.0, "pnl_pct": 0.0,
         "regime": "trending_up", "ensemble_score": 0.62, "xgb_prob": 0.60,
         "lstm_prob": 0.58, "sentiment_score": 0.1, "feature_drivers": "[]"},
        {"timestamp": "2026-07-02T10:00:00", "symbol": "GOOGL", "action": "BUY",
         "shares": 5.0, "price": 180.0, "notional": 900.0, "pnl_pct": 0.0,
         "regime": "trending_up", "ensemble_score": 0.71, "xgb_prob": 0.68,
         "lstm_prob": 0.66, "sentiment_score": 0.2, "feature_drivers": "[]"},
    ]

    def _fake_portfolio_action(symbol, d):
        return {"action": "HOLD", "confidence": 60, "reason": f"reason for {symbol}"}

    def _fake_explanation(symbol, d, portfolio_action=None):
        return {"bullish": [f"{symbol} bullish signal"], "bearish": [f"{symbol} bearish signal"]}

    def _fake_sizing(symbol, d):
        return {"dollar_display": f"${symbol}", "target_weight": 10.0}

    monkeypatch.setattr(sd, "get_portfolio_action", _fake_portfolio_action)
    monkeypatch.setattr(sd, "get_recommendation_explanation", _fake_explanation)
    monkeypatch.setattr(sd, "get_position_sizing", _fake_sizing)
    monkeypatch.setattr(sd, "get_data", lambda: _fake_data(open_pos, prices, trades_rows))
    return open_pos, prices


def test_render_shows_the_requested_symbol_not_another_one(two_symbol_positions):
    html = sd.render_symbol_detail("SNOW")
    assert "Why do I own SNOW?" in html
    assert "SNOW bullish signal" in html
    assert "GOOGL" not in html


def test_switching_symbols_back_to_back_does_not_leak_state(two_symbol_positions):
    """The exact sequence that surfaced the production bug: render GOOGL,
    then render SNOW, and confirm SNOW's output is fully independent."""
    googl_html = sd.render_symbol_detail("GOOGL")
    snow_html  = sd.render_symbol_detail("SNOW")

    assert "Why do I own GOOGL?" in googl_html
    assert "SNOW" not in googl_html

    assert "Why do I own SNOW?" in snow_html
    assert "GOOGL" not in snow_html


def test_open_position_status_badge_uses_correct_symbols_position(two_symbol_positions):
    html = sd.render_symbol_detail("SNOW")
    assert "OPEN POSITION" in html
