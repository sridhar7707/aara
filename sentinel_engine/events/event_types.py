"""Event type constants for the Sentinel event system."""
from enum import Enum


class EventType(str, Enum):
    CANDIDATE_EVALUATED = "CANDIDATE_EVALUATED"
    DECISION_CREATED = "DECISION_CREATED"
    RISK_EVALUATED = "RISK_EVALUATED"
    DECISION_EXECUTED = "DECISION_EXECUTED"
    DECISION_OUTCOME_RECORDED = "DECISION_OUTCOME_RECORDED"

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls._value2member_map_
