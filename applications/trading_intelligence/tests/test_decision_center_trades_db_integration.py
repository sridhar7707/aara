"""End-to-end integration test for the Decision Center's trades.db-snapshot
data flow:

    trades.db (real temp file)
            |
            v
    TradesDbDecisionReader
            |
    TradesDbDecisionSource / TradesDbEvidenceSource /
    TradesDbGovernanceSource / TradesDbAuditSource
            |
            v
    DecisionQueryService / DecisionEvidenceQueryService /
    DecisionGovernanceQueryService
            |
            v
    DecisionCenterController   (unchanged)
            |
            v
    DecisionCenterScreen       (unchanged)

Proves the trades-backed sources compose with the EXISTING, unmodified
query services / controller / screen -- no production code in that chain
was changed.
"""
import os
import sqlite3
import tempfile

import pytest

from applications.trading_intelligence.adapters.trades_db_decision_adapters import (
    TradesDbAuditSource,
    TradesDbDecisionSource,
    TradesDbEvidenceSource,
    TradesDbGovernanceSource,
)
from applications.trading_intelligence.adapters.trades_db_decision_source import (
    TradesDbDecisionReader,
)
from applications.trading_intelligence.projections.decision_view import DecisionState
from applications.trading_intelligence.services.decision_evidence_query_service import (
    DecisionEvidenceQueryService,
)
from applications.trading_intelligence.services.decision_governance_query_service import (
    DecisionGovernanceQueryService,
)
from applications.trading_intelligence.services.decision_query_service import DecisionQueryService
from applications.trading_intelligence.ui.decision_center.controller import DecisionCenterController
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
)
"""
_COLS = (
    "id", "timestamp", "symbol", "action", "ensemble_score", "xgb_prob",
    "lstm_prob", "sentiment_score", "macro_score", "regime", "stop_loss",
    "take_profit", "risk_reward_ratio", "feature_drivers", "ai_reasoning",
)


def _insert(conn, **over):
    row = dict(
        id=None, timestamp="2026-09-02T14:39:08", symbol="AAPL", action="BUY",
        ensemble_score=0.61, xgb_prob=0.6, lstm_prob=0.55, sentiment_score=0.1,
        macro_score=0.5, regime="NORMAL", stop_loss=None, take_profit=None,
        risk_reward_ratio=None, feature_drivers=None, ai_reasoning=None,
    )
    row.update(over)
    conn.execute(
        f"INSERT INTO trades ({', '.join(_COLS)}) VALUES ({', '.join('?' for _ in _COLS)})",
        tuple(row[c] for c in _COLS),
    )


def _db(populate):
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(_DDL)
    populate(conn)
    conn.commit()
    conn.close()
    return path


def _controller(db_path):
    reader = TradesDbDecisionReader(db_path=db_path)
    return DecisionCenterController(
        DecisionQueryService(TradesDbDecisionSource(reader)),
        DecisionEvidenceQueryService(TradesDbEvidenceSource(reader)),
        DecisionGovernanceQueryService(TradesDbGovernanceSource(reader)),
        TradesDbAuditSource(reader),
    )


def _seed_trade_45(conn):
    _insert(
        conn, id=45, timestamp="2026-09-02T14:39:08", symbol="SLB", action="BUY",
        ensemble_score=0.5222, xgb_prob=0.5385, lstm_prob=0.4375,
        sentiment_score=0.0936, macro_score=0.6403, regime="HIGH_VOLATILITY",
        stop_loss=53.2437, take_profit=65.1426, risk_reward_ratio=2.0,
        feature_drivers='{"momentum": 0.41}',
        ai_reasoning="Ensemble cleared the BUY threshold.",
    )


@pytest.fixture
def trade_45_db():
    path = _db(_seed_trade_45)
    yield path
    os.remove(path)


def test_empty_db_produces_an_empty_screen():
    def populate(conn):
        _insert(conn, id=1, action="SELL_RECONCILE")

    path = _db(populate)
    try:
        controller = _controller(path)
        screen = controller.load_screen([])
        assert screen.list_area.is_empty is True
        assert screen.list_area.empty_state_message == "No decisions recorded yet."
        assert screen.detail_area.is_empty is True
    finally:
        os.remove(path)


def test_trade_45_produces_a_complete_screen(trade_45_db):
    controller = _controller(trade_45_db)
    screen = controller.load_screen(["trade-45"])

    assert [d.decision_id for d in screen.list_area.decisions] == ["trade-45"]

    detail = screen.detail_area
    assert detail.decision.symbol == "SLB"
    assert detail.decision.status is DecisionState.EVIDENCE_ATTACHED
    assert detail.confidence_display == "52%"
    assert detail.status_display == "Evidence Attached"
    assert detail.timestamp_display == "2026-09-02 09:39 CDT"

    assert [e.evidence_type for e in detail.evidence] == [
        "MODEL_ENSEMBLE", "FEATURE_DRIVERS", "AI_RATIONALE",
    ]
    assert detail.evidence_status is ReadStatus.OK
    assert [g.policy_id for g in detail.governance] == ["BUY_THRESHOLD"]
    assert detail.governance_status is ReadStatus.OK
    assert detail.approvals == ()
    assert detail.approvals_status is ReadStatus.OK
    assert len(detail.audit_trail) == 1
    assert detail.audit_trail_status is ReadStatus.OK
    assert detail.evidence_reference == ""
    assert detail.risk_reference == ""


def test_multiple_decisions_listed_newest_first():
    def populate(conn):
        _insert(conn, id=10, symbol="AAA", action="BUY", ensemble_score=0.6)
        _insert(conn, id=20, symbol="BBB", action="BUY", ensemble_score=0.6)
        _insert(conn, id=30, symbol="CCC", action="BUY", ensemble_score=0.6)

    path = _db(populate)
    try:
        controller = _controller(path)
        screen = controller.load_screen(["trade-30", "trade-20", "trade-10"])
        assert [d.decision_id for d in screen.list_area.decisions] == [
            "trade-30", "trade-20", "trade-10",
        ]
        assert screen.detail_area.decision.decision_id == "trade-30"
    finally:
        os.remove(path)


def test_middle_row_selection_loads_that_decision():
    def populate(conn):
        _insert(conn, id=10, symbol="AAA", action="BUY", ensemble_score=0.6)
        _insert(conn, id=20, symbol="BBB", action="BUY", ensemble_score=0.6)
        _insert(conn, id=30, symbol="CCC", action="BUY", ensemble_score=0.6)

    path = _db(populate)
    try:
        controller = _controller(path)
        ids = ["trade-30", "trade-20", "trade-10"]
        screen = controller.load_screen(ids, selected_id="trade-20")
        assert screen.detail_area.decision.decision_id == "trade-20"
        assert screen.detail_area.decision.symbol == "BBB"
    finally:
        os.remove(path)


def test_explicit_selection_loads_that_decision():
    def populate(conn):
        _seed_trade_45(conn)
        _insert(conn, id=40, symbol="TSLA", action="BUY", ensemble_score=0.7)

    path = _db(populate)
    try:
        controller = _controller(path)
        screen = controller.load_screen(["trade-45", "trade-40"], selected_id="trade-40")
        assert screen.detail_area.decision.decision_id == "trade-40"
        assert screen.detail_area.decision.symbol == "TSLA"
    finally:
        os.remove(path)


def test_stale_selection_id_is_a_clean_miss(trade_45_db):
    controller = _controller(trade_45_db)
    detail = controller.load_decision_detail("trade-9999")
    assert detail.decision is None
    assert detail.decision_status is ReadStatus.OK


def test_malformed_row_reports_a_decision_read_error():
    def populate(conn):
        conn.execute(
            "INSERT INTO trades (id, timestamp, symbol, action, ensemble_score) "
            "VALUES (5, '2026-09-02T00:00:00', 'IBM', 'BUY', 'bogus')"
        )

    path = _db(populate)
    try:
        detail = _controller(path).load_decision_detail("trade-5")
        assert detail.decision is None
        assert detail.decision_status is ReadStatus.ERROR
    finally:
        os.remove(path)


def test_unparseable_timestamp_reports_a_decision_read_error():
    def populate(conn):
        _insert(conn, id=6, symbol="IBM", action="BUY", timestamp="never", ensemble_score=0.6)

    path = _db(populate)
    try:
        detail = _controller(path).load_decision_detail("trade-6")
        assert detail.decision is None
        assert detail.decision_status is ReadStatus.ERROR
    finally:
        os.remove(path)


def test_row_missing_rationale_and_drivers_still_renders(trade_45_db):
    """An older BUY with NULL feature_drivers / ai_reasoning: decision +
    model evidence + governance still render; no fabricated content."""
    def populate(conn):
        _insert(
            conn, id=11, symbol="F", action="BUY", ensemble_score=0.53,
            xgb_prob=0.0, lstm_prob=0.0, sentiment_score=0.0, macro_score=0.0,
            regime=None, feature_drivers=None, ai_reasoning=None,
        )

    path = _db(populate)
    try:
        detail = _controller(path).load_decision_detail("trade-11")
        assert detail.decision.symbol == "F"
        assert [e.evidence_type for e in detail.evidence] == ["MODEL_ENSEMBLE"]
        assert [g.policy_id for g in detail.governance] == ["BUY_THRESHOLD"]
        assert detail.approvals == ()
        assert detail.evidence_status is ReadStatus.OK
    finally:
        os.remove(path)


def _three_buy_db():
    def populate(conn):
        _insert(conn, id=10, symbol="AAA", action="BUY", ensemble_score=0.6)
        _insert(conn, id=20, symbol="BBB", action="BUY", ensemble_score=0.6)
        _insert(conn, id=30, symbol="CCC", action="BUY", ensemble_score=0.6)

    return _db(populate)


def test_ui_seeded_with_real_ids_renders_newest_first_and_default_selection():
    """TASK 3: the EXISTING selection mechanism (unchanged _render_screen /
    _render_detail / _on_row_select / row-id column) works when seeded with
    the real trade-* id list."""
    path = _three_buy_db()
    try:
        ui = DecisionCenterUI(_controller(path), ["trade-30", "trade-20", "trade-10"])
        rendered = ui._render_screen()
        list_rows = rendered[0]
        assert [r[0] for r in list_rows] == ["trade-30", "trade-20", "trade-10"]
        # default selection is the newest row -> its detail names CCC
        assert any("CCC" in cell for cell in rendered if isinstance(cell, str))
    finally:
        os.remove(path)


def test_ui_render_detail_for_a_specific_row_id_loads_that_decision():
    path = _three_buy_db()
    try:
        ui = DecisionCenterUI(_controller(path), ["trade-30", "trade-20", "trade-10"])
        detail_values = ui._render_detail("trade-20")
        assert any("BBB" in v for v in detail_values if isinstance(v, str))
    finally:
        os.remove(path)


def test_ui_with_no_buy_rows_renders_the_empty_state():
    def populate(conn):
        _insert(conn, id=1, action="SELL")

    path = _db(populate)
    try:
        ui = DecisionCenterUI(_controller(path), [])
        rendered = ui._render_screen()
        assert rendered[0] == []
        assert "No decisions recorded yet." in rendered[1]
    finally:
        os.remove(path)


def test_the_trades_db_file_is_not_written_to(trade_45_db):
    before = os.stat(trade_45_db)
    controller = _controller(trade_45_db)
    controller.load_screen(["trade-45"], selected_id="trade-45")
    controller.load_decisions(["trade-45"])
    controller.load_decision_detail("trade-45")
    after = os.stat(trade_45_db)
    assert (before.st_size, before.st_mtime) == (after.st_size, after.st_mtime)
