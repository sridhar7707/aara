"""Tests for applications.trading_intelligence.adapters.legacy_risk_state_source.

Real, temporary SQLite files -- not mocks of sqlite3 -- exercised exactly
as the adapter would read the production trades.db. Covers the Slice B
requirements: valid NORMAL/WARNING/DEFENSIVE, updated_at passthrough,
missing DB / missing row / missing table / empty / invalid value, and the
read-only + no-write guarantees.
"""
import ast
import inspect
import os
import sqlite3
import tempfile

import pytest

from applications.platform.integrations import IntegrationStatus, ReadResult
from applications.trading_intelligence.adapters.legacy_risk_state_source import (
    LegacyRiskState,
    LegacyRiskStateSource,
)

_CREATE_RISK_STATE = (
    "CREATE TABLE risk_state (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"
)


def _make_db(rows=None, *, create_table=True):
    """A real temp SQLite file with the operational risk_state schema from
    bot/_main_db.py, optionally pre-populated."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    if create_table:
        conn.execute(_CREATE_RISK_STATE)
        for key, value, updated_at in rows or ():
            conn.execute(
                "INSERT INTO risk_state (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, updated_at),
            )
    else:
        conn.execute("CREATE TABLE unrelated (id INTEGER)")
    conn.commit()
    conn.close()
    return path


# Post-ADR-061 (Category A): get_risk_state() returns ReadResult[LegacyRiskState].
# HEALTHY + value = a real observed state; HEALTHY + value=None = table
# present but no risk_governor_state row (genuine "nothing recorded");
# UNAVAILABLE = trades.db file absent / locked; API_ERROR = table missing,
# or a row present with an unusable value / missing timestamp.


@pytest.mark.parametrize("state", ["NORMAL", "WARNING", "DEFENSIVE"])
def test_returns_each_valid_observed_state(state):
    path = _make_db([("risk_governor_state", state, "2026-08-20T15:03:38.405502+00:00")])
    try:
        result = LegacyRiskStateSource(db_path=path).get_risk_state()
        assert isinstance(result, ReadResult)
        assert result.health.status is IntegrationStatus.HEALTHY
        assert isinstance(result.value, LegacyRiskState)
        assert result.value.state == state
    finally:
        os.remove(path)


def test_returns_the_updated_at_verbatim():
    stamp = "2026-08-20T15:03:38.405502+00:00"
    path = _make_db([("risk_governor_state", "NORMAL", stamp)])
    try:
        result = LegacyRiskStateSource(db_path=path).get_risk_state()
        assert result.value.as_of == stamp
    finally:
        os.remove(path)


def test_reads_only_the_risk_governor_state_row_ignoring_other_keys():
    path = _make_db([
        ("daily_start_value", "101409.34", "2026-08-20T15:03:35+00:00"),
        ("portfolio_high", "103289.55", "2026-08-20T15:03:35+00:00"),
        ("risk_governor_state", "WARNING", "2026-08-20T15:03:38+00:00"),
    ])
    try:
        result = LegacyRiskStateSource(db_path=path).get_risk_state()
        assert result.value == LegacyRiskState(state="WARNING", as_of="2026-08-20T15:03:38+00:00")
    finally:
        os.remove(path)


def test_unavailable_when_the_database_file_is_missing():
    source = LegacyRiskStateSource(db_path="this_file_does_not_exist_ri_98765.db")

    result = source.get_risk_state()
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_api_error_when_the_risk_state_table_is_missing():
    path = _make_db(create_table=False)
    try:
        result = LegacyRiskStateSource(db_path=path).get_risk_state()
        assert result.value is None
        assert result.health.status is IntegrationStatus.API_ERROR
    finally:
        os.remove(path)


def test_healthy_empty_when_the_risk_governor_state_row_is_absent():
    path = _make_db([("daily_start_value", "101409.34", "2026-08-20T15:03:35+00:00")])
    try:
        result = LegacyRiskStateSource(db_path=path).get_risk_state()
        assert result.value is None
        assert result.health.status is IntegrationStatus.HEALTHY
    finally:
        os.remove(path)


def test_api_error_when_the_value_is_empty_string():
    path = _make_db([("risk_governor_state", "", "2026-08-20T15:03:38+00:00")])
    try:
        result = LegacyRiskStateSource(db_path=path).get_risk_state()
        assert result.value is None
        assert result.health.status is IntegrationStatus.API_ERROR
    finally:
        os.remove(path)


def test_api_error_when_the_value_is_null():
    path = _make_db([("risk_governor_state", None, "2026-08-20T15:03:38+00:00")])
    try:
        result = LegacyRiskStateSource(db_path=path).get_risk_state()
        assert result.value is None
        assert result.health.status is IntegrationStatus.API_ERROR
    finally:
        os.remove(path)


def test_api_error_when_the_state_is_not_a_recognised_literal():
    path = _make_db([("risk_governor_state", "CRITICAL", "2026-08-20T15:03:38+00:00")])
    try:
        result = LegacyRiskStateSource(db_path=path).get_risk_state()
        assert result.value is None
        assert result.health.status is IntegrationStatus.API_ERROR
    finally:
        os.remove(path)


def test_api_error_when_updated_at_is_empty():
    path = _make_db([("risk_governor_state", "NORMAL", "")])
    try:
        result = LegacyRiskStateSource(db_path=path).get_risk_state()
        assert result.value is None
        assert result.health.status is IntegrationStatus.API_ERROR
    finally:
        os.remove(path)


def test_does_not_create_the_table_when_it_is_missing():
    """Read-only: a missing risk_state table yields None and the adapter
    must never have created it as a side effect."""
    path = _make_db(create_table=False)
    try:
        LegacyRiskStateSource(db_path=path).get_risk_state()
        conn = sqlite3.connect(path)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "risk_state" not in names
    finally:
        os.remove(path)


def test_does_not_mutate_an_existing_row():
    """Read-only: reading the observed state leaves the row byte-for-byte
    unchanged."""
    path = _make_db([("risk_governor_state", "NORMAL", "2026-08-20T15:03:38+00:00")])
    try:
        LegacyRiskStateSource(db_path=path).get_risk_state()
        LegacyRiskStateSource(db_path=path).get_risk_state()
        conn = sqlite3.connect(path)
        rows = conn.execute(
            "SELECT key, value, updated_at FROM risk_state"
        ).fetchall()
        conn.close()
        assert rows == [("risk_governor_state", "NORMAL", "2026-08-20T15:03:38+00:00")]
    finally:
        os.remove(path)


def test_opens_the_database_in_read_only_uri_mode():
    """The connection string must be a mode=ro URI -- the same defensive
    open every sibling legacy_*_source.py adapter uses against the real
    trades.db."""
    source = inspect.getsource(
        inspect.getmodule(LegacyRiskStateSource)
    )
    assert '?mode=ro' in source
    assert 'uri=True' in source


def test_module_imports_no_protected_package():
    """AST-level regression lock: this adapter must never import bot,
    dashboard, database, or scheduler -- it duplicates the trivial SELECT
    rather than importing bot's own risk-state writer, and it never
    touches sentinel_engine / the hash-chained ledger."""
    import applications.trading_intelligence.adapters.legacy_risk_state_source as module

    tree = ast.parse(inspect.getsource(module))
    forbidden = ("bot", "dashboard", "database", "scheduler", "sentinel_engine", "ledger")

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
    """Regression lock, matching legacy_regime_source.py / legacy_capital_source.py:
    grep the adapter's own source for any SQL write keyword rather than
    trusting a runtime check, since the whole risk is a stray write against
    a real production file."""
    import applications.trading_intelligence.adapters.legacy_risk_state_source as module

    source = inspect.getsource(module).upper()
    for forbidden_sql in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "):
        assert forbidden_sql not in source, (
            f"adapter source must never contain a {forbidden_sql.strip()} statement"
        )


def test_module_opens_only_the_operational_db_not_the_ledger():
    """Slice B boundary: this adapter's code reads ONLY trades.db's
    operational risk_state table -- it must never open data/trust_ledger.db
    or name a hash-chained ledger table in an executed SQL string."""
    import applications.trading_intelligence.adapters.legacy_risk_state_source as module

    default_path = getattr(module, "_DB_PATH")
    select_sql = getattr(module, "_SELECT_RISK_GOVERNOR_STATE")
    assert default_path == "trades.db"
    assert "trust_ledger" not in default_path
    assert "risk_evaluation_events" not in select_sql
    assert "risk_state" in select_sql
