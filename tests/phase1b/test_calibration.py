"""Tests for analytics/calibration.py (Phase 1B scaffolding)."""
from __future__ import annotations

import bot.trust_ledger.decisions as decisions
import bot.trust_ledger.outcomes as outcomes
from bot.strategy.model_output_adapter import build_model_outputs

from analytics.calibration import (
    confidence_calibration, data_quality_impact, return_by_model_agreement,
)


def _write_executed(
    conn, reference_chain, asset, xgb_prob, lstm_prob, sentiment,
    final_confidence, net_return, data_completeness=None,
):
    result = decisions.write_decision_event(
        conn,
        candidate_event_id=reference_chain["candidate_event_id"],
        asset=asset, action="BUY", event_type="EXECUTED",
        portfolio_snapshot={"value": 10000.0}, market_context={"regime": "TRENDING_UP"},
        model_outputs=build_model_outputs(xgb_prob, lstm_prob, sentiment),
        risk_checks={"gates": []}, final_confidence=final_confidence,
        deployment_manifest_id=reference_chain["manifest_id"],
        intent=decisions.build_intent("BUY"),
        data_completeness=data_completeness or decisions.build_data_completeness(),
    )
    outcomes.write_decision_outcome_event(
        conn, asset=asset, decision_id=result["decision_id"],
        exit_timestamp="2026-07-29T00:00:00Z",
        gross_return=net_return, holding_period_days=5,
        spread_assumption=0.0, slippage_assumption=0.0,
    )
    return result


def test_confidence_calibration_empty_ledger_returns_empty_list(conn):
    assert confidence_calibration(conn) == []


def test_confidence_calibration_buckets_by_final_confidence(conn, reference_chain):
    _write_executed(conn, reference_chain, "AAPL", 0.7, 0.6, 0.2, final_confidence=0.95, net_return=0.05)
    _write_executed(conn, reference_chain, "MSFT", 0.7, 0.6, 0.2, final_confidence=0.8, net_return=-0.02)
    _write_executed(conn, reference_chain, "TSLA", 0.7, 0.6, 0.2, final_confidence=0.6, net_return=0.01)
    _write_executed(conn, reference_chain, "NVDA", 0.7, 0.6, 0.2, final_confidence=0.3, net_return=-0.01)

    buckets = {b.label: b for b in confidence_calibration(conn)}

    assert buckets[">0.9"].decisions == 1
    assert buckets[">0.9"].win_rate == 1.0
    assert buckets["0.7-0.9"].decisions == 1
    assert buckets["0.7-0.9"].win_rate == 0.0
    assert buckets["0.5-0.7"].decisions == 1
    assert buckets["0.5-0.7"].win_rate == 1.0
    assert buckets["<0.5"].decisions == 1
    assert buckets["<0.5"].win_rate == 0.0


def test_confidence_calibration_bucket_boundaries_are_inclusive_at_low_end(conn, reference_chain):
    _write_executed(conn, reference_chain, "AAPL", 0.7, 0.6, 0.2, final_confidence=0.7, net_return=0.01)
    _write_executed(conn, reference_chain, "MSFT", 0.7, 0.6, 0.2, final_confidence=0.5, net_return=0.01)

    buckets = {b.label: b for b in confidence_calibration(conn)}

    assert buckets["0.7-0.9"].decisions == 1
    assert buckets["0.5-0.7"].decisions == 1


def test_return_by_model_agreement_empty_ledger_returns_empty_list(conn):
    assert return_by_model_agreement(conn) == []


def test_return_by_model_agreement_buckets_by_signal_consensus(conn, reference_chain):
    # All three models signal BUY (xgb>0.5, lstm>0.5, sentiment>0.0).
    _write_executed(conn, reference_chain, "AAPL", 0.7, 0.6, 0.2, final_confidence=0.8, net_return=0.05)
    # xgb+lstm signal BUY, sentiment signals SELL -- 2 of 3 agree.
    _write_executed(conn, reference_chain, "MSFT", 0.7, 0.6, -0.2, final_confidence=0.8, net_return=0.02)
    # xgb BUY, lstm SELL, sentiment HOLD (exactly 0.0) -- three-way disagreement.
    _write_executed(conn, reference_chain, "TSLA", 0.7, 0.3, 0.0, final_confidence=0.6, net_return=-0.03)

    buckets = {b.label: b for b in return_by_model_agreement(conn)}

    assert buckets["XGBoost + LSTM + FinBERT agree"].decisions == 1
    assert buckets["XGBoost + LSTM + FinBERT agree"].avg_return == 0.05
    assert buckets["2 of 3 agree"].decisions == 1
    assert buckets["Disagreement (tie/mixed)"].decisions == 1


def test_data_quality_impact_empty_ledger_returns_empty_list(conn):
    assert data_quality_impact(conn) == []


def test_data_quality_impact_buckets_by_status(conn, reference_chain):
    complete = decisions.build_data_completeness()
    degraded = decisions.build_data_completeness(lstm_is_degraded=True)

    _write_executed(conn, reference_chain, "AAPL", 0.7, 0.6, 0.2, final_confidence=0.8,
                     net_return=0.05, data_completeness=complete)
    _write_executed(conn, reference_chain, "MSFT", 0.7, 0.6, 0.2, final_confidence=0.8,
                     net_return=-0.03, data_completeness=degraded)

    buckets = {b.status: b for b in data_quality_impact(conn)}

    assert buckets["COMPLETE"].decisions == 1
    assert buckets["COMPLETE"].win_rate == 1.0
    assert buckets["DEGRADED"].decisions == 1
    assert buckets["DEGRADED"].win_rate == 0.0
