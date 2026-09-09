"""Domain vocabulary for the investment action a Decision proposes.

Every action here is a recommendation, never an executable order -- see
docs/architecture/SENTINEL_ENGINE_PAPER_TRADING_BEHAVIORAL_CONTRACT_P0.md
Sections 1-2. BUY_MORE is distinct from BUY: it always refers to an
existing position and requires the P0 blank-slate reassessment behavior a
later batch implements against this vocabulary. WAIT is a first-class
recommendation outcome, never an execution order -- nothing in this
module, or in DecisionService, ever calls an executor.
"""
from enum import Enum


class DecisionAction(str, Enum):
    BUY = "BUY"
    BUY_MORE = "BUY_MORE"
    HOLD = "HOLD"
    SELL = "SELL"
    WAIT = "WAIT"

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls._value2member_map_
