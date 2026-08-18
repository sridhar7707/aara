"""Risk Intelligence screen structure -- illustrative MVP.

Framework-independent dataclasses (no gradio import), mirroring
ui/portfolio_intelligence/screen.py's pattern. Deliberately does not name
a class `RiskEvaluation` (or any other sentinel_engine-contract-shaped
name) -- no such contract exists or is proposed by this package (see
docs/products/AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md
Section 4's "Missing contracts" finding). `state` is a plain string, not
an Enum reusing any real class name from bot/trust_ledger/risk.py or the
unrelated sentinel/backend scaffold -- NORMAL/WARNING/DEFENSIVE here are
illustrative literals local to this screen only.
"""
from dataclasses import dataclass, field
from typing import Tuple

_VALID_STATES = ("NORMAL", "WARNING", "DEFENSIVE")


@dataclass(frozen=True)
class RiskHistoryEntry:
    timestamp: str
    state: str
    trigger_reason: str
    recommended_sizing_pct: float
    actual_sizing_pct: float

    def __post_init__(self):
        if self.state not in _VALID_STATES:
            raise ValueError(f"state must be one of {_VALID_STATES}, got {self.state!r}")


@dataclass(frozen=True)
class RiskSnapshot:
    state: str
    trigger_reason: str
    recommended_sizing_pct: float
    actual_sizing_pct: float
    as_of: str

    def __post_init__(self):
        if self.state not in _VALID_STATES:
            raise ValueError(f"state must be one of {_VALID_STATES}, got {self.state!r}")

    @property
    def sizing_gap_pct(self) -> float:
        """Positive means actual sizing is under the recommendation
        (de-risked further than required); negative means actual sizing
        exceeds it."""
        return self.recommended_sizing_pct - self.actual_sizing_pct


@dataclass(frozen=True)
class RiskScreen:
    current: RiskSnapshot
    history: Tuple[RiskHistoryEntry, ...] = field(default=())

    @property
    def is_empty(self) -> bool:
        return len(self.history) == 0

    @property
    def empty_state_message(self) -> str:
        return "No risk evaluations recorded yet."
