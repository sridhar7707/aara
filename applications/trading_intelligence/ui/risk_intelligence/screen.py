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

`RiskScreen.current` defaults to None: when the operational `risk_state`
table (via adapters/legacy_risk_state_source.py) cannot be read -- the
deployed HF Space's normal state -- the production default is "no real
risk data" (is_available is False) and the view renders an explicit
UNAVAILABLE state. Formatter/rendering tests may still construct a
RiskScreen with an explicit `current=` snapshot.

`RiskSnapshot.state` and `.as_of` are the only fields the operational
`risk_state` table can supply, so they stay required. `trigger_reason`,
`recommended_sizing_pct`, and `actual_sizing_pct` are NOT persisted in
`risk_state` (they live only in the hash-chained `risk_evaluation_events`
ledger table, which this slice deliberately does not read) -- they are
Optional and default to None, and the view states explicitly when they
are not recorded in this data source. History is never fabricated.
"""
from dataclasses import dataclass, field
from typing import Optional, Tuple

from applications.platform.integrations import IntegrationHealth

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
class DrawdownPoint:
    """Sprint 1: one real portfolio_snapshots row plus its own drawdown
    from the running peak observed up to and including that point --
    `drawdown_pct` is 0.0 at a new all-time-high point and a positive
    percentage the further `portfolio_value` sits below the running peak.
    This IS a derived figure, computed by bootstrap.py from the same real
    portfolio_snapshots history Portfolio Intelligence's and Morning
    Brief's own charts read -- unlike those two screens' own charts, whose
    scope is deliberately limited to raw, non-derived values, Risk
    Intelligence's whole purpose is risk-relevant derived context, so
    drawdown is computed here by design, not smuggled in."""
    as_of: str
    portfolio_value: float
    drawdown_pct: float


@dataclass(frozen=True)
class RiskSnapshot:
    state: str
    as_of: str
    trigger_reason: Optional[str] = None
    recommended_sizing_pct: Optional[float] = None
    actual_sizing_pct: Optional[float] = None

    def __post_init__(self):
        if self.state not in _VALID_STATES:
            raise ValueError(f"state must be one of {_VALID_STATES}, got {self.state!r}")

    @property
    def sizing_gap_pct(self) -> Optional[float]:
        """Positive means actual sizing is under the recommendation
        (de-risked further than required); negative means actual sizing
        exceeds it. None when either sizing figure is not recorded in the
        current data source -- callers must not compute or display a gap
        in that case."""
        if self.recommended_sizing_pct is None or self.actual_sizing_pct is None:
            return None
        return self.recommended_sizing_pct - self.actual_sizing_pct


@dataclass(frozen=True)
class RiskScreen:
    current: Optional[RiskSnapshot] = None
    history: Tuple[RiskHistoryEntry, ...] = field(default=())
    # ADR-061 Category A (A4): integration health behind the current-state
    # section, populated by the composition root (bootstrap.py) from the
    # LegacyRiskStateSource ReadResult -- carries whether the operational
    # risk_state table was HEALTHY (with or without a row) or unavailable.
    state_health: Optional[IntegrationHealth] = None
    # Sprint 1: real portfolio drawdown over time, alongside (never
    # overlaid onto, never implying a causal link with) the single current
    # observed risk-state classification above. None means unavailable; an
    # empty tuple is a genuine "connected, no rows yet" result -- same
    # None-vs-empty convention as portfolio_history on the sibling screens.
    drawdown_history: Optional[Tuple[DrawdownPoint, ...]] = None
    drawdown_history_health: Optional[IntegrationHealth] = None

    @property
    def drawdown_history_is_available(self) -> bool:
        return self.drawdown_history is not None

    @property
    def drawdown_history_is_empty(self) -> bool:
        return self.drawdown_history is not None and len(self.drawdown_history) == 0

    @property
    def drawdown_history_empty_state_message(self) -> str:
        return "No portfolio history is recorded yet."

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
        # This data source (the operational risk_state table) structurally
        # carries only the current classification, never an evaluation
        # history -- so this is a permanent property of the source, not a
        # "none logged yet" state. Wording mirrors the trigger-reason /
        # sizing "not recorded in this data source" lines on the same card.
        return "Risk evaluation history is not recorded in this data source."
