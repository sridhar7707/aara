"""Tests for analytics/scorecard.py (Phase 1B scaffolding)."""
from __future__ import annotations

import bot.trust_ledger.decisions as decisions
import bot.trust_ledger.outcomes as outcomes
import ledger.ledger as ledger_svc
from bot.strategy.model_output_adapter import build_model_outputs
from bot.trust_ledger.ids import new_constitution_event_id, new_event_id

from analytics.scorecard import generate_scorecard


def _write_executed_with_full_compliance(conn, reference_chain, asset):
    result = decisions.write_decision_event(
        conn,
        candidate_event_id=reference_chain["candidate_event_id"],
        asset=asset, action="BUY", event_type="EXECUTED",
        portfolio_snapshot={"value": 10000.0}, market_context={"regime": "TRENDING_UP"},
        model_outputs=build_model_outputs(0.7, 0.6, 0.2),
        risk_checks={"gates": []}, final_confidence=0.8,
        deployment_manifest_id=reference_chain["manifest_id"],
        intent=decisions.build_intent(
            "BUY", thesis="test thesis", invalidation_point="test invalidation",
            expected_return_basis_points=50.0,
        ),
        data_completeness=decisions.build_data_completeness(),
    )
    decision_id = result["decision_id"]
    outcomes.write_decision_outcome_event(
        conn, asset=asset, decision_id=decision_id,
        exit_timestamp="2026-07-29T00:00:00Z",
        gross_return=0.02, holding_period_days=5,
        spread_assumption=0.0, slippage_assumption=0.0,
    )
    for rule_id, rule_name in (
        ("rule_1", "Risk Governor Authority"), ("rule_2", "Position Sizing Discipline"),
        ("rule_3", "Trade Structure Requirement"), ("rule_4", "Portfolio Drawdown Circuit Breaker"),
        ("rule_5", "Approval Escalation for First N Trades"), ("rule_6", "Override Prevention"),
    ):
        ledger_svc.append_ledger_row(conn, "constitution_enforcement_events", {
            "event_id": new_constitution_event_id(),
            "decision_id": decision_id,
            "rule_id": rule_id, "rule_name": rule_name,
            "check_timestamp": "2026-07-29T00:00:00Z",
            "check_result": "PASS", "action_taken": "execution_proceeded", "reason": "test",
        })
    return decision_id


def _write_risk_evaluation(conn):
    ledger_svc.append_ledger_row(conn, "risk_evaluation_events", {
        "event_id": new_event_id(),
        "timestamp": "2026-07-29T00:00:00Z",
        "from_state": "OBSERVATION", "to_state": "NORMAL",
        "trigger_reason": "test", "validation_mode": "NATURAL",
        "replay_scenario_id": None,
        "recommended_position_size": 100.0, "actual_position_size": 100.0,
    })


def test_generate_scorecard_on_empty_ledger_fails_every_gate(conn):
    scorecard = generate_scorecard(conn)

    assert scorecard.evidence.decisions_collected == 0
    assert scorecard.evidence.hash_chain_broken_count == 0
    assert scorecard.gates.constitution_compliance_pass is False
    assert scorecard.gates.reproducibility_pass is False
    assert scorecard.gates.ledger_integrity_pass is True  # no rows to break
    assert scorecard.gates.risk_controls_active is False
    assert scorecard.all_governance_gates_pass is False


def test_generate_scorecard_passes_all_gates_with_clean_full_evidence(conn, reproducible_chain):
    _write_executed_with_full_compliance(conn, reproducible_chain, "AAPL")
    _write_risk_evaluation(conn)

    scorecard = generate_scorecard(conn)

    assert scorecard.evidence.decisions_collected == 1
    assert scorecard.evidence.outcomes_recorded == 1
    assert scorecard.evidence.hash_chain_broken_count == 0
    assert scorecard.gates.constitution_compliance_pass is True
    assert scorecard.gates.reproducibility_pass is True
    assert scorecard.gates.ledger_integrity_pass is True
    assert scorecard.gates.risk_controls_active is True
    assert scorecard.all_governance_gates_pass is True
    assert scorecard.compliance.overall_pass_rate == 1.0


def test_generate_scorecard_reproducibility_gate_fails_on_missing_artifact(conn, reference_chain):
    """reference_chain's model artifact path is fake ('/tmp/x.pkl', never
    written to disk) -- the reproducibility gate must catch that rather
    than reporting a false pass."""
    _write_executed_with_full_compliance(conn, reference_chain, "AAPL")
    _write_risk_evaluation(conn)

    scorecard = generate_scorecard(conn)

    assert scorecard.gates.reproducibility_pass is False
    assert scorecard.evidence.reproducibility_failures
    assert scorecard.all_governance_gates_pass is False
