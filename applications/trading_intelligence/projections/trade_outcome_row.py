"""Typed, raw view of one ``trades`` row -- BUY or any ``SELL*`` -- for the
Wave 2A trades-only Decision Outcome read model.

Framework-independent: no bot, dashboard, scheduler, database, ledger,
sentinel_engine, or sentinel import. Produced by
adapters/trades_db_outcome_source.py straight from the ``trades`` table;
carries NO derivation. Every column is copied verbatim -- an ``Optional``
numeric field is ``None`` when the column was NULL, never coerced to
``0.0``. Pairing BUYs to SELLs and building a ``DecisionOutcome`` is the
separate, pure job of adapters/trade_outcome_derivation.py.

The ``"trade-<id>"`` decision-id scheme is shared with the Wave 1 Decision
Center path: this module re-uses ``decision_id_for`` /
``trade_id_from_decision_id`` from projections/trade_decision_row.py by
import and does not redefine them.
"""
from dataclasses import dataclass
from typing import Optional

from applications.trading_intelligence.projections.trade_decision_row import (
    decision_id_for,
    trade_id_from_decision_id,
)

__all__ = ["TradeOutcomeRow", "decision_id_for", "trade_id_from_decision_id"]

_SELL_PREFIX = "SELL"


@dataclass(frozen=True)
class TradeOutcomeRow:
    """One ``trades`` row (``action == "BUY"`` or ``action`` starting
    ``"SELL"``), columns verbatim.

    ``timestamp`` is the raw stored ISO string (naive / UTC by the bot's
    convention) -- not parsed here. ``realized_pnl`` / ``pnl_pct`` /
    ``holding_days`` are whatever the row stored; this layer never
    recomputes them.
    """

    id: int
    timestamp: str
    symbol: str
    action: str
    shares: Optional[float]
    price: Optional[float]
    notional: Optional[float]
    realized_pnl: Optional[float]
    pnl_pct: Optional[float]
    holding_days: Optional[int]
    order_id: Optional[str]
    ensemble_score: Optional[float]
    regime: Optional[str]

    @property
    def is_buy(self) -> bool:
        return self.action == "BUY"

    @property
    def is_sell(self) -> bool:
        return self.action.startswith(_SELL_PREFIX)

    @property
    def decision_id(self) -> str:
        """Only meaningful for a BUY row -- the stable ``"trade-<id>"``."""
        return decision_id_for(self.id)
