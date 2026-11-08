"""ADR-083: ETF trend overlay for a dedicated Alpaca PAPER account.

Pure functions only: the rule, order planning and the endpoint guard. No network, no
imports from scripts/. The runner in scripts/etf_paper_rebalance.py does the I/O.
"""
from __future__ import annotations

import pandas as pd

PAPER_URL = "https://paper-api.alpaca.markets"
from config import ETF_OVERLAY_SYMBOLS  # single source for the overlay universe (ADR-085)
ETF_UNIVERSE = sorted(ETF_OVERLAY_SYMBOLS)
TREND_WINDOW = 210     # trading-day mean, proxy for the 10-month average (ADR-082)
MIN_TRADE = 25.0       # dollars; smaller differences are not traded


def assert_paper_endpoint(url: str) -> None:
    """Refuse anything but the exact paper endpoint (ADR-083 decision 2)."""
    if url.rstrip("/") != PAPER_URL:
        raise RuntimeError(f"refusing to run: base URL {url!r} is not the paper endpoint {PAPER_URL!r}")


def trend_targets(closes: pd.DataFrame) -> dict[str, float]:
    """Target weights for the last row of closes (columns = ETF symbols).

    Each ETF whose last close is above its TREND_WINDOW mean is held, equal-weighted
    among the held ETFs (the tested rule). If none is held, the target is all cash.
    Symbols missing from closes are treated as off.
    """
    universe = [s for s in ETF_UNIVERSE if s in closes.columns]
    if len(closes) < TREND_WINDOW:
        raise ValueError(f"need {TREND_WINDOW} closes, have {len(closes)}")
    on = [s for s in universe
          if closes[s].iloc[-1] > closes[s].iloc[-TREND_WINDOW:].mean()]
    if not on:
        return {}
    share = 1.0 / len(on)
    return {s: share for s in on}


def plan_orders(equity: float, current_values: dict[str, float], weights: dict[str, float],
                prices: dict[str, float]) -> list[dict]:
    """Orders that move each holding to its target value. Sells come first.

    Returns dicts with keys: symbol, side ('sell' or 'buy'), notional, qty.
    qty is set for sells (shares), notional for buys (dollars).
    """
    if equity <= 0:
        raise ValueError("equity must be positive")
    symbols = set(current_values) | set(weights)
    sells, buys = [], []
    for s in sorted(symbols):
        target = equity * weights.get(s, 0.0)
        delta = target - current_values.get(s, 0.0)
        if abs(delta) < MIN_TRADE:
            continue
        price = prices.get(s)
        if not price or price <= 0:
            raise ValueError(f"no price for {s}; cannot plan its order")
        if delta < 0:
            sells.append({"symbol": s, "side": "sell", "notional": round(-delta, 2),
                          "qty": round(-delta / price, 6)})
        else:
            buys.append({"symbol": s, "side": "buy", "notional": round(delta, 2), "qty": None})
    return sells + buys
