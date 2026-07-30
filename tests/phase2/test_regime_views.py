"""Tests for analytics/regime_views.py (Phase 2 scaffolding)."""
from __future__ import annotations

import bot.trust_ledger.decisions as decisions
import bot.trust_ledger.outcomes as outcomes
from bot.strategy.model_output_adapter import build_model_outputs

from analytics.regime_views import regime_performance


def _write_executed_decision(conn, reference_chain, asset, regime, net_return):
    result = decisions.write_decision_event(
        conn,
        candidate_event_id=reference_chain["candidate_event_id"],
        asset=asset, action="BUY", event_type="EXECUTED",
        portfolio_snapshot={"value": 10000.0}, market_context={"regime": regime},
        model_outputs=build_model_outputs(0.7, 0.6, 0.2),
        risk_checks={"gates": []}, final_confidence=0.65,
        deployment_manifest_id=reference_chain["manifest_id"],
        intent=decisions.build_intent("BUY"),
        data_completeness=decisions.build_data_completeness(),
    )
    outcomes.write_decision_outcome_event(
        conn, asset=asset, decision_id=result["decision_id"],
        exit_timestamp="2026-07-29T00:00:00Z",
        gross_return=net_return, holding_period_days=5,
        spread_assumption=0.0, slippage_assumption=0.0,
    )


def test_regime_performance_empty_ledger_returns_empty_list(conn):
    assert regime_performance(conn) == []


def test_regime_performance_aggregates_by_regime(conn, reference_chain):
    _write_executed_decision(conn, reference_chain, "AAPL", "TRENDING_UP", 0.05)
    _write_executed_decision(conn, reference_chain, "MSFT", "TRENDING_UP", -0.02)
    _write_executed_decision(conn, reference_chain, "TSLA", "HIGH_VOLATILITY", -0.10)

    results = {r.regime: r for r in regime_performance(conn)}

    assert results["TRENDING_UP"].decisions == 2
    assert results["TRENDING_UP"].win_rate == 0.5
    assert results["HIGH_VOLATILITY"].decisions == 1
    assert results["HIGH_VOLATILITY"].win_rate == 0.0


def test_regime_performance_ignores_qualified_rejections(conn, reference_chain):
    decisions.write_decision_event(
        conn,
        candidate_event_id=reference_chain["candidate_event_id"],
        asset="AAPL", action="HOLD", event_type="QUALIFIED_REJECTION",
        portfolio_snapshot={"value": 10000.0}, market_context={"regime": "RANGING"},
        model_outputs=build_model_outputs(0.5, 0.5, 0.0),
        risk_checks={"gates": []}, final_confidence=0.5,
        deployment_manifest_id=reference_chain["manifest_id"],
        intent=decisions.build_intent("HOLD"),
        data_completeness=decisions.build_data_completeness(),
    )

    assert regime_performance(conn) == []
