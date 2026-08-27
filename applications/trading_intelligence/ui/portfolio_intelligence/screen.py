"""Portfolio Intelligence screen structure -- illustrative MVP.

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
from typing import Optional, Tuple


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
class PortfolioScreen:
    capital: CapitalSummary
    holdings: Tuple[PortfolioHolding, ...] = field(default=())
    alpaca_account: Optional[AlpacaAccountSnapshot] = None
    alpaca_positions: Tuple[AlpacaPosition, ...] = field(default=())

    @property
    def is_empty(self) -> bool:
        return len(self.holdings) == 0

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
