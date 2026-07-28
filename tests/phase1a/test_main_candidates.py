"""Tests for bot/_main_candidates.py::record_candidate_safe (Phase 1A Sprint 2).

Split from test_candidate_pipeline.py: this file covers the defensive
wrapper bot/main.py actually calls, not the underlying ledger-writing
function (bot.trust_ledger.candidates.record_candidate_evaluation_if_concluded,
covered directly in test_candidate_pipeline.py).
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import ledger.db as ledger_db  # noqa: E402
from bot._main_candidates import record_candidate_safe  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_module_cache():
    import bot.trust_ledger.candidates as candidates
    candidates._recorded_today.clear()
    candidates._recorded_date = ""
    yield
    candidates._recorded_today.clear()
    candidates._recorded_date = ""


@pytest.fixture
def conn():
    c = ledger_db.init_db(":memory:")
    yield c
    c.close()


def test_record_candidate_safe_writes_row_on_success(conn):
    record_candidate_safe(
        conn, "AAPL", "2026-07-28", {},
        data_available=True, required_models_available=True, evaluation_completed=True,
    )
    count = conn.execute(
        "SELECT COUNT(*) FROM candidate_evaluation_events WHERE asset='AAPL'"
    ).fetchone()[0]
    assert count == 1


def test_record_candidate_safe_swallows_exception_instead_of_propagating(conn, monkeypatch):
    """The whole point of this wrapper: a ledger write failure must never
    reach the caller (bot/main.py's per-symbol loop) as an exception --
    it's an audit system, not a trading gate."""
    def _boom(*args, **kwargs):
        raise RuntimeError("simulated ledger DB failure")

    import bot._main_candidates as mod
    monkeypatch.setattr(mod, "record_candidate_evaluation_if_concluded", _boom)

    # Must not raise.
    record_candidate_safe(
        conn, "AAPL", "2026-07-28", {},
        data_available=True, required_models_available=True, evaluation_completed=True,
    )
