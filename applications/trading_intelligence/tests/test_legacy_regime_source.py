"""Tests for applications.trading_intelligence.adapters.legacy_regime_source."""
import ast
import inspect
import os
import sqlite3
import tempfile

import pytest

from applications.trading_intelligence.adapters.legacy_regime_source import LegacyRegimeSource


@pytest.fixture
def signal_log_db():
    """A real, temporary SQLite file with a populated signal_log table,
    matching bot/_main_db.py's own DDL -- not a mock of sqlite3, a real
    file this adapter reads exactly as it would read trades.db."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE signal_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, "
        "symbol TEXT NOT NULL, xgb_prob REAL, lstm_prob REAL, "
        "sentiment_score REAL, macro_score REAL, ensemble_score REAL, "
        "ensemble_action TEXT, regime TEXT)"
    )
    conn.execute(
        "INSERT INTO signal_log (timestamp, symbol, ensemble_action, regime) "
        "VALUES ('2026-08-20T15:03:38+00:00', 'XLC', 'HOLD', 'HIGH_VOLATILITY')"
    )
    conn.execute(
        "INSERT INTO signal_log (timestamp, symbol, ensemble_action, regime) "
        "VALUES ('2026-08-21T09:00:00+00:00', 'AAPL', 'BUY', 'TRENDING_UP')"
    )
    conn.commit()
    conn.close()
    yield path
    os.remove(path)


@pytest.fixture
def empty_db():
    """A real, temporary SQLite file with no signal_log table at all."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE unrelated_table (id INTEGER)")
    conn.commit()
    conn.close()
    yield path
    os.remove(path)


def test_get_latest_regime_returns_the_most_recently_inserted_row(signal_log_db):
    source = LegacyRegimeSource(db_path=signal_log_db)

    assert source.get_latest_regime() == "TRENDING_UP"


def test_get_latest_regime_returns_none_when_table_is_missing(empty_db):
    source = LegacyRegimeSource(db_path=empty_db)

    assert source.get_latest_regime() is None


def test_get_latest_regime_returns_none_when_database_file_is_missing():
    source = LegacyRegimeSource(db_path="this_file_does_not_exist_xyz_12345.db")

    assert source.get_latest_regime() is None


def test_get_latest_regime_returns_none_when_table_is_empty():
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE signal_log (id INTEGER, timestamp TEXT, symbol TEXT, "
        "xgb_prob REAL, lstm_prob REAL, sentiment_score REAL, macro_score REAL, "
        "ensemble_score REAL, ensemble_action TEXT, regime TEXT)"
    )
    conn.commit()
    conn.close()
    try:
        source = LegacyRegimeSource(db_path=path)
        assert source.get_latest_regime() is None
    finally:
        os.remove(path)


def test_get_latest_regime_returns_none_when_regime_is_null():
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE signal_log (id INTEGER, timestamp TEXT, symbol TEXT, "
        "xgb_prob REAL, lstm_prob REAL, sentiment_score REAL, macro_score REAL, "
        "ensemble_score REAL, ensemble_action TEXT, regime TEXT)"
    )
    conn.execute(
        "INSERT INTO signal_log (id, timestamp, symbol, regime) "
        "VALUES (1, '2026-08-20T00:00:00+00:00', 'AAPL', NULL)"
    )
    conn.commit()
    conn.close()
    try:
        source = LegacyRegimeSource(db_path=path)
        assert source.get_latest_regime() is None
    finally:
        os.remove(path)


def test_get_latest_regime_returns_none_when_regime_is_empty_string():
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE signal_log (id INTEGER, timestamp TEXT, symbol TEXT, "
        "xgb_prob REAL, lstm_prob REAL, sentiment_score REAL, macro_score REAL, "
        "ensemble_score REAL, ensemble_action TEXT, regime TEXT)"
    )
    conn.execute(
        "INSERT INTO signal_log (id, timestamp, symbol, regime) "
        "VALUES (1, '2026-08-20T00:00:00+00:00', 'AAPL', '')"
    )
    conn.commit()
    conn.close()
    try:
        source = LegacyRegimeSource(db_path=path)
        assert source.get_latest_regime() is None
    finally:
        os.remove(path)


def test_module_imports_no_protected_package():
    """AST-level regression lock: this adapter must never import bot,
    dashboard, database, or scheduler -- the whole point of duplicating
    the trivial SELECT here instead of importing bot's own signal-log
    writer."""
    import applications.trading_intelligence.adapters.legacy_regime_source as module

    source = inspect.getsource(module)
    tree = ast.parse(source)
    forbidden = ("bot", "dashboard", "database", "scheduler")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), (
                    f"forbidden import {alias.name!r}"
                )
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.startswith(forbidden), (
                f"forbidden import from {module_name!r}"
            )


def test_module_never_executes_a_write_statement():
    """Regression lock, matching legacy_capital_source.py's own
    'never executes a write statement' test: grep the adapter's own
    source for any SQL write keyword rather than trusting a runtime mock,
    since the whole risk here is a stray INSERT/UPDATE/DELETE against a
    real production file."""
    import applications.trading_intelligence.adapters.legacy_regime_source as module

    source = inspect.getsource(module)
    for forbidden_sql in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "):
        assert forbidden_sql not in source.upper(), (
            f"adapter source must never contain a {forbidden_sql.strip()} statement"
        )
