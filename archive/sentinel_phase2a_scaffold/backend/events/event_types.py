"""Sentinel event type constants (SYSTEM_EVENT_MODEL_v1.2.md).

Phase 0 events (candidate_evaluation_events, decision_events,
decision_outcome_events, risk_evaluation_events, approval_events,
deployment_manifest_events, cost_models) already exist in the
existing bot/ledger.py + database/schema.sql and are explicitly
"do not modify" -- they are out of scope for this package.

This module lists the v1.2 decision-intelligence event types plus the
Decision lifecycle events that drive DecisionState transitions
(domain/enums.py). No implementation; names only, for use by
EventWriter and repositories once Phase 2A moves past scaffolding.
"""

from enum import Enum


class EventType(str, Enum):
    # Decision lifecycle (drives DecisionState transitions)
    DECISION_IDENTIFIED = "decision_identified_event"
    DECISION_EVALUATED = "decision_evaluated_event"
    DECISION_GOVERNED = "decision_governed_event"
    DECISION_APPROVED = "decision_approved_event"
    DECISION_DISPATCHED = "decision_dispatched_event"
    DECISION_EXECUTED = "decision_executed_event"
    DECISION_REVIEWED = "decision_reviewed_event"
    DECISION_CLOSED = "decision_closed_event"

    # v1.2 NEW event types
    MARKET_CONTEXT_SNAPSHOT = "market_context_snapshot_event"
    EVIDENCE_ARTIFACT_RECORDED = "evidence_artifact_recorded_event"
    POSITION_LOT_OPENED = "position_lot_opened_event"
    POSITION_LOT_CLOSED = "position_lot_closed_event"
    KNOWLEDGE_ENTRY = "knowledge_entry_event"
    KNOWLEDGE_RELATIONSHIP = "knowledge_relationship_event"
    EXECUTION_PARTIAL_FILL = "execution_partial_fill_event"
    GOVERNANCE_EVALUATION = "governance_evaluation_event"
    APPROVAL_DECISION = "approval_decision_event"
    DECISION_QUALITY_ASSESSMENT = "decision_quality_assessment_event"

    # Risk Governor / integrity (RiskGovernorState is 3-state; breaches
    # beyond DEFENSIVE are recorded here, not as a 4th state)
    RISK_GOVERNOR_STATE_CHANGED = "risk_governor_state_changed_event"
    GOVERNANCE_INTEGRITY_BREACH = "governance_integrity_breach_event"
