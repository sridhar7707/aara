"""Tests for adapters.trades_db_outcome_source.TradesDbOutcomeReader.

Every fixture is a real, temporary SQLite file whose ``trades`` table
matches bot/_main_db.py's own DDL -- never a mock of sqlite3.
"""
import os
import sqlite3
import tempfile

from applications.platform.integrations import IntegrationStatus, ReadResult
from applications.trading_intelligence.adapters.trades_db_outcome_source import (
    TradesDbOutcomeReader,
)
from applications.trading_intelligence.projections.trade_outcome_row import TradeOutcomeRow
from applications.trading_intelligence.services.decision_outcome_query_service import (
    TradeRowSource,
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

_INSERT_COLS = (
    "id", "timestamp", "symbol", "action", "shares", "price", "notional",
    "realized_pnl", "pnl_pct", "holding_days", "order_id", "ensemble_score",
    "regime",
)


def _insert(conn, **over):
    row = dict(
        id=None, timestamp="2026-07-01T00:00:00+00:00", symbol="AAA", action="BUY",
        shares=100.0, price=10.0, notional=1000.0, realized_pnl=0.0, pnl_pct=0.0,
        holding_days=0, order_id=None, ensemble_score=0.6, regime="RANGING",
    )
    row.update(over)
    placeholders = ", ".join("?" for _ in _INSERT_COLS)
    conn.execute(
        "INSERT INTO trades ({}) VALUES ({})".format(
            ", ".join(_INSERT_COLS), placeholders
        ),
        tuple(row[c] for c in _INSERT_COLS),
    )


def _make_db(populate=None, *, with_trades_table=True):
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    if with_trades_table:
        conn.executescript(_TRADES_DDL)
    else:
        conn.executescript("CREATE TABLE unrelated (id INTEGER)")
    if populate is not None:
        populate(conn)
    conn.commit()
    conn.close()
    return path


def test_healthy_read_returns_buy_and_sell_rows_oldest_first():
    def populate(conn):
        _insert(conn, id=5, symbol="AAA", action="BUY",
                timestamp="2026-07-01T00:00:00+00:00")
        _insert(conn, id=6, symbol="AAA", action="SELL_TIME_EXIT",
                timestamp="2026-07-10T00:00:00+00:00", order_id="ord-6",
                realized_pnl=12.5, pnl_pct=0.02, holding_days=9)
        _insert(conn, id=7, symbol="BBB", action="SELL_RECONCILE",
                timestamp="2026-07-05T00:00:00+00:00", order_id=None)
        _insert(conn, id=8, symbol="CCC", action="HOLD",
                timestamp="2026-07-02T00:00:00+00:00")

    path = _make_db(populate)
    try:
        result = TradesDbOutcomeReader(db_path=path).read_trade_rows()
        assert result.health.status is IntegrationStatus.HEALTHY
        assert [(r.id, r.action) for r in result.value] == [
            (5, "BUY"),
            (7, "SELL_RECONCILE"),
            (6, "SELL_TIME_EXIT"),
        ]  # HOLD excluded; ordered by (timestamp, id)
    finally:
        os.remove(path)


def test_columns_are_copied_verbatim_including_nulls():
    def populate(conn):
        _insert(
            conn, id=45, symbol="SLB", action="BUY",
            timestamp="2026-09-02T14:39:08+00:00", shares=139.7587, price=57.21,
            notional=7995.5968, realized_pnl=0.0, pnl_pct=0.0, holding_days=0,
            order_id="32d6cffe", ensemble_score=0.5222, regime="HIGH_VOLATILITY",
        )
        _insert(
            conn, id=46, symbol="SLB", action="SELL_RECONCILE",
            timestamp="2026-09-20T00:00:00+00:00", shares=139.7587, price=60.0,
            notional=8385.5, realized_pnl=390.0, pnl_pct=0.0489, holding_days=18,
            order_id=None, ensemble_score=None, regime=None,
        )

    path = _make_db(populate)
    try:
        rows = {r.id: r for r in TradesDbOutcomeReader(db_path=path).read_trade_rows().value}
        assert rows[45] == TradeOutcomeRow(
            id=45, timestamp="2026-09-02T14:39:08+00:00", symbol="SLB", action="BUY",
            shares=139.7587, price=57.21, notional=7995.5968, realized_pnl=0.0,
            pnl_pct=0.0, holding_days=0, order_id="32d6cffe", ensemble_score=0.5222,
            regime="HIGH_VOLATILITY",
        )
        assert rows[46].order_id is None
        assert rows[46].ensemble_score is None
        assert rows[46].regime is None
        assert rows[46].realized_pnl == 390.0
    finally:
        os.remove(path)


def test_empty_trades_table_is_healthy_empty_list():
    path = _make_db()
    try:
        result = TradesDbOutcomeReader(db_path=path).read_trade_rows()
        assert result.health.status is IntegrationStatus.HEALTHY
        assert result.value == []
    finally:
        os.remove(path)


def test_missing_file_is_unavailable():
    result = TradesDbOutcomeReader(db_path="no_such_trades_db_xyz.db").read_trade_rows()
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_missing_trades_table_is_api_error():
    path = _make_db(with_trades_table=False)
    try:
        result = TradesDbOutcomeReader(db_path=path).read_trade_rows()
        assert result.value is None
        assert result.health.status is IntegrationStatus.API_ERROR
    finally:
        os.remove(path)


def test_malformed_row_is_api_error():
    def populate(conn):
        conn.execute(
            "INSERT INTO trades (id, timestamp, symbol, action, shares) "
            "VALUES (8, '2026-09-02T00:00:00+00:00', 'IBM', 'BUY', 'not-a-number')"
        )

    path = _make_db(populate)
    try:
        result = TradesDbOutcomeReader(db_path=path).read_trade_rows()
        assert result.value is None
        assert result.health.status is IntegrationStatus.API_ERROR
    finally:
        os.remove(path)


def test_returns_a_read_result_and_reader_is_a_trade_row_source():
    path = _make_db()
    try:
        assert isinstance(
            TradesDbOutcomeReader(db_path=path).read_trade_rows(), ReadResult
        )
        assert issubclass(TradesDbOutcomeReader, TradeRowSource)
    finally:
        os.remove(path)


def test_module_never_executes_a_write_statement():
    import inspect

    import applications.trading_intelligence.adapters.trades_db_outcome_source as module

    src = inspect.getsource(module).upper()
    for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "CREATE "):
        assert forbidden not in src, "adapter must never contain {}".format(forbidden)
