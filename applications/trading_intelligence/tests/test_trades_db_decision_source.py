"""Tests for applications.trading_intelligence.adapters.trades_db_decision_source.

Every fixture is a real, temporary SQLite file whose ``trades`` table
matches bot/_main_db.py's own DDL -- never a mock of sqlite3.
"""
import ast
import inspect
import os
import sqlite3
import tempfile

import pytest

from applications.platform.integrations import IntegrationStatus, ReadResult
from applications.trading_intelligence.adapters.trades_db_decision_source import (
    TradesDbDecisionReader,
)
from applications.trading_intelligence.projections.trade_decision_row import (
    TradeDecisionRow,
)

_TRADES_DDL = """
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT, symbol TEXT, action TEXT,
    shares REAL, price REAL, notional REAL,
    regime TEXT, portfolio_value REAL, pnl_pct REAL,
    xgb_prob REAL DEFAULT 0.0, lstm_prob REAL DEFAULT 0.0,
    sentiment_score REAL DEFAULT 0.0, macro_score REAL DEFAULT 0.0,
    ensemble_score REAL DEFAULT 0.0, realized_pnl REAL DEFAULT 0.0,
    order_id TEXT DEFAULT NULL, holding_days INTEGER DEFAULT 0,
    feature_drivers TEXT DEFAULT NULL, ai_reasoning TEXT DEFAULT NULL,
    stop_loss REAL DEFAULT NULL, take_profit REAL DEFAULT NULL,
    risk_reward_ratio REAL DEFAULT NULL
)
"""

_TRADE_45_FEATURE_DRIVERS = (
    '{"momentum": 0.41, "trend": "up", "rsi": 55.2, "notes": "breakout"}'
)
_TRADE_45_AI_REASONING = (
    "Ensemble cleared the BUY threshold on strengthening momentum; "
    "macro backdrop supportive despite elevated volatility."
)

_INSERT_COLUMNS = (
    "id", "timestamp", "symbol", "action", "ensemble_score", "xgb_prob",
    "lstm_prob", "sentiment_score", "macro_score", "regime", "stop_loss",
    "take_profit", "risk_reward_ratio", "feature_drivers", "ai_reasoning",
)


def _insert_trade(conn, **overrides):
    row = dict(
        id=None, timestamp="2026-09-02T14:39:08", symbol="AAPL", action="BUY",
        ensemble_score=0.61, xgb_prob=0.6, lstm_prob=0.55, sentiment_score=0.1,
        macro_score=0.5, regime="NORMAL", stop_loss=None, take_profit=None,
        risk_reward_ratio=None, feature_drivers=None, ai_reasoning=None,
    )
    row.update(overrides)
    placeholders = ", ".join("?" for _ in _INSERT_COLUMNS)
    conn.execute(
        f"INSERT INTO trades ({', '.join(_INSERT_COLUMNS)}) VALUES ({placeholders})",
        tuple(row[c] for c in _INSERT_COLUMNS),
    )


def _make_db(populate=None, *, with_trades_table=True):
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    if with_trades_table:
        conn.execute(_TRADES_DDL)
    else:
        conn.execute("CREATE TABLE unrelated (id INTEGER)")
    if populate is not None:
        populate(conn)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def trade_45_db():
    def populate(conn):
        _insert_trade(
            conn, id=45, timestamp="2026-09-02T14:39:08", symbol="SLB", action="BUY",
            ensemble_score=0.5222, xgb_prob=0.5385, lstm_prob=0.4375,
            sentiment_score=0.0936, macro_score=0.6403, regime="HIGH_VOLATILITY",
            stop_loss=53.2437, take_profit=65.1426, risk_reward_ratio=2.0,
            feature_drivers=_TRADE_45_FEATURE_DRIVERS, ai_reasoning=_TRADE_45_AI_REASONING,
        )
        _insert_trade(conn, id=44, symbol="SLB", action="SELL")
        _insert_trade(conn, id=43, symbol="AAPL", action="SELL_STOP")
        _insert_trade(conn, id=42, symbol="MSFT", action="SELL_RECONCILE")
        _insert_trade(conn, id=41, symbol="NVDA", action="SELL_TIME_EXIT")
        _insert_trade(conn, id=40, symbol="TSLA", action="BUY", ensemble_score=0.7)

    path = _make_db(populate)
    yield path
    os.remove(path)


def test_list_decision_ids_returns_only_buy_ids_newest_first(trade_45_db):
    result = TradesDbDecisionReader(db_path=trade_45_db).list_decision_ids()

    assert result.health.status is IntegrationStatus.HEALTHY
    assert result.value == ("trade-45", "trade-40")


def test_get_row_returns_verbatim_fields_for_trade_45(trade_45_db):
    result = TradesDbDecisionReader(db_path=trade_45_db).get_row("trade-45")

    assert result.health.status is IntegrationStatus.HEALTHY
    row = result.value
    assert row == TradeDecisionRow(
        trade_id=45,
        timestamp="2026-09-02T14:39:08",
        symbol="SLB",
        action="BUY",
        ensemble_score=0.5222,
        xgb_prob=0.5385,
        lstm_prob=0.4375,
        sentiment_score=0.0936,
        macro_score=0.6403,
        regime="HIGH_VOLATILITY",
        stop_loss=53.2437,
        take_profit=65.1426,
        risk_reward_ratio=2.0,
        feature_drivers_raw=_TRADE_45_FEATURE_DRIVERS,
        ai_reasoning=_TRADE_45_AI_REASONING,
    )
    assert row.decision_id == "trade-45"


