"""Human/system approval verdict on a decision -- a distinct concept from
DecisionState (sentinel_engine.domain.decision_state): DecisionState
answers "where is this decision in its lifecycle", ApprovalStatus answers
"what was the governance verdict". Never reuse DecisionState for this.
"""
from enum import Enum


class ApprovalStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls._value2member_map_
