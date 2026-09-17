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
class ConcentrationHolding:
    """One open position's symbol plus its already-computed allocation
    weight -- duplicated locally from ui/portfolio_intelligence/screen.py's
    own PortfolioHolding rather than imported (this package must not
    import ui/portfolio_intelligence/, per its own self-containment test,
    test_risk_intelligence_structure.py). Populated by bootstrap.py from
    the SAME PortfolioHolding.weight_pct Portfolio Intelligence's own
    Allocation by Holding section already renders -- this package never
    recomputes a weight itself."""
    symbol: str
    weight_pct: float


def holding_exceeds_max_position_size(
    weight_pct: Optional[float], max_position_size_pct: Optional[float]
) -> bool:
    """True only when `weight_pct` is strictly greater than
    `max_position_size_pct` -- both are real, already-displayed figures
    (a holding's weight_pct, and MAX_POSITION_SIZE_PCT below); this never
    computes, fetches, or infers either one.

    None-safe: either argument missing means no comparison can be made, so
    this returns False rather than guessing -- it never treats "unknown" as
    "exceeds." Equality-safe: a holding sitting exactly at the stated
    maximum has not exceeded it (`>`, not `>=`).

    Purely descriptive, matching this module's existing Concentration
    disclaimer -- naming an observed relationship between two numbers the
    screen already shows, never a risk violation, breach, or trading
    signal judgment."""
    if weight_pct is None or max_position_size_pct is None:
        return False
    return weight_pct > max_position_size_pct


@dataclass(frozen=True)
class RiskParameter:
    """One duplicated, read-only literal mirroring a value from the bot's
    own root config.py -- NOT imported (this package's established
    boundary convention; see adapters/legacy_risk_state_source.py's own
    "duplicates the tiny SELECT it needs as a literal string rather than
    importing bot's own writer" rule, applied here to a config constant
    instead of a SQL SELECT). Display only: shown as the system's current
    configuration, never as proof the UI itself enforces it -- enforcement,
    if any, happens entirely in bot/risk/* and bot/_main_cycle.py, both
    untouched by this package.

    `numeric_value` is an optional companion to `value_display` -- the same
    already-duplicated config.py figure, additionally exposed as a percent-
    scale number (matching ConcentrationHolding.weight_pct's own 0-100
    scale) so a caller can compare against it deterministically instead of
    parsing `value_display`'s free-text string. None for every parameter
    that has no such comparable figure (e.g. "Disabled", a plain count).
    Never a second, independently-chosen threshold -- only "Max Position
    Size" sets it below, from the exact same MAX_POSITION_PCT literal
    `value_display` already renders."""
    label: str
    value_display: str
    numeric_value: Optional[float] = None


# Duplicated from config.py (repo root) -- MUST be kept in sync by hand
# whenever config.py's own values change; there is no live read here, and
# this package must never import config.py or bot.* (see
# test_risk_intelligence_structure.py). Verified against config.py as of
# the Risk Intelligence Concentration/Parameters/Drawdown-Context sprint
# (baseline commit 5dac5d7). Each value's source name is noted so a future
# manual sync is a simple diff, not a re-derivation.
CURRENT_RISK_PARAMETERS: Tuple[RiskParameter, ...] = (
    # config.py: MAX_POSITION_PCT = 0.20
    RiskParameter(
        label="Max Position Size", value_display="20% of portfolio", numeric_value=20.0
    ),
    # config.py: MAX_RISK_PER_TRADE_PCT = 0.015
    RiskParameter(label="Max Risk Per Trade", value_display="1.5% of portfolio"),
    # config.py: MAX_POSITION_DRIFT_PCT = 0.25
    RiskParameter(label="Max Position Drift", value_display="25%"),
    # config.py: MAX_POSITIONS = 8
    RiskParameter(label="Max Open Positions", value_display="8"),
    # config.py: CORRELATION_THRESHOLD = 0.85
    RiskParameter(label="Correlation Threshold", value_display="0.85"),
    # config.py: MACD_CONFIRMATION_MIN = -inf (Gate 7.9, disabled by default)
    RiskParameter(label="MACD Confirmation Minimum", value_display="Disabled"),
)

# The single numeric source of truth for "does this holding exceed the
# stated maximum" -- read from the SAME CURRENT_RISK_PARAMETERS entry above
# by label, never a second literal. None if that entry is ever removed or
# renamed, so a caller must treat a missing maximum as "no comparison" (see
# holding_exceeds_max_position_size below) rather than fabricating one.
MAX_POSITION_SIZE_PCT: Optional[float] = next(
    (p.numeric_value for p in CURRENT_RISK_PARAMETERS if p.label == "Max Position Size"),
    None,
)


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
    # Concentration: real PortfolioHolding-derived weights, populated by the
    # composition root from an independent positions -> prices ->
    # _build_portfolio_holdings() read (the SAME chain Portfolio
    # Intelligence's own Holdings/Allocation by Holding uses, invoked a
    # second time here -- no new adapter, no new market-data source). None
    # means unavailable (open positions or current prices could not be
    # read); an empty tuple is a genuine "connected, no open positions"
    # result -- same None-vs-empty convention as drawdown_history above.
    concentration_holdings: Optional[Tuple[ConcentrationHolding, ...]] = None
    concentration_health: Optional[IntegrationHealth] = None

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
    def current_drawdown_pct(self) -> Optional[float]:
        """The most recently observed drawdown_history point's own
        drawdown_pct -- 0.0 at a new peak, a positive figure the further
        below it (this screen's own DrawdownPoint sign convention). None
        when drawdown_history is unavailable or empty -- never fabricated,
        and never computed from anything other than the already-fetched
        history the Portfolio Drawdown chart itself renders."""
        if not self.drawdown_history:
            return None
        return self.drawdown_history[-1].drawdown_pct

    # --- Concentration -----------------------------------------------------

    @property
    def concentration_is_available(self) -> bool:
        return self.concentration_holdings is not None

    @property
    def concentration_is_empty(self) -> bool:
        return self.concentration_holdings is not None and len(self.concentration_holdings) == 0

    @property
    def concentration_empty_state_message(self) -> str:
        return "No open positions to show concentration for."

    @property
    def largest_concentration_holding(self) -> Optional[ConcentrationHolding]:
        """The single largest position by weight_pct -- weight_pct is
        already the authoritative figure (bootstrap.py's
        _build_portfolio_holdings), never recomputed here. Deterministic:
        highest weight_pct first, ties broken alphabetically by symbol --
        the same tie-break Portfolio Intelligence's own Allocation by
        Holding bar list uses, so identical inputs always render the same
        answer. None when concentration is unavailable or there are no
        open positions."""
        if not self.concentration_holdings:
            return None
        return min(self.concentration_holdings, key=lambda h: (-h.weight_pct, h.symbol))

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
