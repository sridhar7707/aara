"""Phase 1B scaffolding (phase1b_requirements.md Section 4): calibration
bucket analysis over the Trust Ledger's accumulated EXECUTED decisions.

Not wired into any dashboard, cron job, or bot pipeline -- Phase 1B
implementation is gated on Phase 1A acceptance (day 30, phase1b_requirements.md
"Gate"). This module exists so the query shape is ready once there is real
decision history to query; today it will legitimately return empty lists.

Implements Section 4.1 (win rate by confidence bucket), 4.2 (return by model
agreement), and 4.3 (data quality impact) for real -- all three read only
columns that already exist on decision_events/decision_outcome_events with a
decided format (final_confidence, model_outputs[model].signal,
data_completeness.status).

Section 4.4 (Risk Adjustment Effectiveness -- governor recommended vs. actual
position size, per decision) is deliberately NOT implemented here:
risk_evaluation_events has no decision_id column (it logs portfolio-level Risk
Governor state transitions, not per-decision sizing), so there is no join
that connects a decision to "what the governor recommended for it" today.
Building that requires either a schema change or a different data source that
Phase 1B hasn't specified -- guessing one now would risk producing a
same-named-but-wrong metric.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

_EXECUTED_WITH_OUTCOME = (
    "SELECT d.final_confidence, d.model_outputs, d.data_completeness, o.net_return "
    "FROM decision_events d "
    "JOIN decision_outcome_events o ON o.decision_id = d.decision_id "
    "WHERE d.event_type = 'EXECUTED'"
)


@dataclass
class ConfidenceBucket:
    label: str
    decisions: int
    win_rate: float
    avg_return: float


@dataclass
class ModelAgreementBucket:
    label: str
    decisions: int
    avg_return: float


@dataclass
class DataQualityBucket:
    status: str
    decisions: int
    win_rate: float
    avg_return: float


def _confidence_label(confidence: float) -> str:
    if confidence > 0.9:
        return ">0.9"
    if confidence >= 0.7:
        return "0.7-0.9"
    if confidence >= 0.5:
        return "0.5-0.7"
    return "<0.5"


def _agreement_label(model_outputs: dict) -> str:
    signals = [model_outputs[m]["signal"] for m in ("xgboost", "lstm", "finbert") if m in model_outputs]
    if not signals:
        return "Disagreement (tie/mixed)"
    counts: dict[str, int] = {}
    for s in signals:
        counts[s] = counts.get(s, 0) + 1
    top = max(counts.values())
    if top == len(signals):
        return "XGBoost + LSTM + FinBERT agree"
    if top == 2:
        return "2 of 3 agree"
    return "Disagreement (tie/mixed)"


def confidence_calibration(conn: sqlite3.Connection) -> list[ConfidenceBucket]:
    """Section 4.1: win rate and average return, bucketed by final_confidence."""
    by_bucket: dict[str, list[float]] = {}
    for confidence, _model_outputs, _data_completeness, net_return in conn.execute(_EXECUTED_WITH_OUTCOME):
        by_bucket.setdefault(_confidence_label(confidence), []).append(net_return)

    return [
        ConfidenceBucket(
            label=label,
            decisions=len(returns),
            win_rate=sum(1 for r in returns if r > 0) / len(returns),
            avg_return=sum(returns) / len(returns),
        )
        for label, returns in by_bucket.items()
    ]


def return_by_model_agreement(conn: sqlite3.Connection) -> list[ModelAgreementBucket]:
    """Section 4.2: average return, bucketed by how many of the three models
    (XGBoost/LSTM/FinBERT) agreed on the same signal for that decision."""
    by_bucket: dict[str, list[float]] = {}
    for _confidence, model_outputs_json, _data_completeness, net_return in conn.execute(_EXECUTED_WITH_OUTCOME):
        model_outputs = json.loads(model_outputs_json)
        by_bucket.setdefault(_agreement_label(model_outputs), []).append(net_return)

    return [
        ModelAgreementBucket(label=label, decisions=len(returns), avg_return=sum(returns) / len(returns))
        for label, returns in by_bucket.items()
    ]


def data_quality_impact(conn: sqlite3.Connection) -> list[DataQualityBucket]:
    """Section 4.3: win rate and average return, bucketed by data_completeness.status."""
    by_bucket: dict[str, list[float]] = {}
    for _confidence, _model_outputs, data_completeness_json, net_return in conn.execute(_EXECUTED_WITH_OUTCOME):
        status = json.loads(data_completeness_json)["status"]
        by_bucket.setdefault(status, []).append(net_return)

    return [
        DataQualityBucket(
            status=status,
            decisions=len(returns),
            win_rate=sum(1 for r in returns if r > 0) / len(returns),
            avg_return=sum(returns) / len(returns),
        )
        for status, returns in by_bucket.items()
    ]
