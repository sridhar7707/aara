"""Tests for scripts/check_decision_freshness.py -- a read-only Trust Ledger
freshness check. Written after the 2026-08-06 to 2026-08-14 incident where
candidate_evaluation_events kept accumulating while decision_events silently
stopped for 11 days (root cause: bot/_main_market.py's stale-5-min-feed bug,
ADR-026) with nothing surfacing the gap until a manual check."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import ledger.db as ledger_db  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
import bot.trust_ledger.decisions as decisions  # noqa: E402
from scripts.check_decision_freshness import (  # noqa: E402
    check_pipeline_staleness,
    check_decision_write_freeze,
    check_data_availability,
)

NOW = datetime(2026, 8, 17, 14, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _clear_module_cache():
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


@pytest.fixture
def manifest(conn):
    conn.execute("INSERT INTO model_artifacts VALUES ('xgb_v1','xgboost','v1',NULL,'fh1','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO model_training_runs VALUES "
        "('run1','xgb_v1','2026-01-01','2026-06-01','{}','2026-06-01T00:00:00Z',"
        "'/tmp/x.pkl','deadbeef',1024,'2026-06-01T00:00:00Z')"
    )
    conn.execute("INSERT INTO strategy_versions VALUES ('strat_v1','{}','2026-01-01T00:00:00Z',NULL)")
    conn.execute("INSERT INTO risk_rulesets VALUES ('risk_v1','{}','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO deployment_manifests VALUES "
        "('mani_v1','{\"xgboost\":\"run1\"}','risk_v1','strat_v1','fp_v1','{}','2026-07-28T00:00:00Z')"
    )
    conn.commit()
    return "mani_v1"


def _add_candidate(conn, symbol: str, trading_day: str, timestamp: str, data_available: bool = True) -> str:
    with patch("bot.trust_ledger.candidates._utc_now", return_value=timestamp):
        row = candidates.record_candidate_evaluation_if_concluded(
            conn, symbol, trading_day, {}, data_available=data_available,
            required_models_available=True, evaluation_completed=True,
        )
    return row["candidate_event_id"]


def _add_decision(conn, manifest_id: str, candidate_event_id: str, asset: str, timestamp: str) -> None:
    decisions.write_decision_event(
        conn, candidate_event_id, asset, "REJECT", "QUALIFIED_REJECTION",
        {"value": 10000.0}, {"regime": "bull"}, {}, {"gates": []}, 0.5,
        manifest_id, decisions.build_intent("REJECT"), decisions.build_data_completeness(),
        timestamp=timestamp,
    )


# --- check_pipeline_staleness ---

def test_pipeline_staleness_passes_when_latest_candidate_is_recent(conn, manifest):
    _add_candidate(conn, "AAPL", "2026-08-17", "2026-08-17T13:00:00+00:00")
    result = check_pipeline_staleness(conn, now=NOW)
    assert result.passed is True


def test_pipeline_staleness_fails_when_latest_candidate_is_old(conn, manifest):
    _add_candidate(conn, "AAPL", "2026-08-06", "2026-08-06T14:00:00+00:00")
    result = check_pipeline_staleness(conn, now=NOW, max_hours=72)
    assert result.passed is False
    assert "2026-08-06" not in result.detail or "h old" in result.detail


def test_pipeline_staleness_fails_when_no_candidates_exist(conn, manifest):
    result = check_pipeline_staleness(conn, now=NOW)
    assert result.passed is False


# --- check_decision_write_freeze ---

def test_decision_write_freeze_passes_when_latest_candidate_day_has_decisions(conn, manifest):
    cand_id = _add_candidate(conn, "AAPL", "2026-08-17", "2026-08-17T13:00:00+00:00")
    _add_decision(conn, manifest, cand_id, "AAPL", "2026-08-17T13:05:00+00:00")
    result = check_decision_write_freeze(conn)
    assert result.passed is True


def test_decision_write_freeze_fails_when_latest_candidate_day_has_zero_decisions(conn, manifest):
    """Reproduces the actual 2026-08-06..08-14 incident shape: candidates
    evaluated, but the decision-write path produced nothing that day."""
    _add_candidate(conn, "AAPL", "2026-08-14", "2026-08-14T13:00:00+00:00")
    _add_candidate(conn, "MSFT", "2026-08-14", "2026-08-14T13:01:00+00:00")
    result = check_decision_write_freeze(conn)
    assert result.passed is False
    assert "2026-08-14" in result.detail


def test_decision_write_freeze_ignores_decisions_on_other_days(conn, manifest):
    """A decision written on an earlier day must not mask today's freeze."""
    cand_id_old = _add_candidate(conn, "AAPL", "2026-08-06", "2026-08-06T13:00:00+00:00")
    _add_decision(conn, manifest, cand_id_old, "AAPL", "2026-08-06T13:05:00+00:00")
    _add_candidate(conn, "MSFT", "2026-08-14", "2026-08-14T13:00:00+00:00")
    result = check_decision_write_freeze(conn)
    assert result.passed is False
    assert "2026-08-14" in result.detail


def test_decision_write_freeze_fails_when_no_candidates_exist(conn, manifest):
    result = check_decision_write_freeze(conn)
    assert result.passed is False


# --- check_data_availability ---

def test_data_availability_passes_when_most_candidates_available(conn, manifest):
    _add_candidate(conn, "AAPL", "2026-08-17", "2026-08-17T13:00:00+00:00", data_available=True)
    _add_candidate(conn, "MSFT", "2026-08-17", "2026-08-17T13:01:00+00:00", data_available=True)
    _add_candidate(conn, "GOOGL", "2026-08-17", "2026-08-17T13:02:00+00:00", data_available=False)
    result = check_data_availability(conn, threshold=0.5)
    assert result.passed is True


def test_data_availability_fails_when_most_candidates_unavailable(conn, manifest):
    """Reproduces the actual incident's root cause: 17/20 and 20/20 candidates
    showed data_available=0 on 2026-08-13/08-14 (bot/_main_market.py's
    stale-5-min-feed bug, fixed by ADR-026)."""
    _add_candidate(conn, "AAPL", "2026-08-14", "2026-08-14T13:00:00+00:00", data_available=False)
    _add_candidate(conn, "MSFT", "2026-08-14", "2026-08-14T13:01:00+00:00", data_available=False)
    _add_candidate(conn, "GOOGL", "2026-08-14", "2026-08-14T13:02:00+00:00", data_available=True)
    result = check_data_availability(conn, threshold=0.5)
    assert result.passed is False
    assert "2026-08-14" in result.detail


def test_data_availability_fails_when_no_candidates_exist(conn, manifest):
    result = check_data_availability(conn, threshold=0.5)
    assert result.passed is False


def test_data_availability_only_considers_latest_candidate_day(conn, manifest):
    """A bad day in the past must not fail today's check."""
    _add_candidate(conn, "AAPL", "2026-08-06", "2026-08-06T13:00:00+00:00", data_available=False)
    _add_candidate(conn, "MSFT", "2026-08-06", "2026-08-06T13:01:00+00:00", data_available=False)
    _add_candidate(conn, "GOOGL", "2026-08-17", "2026-08-17T13:00:00+00:00", data_available=True)
    result = check_data_availability(conn, threshold=0.5)
    assert result.passed is True
    assert "2026-08-17" in result.detail
