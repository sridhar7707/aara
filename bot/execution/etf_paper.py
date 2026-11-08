"""ADR-083 / ADR-085: ETF trend overlay on the shared PAPER account.

Pure functions only: the rule, order planning and the endpoint guard. No network, no
imports from scripts/. The runner in scripts/etf_paper_rebalance.py does the I/O.

The overlay manages a fixed SLEEVE of dollars, not the whole account. Only overlay
symbols are planned, and only their holdings are counted against the sleeve.
"""
from __future__ import annotations

import math

import pandas as pd

from config import ETF_OVERLAY_SYMBOLS  # single source for the overlay universe (ADR-085)

PAPER_URL = "https://paper-api.alpaca.markets"
ETF_UNIVERSE = sorted(ETF_OVERLAY_SYMBOLS)
TREND_WINDOW = 210     # trading-day mean, proxy for the 10-month average (ADR-082)
MIN_TRADE = 25.0       # dollars; smaller differences are not traded (full exits always are)


def assert_paper_endpoint(url: str) -> None:
    """Refuse anything but the exact paper endpoint (ADR-083 decision 2)."""
    if url.rstrip("/") != PAPER_URL:
        raise RuntimeError(f"refusing to run: base URL {url!r} is not the paper endpoint {PAPER_URL!r}")


def trend_targets(closes: pd.DataFrame) -> dict[str, float]:
    """Target weights from the last row of closes.

    Every ETF in the universe must have a valid last close; a missing or NaN close is an
    error, never silently treated as off-trend. An ETF whose last close is above its
    TREND_WINDOW mean is held, equal-weighted among the held ETFs (the tested rule). If
    none is held, the target is all cash.
    """
    if len(closes) < TREND_WINDOW:
        raise ValueError(f"need {TREND_WINDOW} closes, have {len(closes)}")
    missing = [s for s in ETF_UNIVERSE if s not in closes.columns]
    if missing:
        raise ValueError(f"no price history for {missing}; refusing to plan a partial universe")
    last = closes[ETF_UNIVERSE].iloc[-1]
    bad = [s for s in ETF_UNIVERSE if not math.isfinite(float(last[s]))]
    if bad:
        raise ValueError(f"invalid last close for {bad}; refusing to plan on bad data")
    on = [s for s in ETF_UNIVERSE
          if last[s] > closes[s].iloc[-TREND_WINDOW:].mean()]
    if not on:
        return {}
    share = 1.0 / len(on)
    return {s: share for s in on}


def plan_orders(sleeve: float, current_values: dict[str, float], current_qty: dict[str, float],
                weights: dict[str, float], prices: dict[str, float], cash_available: float) -> list[dict]:
    """Orders that move each overlay holding to its target value within the sleeve. Sells first.

    current_values / current_qty must cover overlay symbols only. Returns dicts with:
    symbol, side ('sell' or 'buy'), notional (dollars), qty (shares for sells, None for buys).
    A full exit sells the actual held quantity, so residual dust is never left behind.
    Raises if the buys exceed the cash available, so no order is planned that cannot fill.
    """
    if sleeve <= 0:
        raise ValueError("sleeve must be positive")
    outside = (set(current_values) | set(weights)) - set(ETF_UNIVERSE)
    if outside:
        raise ValueError(f"non-overlay symbols in plan: {sorted(outside)}")
    sells, buys = [], []
    for s in sorted(set(current_values) | set(weights)):
        target = sleeve * weights.get(s, 0.0)
        held = current_values.get(s, 0.0)
        delta = target - held
        full_exit = target == 0.0 and held > 0.0
        if not full_exit and abs(delta) < MIN_TRADE:
            continue
        price = prices.get(s)
        if price is None or not (price > 0 and math.isfinite(price)):
            raise ValueError(f"no valid price for {s}; cannot plan its order")
        if delta < 0:
            qty = current_qty.get(s, 0.0) if full_exit else round(-delta / price, 6)
            if qty <= 0:
                raise ValueError(f"no held quantity for {s}; cannot plan its sell")
            sells.append({"symbol": s, "side": "sell", "notional": round(-delta, 2), "qty": qty})
        else:
            buys.append({"symbol": s, "side": "buy", "notional": round(delta, 2), "qty": None})
    total_buys = sum(b["notional"] for b in buys)
    if total_buys > cash_available + 1e-6:
        raise ValueError(f"buys ${total_buys:,.2f} exceed cash ${cash_available:,.2f}; reduce the sleeve or wait")
    return sells + buys