def test_get_row_does_not_parse_the_timestamp(trade_45_db):
    row = TradesDbDecisionReader(db_path=trade_45_db).get_row("trade-45").value
    assert isinstance(row.timestamp, str)
    assert row.timestamp == "2026-09-02T14:39:08"


@pytest.mark.parametrize("bad_id", ["garbage", "trade-", "trade-x", "trade--1", "45", ""])
def test_get_row_ill_formed_id_is_healthy_none(trade_45_db, bad_id):
    result = TradesDbDecisionReader(db_path=trade_45_db).get_row(bad_id)
    assert result.health.status is IntegrationStatus.HEALTHY
    assert result.value is None


def test_get_row_unknown_id_is_healthy_none(trade_45_db):
    result = TradesDbDecisionReader(db_path=trade_45_db).get_row("trade-9999")
    assert result.health.status is IntegrationStatus.HEALTHY
    assert result.value is None


def test_get_row_for_a_sell_trade_id_is_healthy_none(trade_45_db):
    """id 44 exists but its action is SELL -- the BUY-only filter must make
    it invisible here, not an error."""
    result = TradesDbDecisionReader(db_path=trade_45_db).get_row("trade-44")
    assert result.health.status is IntegrationStatus.HEALTHY
    assert result.value is None


def test_row_with_null_optional_fields_parses():
    def populate(conn):
        _insert_trade(
            conn, id=7, symbol="AMD", action="BUY", ensemble_score=None,
            xgb_prob=None, lstm_prob=None, sentiment_score=None, macro_score=None,
            regime=None, stop_loss=None, take_profit=None, risk_reward_ratio=None,
            feature_drivers=None, ai_reasoning=None,
        )

    path = _make_db(populate)
    try:
        row = TradesDbDecisionReader(db_path=path).get_row("trade-7").value
        assert row.trade_id == 7
        assert row.ensemble_score is None
        assert row.feature_drivers_raw is None
        assert row.ai_reasoning is None
        assert row.regime is None
    finally:
        os.remove(path)


def test_malformed_row_is_api_error():
    def populate(conn):
        conn.execute(
            "INSERT INTO trades (id, timestamp, symbol, action, ensemble_score) "
            "VALUES (8, '2026-09-02T00:00:00', 'IBM', 'BUY', 'not-a-number')"
        )

    path = _make_db(populate)
    try:
        result = TradesDbDecisionReader(db_path=path).get_row("trade-8")
        assert result.value is None
        assert result.health.status is IntegrationStatus.API_ERROR
    finally:
        os.remove(path)


def test_missing_file_is_unavailable_for_every_method():
    source = TradesDbDecisionReader(db_path="does_not_exist_trades_xyz_123.db")

    for result in (
        source.list_decision_ids(),
        source.get_row("trade-1"),
        source.list_rows(["trade-1"]),
    ):
        assert result.value is None
        assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_missing_trades_table_is_api_error():
    path = _make_db(with_trades_table=False)
    try:
        source = TradesDbDecisionReader(db_path=path)
        for result in (
            source.list_decision_ids(),
            source.get_row("trade-1"),
            source.list_rows(["trade-1"]),
        ):
            assert result.value is None
            assert result.health.status is IntegrationStatus.API_ERROR
    finally:
        os.remove(path)


def test_list_decision_ids_is_capped_at_50_newest_first():
    def populate(conn):
        for i in range(1, 61):
            _insert_trade(conn, id=i, symbol="AAA", action="BUY")

    path = _make_db(populate)
    try:
        result = TradesDbDecisionReader(db_path=path).list_decision_ids()
        assert result.health.status is IntegrationStatus.HEALTHY
        assert len(result.value) == 50
        assert result.value[0] == "trade-60"
        assert result.value[-1] == "trade-11"
    finally:
        os.remove(path)


def test_list_decision_ids_healthy_empty_when_no_buys():
    def populate(conn):
        _insert_trade(conn, id=1, action="SELL")
        _insert_trade(conn, id=2, action="SELL_RECONCILE")

    path = _make_db(populate)
    try:
        result = TradesDbDecisionReader(db_path=path).list_decision_ids()
        assert result.health.status is IntegrationStatus.HEALTHY
        assert result.value == ()
    finally:
        os.remove(path)


def test_list_rows_preserves_requested_order_and_skips_missing_or_ill_formed(trade_45_db):
    result = TradesDbDecisionReader(db_path=trade_45_db).list_rows(
        ["trade-40", "trade-9999", "garbage", "trade-45", "trade-44"]
    )

    assert result.health.status is IntegrationStatus.HEALTHY
    assert [r.decision_id for r in result.value] == ["trade-40", "trade-45"]


def test_list_rows_healthy_empty_list_for_no_matches(trade_45_db):
    result = TradesDbDecisionReader(db_path=trade_45_db).list_rows(["trade-9999"])
    assert result.health.status is IntegrationStatus.HEALTHY
    assert result.value == []


def test_returns_are_read_result_instances(trade_45_db):
    source = TradesDbDecisionReader(db_path=trade_45_db)
    assert isinstance(source.list_decision_ids(), ReadResult)
    assert isinstance(source.get_row("trade-45"), ReadResult)
    assert isinstance(source.list_rows(["trade-45"]), ReadResult)


def test_module_imports_no_protected_package():
    import applications.trading_intelligence.adapters.trades_db_decision_source as module

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


def test_module_never_executes_a_write_statement():
    import applications.trading_intelligence.adapters.trades_db_decision_source as module

    source = inspect.getsource(module).upper()
    for forbidden_sql in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "CREATE "):
        assert forbidden_sql not in source, (
            f"adapter source must never contain a {forbidden_sql.strip()} statement"
        )
