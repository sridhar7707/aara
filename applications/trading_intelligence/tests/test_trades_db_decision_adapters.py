"""Tests for applications.trading_intelligence.adapters.trades_db_decision_adapters.

The four trades-backed read sources, exercised against a real temporary
SQLite file through a real TradesDbDecisionReader.
"""
import ast
import inspect
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
from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.decision_view import DecisionState

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
_FEATURE_DRIVERS = '{"momentum": 0.41, "trend": "up"}'
_AI_REASONING = "Ensemble cleared the BUY threshold on strengthening momentum."


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


@pytest.fixture
def reader():
    def populate(conn):
        _insert(
            conn, id=45, timestamp="2026-09-02T14:39:08", symbol="SLB", action="BUY",
            ensemble_score=0.5222, xgb_prob=0.5385, lstm_prob=0.4375,
            sentiment_score=0.0936, macro_score=0.6403, regime="HIGH_VOLATILITY",
            stop_loss=53.2437, take_profit=65.1426, risk_reward_ratio=2.0,
            feature_drivers=_FEATURE_DRIVERS, ai_reasoning=_AI_REASONING,
        )
        _insert(conn, id=40, symbol="TSLA", action="BUY", ensemble_score=0.7)
        _insert(conn, id=39, symbol="SLB", action="SELL_RECONCILE")

    path = _db(populate)
    yield TradesDbDecisionReader(db_path=path)
    os.remove(path)


@pytest.fixture
def missing_reader():
    return TradesDbDecisionReader(db_path="no_such_trades_file_abc_987.db")


# -- TradesDbDecisionSource -------------------------------------------------

def test_get_decision_maps_trade_45(reader):
    contract = TradesDbDecisionSource(reader).get_decision("trade-45")
    assert isinstance(contract, DecisionContract)
    assert contract.decision_id == "trade-45"
    assert contract.symbol == "SLB"
    assert contract.action == "BUY"
    assert contract.status is DecisionState.EVIDENCE_ATTACHED
    assert contract.confidence == 0.5222
    assert contract.evidence_reference == ""
    assert contract.risk_reference == ""
    assert contract.approval_status is None


def test_get_decision_unknown_id_returns_none(reader):
    assert TradesDbDecisionSource(reader).get_decision("trade-9999") is None


def test_get_decision_sell_id_returns_none(reader):
    assert TradesDbDecisionSource(reader).get_decision("trade-39") is None


def test_get_decision_raises_read_error_when_source_unavailable(missing_reader):
    with pytest.raises(TradingIntelligenceReadError):
        TradesDbDecisionSource(missing_reader).get_decision("trade-45")


def test_get_decision_raises_read_error_on_malformed_row():
    def populate(conn):
        conn.execute(
            "INSERT INTO trades (id, timestamp, symbol, action, ensemble_score) "
            "VALUES (5, '2026-09-02T00:00:00', 'IBM', 'BUY', 'bogus')"
        )

    path = _db(populate)
    try:
        with pytest.raises(TradingIntelligenceReadError):
            TradesDbDecisionSource(TradesDbDecisionReader(db_path=path)).get_decision("trade-5")
    finally:
        os.remove(path)


def test_get_decision_raises_read_error_on_unparseable_timestamp():
    def populate(conn):
        _insert(conn, id=6, symbol="IBM", action="BUY", timestamp="never", ensemble_score=0.6)

    path = _db(populate)
    try:
        with pytest.raises(TradingIntelligenceReadError):
            TradesDbDecisionSource(TradesDbDecisionReader(db_path=path)).get_decision("trade-6")
    finally:
        os.remove(path)


def test_list_decisions_preserves_order(reader):
    contracts = TradesDbDecisionSource(reader).list_decisions(["trade-45", "trade-40"])
    assert [c.decision_id for c in contracts] == ["trade-45", "trade-40"]


def test_list_decisions_returns_empty_list_when_source_unavailable(missing_reader):
    assert TradesDbDecisionSource(missing_reader).list_decisions(["trade-45"]) == []


# -- TradesDbEvidenceSource ----------------------------------------------

def test_get_evidence_trade_45(reader):
    entries = TradesDbEvidenceSource(reader).get_evidence("trade-45")
    assert [e.evidence_type for e in entries] == [
        "MODEL_ENSEMBLE", "FEATURE_DRIVERS", "AI_RATIONALE",
    ]


def test_get_evidence_unknown_id_is_empty(reader):
    assert TradesDbEvidenceSource(reader).get_evidence("trade-9999") == []


def test_get_evidence_raises_read_error_when_unavailable(missing_reader):
    with pytest.raises(TradingIntelligenceReadError):
        TradesDbEvidenceSource(missing_reader).get_evidence("trade-45")


# -- TradesDbGovernanceSource ------------------------------------------

def test_get_governance_trade_45(reader):
    entries = TradesDbGovernanceSource(reader).get_governance("trade-45")
    assert [g.policy_id for g in entries] == ["BUY_THRESHOLD"]
    assert entries[0].enabled is True


def test_get_approvals_is_always_empty(reader):
    assert TradesDbGovernanceSource(reader).get_approvals("trade-45") == []


def test_get_governance_raises_read_error_when_unavailable(missing_reader):
    with pytest.raises(TradingIntelligenceReadError):
        TradesDbGovernanceSource(missing_reader).get_governance("trade-45")


def test_get_approvals_unknown_id_is_empty(reader):
    assert TradesDbGovernanceSource(reader).get_approvals("trade-9999") == []


# -- TradesDbAuditSource --------------------------------------------------

def test_get_audit_trail_trade_45(reader):
    entries = TradesDbAuditSource(reader).get_audit_trail("trade-45")
    assert len(entries) == 1
    assert entries[0].event_type == "DECISION_CREATED"
    assert "decision_id" not in entries[0].payload


def test_get_audit_trail_unknown_id_is_empty(reader):
    assert TradesDbAuditSource(reader).get_audit_trail("trade-9999") == []


def test_get_audit_trail_raises_read_error_when_unavailable(missing_reader):
    with pytest.raises(TradingIntelligenceReadError):
        TradesDbAuditSource(missing_reader).get_audit_trail("trade-45")


# -- structural --------------------------------------------------------

def test_module_imports_no_protected_package():
    import applications.trading_intelligence.adapters.trades_db_decision_adapters as module

    tree = ast.parse(inspect.getsource(module))
    forbidden = ("bot", "dashboard", "database", "scheduler", "ledger", "sentinel_engine")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), f"forbidden import {alias.name!r}"
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.startswith(forbidden), (
                f"forbidden import from {module_name!r}"
            )
