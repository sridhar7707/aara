"""Domain vocabulary for who authored a Decision's action.

ADR-069 (B2): a Decision's action is authored either by the upstream
strategy / ensemble or by Sentinel's B2 recommendation rule. This enum is
the smallest vocabulary that distinguishes the two; `None` (field absent)
remains valid as a third state -- legacy / unknown / unspecified provenance --
and is never rewritten.

Inert classification only: it carries a value and nothing else -- no
evaluation, no enforcement beyond the adapter boundary check, no lifecycle,
no side effect, no authority. Mirrors the ADR-066 treatment of
DecisionAction / Horizon / EvidencePolarity.
"""
from enum import Enum


class ActionSource(str, Enum):
    STRATEGY = "STRATEGY"   # the action was authored by the upstream strategy / ensemble
    SENTINEL = "SENTINEL"   # the action was authored by Sentinel's B2 recommendation rule (ADR-069)

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls._value2member_map_
