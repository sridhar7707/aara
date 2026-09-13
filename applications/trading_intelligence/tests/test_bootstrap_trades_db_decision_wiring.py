"""Tests for the Wave 1 Decision Center composition wiring:
``build_application_from_trades_snapshot()`` and its use inside
``build_trading_intelligence_app()``.

Coexistence guarantee: ``build_application()`` (the Sentinel path) is
unchanged -- its own suite is ``tests/test_bootstrap.py``; here we only
re-confirm it still returns an empty-seeded UI and that the new entrypoint
constructs no ``sentinel_engine`` object.
"""
import ast
import inspect
import os
import sqlite3
import tempfile

import gradio as gr

from sentinel_engine.queries.decision_query import DecisionQuery
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.services.sentinel_engine import SentinelEngine

from applications.trading_intelligence.bootstrap import (
    build_application,
    build_application_from_trades_snapshot,
    build_trading_intelligence_app,
)
from applications.trading_intelligence.ui.decision_center.gradio_view import DecisionCenterUI
from applications.trading_intelligence.ui.decision_center.screen import ReadStatus

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
);
CREATE TABLE news_cache (
    symbol TEXT, fetch_date TEXT, headlines_json TEXT, cached_at TEXT,
    PRIMARY KEY (symbol, fetch_date)
);
CREATE TABLE recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL,
    prediction_date TEXT NOT NULL, recommendation TEXT, confidence REAL,
    prev_recommendation TEXT, price_at_recommendation REAL, created_at TEXT,
    UNIQUE(symbol, prediction_date)
)
"""


def _seeded_db():
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.executescript(_DDL)
    conn.execute(
        "INSERT INTO trades (id, timestamp, symbol, action, ensemble_score, "
        "feature_drivers, ai_reasoning) VALUES "
        "(45, '2026-09-02T14:39:08', 'SLB', 'BUY', 0.5222, '{\"m\": 1}', 'reasoning')"
    )
    conn.execute(
        "INSERT INTO trades (id, timestamp, symbol, action) VALUES "
        "(44, '2026-09-01T10:00:00', 'SLB', 'SELL_RECONCILE')"
    )
    conn.commit()
    conn.close()
    return path


def _track(monkeypatch, cls):
    calls = []
    original = cls.__init__

    def wrapped(self, *args, **kwargs):
        calls.append(self)
        original(self, *args, **kwargs)

    monkeypatch.setattr(cls, "__init__", wrapped)
    return calls


# -- build_application() is unchanged -----------------------------------

def test_build_application_still_returns_an_empty_seeded_ui():
    ui = build_application()
    assert isinstance(ui, DecisionCenterUI)
    assert ui._decision_ids == []


def test_build_application_sentinel_path_has_no_news_cache_diff_source():
    """Coexistence: build_application() (the Sentinel path) has no
    trades.db to read at all, so it must not be given a news-cache diff
    collaborator -- confirmed at the controller it constructs."""
    ui = build_application()
    assert ui._controller._news_cache_diff_source is None


def test_build_application_sentinel_path_has_no_recommendation_diff_source():
    """Coexistence: build_application() (the Sentinel path) has no
    trades.db to read at all, so it must not be given a recommendation
    diff collaborator either."""
    ui = build_application()
    assert ui._controller._recommendation_diff_source is None


# -- build_application_from_trades_snapshot() --------------------------

def test_none_db_path_is_safe_and_builds():
    ui = build_application_from_trades_snapshot(None)
    assert isinstance(ui, DecisionCenterUI)
    assert isinstance(ui._decision_ids, list)
    assert isinstance(ui.build(), gr.Blocks)


def test_explicit_missing_db_path_yields_no_decisions():
    ui = build_application_from_trades_snapshot("no_such_trades_file_zzz_42.db")
    assert ui._decision_ids == []


def test_seeded_db_exposes_trade_45_only():
    path = _seeded_db()
    try:
        ui = build_application_from_trades_snapshot(path)
        assert ui._decision_ids == ["trade-45"]
        # the existing controller renders it end-to-end
        detail = ui._controller.load_decision_detail("trade-45")
        assert detail.decision.symbol == "SLB"
        assert [e.evidence_type for e in detail.evidence] == [
            "MODEL_ENSEMBLE", "FEATURE_DRIVERS", "AI_RATIONALE",
        ]
    finally:
        os.remove(path)


def test_seeded_db_wires_a_real_news_cache_diff_source():
    """Confirms build_application_from_trades_snapshot() actually
    constructs and injects TradesDbNewsCacheDiffSource into the controller
    -- not asserting a specific diff (today's real date is not under this
    test's control), only that the collaborator is wired and the read path
    is safe/honest (an empty temp DB has no news_cache rows for any date,
    so the honest result is OK/None, never an error)."""
    path = _seeded_db()
    try:
        ui = build_application_from_trades_snapshot(path)
        assert ui._controller._news_cache_diff_source is not None
        detail = ui._controller.load_decision_detail("trade-45")
        assert detail.news_cache_diff is None
        assert detail.news_cache_diff_status is ReadStatus.OK
    finally:
        os.remove(path)


def test_seeded_db_wires_a_real_recommendation_diff_source():
    """Confirms build_application_from_trades_snapshot() actually
    constructs and injects TradesDbRecommendationDiffSource into the
    controller -- not asserting a specific diff (today's real date is not
    under this test's control), only that the collaborator is wired and
    the read path is safe/honest (an empty temp DB has no recommendations
    rows for any date, so the honest result is OK/None, never an error)."""
    path = _seeded_db()
    try:
        ui = build_application_from_trades_snapshot(path)
        assert ui._controller._recommendation_diff_source is not None
        detail = ui._controller.load_decision_detail("trade-45")
        assert detail.recommendation_diff is None
        assert detail.recommendation_diff_status is ReadStatus.OK
    finally:
        os.remove(path)


def test_constructs_no_sentinel_engine_objects(monkeypatch):
    engine_calls = _track(monkeypatch, SentinelEngine)
    ledger_calls = _track(monkeypatch, LedgerRepository)
    query_calls = _track(monkeypatch, DecisionQuery)

    build_application_from_trades_snapshot(None)

    assert engine_calls == []
    assert ledger_calls == []
    assert query_calls == []


def test_source_module_does_not_import_sentinel_engine():
    import applications.trading_intelligence.bootstrap as bootstrap

    # The new entrypoint's own body must not reference any sentinel_engine
    # symbol -- checked by re-parsing just that function.
    tree = ast.parse(inspect.getsource(build_application_from_trades_snapshot))
    names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    for leaked in ("SentinelEngine", "LedgerRepository", "ProjectionRepository", "DecisionQuery"):
        assert leaked not in names
    assert bootstrap is not None  # module import sanity


# -- six-tab composition intact --------------------------------------

def test_six_tab_composition_is_intact():
    app = build_trading_intelligence_app()
    tab_labels = [b.label for b in app.blocks.values() if isinstance(b, gr.Tab)]
    assert tab_labels == [
        "Morning Brief", "Decision Center", "Portfolio Intelligence",
        "Risk Intelligence", "Performance & Learning", "Settings",
    ]


# -- new adapter modules: no forbidden imports ----------------------

def test_new_adapter_modules_have_no_forbidden_imports():
    import applications.trading_intelligence.adapters.trade_decision_derivation as m1
    import applications.trading_intelligence.adapters.trades_db_decision_adapters as m2
    import applications.trading_intelligence.adapters.trades_db_decision_source as m3
    import applications.trading_intelligence.projections.trade_decision_row as m4

    forbidden = ("bot", "dashboard", "database", "scheduler", "ledger", "sentinel_engine")
    for module in (m1, m2, m3, m4):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden), (
                        f"{module.__name__}: forbidden import {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith(forbidden), (
                    f"{module.__name__}: forbidden import from {mod!r}"
                )
