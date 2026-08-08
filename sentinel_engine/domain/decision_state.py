"""Decision lifecycle state: where a decision currently is in its
event-sourced lifecycle, as derived by DecisionProjection.

Distinct from EventType (sentinel_engine.events.event_types): EventType
answers "what happened" (the ledger's event vocabulary); DecisionState
answers "where is this decision now" (the projection's current status).
They are aliased 1:1 today only because every currently-implemented
lifecycle step happens to advance status to its own triggering event's
name -- that is a today-only implementation detail, not a reason to merge
the two types.

Only states a real service currently produces belong here. Do not add
CANDIDATE_EVALUATED, RISK_EVALUATED, DECISION_EXECUTED, or
DECISION_OUTCOME_RECORDED until an actual service path transitions a
decision into one of them.
"""
from enum import Enum


class DecisionState(str, Enum):
    DECISION_CREATED = "DECISION_CREATED"
    EVIDENCE_ATTACHED = "EVIDENCE_ATTACHED"
    GOVERNANCE_EVALUATED = "GOVERNANCE_EVALUATED"
    APPROVAL_RECORDED = "APPROVAL_RECORDED"

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls._value2member_map_
