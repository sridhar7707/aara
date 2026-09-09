"""Domain vocabulary for a Decision's investment horizon.

The horizon reflects what drives the opportunity, not a fixed calendar
length -- see docs/architecture/SENTINEL_ENGINE_PAPER_TRADING_BEHAVIORAL_CONTRACT_P0.md
Section 4. A horizon change is a new, separately reasoned Decision, never
an edit to an existing one. This module defines the vocabulary only --
no transition rule, expiry, or extension logic belongs here or in this
batch.
"""
from enum import Enum


class Horizon(str, Enum):
    TACTICAL = "TACTICAL"
    MEDIUM = "MEDIUM"
    LONG = "LONG"

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls._value2member_map_
