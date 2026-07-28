"""Plain dataclasses mirroring each Phase 0 table's logical payload.

Group A (ledger) dataclasses cover the caller-supplied fields only --
sequence_number/record_hash/previous_record_hash are computed by
ledger.append_ledger_row() and are not part of the logical payload a caller
constructs. Group B (reference) dataclasses mirror the full row, since those
tables carry no hash-chain columns.

JSON-typed fields (portfolio_snapshot, market_context, model_outputs, etc.)
are native dicts/lists here, not pre-serialized strings -- ledger.py handles
JSON encoding at the storage boundary.
"""
from __future__ import annotations

import dataclasses


# ── Group A: Immutable Trust Ledger (payload only, pre-hash) ─────────────────

@dataclasses.dataclass
class CandidateEvaluationEvent:
    candidate_event_id: str
    timestamp: str
    asset: str
    screening_version: str
    screening_results: dict
    data_available: bool
    required_models_available: bool
    evaluation_requested: bool
    evaluation_completed: bool   # v1.2 (FR-0.13): distinct from evaluation_requested --
                                  # a crashed/partial evaluation must never look like a
                                  # genuine qualified rejection (FR-0.1a)


@dataclasses.dataclass
class DecisionEvent:
    """No outcome_state field (v1.2) -- decision_events is immutable with
    zero exceptions. Lifecycle state (OPEN/CLOSED) is derived by the
    decision_state SQL view, based on whether a decision_outcome_events row
    exists; ANALYZED is deliberately not modeled in Phase 0 (Phase 1
    calibration-batch design)."""
    decision_id: str
    candidate_event_id: str
    timestamp: str
    asset: str
    action: str                     # BUY / SELL / HOLD / REJECT
    event_type: str                 # EXECUTED / QUALIFIED_REJECTION
    portfolio_snapshot: dict
    market_context: dict
    model_outputs: dict
    risk_checks: dict
    final_confidence: float         # 0.0-1.0, DB-enforced via CHECK
    deployment_manifest_id: str
    intent: dict                    # {primary_intent, contributing_modules[]}
    data_completeness: dict         # {status, missing_inputs[], stale_inputs[]}


@dataclasses.dataclass
class DecisionOutcomeEvent:
    outcome_id: str
    decision_id: str
    exit_timestamp: str
    gross_return: float
    net_return: float
    holding_period_days: int
    cost_breakdown: dict
    cost_model_id: str


@dataclasses.dataclass
class RiskEvaluationEvent:
    event_id: str
    timestamp: str
    from_state: str                 # OBSERVATION / NORMAL / WARNING / DEFENSIVE
    to_state: str
    trigger_reason: str
    validation_mode: str             # NATURAL / REPLAY_FORCED
    replay_scenario_id: str | None = None
    recommended_position_size: float | None = None   # v1.5: what the Risk Governor would apply
    actual_position_size: float | None = None         # v1.5: what actually happened to the account


@dataclasses.dataclass
class ApprovalEvent:
    approval_id: str
    timestamp: str
    subject_type: str    # WEIGHT_CHANGE / MANIFEST_PROMOTION / EXPERIMENT_PROMOTION / RISK_RULE_CHANGE / CAPITAL_INCREASE
    subject_id: str
    decision: str         # APPROVE / REJECT / DEFER
    reason_checklist: dict
    reason_comment: str
    reviewer: str


@dataclasses.dataclass
class DeploymentManifestEvent:
    event_id: str         # v1.3, e.g. MFE-20260728-001
    manifest_id: str
    event_type: str       # CREATED / TESTING_STARTED / REVIEW_REQUESTED / APPROVED / PROMOTED / RETIRED
    timestamp: str
    approval_event_id: str | None = None


@dataclasses.dataclass
class CostModel:
    cost_model_id: str
    spread_assumption: float
    slippage_assumption: float
    commission_rules: dict
    tax_assumptions: dict
    created_at: str


# ── Group B: Versioned Reference Records (full row, no hash chain) ──────────

@dataclasses.dataclass
class ModelArtifact:
    artifact_id: str
    model_family: str
    version_label: str
    feature_set_hash: str
    created_at: str
    architecture_notes: str | None = None


@dataclasses.dataclass
class ModelTrainingRun:
    training_run_id: str
    artifact_id: str
    training_data_start: str
    training_data_end: str
    validation_metrics: dict
    trained_at: str
    artifact_storage_ref: str
    artifact_checksum: str
    artifact_size_bytes: int    # v1.2: cheap second signal alongside checksum
    artifact_created_at: str    # v1.2: filesystem timestamp, distinct from trained_at


@dataclasses.dataclass
class StrategyVersion:
    strategy_version_id: str
    rules: dict
    created_at: str
    notes: str | None = None


@dataclasses.dataclass
class RiskRuleset:
    risk_ruleset_id: str
    rules: dict
    created_at: str


@dataclasses.dataclass
class DeploymentManifest:
    manifest_id: str
    component_training_runs: dict
    risk_ruleset_id: str
    strategy_version_id: str
    feature_pipeline_version: str   # v1.2: promoted out of runtime_environment JSON
    runtime_environment: dict       # {python, xgboost_lib_version, random_seed}
    created_at: str


# ── Group C: Operational Tables ──────────────────────────────────────────────

@dataclasses.dataclass
class DataQualityEvent:
    event_id: str
    timestamp: str
    source: str
    status: str    # HEALTHY / DEGRADED / DOWN
    detail: str | None = None
