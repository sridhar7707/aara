"""Tests for
applications.trading_intelligence.adapters.legacy_portfolio_snapshot_source.
"""
import ast
import inspect
import os
import sqlite3
import tempfile

import pytest

from applications.platform.integrations import IntegrationStatus, ReadResult
from applications.trading_intelligence.adapters.legacy_portfolio_snapshot_source import (
    LegacyPortfolioSnapshotSource,
    PortfolioSnapshotValue,
)


def _assert_healthy_empty(result):
    assert isinstance(result, ReadResult)
    assert result.value is None
    assert result.health.status is IntegrationStatus.HEALTHY


@pytest.fixture
def portfolio_snapshots_db():
    """A real, temporary SQLite file with a populated portfolio_snapshots
    table, matching bot/_main_db.py's own DDL -- a real file this adapter
    reads exactly as it would read trades.db."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE portfolio_snapshots ("
        "timestamp TEXT PRIMARY KEY, portfolio_value REAL, available_cash REAL, "
        "open_positions INTEGER)"
    )
    conn.execute(
        "INSERT INTO portfolio_snapshots VALUES "
        "('2026-08-30T15:03:38+00:00', 90000.0, 30000.0, 4)"
    )
    conn.execute(
        "INSERT INTO portfolio_snapshots VALUES "
        "('2026-08-31T19:39:42+00:00', 100029.85, 59869.06, 5)"
    )
    conn.commit()
    conn.close()
    yield path
    os.remove(path)


@pytest.fixture
def empty_db():
    """A real, temporary SQLite file with no portfolio_snapshots table."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE unrelated_table (id INTEGER)")
    conn.commit()
    conn.close()
    yield path
    os.remove(path)


def test_is_healthy_with_the_most_recent_row_and_derives_invested(portfolio_snapshots_db):
    source = LegacyPortfolioSnapshotSource(db_path=portfolio_snapshots_db)

    result = source.get_latest_portfolio_snapshot()

    assert result.health.status is IntegrationStatus.HEALTHY
    assert result.value == PortfolioSnapshotValue(
        total_value=100029.85,
        available_cash=59869.06,
        invested_amount=100029.85 - 59869.06,
        # the latest row's own portfolio_snapshots.timestamp
        as_of="2026-08-31T19:39:42+00:00",
    )


def test_is_api_error_when_table_is_missing(empty_db):
    source = LegacyPortfolioSnapshotSource(db_path=empty_db)

    result = source.get_latest_portfolio_snapshot()
    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


def test_is_unavailable_when_database_file_is_missing():
    source = LegacyPortfolioSnapshotSource(
        db_path="this_file_does_not_exist_xyz_12345.db"
    )

    result = source.get_latest_portfolio_snapshot()
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_is_healthy_empty_when_table_is_empty():
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE portfolio_snapshots (timestamp TEXT, portfolio_value REAL, "
        "available_cash REAL, open_positions INTEGER)"
    )
    conn.commit()
    conn.close()
    try:
        source = LegacyPortfolioSnapshotSource(db_path=path)
        _assert_healthy_empty(source.get_latest_portfolio_snapshot())
    finally:
        os.remove(path)


def test_skips_nonpositive_portfolio_value_rows():
    """A fabricated `portfolio_value = 0` row (bad Alpaca reconcile read)
    must never be picked up as the latest snapshot -- the older positive
    row is returned instead."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE portfolio_snapshots (timestamp TEXT PRIMARY KEY, "
        "portfolio_value REAL, available_cash REAL, open_positions INTEGER)"
    )
    conn.execute(
        "INSERT INTO portfolio_snapshots VALUES "
        "('2026-08-30T00:00:00+00:00', 77000.0, 7000.0, 3)"
    )
    conn.execute(
        "INSERT INTO portfolio_snapshots VALUES "
        "('2026-08-31T00:00:00+00:00', 0.0, 0.0, 0)"
    )
    conn.commit()
    conn.close()
    try:
        source = LegacyPortfolioSnapshotSource(db_path=path)
        result = source.get_latest_portfolio_snapshot()
        assert result.health.status is IntegrationStatus.HEALTHY
        assert result.value.total_value == 77000.0
        assert result.value.available_cash == 7000.0
    finally:
        os.remove(path)


def test_is_healthy_empty_when_only_row_has_null_values():
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE portfolio_snapshots (timestamp TEXT PRIMARY KEY, "
        "portfolio_value REAL, available_cash REAL, open_positions INTEGER)"
    )
    conn.execute(
        "INSERT INTO portfolio_snapshots VALUES "
        "('2026-08-31T00:00:00+00:00', 50000.0, NULL, 2)"
    )
    conn.commit()
    conn.close()
    try:
        source = LegacyPortfolioSnapshotSource(db_path=path)
        _assert_healthy_empty(source.get_latest_portfolio_snapshot())
    finally:
        os.remove(path)


def test_module_imports_no_protected_package():
    """AST-level regression lock: this adapter must never import bot,
    dashboard, database, or scheduler -- the whole point of duplicating
    the trivial SELECT here instead of importing
    bot.monitor.dashboard_data."""
    import applications.trading_intelligence.adapters.legacy_portfolio_snapshot_source as module

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
    """Regression lock, matching this product's other legacy adapters'
    own 'never executes a write statement' test: grep the adapter's own
    source for any SQL write keyword rather than trusting a runtime mock,
    since the whole risk here is a stray INSERT/UPDATE/DELETE against a
    real production file."""
    import applications.trading_intelligence.adapters.legacy_portfolio_snapshot_source as module

    source = inspect.getsource(module)
    for forbidden_sql in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "):
        assert forbidden_sql not in source.upper(), (
            f"adapter source must never contain a {forbidden_sql.strip()} statement"
        )
