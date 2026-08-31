"""Tests for applications.trading_intelligence.adapters.legacy_capital_source."""
import ast
import inspect
import os
import sqlite3
import tempfile

import pytest

from applications.platform.integrations import IntegrationStatus, ReadResult
from applications.trading_intelligence.adapters.legacy_capital_source import LegacyCapitalSource
from applications.trading_intelligence.ui.portfolio_intelligence.screen import CapitalSummary


@pytest.fixture
def capital_pools_db():
    """A real, temporary SQLite file with a populated capital_pools table,
    matching bot/capital/pool.py's own DDL -- not a mock of sqlite3, a real
    file this adapter reads exactly as it would read trades.db."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE capital_pools ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, status TEXT, "
        "allocated_amount REAL, available_cash REAL, invested_amount REAL, "
        "reserve REAL, realized_profit REAL, profit_withdrawn REAL)"
    )
    conn.execute(
        "INSERT INTO capital_pools "
        "(name, status, allocated_amount, available_cash, invested_amount, reserve, realized_profit) "
        "VALUES ('default', 'active', 50000.0, 12000.0, 38000.0, 1000.0, 2500.0)"
    )
    conn.commit()
    conn.close()
    yield path
    os.remove(path)


@pytest.fixture
def empty_db():
    """A real, temporary SQLite file with no capital_pools table at all."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE unrelated_table (id INTEGER)")
    conn.commit()
    conn.close()
    yield path
    os.remove(path)


def test_get_capital_summary_is_healthy_with_a_real_row(capital_pools_db):
    source = LegacyCapitalSource(db_path=capital_pools_db)

    result = source.get_capital_summary()

    assert isinstance(result, ReadResult)
    assert result.health.status is IntegrationStatus.HEALTHY
    assert result.value == CapitalSummary(
        allocated_amount=50000.0, available_cash=12000.0, invested_amount=38000.0,
        reserve=1000.0, realized_profit=2500.0,
    )


def test_get_capital_summary_is_api_error_when_table_is_missing(empty_db):
    source = LegacyCapitalSource(db_path=empty_db)

    result = source.get_capital_summary()
    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


def test_get_capital_summary_is_unavailable_when_database_file_is_missing():
    source = LegacyCapitalSource(db_path="this_file_does_not_exist_xyz_12345.db")

    result = source.get_capital_summary()
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_get_capital_summary_is_healthy_empty_when_no_active_pool_row_exists():
    """A table that exists but holds no active pool row is a genuine
    "nothing recorded" state -- HEALTHY with value=None -- distinct from
    the file or table being absent."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE capital_pools (id INTEGER, name TEXT, status TEXT, "
        "allocated_amount REAL, available_cash REAL, invested_amount REAL, "
        "reserve REAL, realized_profit REAL)"
    )
    conn.execute(
        "INSERT INTO capital_pools VALUES (1, 'default', 'closed', 1.0, 1.0, 1.0, 1.0, 1.0)"
    )
    conn.commit()
    conn.close()
    try:
        source = LegacyCapitalSource(db_path=path)
        result = source.get_capital_summary()
        assert result.value is None
        assert result.health.status is IntegrationStatus.HEALTHY
    finally:
        os.remove(path)


def test_module_imports_no_protected_package():
    """AST-level regression lock: this adapter must never import bot,
    dashboard, database, or scheduler -- the whole point of duplicating
    the trivial SELECT here instead of importing bot.capital.pool."""
    import applications.trading_intelligence.adapters.legacy_capital_source as module

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
    """Regression lock, matching this product's other adapters' own
    'never calls a write operation' tests: grep the adapter's own source
    for any SQL write keyword rather than trusting a runtime mock, since
    the whole risk here is a stray INSERT/UPDATE/DELETE against a real
    production file."""
    import applications.trading_intelligence.adapters.legacy_capital_source as module

    source = inspect.getsource(module)
    for forbidden_sql in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "):
        assert forbidden_sql not in source.upper(), (
            f"adapter source must never contain a {forbidden_sql.strip()} statement"
        )
