"""Portfolio Intelligence screen structure -- real data or an explicit
unavailable state; never fabricated/illustrative portfolio figures.

Framework-independent dataclasses (no gradio import), mirroring
ui/decision_center/screen.py's pattern. Field names on CapitalSummary
match bot/capital/pool.py::CapitalPool's real vocabulary
(allocated_amount/available_cash/invested_amount/reserve/realized_profit)
and total_value/tradeable_cash reuse its exact definitions -- not imported
(bot/ is ADR-002-protected and out of scope for this package), just the
same real names rather than inventing new ones, per the "Feature Discovery
vs. Feature Invention" principle applied elsewhere in this product's docs.

AlpacaAccountSnapshot/AlpacaPosition (2026-08-27 unit) are a deliberately
SEPARATE concept from CapitalSummary/PortfolioHolding, not a replacement --
CapitalSummary/PortfolioHolding reflect the bot's own internal bookkeeping
(capital_pools/position_state, trades.db), while these reflect Alpaca's
own broker-side paper account, the actual system of record for what the
paper account holds. The two are expected to occasionally disagree (a
real, observed divergence: as of this unit, Alpaca's paper account holds
5 positions while position_state holds 6 -- BAC is absent from Alpaca).
Rendered as its own clearly-labeled "ALPACA PAPER" section, never merged
into or silently reconciled with Holdings.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from applications.platform.integrations import IntegrationHealth


@dataclass(frozen=True)
class PortfolioHolding:
    symbol: str
    quantity: float
    price: float
    market_value: float
    weight_pct: float


@dataclass(frozen=True)
class CapitalSummary:
    allocated_amount: float
    available_cash: float
    invested_amount: float
    reserve: float
    realized_profit: float

    @property
    def total_value(self) -> float:
        """Available cash + current open-position cost basis -- same
        definition as CapitalPool.total_value."""
        return self.available_cash + self.invested_amount

    @property
    def tradeable_cash(self) -> float:
        """Cash available for new positions (available minus reserve) --
        same definition as CapitalPool.tradeable_cash."""
        return max(0.0, self.available_cash - self.reserve)

    @property
    def cash_weight_pct(self) -> float:
        if self.total_value <= 0:
            return 0.0
        return (self.available_cash / self.total_value) * 100

    @property
    def invested_weight_pct(self) -> float:
        if self.total_value <= 0:
            return 0.0
        return (self.invested_amount / self.total_value) * 100


@dataclass(frozen=True)
class AlpacaPosition:
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_plpc: float
    side: str


@dataclass(frozen=True)
class AlpacaAccountSnapshot:
    equity: float
    cash: float
    buying_power: float
    portfolio_value: float


@dataclass(frozen=True)
class AlpacaOrder:
    """One row of Alpaca's own broker-side Paper order history (2026-08-27
    unit). A pure observation record: `side`/`status` are the broker's own
    verbatim strings, `order_id` is retained only for dedupe/stable
    ordering and is never presented as a Decision identifier, and no
    client_order_id/order_class/legs/strategy metadata is carried. Working
    (still-live) orders are flagged via `is_working`; the raw `status`
    string is preserved unchanged regardless."""
    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: str
    filled_quantity: str
    status: str
    submitted_at: datetime
    filled_at: Optional[datetime]
    limit_price: str
    is_working: bool


@dataclass(frozen=True)
class PortfolioHistoryPoint:
    """One real portfolio_snapshots row -- the equity/value-over-time chart
    plots these verbatim, in ascending as_of order. No derived figures
    (return, drawdown, Sharpe, etc.) are ever computed from this or carried
    on it; it is portfolio_value at a point in time, nothing else."""
    as_of: str
    portfolio_value: float


class ReconciliationStatus(Enum):
    """The four factual outcomes of comparing one symbol's Internal
    Portfolio quantity against its Alpaca PAPER quantity -- descriptive
    only, never a risk/error/health/trading judgment. See ReconciliationRow
    below."""
    MATCHED = "MATCHED"
    INTERNAL_ONLY = "INTERNAL_ONLY"
    BROKER_ONLY = "BROKER_ONLY"
    QUANTITY_DIFFERENCE = "QUANTITY_DIFFERENCE"


@dataclass(frozen=True)
class ReconciliationRow:
    """One symbol's Internal Portfolio vs Alpaca PAPER comparison -- a
    pure, descriptive fact computed (see bootstrap.py's
    _compute_portfolio_reconciliation) from the SAME already-fetched
    PortfolioHolding / AlpacaPosition tuples this screen already carries.
    No new read, no new adapter, no invented tolerance/valuation/health
    score. `internal_quantity`/`alpaca_quantity`/market values are None
    only when that side has no position in this symbol at all (INTERNAL_
    ONLY / BROKER_ONLY); `quantity_difference` is populated only when both
    sides have a position (0.0 for MATCHED, the real signed difference for
    QUANTITY_DIFFERENCE) and is None otherwise -- never a fabricated
    number for a one-sided row. Market values are each side's own already-
    real PortfolioHolding.market_value / AlpacaPosition.market_value,
    carried through verbatim; no new valuation is computed here."""
    symbol: str
    status: ReconciliationStatus
    internal_quantity: Optional[float] = None
    alpaca_quantity: Optional[float] = None
    quantity_difference: Optional[float] = None
    internal_market_value: Optional[float] = None
    alpaca_market_value: Optional[float] = None


@dataclass(frozen=True)
class AlpacaOrdersSnapshot:
    """A successful, real read of Alpaca Paper recent orders. An empty
    `orders` tuple is a legitimate real result ("connected, no matching
    recent orders"), distinct from the adapter returning None
    (unavailable). `truncated` is True when either underlying API call hit
    its defensive per-call cap, so the UI can say so explicitly."""
    orders: Tuple[AlpacaOrder, ...] = ()
    truncated: bool = False

    @property
    def is_empty(self) -> bool:
        return len(self.orders) == 0


@dataclass(frozen=True)
class PortfolioScreen:
    capital: Optional[CapitalSummary] = None
    holdings: Optional[Tuple[PortfolioHolding, ...]] = None
    alpaca_account: Optional[AlpacaAccountSnapshot] = None
    alpaca_positions: Tuple[AlpacaPosition, ...] = field(default=())
    alpaca_orders: Optional[AlpacaOrdersSnapshot] = None
    portfolio_history: Optional[Tuple[PortfolioHistoryPoint, ...]] = None
    # Internal vs Alpaca PAPER reconciliation: populated by the composition
    # root (bootstrap.py's _with_portfolio_reconciliation_data) from the
    # SAME already-fetched holdings / alpaca_positions above -- no new
    # read. None (unavailable) whenever either source is unavailable
    # (holdings is None, or alpaca_is_available is False) -- never
    # inferring a match when one side could not be read. An empty tuple is
    # a real "both sides read, nothing to reconcile" result, distinct from
    # None, matching every other None-vs-empty convention on this screen.
    reconciliation: Optional[Tuple[ReconciliationRow, ...]] = None
    # ADR-061 Category A (A4): per-section integration health, populated by
    # the composition root (bootstrap.py) from each adapter's ReadResult.
    # Carries the reason a section is unavailable; consumed by rendering in
    # a later phase. `None` only when no adapter read backed the section.
    capital_health: Optional[IntegrationHealth] = None
    holdings_health: Optional[IntegrationHealth] = None
    alpaca_health: Optional[IntegrationHealth] = None
    alpaca_orders_health: Optional[IntegrationHealth] = None
    portfolio_history_health: Optional[IntegrationHealth] = None

    @property
    def capital_is_available(self) -> bool:
        """True only once a real CapitalSummary has been supplied (see
        bootstrap.py's _build_portfolio_intelligence_ui) -- default None
        means the managed capital pool could not be read in this
        environment, matching every other real/unavailable convention in
        this product. The production UI must render an explicit
        unavailable state when this is False, never fabricated figures."""
        return self.capital is not None

    @property
    def holdings_is_available(self) -> bool:
        """True once a real holdings tuple has been supplied. An empty
        tuple is a real "no open positions" result (see is_empty), which
        is distinct from None -- None means the open-position source or
        the live-price source was unavailable."""
        return self.holdings is not None

    @property
    def is_empty(self) -> bool:
        """True ONLY when holdings is explicitly available (not None) and
        equals () -- a genuine "connected, zero open positions" state.
        When holdings is None the section is unavailable, not empty."""
        return self.holdings is not None and len(self.holdings) == 0

    @property
    def empty_state_message(self) -> str:
        return "No holdings recorded yet."

    @property
    def alpaca_is_available(self) -> bool:
        """True only once a real AlpacaAccountSnapshot has been supplied
        (see bootstrap.py) -- default None means unavailable, matching
        every other real/unavailable convention in this product.
        alpaca_positions is meaningful only when this is True; an empty
        tuple then means "connected, zero open positions" (a legitimate
        real state), not "unavailable"."""
        return self.alpaca_account is not None

    @property
    def alpaca_empty_state_message(self) -> str:
        return "Alpaca Paper account has no open positions."

    @property
    def alpaca_orders_available(self) -> bool:
        """True only once a real AlpacaOrdersSnapshot has been supplied
        (see bootstrap.py) -- default None means unavailable. Fully
        independent of alpaca_is_available: the recent-orders channel can
        be available while the account snapshot is not, and vice versa."""
        return self.alpaca_orders is not None

    @property
    def alpaca_orders_empty_state_message(self) -> str:
        return "Alpaca Paper account has no recent orders."

    @property
    def portfolio_history_is_available(self) -> bool:
        """True once a real portfolio_history tuple has been supplied. An
        empty tuple is a real "connected, no rows yet" result, distinct
        from None (the portfolio_snapshots read was unavailable)."""
        return self.portfolio_history is not None

    @property
    def portfolio_history_is_empty(self) -> bool:
        return self.portfolio_history is not None and len(self.portfolio_history) == 0

    @property
    def portfolio_history_empty_state_message(self) -> str:
        return "No portfolio history is recorded yet."

    @property
    def reconciliation_is_available(self) -> bool:
        """True only once a real reconciliation tuple has been supplied --
        which itself requires BOTH holdings_is_available and
        alpaca_is_available to be True (see bootstrap.py). False means one
        or both sides could not be read; the UI must never present a match
        or a difference it cannot actually support."""
        return self.reconciliation is not None

    @property
    def reconciliation_is_empty(self) -> bool:
        return self.reconciliation is not None and len(self.reconciliation) == 0

    @property
    def reconciliation_empty_state_message(self) -> str:
        return "No internal or Alpaca Paper positions to reconcile."
