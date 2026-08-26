"""Read-only, network-only adapter fetching live current prices via
yfinance, backing Portfolio Intelligence's Holdings table with real
market values when both trades.db's open positions AND a live price
fetch succeed.

Deliberately isolated from adapters/legacy_position_source.py's SQLite
access -- this module never touches trades.db or opens a database
connection of any kind, and legacy_position_source never touches the
network. Composing the two happens one level up, in bootstrap.py.

Explicitly authorized live network dependency (recorded per the user's
2026-08-26 decision extending Portfolio Intelligence's Holdings unit):
current price has no persisted value anywhere in trades.db (see
dashboard/data.py's own _current_prices(), which calls the same
yfinance.download() -- duplicated here as an isolated call, never
importing dashboard/, per this product's "duplicate the primitive, never
import the protected package" convention). Unlike every prior adapter in
this product (LegacyCapitalSource, LegacyRegimeSource, and this module's
own sibling LegacyPositionSource), this is the first read that is not a
local SQLite SELECT -- it is a live call to a market data provider over
the network, with its own independent failure modes (timeout, outage,
rate limiting, malformed/partial response) distinct from "trades.db is
missing."

Fail-safe policy: any failure -- network error, timeout, empty response,
or a missing/invalid (NaN, zero, negative) price for even one requested
symbol -- fails the *entire* batch to None. dashboard/data.py's own
fallback of a fabricated 0.0 price per symbol is deliberately NOT
replicated here, since that would silently render a real symbol/quantity
next to a fabricated $0.00 market value as though it were real data.
There is no partial-real result from this adapter.

Production note: in addition to the existing trades.db-availability gap
(see legacy_position_source.py), the deployed HF Space also needs
outbound network access to the market data provider for this module to
ever return real prices. If either dependency is unavailable,
get_current_prices() returns None and callers must fall back to the
existing illustrative Holdings path -- this is the intended, safe
behavior, not a bug.
"""
from typing import Dict, Optional, Tuple

_FETCH_PERIOD = "1d"
_FETCH_TIMEOUT_SECONDS = 10


class LivePriceSource:
    def get_current_prices(self, symbols: Tuple[str, ...]) -> Optional[Dict[str, float]]:
        """Returns {symbol: current_price} for every requested symbol, or
        None if the network call fails, times out, returns an empty
        response, or is missing/has an invalid price for even one
        requested symbol -- callers must treat None as "fall back to the
        existing illustrative Holdings path," never as an error, and must
        never use a partial result."""
        if not symbols:
            return {}
        try:
            import yfinance as yf
            data = yf.download(
                " ".join(symbols),
                period=_FETCH_PERIOD,
                progress=False,
                auto_adjust=True,
                timeout=_FETCH_TIMEOUT_SECONDS,
            )
        except Exception:
            return None
        if data is None or data.empty or "Close" not in data:
            return None
        close = data["Close"]
        prices: Dict[str, float] = {}
        for symbol in symbols:
            try:
                column = close[symbol] if hasattr(close, "columns") else close
                clean = column.dropna()
                if clean.empty:
                    return None
                price = float(clean.iloc[-1])
            except Exception:
                return None
            if not (price > 0.0):
                return None
            prices[symbol] = price
        return prices
