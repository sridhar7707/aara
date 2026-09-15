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
from applications.trading_intelligence.contracts.decision_outcome_contract import (
    OutcomeDirection,
    OutcomeStatus,
)
from applications.trading_intelligence.projections.trade_decision_row import decision_id_for
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
);
CREATE TABLE earnings_cache (
    symbol TEXT PRIMARY KEY, near_earnings INTEGER, cached_at TEXT
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


def test_build_application_sentinel_path_has_no_earnings_source():
    """Coexistence: build_application() (the Sentinel path) has no
    trades.db to read at all, so it must not be given an earnings
    collaborator either."""
    ui = build_application()
    assert ui._controller._earnings_source is None


def test_build_application_sentinel_path_has_no_outcome_source():
    """Coexistence: build_application() (the Sentinel path) has no
    trades.db to read at all, so it must not be given a Decision ->
    Outcome collaborator either."""
    ui = build_application()
    assert ui._controller._outcome_source is None


def test_build_application_sentinel_path_has_no_calibration_source():
    """Coexistence: build_application() (the Sentinel path) has no
    trades.db to read at all, so it must not be given a Decision Quality
    Cross-Linking calibration collaborator either."""
    ui = build_application()
    assert ui._controller._calibration_source is None


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


def test_seeded_db_decision_renders_through_the_full_ui_layer():
    """End-to-end wiring proof, one level past test_seeded_db_exposes_
    trade_45_only above: that test only reaches the controller
    (``ui._controller.load_decision_detail(...)``) -- this proves the same
    seeded trades.db row survives all the way through the actual UI render
    call (``DecisionCenterUI._render_screen()``, the exact function
    ``demo.load()``/the Refresh button invoke in the real app), using the
    real, production ``build_application_from_trades_snapshot()`` wiring --
    no fake controller, no test-only shortcut."""
    path = _seeded_db()
    try:
        ui = build_application_from_trades_snapshot(path)

        list_rows, list_empty, *detail = ui._render_screen()

        # The decision reached the rendered Decisions table.
        assert list_rows[0][0] == "trade-45"
        assert list_rows[0][1] == "SLB"
        # The decision reached the rendered Evidence section (index 6 of
        # the 11 detail outputs -- see build()'s detail_outputs ordering).
        evidence_html = detail[6]
        assert "MODEL_ENSEMBLE" in evidence_html
        assert "FEATURE_DRIVERS" in evidence_html
        # Rendered display label, not the domain-level evidence_type (still
        # "AI_RATIONALE" -- the stored ai_reasoning text is a deterministic
        # formatted summary, not independently generated AI reasoning).
        assert "Entry Summary" in evidence_html
        assert "reasoning" in evidence_html
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


def test_seeded_db_wires_a_real_earnings_source():
    """Confirms build_application_from_trades_snapshot() actually
    constructs and injects TradesDbEarningsSource into the controller --
    the read path is safe/honest (an empty temp DB has no earnings_cache
    rows for any symbol, so the honest result is OK/None, never an
    error)."""
    path = _seeded_db()
    try:
        ui = build_application_from_trades_snapshot(path)
        assert ui._controller._earnings_source is not None
        detail = ui._controller.load_decision_detail("trade-45")
        assert detail.earnings_snapshot is None
        assert detail.earnings_status is ReadStatus.OK
    finally:
        os.remove(path)


def test_seeded_db_wires_a_real_outcome_source():
    """Confirms build_application_from_trades_snapshot() actually
    constructs and injects TradesDbDecisionOutcomeSource into the
    controller. trade-45 has no matching bot-fill exit in _seeded_db()
    (trade-44's SELL_RECONCILE predates it), so the honest, real result is
    a DecisionOutcome with status OPEN -- never None, and never an
    error -- proving the shared decision_id lineage: the exact
    "trade-45" id Decision Center's own list uses resolves to a real
    outcome for that same underlying trades row."""
    path = _seeded_db()
    try:
        ui = build_application_from_trades_snapshot(path)
        assert ui._controller._outcome_source is not None
        detail = ui._controller.load_decision_detail("trade-45")
        assert detail.outcome is not None
        assert detail.outcome.decision_id == "trade-45"
        assert detail.outcome.status is OutcomeStatus.OPEN
        assert detail.outcome_status is ReadStatus.OK
    finally:
        os.remove(path)


def _seeded_db_with_closed_outcome():
    """A BUY plus a real bot-fill SELL_TIME_EXIT inside its pairing window
    -- the same shape services/decision_outcome_query_service.py's own
    Wave 2A pairing resolves to a CLOSED outcome, used here to prove the
    Decision -> Outcome linkage renders a real, closed result end-to-end."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.executescript(_DDL)
    conn.execute(
        "INSERT INTO trades (id, timestamp, symbol, action, ensemble_score, "
        "feature_drivers, ai_reasoning) VALUES "
        "(1, '2026-07-16T16:50:00', 'AMZN', 'BUY', 0.62, '{\"m\": 1}', 'reasoning')"
    )
    conn.execute(
        "INSERT INTO trades (id, timestamp, symbol, action, realized_pnl, "
        "pnl_pct, holding_days, order_id) VALUES "
        "(2, '2026-09-02T14:33:00', 'AMZN', 'SELL_TIME_EXIT', -27.77, "
        "-0.00234, 47, 'o-2')"
    )
    conn.commit()
    conn.close()
    return path


def test_seeded_db_decision_outcome_renders_through_the_full_ui_layer():
    """End-to-end proof, one level past test_seeded_db_wires_a_real_
    outcome_source above: that test only reaches the controller -- this
    proves the same seeded, real CLOSED outcome survives all the way
    through the actual UI render call (DecisionCenterUI._render_screen(),
    the exact function demo.load()/Refresh invoke in the real app), using
    the real, production build_application_from_trades_snapshot() wiring
    -- no fake controller, no test-only shortcut. The header is detail
    output index 0 (see build()'s detail_outputs ordering) -- the Decision
    Outcome section is rendered inside it (see gradio_view.py's
    _decision_header_html)."""
    path = _seeded_db_with_closed_outcome()
    try:
        ui = build_application_from_trades_snapshot(path)

        list_rows, list_empty, *detail = ui._render_screen()

        assert list_rows[0][0] == "trade-1"
        header_html = detail[0]
        assert "Decision Outcome" in header_html
        assert "CLOSED" in header_html
        assert "LOSS" in header_html
        assert "-0.23%" in header_html
        assert "47" in header_html
    finally:
        os.remove(path)


# --- Decision Quality Cross-Linking ----------------------------------------


def test_seeded_db_wires_a_real_calibration_source():
    """Confirms build_application_from_trades_snapshot() actually
    constructs and injects TradesDbDecisionCalibrationSource into the
    controller. trade-45's real ensemble_score (0.5222, from _seeded_db())
    falls in the 0.50-0.55 band -- proving the shared decision_id/evidence
    lineage: the same evidence Decision Center's own detail load already
    reads (MODEL_ENSEMBLE.ensemble) drives a real band lookup, not a
    fabricated one. No qualifying CLOSED WIN/LOSS outcome exists in this
    tiny seeded db, so the honest, real result is an all-zero band -- never
    an error."""
    path = _seeded_db()
    try:
        ui = build_application_from_trades_snapshot(path)
        assert ui._controller._calibration_source is not None
        detail = ui._controller.load_decision_detail("trade-45")
        assert detail.calibration_context is not None
        assert detail.calibration_context.band.label == "0.50-0.55"
        assert detail.calibration_context.total_outcomes == 0
        assert detail.calibration_status is ReadStatus.OK
    finally:
        os.remove(path)


def test_seeded_db_calibration_context_renders_through_the_full_ui_layer():
    """End-to-end wiring proof, one level past
    test_seeded_db_wires_a_real_calibration_source above: proves the same
    seeded, real ensemble score survives all the way through the actual UI
    render call (DecisionCenterUI._render_screen(), the exact function
    demo.load()/the Refresh button invoke in the real app), using the real,
    production build_application_from_trades_snapshot() wiring -- no fake
    controller, no test-only shortcut. The header is detail output index 0
    (see build()'s detail_outputs ordering) -- the Historical Confidence
    Band section is rendered inside it (see gradio_view.py's
    _format_calibration_context_html)."""
    path = _seeded_db_with_closed_outcome()
    try:
        ui = build_application_from_trades_snapshot(path)

        list_rows, list_empty, *detail = ui._render_screen()

        assert list_rows[0][0] == "trade-1"
        header_html = detail[0]
        assert "Historical Confidence Band" in header_html
        assert "0.60-0.65" in header_html
        # Only 1 qualifying outcome in this tiny seeded db -- well below the
        # 30-outcome floor -- so the honest small-n message, never a
        # fabricated percentage.
        assert "Historical performance: not enough data yet." in header_html
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
