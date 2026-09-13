"""Tests for applications.trading_intelligence.adapters.legacy_recommendation_source.

Mirrors legacy_news_cache_source.py's own precedent: a new, additive
module may open its own SQLite connection to trades.db and SELECT from an
existing table (here, recommendations -- written every cycle by
bot/main.py via bot/db/trade_log.py::log_recommendation()), provided it
never imports bot.*/dashboard.*/database.*/scheduler.*/ledger.*, never
writes, and never touches any ADR-002-protected file.
"""
import ast
import inspect
import os
import sqlite3
import tempfile

import pytest

from applications.platform.integrations import IntegrationStatus, ReadResult
from applications.trading_intelligence.adapters.legacy_recommendation_source import (
    LegacyRecommendationSource,
    RecommendationSnapshot,
)


def _healthy_value(result):
    assert isinstance(result, ReadResult)
    assert result.health.status is IntegrationStatus.HEALTHY
    return result.value


def _create_recommendations_db(rows):
    """A real, temporary SQLite file with a populated recommendations
    table, matching bot/_main_db.py's own DDL -- not a mock of sqlite3."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE recommendations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, "
        "prediction_date TEXT NOT NULL, recommendation TEXT, confidence REAL, "
        "prev_recommendation TEXT, price_at_recommendation REAL, created_at TEXT, "
        "UNIQUE(symbol, prediction_date))"
    )
    for symbol, prediction_date, recommendation, confidence in rows:
        conn.execute(
            "INSERT INTO recommendations "
            "(symbol, prediction_date, recommendation, confidence) VALUES (?, ?, ?, ?)",
            (symbol, prediction_date, recommendation, confidence),
        )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def populated_db():
    path = _create_recommendations_db([
        ("AAPL", "2026-09-01", "BUY", 0.61),
        ("AAPL", "2026-09-05", "WAIT", 0.48),
        ("MSFT", "2026-09-01", "BUY", 0.55),
    ])
    yield path
    os.remove(path)


@pytest.fixture
def empty_recommendations_db():
    path = _create_recommendations_db([])
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
    source = LegacyRecommendationSource(db_path=populated_db)

    snapshot = _healthy_value(source.get_snapshot("AAPL", "2026-09-05"))

    assert snapshot == RecommendationSnapshot(
        symbol="AAPL",
        prediction_date="2026-09-05",
        recommendation="WAIT",
        confidence=0.48,
    )


def test_get_snapshot_is_healthy_empty_when_symbol_date_pair_not_cached(populated_db):
    source = LegacyRecommendationSource(db_path=populated_db)

    result = source.get_snapshot("AAPL", "2026-09-09")

    assert result.value is None
    assert result.health.status is IntegrationStatus.HEALTHY


def test_get_snapshot_is_healthy_empty_when_table_has_no_rows(empty_recommendations_db):
    source = LegacyRecommendationSource(db_path=empty_recommendations_db)

    result = source.get_snapshot("AAPL", "2026-09-01")

    assert result.value is None
    assert result.health.status is IntegrationStatus.HEALTHY


def test_get_snapshot_is_api_error_when_table_is_missing(missing_table_db):
    source = LegacyRecommendationSource(db_path=missing_table_db)

    result = source.get_snapshot("AAPL", "2026-09-01")

    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


def test_get_snapshot_is_unavailable_when_database_file_is_missing():
    source = LegacyRecommendationSource(db_path="this_file_does_not_exist_xyz_12345.db")

    result = source.get_snapshot("AAPL", "2026-09-01")

    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_get_snapshot_does_not_match_a_different_symbol_or_date(populated_db):
    source = LegacyRecommendationSource(db_path=populated_db)

    assert source.get_snapshot("MSFT", "2026-09-05").value is None
    assert source.get_snapshot("GOOG", "2026-09-01").value is None


def test_module_imports_no_protected_package():
    """AST-level regression lock: this adapter must never import bot,
    dashboard, database, scheduler, or ledger."""
    import applications.trading_intelligence.adapters.legacy_recommendation_source as module

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
    import applications.trading_intelligence.adapters.legacy_recommendation_source as module

    source = inspect.getsource(module)
    for forbidden_sql in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "):
        assert forbidden_sql not in source.upper(), (
            f"adapter source must never contain a {forbidden_sql.strip()} statement"
        )
