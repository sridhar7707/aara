"""Phase 1A prerequisite #2 (CURRENT_ARCHITECTURE.md): every timestamp written
through the live decision path must be UTC ISO-8601, no exceptions. Exercises
the real writer functions end-to-end (not hand-crafted fixture strings) so a
future regression -- someone swapping in a naive datetime.now() somewhere --
gets caught here rather than discovered by audit."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

import bot._main_db as main_db  # noqa: E402
import ledger.db as ledger_db  # noqa: E402
import ledger.ledger as ledger_svc  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
import bot.trust_ledger.constitution as constitution  # noqa: E402
import bot.trust_ledger.decisions as decisions  # noqa: E402
import bot.trust_ledger.outcomes as outcomes  # noqa: E402
import bot.trust_ledger.risk as risk_ledger  # noqa: E402
from bot.risk.risk_manager import RiskManager  # noqa: E402
from bot.strategy.model_output_adapter import build_model_outputs  # noqa: E402


def _assert_utc_iso8601(value: str, label: str) -> None:
    assert value, f"{label} is empty/None"
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None, f"{label}={value!r} has no timezone info"
    assert parsed.utcoffset() == timedelta(0), f"{label}={value!r} is not UTC (offset={parsed.utcoffset()})"


@pytest.fixture(autouse=True)
def _clear_module_cache():
    candidates._recorded_today.clear()
    candidates._recorded_date = ""
    yield
    candidates._recorded_today.clear()
    candidates._recorded_date = ""


@pytest.fixture
def trust_conn():
    c = ledger_db.init_db(":memory:")
    yield c
    c.close()


@pytest.fixture
def trades_conn():
    c = main_db.init_db(":memory:")
    yield c
    c.close()


@pytest.fixture
def reference_chain(trust_conn):
    trust_conn.execute("INSERT INTO model_artifacts VALUES ('xgb_v1','xgboost','v1',NULL,'fh1','2026-01-01T00:00:00Z')")
    trust_conn.execute(
        "INSERT INTO model_training_runs VALUES "
        "('run1','xgb_v1','2026-01-01','2026-06-01','{}','2026-06-01T00:00:00Z',"
        "'/tmp/x.pkl','deadbeef',1024,'2026-06-01T00:00:00Z')"
    )
    trust_conn.execute("INSERT INTO strategy_versions VALUES ('strat_v1','{}','2026-01-01T00:00:00Z',NULL)")
    trust_conn.execute("INSERT INTO risk_rulesets VALUES ('risk_v1','{}','2026-01-01T00:00:00Z')")
    trust_conn.execute(
        "INSERT INTO deployment_manifests VALUES "
        "('mani_v1','{\"xgboost\":\"run1\"}','risk_v1','strat_v1','fp_v1','{}','2026-07-28T00:00:00Z')"
    )
    ledger_svc.append_ledger_row(trust_conn, "cost_models", {
        "cost_model_id": "cost_v1", "spread_assumption": 0.001, "slippage_assumption": 0.001,
        "commission_rules": {}, "tax_assumptions": {}, "created_at": "2026-07-28T00:00:00Z",
    })
    trust_conn.commit()
    row = candidates.record_candidate_evaluation_if_concluded(
        trust_conn, "AAPL", "2026-07-29", {}, data_available=True,
        required_models_available=True, evaluation_completed=True,
    )
    return {"manifest_id": "mani_v1", "candidate_event_id": row["candidate_event_id"]}


def test_candidate_evaluation_events_timestamp_is_utc(trust_conn, reference_chain):
    row = trust_conn.execute(
        "SELECT timestamp FROM candidate_evaluation_events WHERE candidate_event_id=?",
        (reference_chain["candidate_event_id"],),
    ).fetchone()
    _assert_utc_iso8601(row[0], "candidate_evaluation_events.timestamp")


def test_decision_events_timestamp_and_market_context_are_utc(trust_conn, reference_chain):
    decision_row = decisions.write_decision_event(
        trust_conn,
        candidate_event_id=reference_chain["candidate_event_id"],
        asset="AAPL", action="BUY", event_type="EXECUTED",
        portfolio_snapshot={"portfolio_value": 10000.0},
        market_context={
            "regime": "bull",
            "decision_timestamp": "2026-07-29T12:00:00+00:00",
            "price_data_timestamp": "2026-07-29T11:55:00+00:00",
            "news_data_timestamp": "2026-07-29T08:00:00+00:00",
        },
        model_outputs=build_model_outputs(0.7, 0.6, 0.2),
        risk_checks={"gates": []}, final_confidence=0.65,
        deployment_manifest_id=reference_chain["manifest_id"],
        intent=decisions.build_intent("BUY"),
        data_completeness=decisions.build_data_completeness(),
    )
    stored = trust_conn.execute(
        "SELECT timestamp, market_context FROM decision_events WHERE decision_id=?",
        (decision_row["decision_id"],),
    ).fetchone()
    _assert_utc_iso8601(stored[0], "decision_events.timestamp")
    market_context = json.loads(stored[1])
    for field in ("decision_timestamp", "price_data_timestamp", "news_data_timestamp"):
        _assert_utc_iso8601(market_context[field], f"market_context.{field}")


def test_decision_outcome_events_exit_timestamp_is_utc(trust_conn, reference_chain):
    """write_decision_outcome_event() takes exit_timestamp as a caller-supplied
    argument rather than generating it internally -- the live caller
    (bot/_main_trust_decisions.py::ExitDecisionRecorder._record_outcome())
    passes _utc_now(), which this test mirrors exactly, so a future caller
    that regresses to a naive datetime.now().isoformat() would fail here."""
    from datetime import timezone

    decision_row = decisions.write_decision_event(
        trust_conn,
        candidate_event_id=reference_chain["candidate_event_id"],
        asset="AAPL", action="BUY", event_type="EXECUTED",
        portfolio_snapshot={"portfolio_value": 10000.0}, market_context={"regime": "bull"},
        model_outputs=build_model_outputs(0.7, 0.6, 0.2),
        risk_checks={"gates": []}, final_confidence=0.65,
        deployment_manifest_id=reference_chain["manifest_id"],
        intent=decisions.build_intent("BUY"),
        data_completeness=decisions.build_data_completeness(),
    )
    outcome_row = outcomes.write_decision_outcome_event(
        trust_conn, "AAPL", decision_row["decision_id"],
        datetime.now(timezone.utc).isoformat(), 0.02, 3,
    )
    stored = trust_conn.execute(
        "SELECT exit_timestamp FROM decision_outcome_events WHERE outcome_id=?",
        (outcome_row["outcome_id"],),
    ).fetchone()
    _assert_utc_iso8601(stored[0], "decision_outcome_events.exit_timestamp")


def test_risk_evaluation_events_timestamp_is_utc(trust_conn, trades_conn, reference_chain):
    risk = RiskManager()
    risk_ledger.record_risk_evaluation(trades_conn, trust_conn, risk, 10000.0, 10000.0, 0.0)
    row = trust_conn.execute(
        "SELECT timestamp FROM risk_evaluation_events ORDER BY sequence_number DESC LIMIT 1"
    ).fetchone()
    _assert_utc_iso8601(row[0], "risk_evaluation_events.timestamp")


def test_constitution_enforcement_events_check_timestamp_is_utc(trust_conn, reference_chain):
    decision_row = decisions.write_decision_event(
        trust_conn,
        candidate_event_id=reference_chain["candidate_event_id"],
        asset="AAPL", action="BUY", event_type="EXECUTED",
        portfolio_snapshot={"portfolio_value": 10000.0}, market_context={"regime": "bull"},
        model_outputs=build_model_outputs(0.7, 0.6, 0.2),
        risk_checks={"gates": []}, final_confidence=0.65,
        deployment_manifest_id=reference_chain["manifest_id"],
        intent=decisions.build_intent("BUY"),
        data_completeness=decisions.build_data_completeness(),
    )
    rows = constitution.check_and_log(trust_conn, decision_row, risk=RiskManager())
    assert len(rows) == 6
    for row in rows:
        _assert_utc_iso8601(row["check_timestamp"], f"constitution_enforcement_events.check_timestamp ({row['rule_id']})")
