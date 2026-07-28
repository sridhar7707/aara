"""Tests for bot/trust_ledger/outcomes.py (Phase 1A Sprint 5)."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import ledger.db as ledger_db  # noqa: E402
import ledger.ledger as ledger_svc  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
import bot.trust_ledger.decisions as decisions  # noqa: E402
import bot.trust_ledger.outcomes as outcomes  # noqa: E402


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
def reference_chain(conn):
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
    ledger_svc.append_ledger_row(conn, "cost_models", {
        "cost_model_id": "cost_model_v1", "spread_assumption": 0.001, "slippage_assumption": 0.001,
        "commission_rules": {}, "tax_assumptions": {}, "created_at": "2026-07-28T00:00:00Z",
    })
    row = candidates.record_candidate_evaluation_if_concluded(
        conn, "AAPL", "2026-07-28", {}, data_available=True,
        required_models_available=True, evaluation_completed=True,
    )
    return {"manifest_id": "mani_v1", "candidate_event_id": row["candidate_event_id"]}


def _write_buy(conn, reference_chain, decision_id="DEC-1"):
    return decisions.write_decision_event(
        conn, candidate_event_id=reference_chain["candidate_event_id"], asset="AAPL",
        action="BUY", event_type="EXECUTED", portfolio_snapshot={}, market_context={},
        model_outputs={}, risk_checks={}, final_confidence=0.7,
        deployment_manifest_id=reference_chain["manifest_id"],
        intent=decisions.build_intent("BUY"), data_completeness=decisions.build_data_completeness(),
    )


def test_find_open_buy_decision_id_finds_open_position(conn, reference_chain):
    row = _write_buy(conn, reference_chain)
    found = outcomes.find_open_buy_decision_id(conn, "AAPL")
    assert found == row["decision_id"]


def test_find_open_buy_decision_id_none_when_no_buy(conn):
    assert outcomes.find_open_buy_decision_id(conn, "AAPL") is None


def test_find_open_buy_decision_id_none_once_closed(conn, reference_chain):
    row = _write_buy(conn, reference_chain)
    outcomes.write_decision_outcome_event(conn, "AAPL", row["decision_id"], "2026-07-28T15:00:00Z", 0.02, 3)
    assert outcomes.find_open_buy_decision_id(conn, "AAPL") is None


def test_estimate_net_return_subtracts_costs():
    net, breakdown = outcomes.estimate_net_return(0.08, 0.002, 0.003)
    assert net == pytest.approx(0.08 - 0.002 - 0.003)
    assert breakdown["spread"] == 0.002
    assert breakdown["slippage"] == 0.003
    assert breakdown["commission"] == 0.0


def test_write_decision_outcome_event_closes_decision_state(conn, reference_chain):
    row = _write_buy(conn, reference_chain)
    assert conn.execute(
        "SELECT outcome_state FROM decision_state WHERE decision_id=?", (row["decision_id"],)
    ).fetchone()[0] == "OPEN"

    outcomes.write_decision_outcome_event(conn, "AAPL", row["decision_id"], "2026-07-28T15:00:00Z", 0.05, 4)

    assert conn.execute(
        "SELECT outcome_state FROM decision_state WHERE decision_id=?", (row["decision_id"],)
    ).fetchone()[0] == "CLOSED"


def test_write_decision_outcome_event_resolves_latest_cost_model(conn, reference_chain):
    row = _write_buy(conn, reference_chain)
    outcome = outcomes.write_decision_outcome_event(conn, "AAPL", row["decision_id"], "2026-07-28T15:00:00Z", 0.05, 4)
    assert outcome["cost_model_id"] == "cost_model_v1"
