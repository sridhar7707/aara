"""Tests for applications.trading_intelligence.adapters.legacy_news_cache_source.

Mirrors legacy_candidate_screening_source.py's own precedent: a new,
additive module may open its own SQLite connection to trades.db and SELECT
from an existing table (here, news_cache -- written by bot/strategy/
sentiment.py's NewsAPI L2 cache), provided it never imports bot.*/
dashboard.*/database.*/scheduler.*/ledger.*, never writes, and never
touches any ADR-002-protected file.
"""
import ast
import inspect
import json
import os
import sqlite3
import tempfile

import pytest

from applications.platform.integrations import IntegrationStatus, ReadResult
from applications.trading_intelligence.adapters.legacy_news_cache_source import (
    LegacyNewsCacheSource,
    NewsCacheSnapshot,
)


def _healthy_value(result):
    assert isinstance(result, ReadResult)
    assert result.health.status is IntegrationStatus.HEALTHY
    return result.value


def _create_news_cache_db(rows):
    """A real, temporary SQLite file with a populated news_cache table,
    matching bot/_main_db.py's own DDL exactly -- not a mock of sqlite3."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE news_cache (symbol TEXT, fetch_date TEXT, "
        "headlines_json TEXT, cached_at TEXT, PRIMARY KEY (symbol, fetch_date))"
    )
    for symbol, fetch_date, headlines, cached_at in rows:
        conn.execute(
            "INSERT INTO news_cache VALUES (?, ?, ?, ?)",
            (symbol, fetch_date, json.dumps(headlines), cached_at),
        )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def populated_db():
    path = _create_news_cache_db([
        ("AAPL", "2026-09-01", ["Stock rises on earnings"], "2026-09-01T08:30:00"),
        ("AAPL", "2026-09-02", ["Stock rises on earnings", "New product announced"], "2026-09-02T08:31:00"),
        ("MSFT", "2026-09-01", ["Cloud revenue grows"], "2026-09-01T08:32:00"),
    ])
    yield path
    os.remove(path)


@pytest.fixture
def empty_news_cache_db():
    path = _create_news_cache_db([])
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


def test_get_snapshot_returns_the_matching_row(populated_db):
    source = LegacyNewsCacheSource(db_path=populated_db)

    snapshot = _healthy_value(source.get_snapshot("AAPL", "2026-09-02"))

    assert snapshot == NewsCacheSnapshot(
        symbol="AAPL",
        fetch_date="2026-09-02",
        headlines=("Stock rises on earnings", "New product announced"),
        cached_at="2026-09-02T08:31:00",
    )


def test_get_snapshot_is_healthy_empty_when_symbol_date_pair_not_cached(populated_db):
    source = LegacyNewsCacheSource(db_path=populated_db)

    result = source.get_snapshot("AAPL", "2026-09-05")

    assert result.value is None
    assert result.health.status is IntegrationStatus.HEALTHY


def test_get_snapshot_is_healthy_empty_when_table_has_no_rows(empty_news_cache_db):
    source = LegacyNewsCacheSource(db_path=empty_news_cache_db)

    result = source.get_snapshot("AAPL", "2026-09-01")

    assert result.value is None
    assert result.health.status is IntegrationStatus.HEALTHY


def test_get_snapshot_is_api_error_when_table_is_missing(missing_table_db):
    source = LegacyNewsCacheSource(db_path=missing_table_db)

    result = source.get_snapshot("AAPL", "2026-09-01")

    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


def test_get_snapshot_is_unavailable_when_database_file_is_missing():
    source = LegacyNewsCacheSource(db_path="this_file_does_not_exist_xyz_12345.db")

    result = source.get_snapshot("AAPL", "2026-09-01")

    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_get_snapshot_is_api_error_when_headlines_json_is_malformed():
    """A malformed headlines_json value (not valid JSON) must never crash
    the adapter -- it is reported as API_ERROR, matching the sibling
    adapters' 'malformed row' contract."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE news_cache (symbol TEXT, fetch_date TEXT, "
        "headlines_json TEXT, cached_at TEXT, PRIMARY KEY (symbol, fetch_date))"
    )
    conn.execute(
        "INSERT INTO news_cache VALUES (?, ?, ?, ?)",
        ("AAPL", "2026-09-01", "{not valid json", "2026-09-01T08:30:00"),
    )
    conn.commit()
    conn.close()
    try:
        source = LegacyNewsCacheSource(db_path=path)
        result = source.get_snapshot("AAPL", "2026-09-01")
        assert result.value is None
        assert result.health.status is IntegrationStatus.API_ERROR
    finally:
        os.remove(path)


def test_get_snapshot_does_not_match_a_different_symbol_or_date(populated_db):
    source = LegacyNewsCacheSource(db_path=populated_db)

    assert source.get_snapshot("MSFT", "2026-09-02").value is None
    assert source.get_snapshot("GOOG", "2026-09-01").value is None


def test_module_imports_no_protected_package():
    """AST-level regression lock: this adapter must never import bot,
    dashboard, database, scheduler, or ledger."""
    import applications.trading_intelligence.adapters.legacy_news_cache_source as module

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
    import applications.trading_intelligence.adapters.legacy_news_cache_source as module

    source = inspect.getsource(module)
    for forbidden_sql in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "):
        assert forbidden_sql not in source.upper(), (
            f"adapter source must never contain a {forbidden_sql.strip()} statement"
        )
