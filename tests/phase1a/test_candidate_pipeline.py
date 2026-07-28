"""Tests for bot/trust_ledger/candidates.py (Phase 1A Sprint 2)."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import ledger.db as ledger_db  # noqa: E402
import ledger.ledger as ledger_svc  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_module_cache():
    """The write-once cache is module-level state -- reset between tests so
    one test's writes don't leak into another's assertions."""
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


_UNIVERSE_PAYLOAD = {
    "date": "2026-07-28",
    "picks": [
        {"symbol": "AAPL", "rank": 1, "composite_score": 0.91, "analyst_signal": 0.7,
         "etf_momentum": 0.3, "regime": "TRENDING", "sector": "Technology"},
        {"symbol": "MSFT", "rank": 2, "composite_score": 0.85, "analyst_signal": 0.6,
         "etf_momentum": 0.2, "regime": "TRENDING", "sector": "Technology"},
    ],
}


def test_one_candidate_per_symbol_per_day_across_many_calls(conn):
    first = candidates.record_candidate_evaluation_if_concluded(
        conn, "AAPL", "2026-07-28", _UNIVERSE_PAYLOAD,
        data_available=True, required_models_available=True, evaluation_completed=True,
    )
    assert first is not None

    # Simulate 10 more cycles the same day -- none should write a new row.
    for _ in range(10):
        result = candidates.record_candidate_evaluation_if_concluded(
            conn, "AAPL", "2026-07-28", _UNIVERSE_PAYLOAD,
            data_available=True, required_models_available=True, evaluation_completed=True,
        )
        assert result is None

    count = conn.execute(
        "SELECT COUNT(*) FROM candidate_evaluation_events WHERE asset='AAPL'"
    ).fetchone()[0]
    assert count == 1


def test_write_once_survives_cache_reset_via_db_check(conn):
    """Simulates a process restart: the in-memory cache is cleared but the
    DB already has a row for (symbol, day) -- the DB fallback check must
    still prevent a duplicate write."""
    candidates.record_candidate_evaluation_if_concluded(
        conn, "AAPL", "2026-07-28", _UNIVERSE_PAYLOAD,
        data_available=True, required_models_available=True, evaluation_completed=True,
    )
    candidates._recorded_today.clear()  # simulate fresh process

    result = candidates.record_candidate_evaluation_if_concluded(
        conn, "AAPL", "2026-07-28", _UNIVERSE_PAYLOAD,
        data_available=True, required_models_available=True, evaluation_completed=True,
    )
    assert result is None
    count = conn.execute(
        "SELECT COUNT(*) FROM candidate_evaluation_events WHERE asset='AAPL'"
    ).fetchone()[0]
    assert count == 1


def test_new_day_allows_a_new_candidate(conn):
    candidates.record_candidate_evaluation_if_concluded(
        conn, "AAPL", "2026-07-28", _UNIVERSE_PAYLOAD,
        data_available=True, required_models_available=True, evaluation_completed=True,
    )
    second_day = candidates.record_candidate_evaluation_if_concluded(
        conn, "AAPL", "2026-07-29", _UNIVERSE_PAYLOAD,
        data_available=True, required_models_available=True, evaluation_completed=True,
    )
    assert second_day is not None
    count = conn.execute(
        "SELECT COUNT(*) FROM candidate_evaluation_events WHERE asset='AAPL'"
    ).fetchone()[0]
    assert count == 2


def test_failure_path_writes_evaluation_completed_false(conn):
    row = candidates.record_candidate_evaluation_if_concluded(
        conn, "MSFT", "2026-07-28", _UNIVERSE_PAYLOAD,
        data_available=False, required_models_available=False, evaluation_completed=False,
    )
    assert row is not None
    stored = conn.execute(
        "SELECT evaluation_completed FROM candidate_evaluation_events WHERE asset='MSFT'"
    ).fetchone()
    assert stored == (0,)


def test_decision_events_insert_against_failed_candidate_is_rejected_by_frozen_trigger(conn):
    """Proves the Phase 0 trg_decision_events_requires_completed_evaluation
    trigger is actually reachable from this new Sprint 2 code path, not just
    from Phase 0's own tests."""
    import sqlite3

    conn.execute("INSERT INTO model_artifacts VALUES ('a1','xgboost','v1',NULL,'fh1','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO model_training_runs VALUES "
        "('r1','a1','2026-01-01','2026-06-01','{}','2026-06-01T00:00:00Z','/tmp/x.pkl','deadbeef',1024,'2026-06-01T00:00:00Z')"
    )
    conn.execute("INSERT INTO strategy_versions VALUES ('s1','{}','2026-01-01T00:00:00Z',NULL)")
    conn.execute("INSERT INTO risk_rulesets VALUES ('rk1','{}','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO deployment_manifests VALUES "
        "('m1','{\"xgboost\":\"r1\"}','rk1','s1','fp1','{}','2026-07-28T00:00:00Z')"
    )
    conn.commit()

    row = candidates.record_candidate_evaluation_if_concluded(
        conn, "MSFT", "2026-07-28", _UNIVERSE_PAYLOAD,
        data_available=False, required_models_available=False, evaluation_completed=False,
    )

    with pytest.raises(sqlite3.IntegrityError):
        ledger_svc.append_ledger_row(conn, "decision_events", {
            "decision_id": "DEC-BAD", "candidate_event_id": row["candidate_event_id"],
            "timestamp": "2026-07-28T10:00:00Z", "asset": "MSFT", "action": "REJECT",
            "event_type": "QUALIFIED_REJECTION", "portfolio_snapshot": {}, "market_context": {},
            "model_outputs": {}, "risk_checks": {}, "final_confidence": 0.5,
            "deployment_manifest_id": "m1",
            "intent": {"primary_intent": "X", "contributing_modules": []},
            "data_completeness": {"status": "DEGRADED", "missing_inputs": ["all"], "stale_inputs": []},
        })


def test_screening_results_round_trips_screener_picks(conn):
    row = candidates.record_candidate_evaluation_if_concluded(
        conn, "AAPL", "2026-07-28", _UNIVERSE_PAYLOAD,
        data_available=True, required_models_available=True, evaluation_completed=True,
    )
    assert row["screening_results"]["rank"] == 1
    assert row["screening_results"]["composite_score"] == 0.91
    assert row["screening_results"]["sector"] == "Technology"


def test_symbol_not_in_universe_payload_still_records_with_note(conn):
    row = candidates.record_candidate_evaluation_if_concluded(
        conn, "TSLA", "2026-07-28", _UNIVERSE_PAYLOAD,
        data_available=True, required_models_available=True, evaluation_completed=True,
    )
    assert "note" in row["screening_results"]
