"""Tests for the Wave 2B Performance & Learning composition wiring:
``_build_performance_learning_screen()`` / ``_build_performance_learning_ui()``
and their use inside ``build_trading_intelligence_app()``.

The wiring maps the frozen Wave 2A ``OutcomeLineage`` (via
``DecisionOutcomeQueryService`` over a real trades.db) into the P&L
screen's Outcome History area. Attribution Breakdown and Model Confidence
Calibration stay unavailable.
"""
import os
import sqlite3
import tempfile
from collections import Counter

import gradio as gr

from applications.platform.integrations import IntegrationStatus
from applications.trading_intelligence.bootstrap import (
    _build_performance_learning_screen,
    _build_performance_learning_ui,
    build_trading_intelligence_app,
)
from applications.trading_intelligence.ui.performance_learning.screen import (
    OutcomeHistoryRow,
    PerformanceLearningScreen,
)

_DDL = """
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT, symbol TEXT, action TEXT,
    shares REAL, price REAL, notional REAL,
    regime TEXT, portfolio_value REAL, pnl_pct REAL,
    xgb_prob REAL, lstm_prob REAL, sentiment_score REAL, macro_score REAL,
    ensemble_score REAL, realized_pnl REAL, order_id TEXT, holding_days INTEGER,
    feature_drivers TEXT, ai_reasoning TEXT,
    stop_loss REAL, take_profit REAL, risk_reward_ratio REAL
)
"""

_COLS = (
    "id", "timestamp", "symbol", "action", "shares", "price", "notional",
    "realized_pnl", "pnl_pct", "holding_days", "order_id", "ensemble_score", "regime",
)


def _row(**over):
    base = dict(
        id=None, timestamp="2026-07-01T00:00:00+00:00", symbol="AAA", action="BUY",
        shares=100.0, price=10.0, notional=1000.0, realized_pnl=0.0, pnl_pct=0.0,
        holding_days=0, order_id=None, ensemble_score=0.6, regime="RANGING",
    )
    base.update(over)
    return tuple(base[c] for c in _COLS)


def _make_db(rows):
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(_DDL)
    ph = ", ".join("?" for _ in _COLS)
    conn.executemany(
        f"INSERT INTO trades ({', '.join(_COLS)}) VALUES ({ph})", rows
    )
    conn.commit()
    conn.close()
    return path


def _empty_db():
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(_DDL)
    conn.commit()
    conn.close()
    return path


# --- state 1: no snapshot -> unavailable --------------------------------

def test_no_snapshot_yields_unavailable_screen():
    screen = _build_performance_learning_screen(None)  # -> reader default "trades.db"
    # In CI no local trades.db exists; on a dev box one may. Accept either
    # the honest unavailable state or a HEALTHY populated one -- the
    # invariant is that it is a real PerformanceLearningScreen and never
    # fabricated.
    assert isinstance(screen, PerformanceLearningScreen)
    if not screen.outcome_history_available:
        assert screen.outcome_rows == ()
        assert screen.summary is None


def test_missing_db_path_is_explicitly_unavailable():
    screen = _build_performance_learning_screen("no_such_pl_wiring_db_xyz.db")
    assert screen.outcome_history_available is False
    assert screen.outcome_health.status is IntegrationStatus.UNAVAILABLE
    assert screen.outcome_rows == ()
    assert screen.summary is None
    # Attribution + Calibration untouched
    assert "attribution contract is wired yet" in screen.attribution_breakdown.unavailable_message
    assert "model-calibration contract is wired yet" in screen.model_confidence_calibration.unavailable_message


def test_missing_trades_table_is_api_error_unavailable():
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE unrelated (id INTEGER)")
    conn.commit()
    conn.close()
    try:
        screen = _build_performance_learning_screen(path)
        assert screen.outcome_history_available is False
        assert screen.outcome_health.status is IntegrationStatus.API_ERROR
    finally:
        os.remove(path)


# --- state 2: HEALTHY, zero decisions -> empty -------------------------

def test_empty_trades_db_is_healthy_but_empty():
    path = _empty_db()
    try:
        screen = _build_performance_learning_screen(path)
        assert screen.outcome_history_available is True
        assert screen.outcome_history_is_empty is True
        assert screen.outcome_rows == ()
        assert screen.summary == (
            "0 BUY decisions — 0 CLOSED · 0 PARTIAL · 0 OPEN · 0 AMBIGUOUS."
        )
    finally:
        os.remove(path)


# --- state 3: HEALTHY, decisions -> populated ------------------------

