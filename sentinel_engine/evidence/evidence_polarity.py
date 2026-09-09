"""Domain vocabulary distinguishing whether a piece of Evidence supports
or contradicts the Decision it is attached to -- see
docs/architecture/SENTINEL_ENGINE_PAPER_TRADING_BEHAVIORAL_CONTRACT_P0.md
Section 3. Both polarities are preserved on the one Evidence type; this
is a classification of existing evidence, not a reason to fork separate
SupportingEvidence/ContradictingEvidence types.
"""
from enum import Enum


class EvidencePolarity(str, Enum):
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls._value2member_map_
