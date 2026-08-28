"""Risk Intelligence screen structure -- real data or an explicit
unavailable state; never fabricated/illustrative risk figures.

Framework-independent dataclasses (no gradio import), mirroring
ui/portfolio_intelligence/screen.py's pattern. Deliberately does not name
a class `RiskEvaluation` (or any other sentinel_engine-contract-shaped
name) -- no such contract exists or is proposed by this package (see
docs/products/AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md
Section 4's "Missing contracts" finding). `state` is a plain string, not
an Enum reusing any real class name from bot/trust_ledger/risk.py or the
unrelated sentinel/backend scaffold -- NORMAL/WARNING/DEFENSIVE remain
valid literals only for an explicitly-injected RiskSnapshot.

`RiskScreen.current` defaults to None: no governed real risk source is
wired yet (ADR-004 Deferred; the Risk Intelligence design is future
architectural work), so the production default is "no real risk data"
(is_available is False) and the view renders an explicit UNAVAILABLE
state. Formatter/rendering tests may still construct a RiskScreen with an
explicit `current=` snapshot; that path is unchanged.
"""
from dataclasses import dataclass, field
from typing import Optional, Tuple

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
    current: Optional[RiskSnapshot] = None
    history: Tuple[RiskHistoryEntry, ...] = field(default=())

    @property
    def is_available(self) -> bool:
        """True only once a real RiskSnapshot has been supplied. The
        default (None) means no governed real risk source could be read in
        this environment -- the production UI must render an explicit
        UNAVAILABLE state, never a fabricated NORMAL/WARNING/DEFENSIVE
        badge, history, or sizing."""
        return self.current is not None

    @property
    def unavailable_message(self) -> str:
        return "Risk Intelligence data is currently unavailable."

    @property
    def is_empty(self) -> bool:
        return len(self.history) == 0

    @property
    def empty_state_message(self) -> str:
        return "No risk evaluations recorded yet."
