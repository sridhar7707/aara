"""SUPERVISED execution mode -- REQ-200/202 (architecture only, per
REQUIREMENTS_MATRIX.md frozen decision #4: "No SUPERVISED execution in
Phase 1A. Interface only. Architecture ready, implementation deferred to
Phase 2+.").

Reads (account/positions/prices) delegate to a real AlpacaClient -- observing
the account doesn't need human approval. Every order-placing method is a
structural no-op: it logs what it *would* have done and returns None/empty,
the same "no fill" shape callers already handle for a rejected/failed order.
There is no seam here through which a real order can be placed, matching the
safety property PaperExecutor already establishes for its own no-real-orders
guarantee.

Deliberately NOT built here (see CURRENT_ARCHITECTURE.md "Deferred, Not
Forgotten"): an approval queue, any new table, or a mutable status column.
The concrete revisit trigger for that real design -- a new append-only
execution_events table, never a mutable column -- is Phase 2+, when live
capital is involved and the Risk Governor can actually enter DEFENSIVE
against real positions. Until that trigger fires, this class exists so
EXECUTION_BACKEND=supervised is a selectable, testable, always-safe mode --
not so it does anything yet.
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from bot.execution.alpaca_client import AlpacaClient


class SupervisedExecutor:
    def __init__(self):
        self._reader = AlpacaClient()
        self.api = self._reader.api

    # ── reads: delegate straight through, no approval needed to observe ──

    def get_account(self) -> Any:
        return self._reader.get_account()

    def get_account_summary(self) -> tuple[float, float]:
        return self._reader.get_account_summary()

    def get_portfolio_value(self) -> float:
        return self._reader.get_portfolio_value()

    def get_cash(self) -> float:
        return self._reader.get_cash()

    def get_positions(self) -> dict:
        return self._reader.get_positions()

    def get_latest_price(self, symbol: str) -> float:
        return self._reader.get_latest_price(symbol)

    def get_bars(self, symbol: str, timeframe: str = "5Min", limit: int = 100) -> Any:
        return self._reader.get_bars(symbol, timeframe=timeframe, limit=limit)

    def get_position_value(self, symbol: str, positions: dict | None = None) -> float:
        return self._reader.get_position_value(symbol, positions=positions)

    def get_position_pnl_pct(self, symbol: str, positions: dict | None = None) -> float:
        return self._reader.get_position_pnl_pct(symbol, positions=positions)

    # ── orders: no-op by construction -- SUPERVISED never executes in Phase 1A ──

    def buy(self, symbol: str, notional: float, limit_price: float | None = None) -> dict | None:
        logger.info(
            f"SUPERVISED mode: would BUY {symbol} notional=${notional:.2f} "
            "-- approval workflow not implemented until Phase 2+ (phase0_decisions.md #17); "
            "no order placed."
        )
        return None

    def sell(self, symbol: str, qty: float | None = None, limit_price: float | None = None) -> dict | None:
        logger.info(
            f"SUPERVISED mode: would SELL {symbol} qty={qty} "
            "-- approval workflow not implemented until Phase 2+ (phase0_decisions.md #17); "
            "no order placed."
        )
        return None

    def sell_market(self, symbol: str, qty: float) -> dict | None:
        return self.sell(symbol, qty=qty, limit_price=None)

    def wait_for_fill(self, order_id: str, timeout_secs: int = 15) -> float:
        """Never called with a real order_id -- buy()/sell() never return one."""
        return 0.0

    def get_fill_price(self, order_id: str) -> float | None:
        return None

    def get_open_order_symbols(self) -> tuple[set[str], set[str]]:
        """No orders are ever placed, so there is never an open/pending one."""
        return set(), set()
