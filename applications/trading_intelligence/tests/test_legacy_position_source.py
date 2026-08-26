"""Tests for applications.trading_intelligence.adapters.legacy_position_source."""
import ast
import inspect
import os
import sqlite3
import tempfile

import pytest

from applications.trading_intelligence.adapters.legacy_position_source import (
    LegacyPositionSource,
    OpenPosition,
)


def _create_position_state_db(rows):
    """A real, temporary SQLite file with a populated position_state table,
    matching bot/_main_db.py's own DDL -- not a mock of sqlite3, a real
    file this adapter reads exactly as it would read trades.db."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE position_state ("
        "symbol TEXT PRIMARY KEY, entry_price REAL, high_water_mark REAL, "
        "atr_at_entry REAL, opened_at TEXT, shares REAL DEFAULT 0.0)"
    )
    for symbol, entry_price, shares in rows:
        conn.execute(
            "INSERT INTO position_state (symbol, entry_price, shares) VALUES (?, ?, ?)",
            (symbol, entry_price, shares),
        )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def position_state_db():
    path = _create_position_state_db([("AAPL", 315.01, 19.11)])
    yield path
    os.remove(path)


@pytest.fixture
def multi_position_state_db():
    path = _create_position_state_db([
        ("AAPL", 315.01, 19.11),
        ("BA", 223.20, 35.41),
        ("GOOGL", 347.41, 34.68),
    ])
    yield path
    os.remove(path)


@pytest.fixture
def empty_position_state_db():
    """A real, temporary SQLite file with position_state present but
    containing zero qualifying rows -- distinct from the table not
    existing at all."""
    path = _create_position_state_db([])
    yield path
    os.remove(path)


@pytest.fixture
def missing_table_db():
    """A real, temporary SQLite file with no position_state table at all."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE unrelated_table (id INTEGER)")
    conn.commit()
    conn.close()
    yield path
    os.remove(path)


def test_get_open_positions_returns_a_single_real_row(position_state_db):
    source = LegacyPositionSource(db_path=position_state_db)

    positions = source.get_open_positions()

    assert positions == (OpenPosition(symbol="AAPL", quantity=19.11, entry_price=315.01),)


def test_get_open_positions_returns_every_open_position_in_symbol_order(multi_position_state_db):
    source = LegacyPositionSource(db_path=multi_position_state_db)

    positions = source.get_open_positions()

    assert [p.symbol for p in positions] == ["AAPL", "BA", "GOOGL"]


def test_get_open_positions_excludes_rows_at_or_below_the_dust_threshold():
    path = _create_position_state_db([("AAPL", 100.0, 19.0), ("MSFT", 200.0, 0.0005)])
    try:
        source = LegacyPositionSource(db_path=path)
        positions = source.get_open_positions()
        assert [p.symbol for p in positions] == ["AAPL"]
    finally:
        os.remove(path)


def test_get_open_positions_returns_empty_tuple_when_table_has_no_qualifying_rows(empty_position_state_db):
    """An empty position_state table is a legitimate real result -- zero
    open positions right now -- and must be distinguished from the table
    or database not existing at all (which return None below)."""
    source = LegacyPositionSource(db_path=empty_position_state_db)

    assert source.get_open_positions() == ()


def test_get_open_positions_returns_none_when_table_is_missing(missing_table_db):
    source = LegacyPositionSource(db_path=missing_table_db)

    assert source.get_open_positions() is None


def test_get_open_positions_returns_none_when_database_file_is_missing():
    source = LegacyPositionSource(db_path="this_file_does_not_exist_xyz_12345.db")

    assert source.get_open_positions() is None


def test_module_imports_no_protected_package():
    """AST-level regression lock: this adapter must never import bot,
    dashboard, database, scheduler, or ledger -- the whole point of
    duplicating the trivial SELECT here instead of importing bot's own
    position_state writer."""
    import applications.trading_intelligence.adapters.legacy_position_source as module

    source = inspect.getsource(module)
    tree = ast.parse(source)
    forbidden = ("bot", "dashboard", "database", "scheduler", "ledger")

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
    import applications.trading_intelligence.adapters.legacy_position_source as module

    source = inspect.getsource(module)
    for forbidden_sql in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "):
        assert forbidden_sql not in source.upper(), (
            f"adapter source must never contain a {forbidden_sql.strip()} statement"
        )
