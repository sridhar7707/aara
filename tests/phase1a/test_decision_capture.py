"""Tests for bot/trust_ledger/decisions.py and bot/strategy/model_output_adapter.py
(Phase 1A Sprint 3 core logic -- _handle_entry/_handle_exits integration
tests live in test_decision_capture_integration.py)."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import ledger.db as ledger_db  # noqa: E402
import bot.trust_ledger.decisions as decisions  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
from bot.strategy.model_output_adapter import build_model_outputs  # noqa: E402


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
    """Minimal Group B chain + a candidate_evaluation_events row, mirroring
    the fixture pattern in tests/test_ledger_phase0.py."""
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
    row = candidates.record_candidate_evaluation_if_concluded(
        conn, "AAPL", "2026-07-28", {}, data_available=True,
        required_models_available=True, evaluation_completed=True,
    )
    return {"manifest_id": "mani_v1", "candidate_event_id": row["candidate_event_id"]}


def _decision_kwargs(reference_chain, action="BUY", event_type="EXECUTED"):
    return dict(
        candidate_event_id=reference_chain["candidate_event_id"],
        asset="AAPL", action=action, event_type=event_type,
        portfolio_snapshot={"value": 10000.0}, market_context={"regime": "bull"},
        model_outputs=build_model_outputs(0.7, 0.6, 0.2),
        risk_checks={"gates": []}, final_confidence=0.65,
        deployment_manifest_id=reference_chain["manifest_id"],
        intent=decisions.build_intent(action),
        data_completeness=decisions.build_data_completeness(),
    )


# ── build_model_outputs ───────────────────────────────────────────────────

def test_build_model_outputs_shape():
    out = build_model_outputs(0.7, 0.3, -0.5, xgb_drivers=[("rsi", 0.12)],
                              lstm_is_degraded=True, lstm_val_loss=0.61)
    assert set(out.keys()) == {"xgboost", "lstm", "finbert"}
    for model in out.values():
        assert set(model.keys()) == {"signal", "confidence", "metadata"}
    assert out["xgboost"]["signal"] == "BUY"
    assert out["lstm"]["signal"] == "SELL"
    assert out["finbert"]["signal"] == "SELL"
    assert out["xgboost"]["metadata"]["shap_drivers"] == [{"feature": "rsi", "shap_value": 0.12}]
    assert out["lstm"]["metadata"]["is_degraded"] is True


def test_build_model_outputs_confidence_values_are_native_floats():
    import numpy as np
    out = build_model_outputs(np.float64(0.7), np.float64(0.3), np.float64(0.1))
    for model in out.values():
        assert isinstance(model["confidence"], float)
        assert not isinstance(model["confidence"], np.floating)


# ── build_intent / build_data_completeness ────────────────────────────────

def test_build_intent_maps_each_action():
    assert decisions.build_intent("BUY")["primary_intent"] == "OPPORTUNITY_ENTRY"
    assert decisions.build_intent("SELL")["primary_intent"] == "RISK_MANAGEMENT_EXIT"
    assert decisions.build_intent("HOLD")["primary_intent"] == "NO_ACTION"
    assert decisions.build_intent("REJECT")["primary_intent"] == "NO_ACTION"


def test_build_intent_with_override_reason():
    intent = decisions.build_intent("BUY", override_reason="manual re-entry approved")
    assert intent["override_reason"] == "manual re-entry approved"


def test_build_data_completeness_complete_when_nothing_missing():
    dc = decisions.build_data_completeness()
    assert dc == {"status": "COMPLETE", "missing_inputs": [], "stale_inputs": []}


def test_build_data_completeness_degraded_when_lstm_degraded():
    dc = decisions.build_data_completeness(lstm_is_degraded=True)
    assert dc["status"] == "DEGRADED"
    assert "lstm" in dc["stale_inputs"]


def test_build_data_completeness_missing_sentiment_and_vix():
    dc = decisions.build_data_completeness(sentiment_available=False, vix_available=False)
    assert dc["status"] == "DEGRADED"
    assert set(dc["missing_inputs"]) == {"finbert", "vix"}


# ── write_decision_event ──────────────────────────────────────────────────

def test_write_decision_event_inserts_row(conn, reference_chain):
    row = decisions.write_decision_event(conn, **_decision_kwargs(reference_chain))
    stored = conn.execute(
        "SELECT asset, action, event_type FROM decision_events WHERE decision_id=?",
        (row["decision_id"],),
    ).fetchone()
    assert stored == ("AAPL", "BUY", "EXECUTED")


def test_write_decision_event_rejects_incomplete_candidate(conn, reference_chain):
    """Proves the frozen Phase 0 trigger is reachable from this new writer."""
    import sqlite3
    bad_candidate = candidates.record_candidate_evaluation_if_concluded(
        conn, "MSFT", "2026-07-28", {}, data_available=False,
        required_models_available=False, evaluation_completed=False,
    )
    kwargs = _decision_kwargs(reference_chain)
    kwargs["candidate_event_id"] = bad_candidate["candidate_event_id"]
    kwargs["asset"] = "MSFT"
    with pytest.raises(sqlite3.IntegrityError):
        decisions.write_decision_event(conn, **kwargs)


# ── check_fingerprint ──────────────────────────────────────────────────────

def test_check_fingerprint_allows_first_buy(conn, reference_chain):
    decisions.check_fingerprint(conn, "AAPL", "BUY")  # no prior decision -- must not raise


def test_check_fingerprint_blocks_duplicate_while_open(conn, reference_chain):
    decisions.write_decision_event(conn, **_decision_kwargs(reference_chain))
    with pytest.raises(decisions.DuplicateDecisionError):
        decisions.check_fingerprint(conn, "AAPL", "BUY")


def test_check_fingerprint_override_bypasses_block(conn, reference_chain):
    decisions.write_decision_event(conn, **_decision_kwargs(reference_chain))
    decisions.check_fingerprint(conn, "AAPL", "BUY", override_reason="manual")  # must not raise


def test_check_fingerprint_allows_reentry_after_close(conn, reference_chain):
    """The doc's own example: first BUY closes, a second BUY later the same
    day is a legitimate re-entry, not a blocked duplicate."""
    first = decisions.write_decision_event(conn, **_decision_kwargs(reference_chain))
    decisions_svc_conn = conn
    decisions_svc_conn.execute(
        "INSERT INTO cost_models (sequence_number, cost_model_id, spread_assumption, "
        "slippage_assumption, commission_rules, tax_assumptions, created_at, record_hash, "
        "previous_record_hash) VALUES (1,'cm1',0.001,0.001,'{}','{}','2026-07-28T00:00:00Z',"
        "'" + "0" * 64 + "','" + "0" * 64 + "')"
    )
    conn.commit()
    conn.execute(
        "INSERT INTO decision_outcome_events "
        "(outcome_id, decision_id, exit_timestamp, gross_return, net_return, holding_period_days, "
        "cost_breakdown, cost_model_id, record_hash, previous_record_hash) "
        "VALUES ('OUT-1', ?, '2026-07-28T15:00:00Z', 0.02, 0.018, 0, '{}', 'cm1', '" + "1" * 64 + "', '" + "0" * 64 + "')",
        (first["decision_id"],),
    )
    conn.commit()

    decisions.check_fingerprint(conn, "AAPL", "BUY")  # must not raise -- position closed


def test_check_fingerprint_does_not_block_different_action(conn, reference_chain):
    decisions.write_decision_event(conn, **_decision_kwargs(reference_chain, action="SELL", event_type="EXECUTED"))
    decisions.check_fingerprint(conn, "AAPL", "BUY")  # a SELL on record doesn't block a BUY


# ── get_todays_candidate_event_id ─────────────────────────────────────────

def test_get_todays_candidate_event_id_finds_existing_row(conn, reference_chain):
    found = candidates.get_todays_candidate_event_id(conn, "AAPL", "2026-07-28")
    assert found == reference_chain["candidate_event_id"]


def test_get_todays_candidate_event_id_none_when_absent(conn):
    assert candidates.get_todays_candidate_event_id(conn, "TSLA", "2026-07-28") is None


def test_get_todays_candidate_event_id_survives_cache_reset(conn, reference_chain):
    candidates._recorded_today.clear()  # simulate fresh process
    found = candidates.get_todays_candidate_event_id(conn, "AAPL", "2026-07-28")
    assert found == reference_chain["candidate_event_id"]
