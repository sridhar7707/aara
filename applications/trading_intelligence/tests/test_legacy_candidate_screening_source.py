"""Tests for applications.trading_intelligence.adapters.legacy_candidate_screening_source."""
import ast
import inspect
import os
import sqlite3
import tempfile

import pytest

from applications.trading_intelligence.adapters.legacy_candidate_screening_source import (
    CandidateScreeningPick,
    LegacyCandidateScreeningSource,
)


def _create_screener_log_db(rows):
    """A real, temporary SQLite file with a populated screener_log table,
    matching bot/_main_db.py's own DDL -- not a mock of sqlite3, a real
    file this adapter reads exactly as it would read trades.db."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE screener_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, screened_at TEXT NOT NULL, "
        "symbol TEXT NOT NULL, rank INTEGER, composite_score REAL, "
        "analyst_signal REAL, etf_momentum REAL, regime TEXT, sector TEXT)"
    )
    for screened_at, symbol, rank, composite_score, sector in rows:
        conn.execute(
            "INSERT INTO screener_log (screened_at, symbol, rank, composite_score, sector) "
            "VALUES (?, ?, ?, ?, ?)",
            (screened_at, symbol, rank, composite_score, sector),
        )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def single_batch_db():
    path = _create_screener_log_db([
        ("2026-08-20T11:32:31+00:00", "SNOW", 1, 0.7295, "Technology"),
        ("2026-08-20T11:32:31+00:00", "BLK", 2, 0.6959, "Financials"),
        ("2026-08-20T11:32:31+00:00", "BAC", 3, 0.6252, "Financials"),
    ])
    yield path
    os.remove(path)


@pytest.fixture
def multi_batch_db():
    path = _create_screener_log_db([
        ("2026-08-13T11:00:00+00:00", "OLD1", 1, 0.5, "Energy"),
        ("2026-08-13T11:00:00+00:00", "OLD2", 2, 0.4, "Energy"),
        ("2026-08-20T11:32:31+00:00", "SNOW", 1, 0.7295, "Technology"),
        ("2026-08-20T11:32:31+00:00", "BLK", 2, 0.6959, "Financials"),
    ])
    yield path
    os.remove(path)


@pytest.fixture
def empty_screener_log_db():
    """A real, temporary SQLite file with screener_log present but
    containing zero rows -- distinct from the table not existing."""
    path = _create_screener_log_db([])
    yield path
    os.remove(path)


@pytest.fixture
def missing_table_db():
    """A real, temporary SQLite file with no screener_log table at all."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE unrelated_table (id INTEGER)")
    conn.commit()
    conn.close()
    yield path
    os.remove(path)


def test_get_latest_screening_returns_the_batch_ordered_by_rank(single_batch_db):
    source = LegacyCandidateScreeningSource(db_path=single_batch_db)

    snapshot = source.get_latest_screening()

    assert snapshot.screened_at == "2026-08-20T11:32:31+00:00"
    assert snapshot.picks == (
        CandidateScreeningPick(symbol="SNOW", rank=1, composite_score=0.7295, sector="Technology"),
        CandidateScreeningPick(symbol="BLK", rank=2, composite_score=0.6959, sector="Financials"),
        CandidateScreeningPick(symbol="BAC", rank=3, composite_score=0.6252, sector="Financials"),
    )


def test_get_latest_screening_selects_the_most_recent_batch_only(multi_batch_db):
    source = LegacyCandidateScreeningSource(db_path=multi_batch_db)

    snapshot = source.get_latest_screening()

    assert snapshot.screened_at == "2026-08-20T11:32:31+00:00"
    assert [p.symbol for p in snapshot.picks] == ["SNOW", "BLK"]


def test_get_latest_screening_returns_none_when_table_has_no_rows(empty_screener_log_db):
    source = LegacyCandidateScreeningSource(db_path=empty_screener_log_db)

    assert source.get_latest_screening() is None


def test_get_latest_screening_returns_none_when_table_is_missing(missing_table_db):
    source = LegacyCandidateScreeningSource(db_path=missing_table_db)

    assert source.get_latest_screening() is None


def test_get_latest_screening_returns_none_when_database_file_is_missing():
    source = LegacyCandidateScreeningSource(db_path="this_file_does_not_exist_xyz_12345.db")

    assert source.get_latest_screening() is None


def test_get_latest_screening_handles_null_rank_and_score_safely():
    """A malformed/unusable row (missing rank/composite_score/sector --
    all nullable per the real schema) must never crash the adapter, and
    must sort after every row that does carry a rank."""
    path = _create_screener_log_db([
        ("2026-08-20T11:32:31+00:00", "GOOD", 1, 0.9, "Technology"),
        ("2026-08-20T11:32:31+00:00", "INCOMPLETE", None, None, None),
    ])
    try:
        source = LegacyCandidateScreeningSource(db_path=path)
        snapshot = source.get_latest_screening()
        assert [p.symbol for p in snapshot.picks] == ["GOOD", "INCOMPLETE"]
        assert snapshot.picks[1].rank is None
        assert snapshot.picks[1].composite_score is None
        assert snapshot.picks[1].sector is None
    finally:
        os.remove(path)


def test_get_latest_screening_handles_a_batch_with_only_null_ranks():
    """Every row in the batch lacking a rank must still return safely
    (an arbitrary but deterministic order via the symbol tiebreaker)."""
    path = _create_screener_log_db([
        ("2026-08-20T11:32:31+00:00", "ZZZ", None, None, None),
        ("2026-08-20T11:32:31+00:00", "AAA", None, None, None),
    ])
    try:
        source = LegacyCandidateScreeningSource(db_path=path)
        snapshot = source.get_latest_screening()
        assert [p.symbol for p in snapshot.picks] == ["AAA", "ZZZ"]
    finally:
        os.remove(path)


def test_module_imports_no_protected_package():
    """AST-level regression lock: this adapter must never import bot,
    dashboard, database, scheduler, or ledger -- the whole point of
    duplicating the trivial SELECT here instead of importing bot's own
    screener-log writer."""
    import applications.trading_intelligence.adapters.legacy_candidate_screening_source as module

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
    import applications.trading_intelligence.adapters.legacy_candidate_screening_source as module

    source = inspect.getsource(module)
    for forbidden_sql in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "):
        assert forbidden_sql not in source.upper(), (
            f"adapter source must never contain a {forbidden_sql.strip()} statement"
        )


def test_module_never_reads_the_trust_ledger_candidate_table():
    """Regression lock backing this module's own docstring: candidate
    screening is separately duplicated into the Trust Ledger's
    candidate_evaluation_events table, which is explicitly out of scope
    (ADR-004/Q1-gated) -- this adapter must never reference it."""
    import applications.trading_intelligence.adapters.legacy_candidate_screening_source as module

    source = inspect.getsource(module)
    assert "candidate_evaluation_events" not in source.split('"""', 2)[-1]
