"""Tests for applications.trading_intelligence.adapters.legacy_earnings_source.

Mirrors legacy_news_cache_source.py's/legacy_risk_state_source.py's own
precedent: a new, additive module may open its own SQLite connection to
trades.db and SELECT from an existing table (here, earnings_cache --
written by bot/_main_market.py), provided it never imports
bot.*/dashboard.*/database.*/scheduler.*/ledger.*, never writes, and
never touches any ADR-002-protected file.
"""
import ast
import inspect
import os
import sqlite3
import tempfile

import pytest

from applications.platform.integrations import IntegrationStatus, ReadResult
from applications.trading_intelligence.adapters.legacy_earnings_source import (
    EarningsSnapshot,
    LegacyEarningsSource,
)


def _healthy_value(result):
    assert isinstance(result, ReadResult)
    assert result.health.status is IntegrationStatus.HEALTHY
    return result.value


def _create_earnings_cache_db(rows):
    """A real, temporary SQLite file with a populated earnings_cache
    table, matching bot/_main_market.py's own DDL -- not a mock of
    sqlite3."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE earnings_cache (symbol TEXT PRIMARY KEY, "
        "near_earnings INTEGER, cached_at TEXT)"
    )
    for symbol, near_earnings, cached_at in rows:
        conn.execute(
            "INSERT INTO earnings_cache VALUES (?, ?, ?)",
            (symbol, near_earnings, cached_at),
        )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def populated_db():
    path = _create_earnings_cache_db([
        ("AVGO", 1, "2026-09-01T16:41:57.317837+00:00"),
        ("AAPL", 0, "2026-09-01T16:41:57.317837+00:00"),
    ])
    yield path
    os.remove(path)


@pytest.fixture
def empty_earnings_cache_db():
    path = _create_earnings_cache_db([])
    yield path
    os.remove(path)


@pytest.fixture
def missing_table_db():
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE unrelated_table (id INTEGER)")
    conn.commit()
    conn.close()
    yield path
    os.remove(path)


def test_get_snapshot_returns_the_matching_row_near_earnings(populated_db):
    source = LegacyEarningsSource(db_path=populated_db)

    snapshot = _healthy_value(source.get_snapshot("AVGO"))

    assert snapshot == EarningsSnapshot(
        symbol="AVGO",
        near_earnings=True,
        cached_at="2026-09-01T16:41:57.317837+00:00",
    )


def test_get_snapshot_returns_the_matching_row_not_near_earnings(populated_db):
    source = LegacyEarningsSource(db_path=populated_db)

    snapshot = _healthy_value(source.get_snapshot("AAPL"))

    assert snapshot == EarningsSnapshot(
        symbol="AAPL",
        near_earnings=False,
        cached_at="2026-09-01T16:41:57.317837+00:00",
    )


def test_get_snapshot_is_healthy_empty_when_symbol_not_cached(populated_db):
    source = LegacyEarningsSource(db_path=populated_db)

    result = source.get_snapshot("GOOG")

    assert result.value is None
    assert result.health.status is IntegrationStatus.HEALTHY


def test_get_snapshot_is_healthy_empty_when_table_has_no_rows(empty_earnings_cache_db):
    source = LegacyEarningsSource(db_path=empty_earnings_cache_db)

    result = source.get_snapshot("AAPL")

    assert result.value is None
    assert result.health.status is IntegrationStatus.HEALTHY


def test_get_snapshot_is_api_error_when_table_is_missing(missing_table_db):
    source = LegacyEarningsSource(db_path=missing_table_db)

    result = source.get_snapshot("AAPL")

    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


def test_get_snapshot_is_unavailable_when_database_file_is_missing():
    source = LegacyEarningsSource(db_path="this_file_does_not_exist_xyz_12345.db")

    result = source.get_snapshot("AAPL")

    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_module_imports_no_protected_package():
    """AST-level regression lock: this adapter must never import bot,
    dashboard, database, scheduler, or ledger."""
    import applications.trading_intelligence.adapters.legacy_earnings_source as module

    source = inspect.getsource(module)
    tree = ast.parse(source)
    forbidden = ("bot", "dashboard", "database", "scheduler", "ledger")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), f"forbidden import {alias.name!r}"
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.startswith(forbidden), f"forbidden import from {module_name!r}"


def test_module_never_executes_a_write_statement():
    import applications.trading_intelligence.adapters.legacy_earnings_source as module

    source = inspect.getsource(module)
    for forbidden_sql in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "):
        assert forbidden_sql not in source.upper(), (
            f"adapter source must never contain a {forbidden_sql.strip()} statement"
        )
