"""ADR-085 amendment A1: exit-only management of overlay names the stock bot already holds.

An ETF-overlay symbol is excluded from stock entries and from universe selection. If the stock bot
holds a lot of one (a position_state row AND a broker position), the stock exit rules still run on
that lot. The broker position may be blended with the overlay's own shares, so the exit position is
a copy whose quantity and cost basis come from the stock bot's own records. The broker position
dict (positions, EntryContext.positions) is never modified.
"""
from __future__ import annotations

import html
import math
import sqlite3
from types import SimpleNamespace

from loguru import logger

from bot._main_cycle import position_placeholder
from config import ETF_OVERLAY_SYMBOLS

_MIN_QTY = 0.001   # same dust threshold the reconcile and exit code use


def stock_held_overlay_symbols(con: sqlite3.Connection, positions: dict) -> list[str]:
    """Overlay names with a position_state row AND a broker position, sorted. Read-only."""
    rows = con.execute("SELECT symbol FROM position_state").fetchall()
    return sorted({r[0] for r in rows} & set(ETF_OVERLAY_SYMBOLS) & set(positions))


def net_trade_shares(con: sqlite3.Connection, symbol: str) -> float:
    """Stock-bot BUY shares minus every other action's shares, from the trades table.

    Same netting as _reconcile_positions (bot/_main_positions.py): any non-BUY row is a reduction.
    """
    rows = con.execute("SELECT action, shares FROM trades WHERE symbol=?", (symbol,)).fetchall()
    return sum((r[1] or 0.0) if r[0] == "BUY" else -(r[1] or 0.0) for r in rows)


def _finite_positive(value: float) -> bool:
    return math.isfinite(value) and value > 0


def exit_position_for(symbol: str, broker_pos, state_row, net_trade_shares: float,
                      current_price: float) -> SimpleNamespace | None:
    """Position object for _handle_exits covering only the stock bot's own lot, or None.

    state_row is (entry_price, shares) from position_state, or None. qty is the smallest of the broker
    quantity, position_state.shares and the net trades shares, so a sell never exceeds what the stock
    bot owns. avg_entry_price is position_state.entry_price, not the broker's blended average, and
    unrealized_plpc is computed from it. Returns None, with a WARNING, when no safe lot can be built.
    """
    entry = float(state_row[0] or 0.0) if state_row else 0.0
    shares = float(state_row[1] or 0.0) if state_row else 0.0
    if not _finite_positive(entry) or not _finite_positive(shares):
        logger.warning(f"{symbol}: exit-only overlay lot has no usable position_state "
                       f"(entry_price={entry}, shares={shares}) -- NOT managed this cycle")
        return None
    broker_qty = float(getattr(broker_pos, "qty", 0) or 0.0)
    net = float(net_trade_shares)
    # min() with a NaN is order-dependent, so a non-finite quantity must be rejected before clamping.
    qty = min(broker_qty, shares, net) if all(map(math.isfinite, (broker_qty, shares, net))) else float("nan")
    if not qty >= _MIN_QTY:   # also rejects NaN
        logger.warning(f"{symbol}: exit-only overlay lot clamps to {qty} shares "
                       f"(broker={broker_qty}, state={shares}, trades={net}) -- NOT managed this cycle")
        return None
    if not _finite_positive(current_price):
        logger.warning(f"{symbol}: exit-only overlay lot has no valid price ({current_price}) -- NOT managed this cycle")
        return None
    pos = position_placeholder(symbol, qty=qty, market_value=qty * current_price,
                               avg_entry_price=entry, current_price=current_price)
    pos.unrealized_plpc = current_price / entry - 1.0
    pos.unrealized_pl = (current_price - entry) * qty
    pos.clamp_inputs = {"broker_qty": broker_qty, "position_state_shares": shares, "net_trade_shares": net}
    return pos


def exit_view(con: sqlite3.Connection, symbol: str, positions: dict, current_price: float) -> dict:
    """A copy of positions in which `symbol` is replaced by its clamped exit lot, or removed if none.

    When the lot is dropped the symbol is absent, so _handle_exits sends no order; the caller's
    exit-only guard then skips the entry path.
    """
    view = {k: v for k, v in positions.items() if k != symbol}
    row = con.execute("SELECT entry_price, shares FROM position_state WHERE symbol=?", (symbol,)).fetchone()
    pos = exit_position_for(symbol, positions[symbol], row, net_trade_shares(con, symbol), current_price)
    if pos is not None:
        view[symbol] = pos
    return view


def alert_exit_unevaluated(symbol: str, reason: str, alerted: set, send) -> bool:
    """Operator alert (once per symbol per day via `alerted`) that a held overlay lot's exit
    rules were not evaluated this cycle. Returns True when an alert was sent."""
    if symbol in alerted:
        return False
    alerted.add(symbol)
    send(f"⚠️ <b>{html.escape(symbol)}</b> stop protection NOT evaluated: {html.escape(reason)}. "
         "The held lot has no stop this cycle; check logs/trading.log.")
    return True