def test_valid_snapshot_populates_outcome_history():
    rows = [
        # trade-1: clean CLOSED bot exit, WIN
        _row(id=1, symbol="AMZN", action="BUY", shares=23.68,
             timestamp="2026-07-16T16:50:00+00:00", price=256.09),
        _row(id=2, symbol="AMZN", action="SELL_TIME_EXIT", shares=23.66,
             timestamp="2026-09-02T14:33:00+00:00", price=254.92, order_id="o-2",
             realized_pnl=-27.77, pnl_pct=-0.00234, holding_days=47),
        # trade-3: OPEN (no sell)
        _row(id=3, symbol="SLB", action="BUY", shares=139.75,
             timestamp="2026-09-02T14:39:08+00:00", order_id="o-3"),
    ]
    path = _make_db(rows)
    try:
        screen = _build_performance_learning_screen(path)
        assert screen.outcome_history_available is True
        assert screen.is_empty is False
        assert len(screen.outcome_rows) == 2

        by_decision = {r.decision: r for r in screen.outcome_rows}
        amzn = by_decision["AMZN BUY · trade-1"]
        assert amzn.status == "CLOSED"
        assert amzn.exit_basis == "Bot fill"
        assert amzn.direction == "LOSS"
        assert amzn.realized_pnl_usd == "-27.77"
        assert amzn.realized_pnl_pct == "-0.23%"
        assert amzn.holding_days == "47"
        assert amzn.pairing_method == "WINDOW_SINGLE_BOT_EXIT"
        assert amzn.pairing_confidence == "HIGH"

        slb = by_decision["SLB BUY · trade-3"]
        assert slb.status == "OPEN"
        assert slb.exit_date == "" and slb.realized_pnl_usd == "" and slb.direction == ""

        assert screen.summary == (
            "2 BUY decisions — 1 CLOSED · 0 PARTIAL · 1 OPEN · 0 AMBIGUOUS."
        )
    finally:
        os.remove(path)


def test_excluded_sell_breakdown_is_in_the_summary():
    rows = [
        _row(id=1, symbol="MS", action="SELL_STOP", order_id="o-1",
             timestamp="2026-06-26T19:50:00+00:00"),  # orphan
        _row(id=2, symbol="AAA", action="BUY", shares=100.0,
             timestamp="2026-07-01T00:00:00+00:00"),  # open
    ]
    path = _make_db(rows)
    try:
        screen = _build_performance_learning_screen(path)
        assert "1 SELL rows excluded (1 orphan)." in screen.summary
    finally:
        os.remove(path)


# --- the UI builder / provider --------------------------------------

def test_ui_builder_returns_ui_whose_provider_returns_a_fresh_screen():
    rows = [_row(id=1, symbol="AAA", action="BUY", shares=100.0,
                 timestamp="2026-07-01T00:00:00+00:00", order_id="o-1")]
    path = _make_db(rows)
    try:
        ui = _build_performance_learning_ui(path)
        first = ui._screen_provider()
        second = ui._screen_provider()
        assert isinstance(first, PerformanceLearningScreen)
        # A fresh read each call: same data (health.checked_at differs by
        # design, so compare the payload, not the whole frozen dataclass).
        assert first.outcome_history_available is True and second.outcome_history_available is True
        assert first.outcome_rows == second.outcome_rows
        assert first.summary == second.summary
        assert first.outcome_health.status is second.outcome_health.status
    finally:
        os.remove(path)


def test_composed_app_still_has_six_screen_labels_and_merged_assets():
    app = build_trading_intelligence_app()
    assert isinstance(app, gr.Blocks)
    for name in (
        "Morning Brief", "Decision Center", "Portfolio Intelligence",
        "Risk Intelligence", "Performance & Learning", "Settings",
    ):
        assert name in app.head
    # P&L's Outcome History table CSS survived the TabbedInterface merge.
    assert app.css and "pl-outcome-table" in app.css


# --- production regression (opt-in) --------------------------------

_PROD = os.environ.get("AARA_WAVE2A_PROD_SNAPSHOT")


import pytest  # noqa: E402


@pytest.mark.skipif(not _PROD, reason="set AARA_WAVE2A_PROD_SNAPSHOT to a real 42-row trades.db")
def test_production_snapshot_maps_to_expected_outcome_history():
    screen = _build_performance_learning_screen(_PROD)
    assert screen.outcome_history_available is True
    rows = screen.outcome_rows
    assert len(rows) == 19

    status_counts = Counter(r.status for r in rows)
    assert status_counts["CLOSED"] == 15
    assert status_counts["PARTIAL"] == 1
    assert status_counts["OPEN"] == 3
    assert status_counts.get("AMBIGUOUS", 0) == 0

    directions = Counter(r.direction for r in rows if r.status == "CLOSED")
    assert directions["WIN"] == 7
    assert directions["LOSS"] == 8

    assert screen.summary == (
        "19 BUY decisions — 15 CLOSED · 1 PARTIAL · 3 OPEN · 0 AMBIGUOUS. "
        "7 SELL rows excluded (6 phantom-reconcile-suppressed, 1 orphan)."
    )

    by_decision = {r.decision: r for r in rows}
    assert by_decision["SLB BUY · trade-45"].status == "OPEN"
    assert by_decision["BA BUY · trade-28"].status == "OPEN"
    assert by_decision["AAPL BUY · trade-35"].status == "OPEN"
    assert by_decision["NKE BUY · trade-40"].status == "PARTIAL"

    amzn = by_decision["AMZN BUY · trade-38"]
    assert amzn.status == "CLOSED"
    assert amzn.exit_basis == "Bot fill"
    assert amzn.direction == "LOSS"
    assert amzn.realized_pnl_usd == "-27.77"
    assert amzn.realized_pnl_pct == "-0.23%"
    assert amzn.holding_days == "47"

    for sym_id in ("GOOGL BUY · trade-4", "SNOW BUY · trade-8", "BAC BUY · trade-36"):
        assert by_decision[sym_id].status == "CLOSED"
        assert by_decision[sym_id].exit_basis == "Reconciliation mark"
