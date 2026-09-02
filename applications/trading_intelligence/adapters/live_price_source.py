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
symbol -- fails the *entire* batch. dashboard/data.py's own fallback of a
fabricated 0.0 price per symbol is deliberately NOT replicated here,
since that would silently render a real symbol/quantity next to a
fabricated $0.00 market value as though it were real data. There is no
partial-real result from this adapter.

Health contract (ADR-061 Category A): get_current_prices() returns
ReadResult[Dict[str, float]]. A HEALTHY result carries the full price map
(an empty dict for an empty `symbols` argument is a legitimate HEALTHY
result). A non-HEALTHY result carries value=None plus an IntegrationHealth
naming the reason: NOT_CONFIGURED (yfinance not importable), RATE_LIMITED
(429 / throttle signal), UNAVAILABLE (network / timeout / empty provider
response), API_ERROR (an invalid / missing / NaN / non-positive price for
a requested symbol). No credential value is ever placed in
IntegrationHealth.detail (ADR-061 Section 2.9) -- yfinance uses no
credentials.

Production note: in addition to the existing trades.db-availability gap
(see legacy_position_source.py), the deployed HF Space also needs
outbound network access to the market data provider for this module to
ever return real prices. If either dependency is unavailable,
get_current_prices() returns a non-HEALTHY result and callers must fall
back to the existing illustrative Holdings path -- this is the intended,
safe behavior, not a bug.
"""
import logging
from typing import Dict, Tuple

from applications.platform.integrations import (
    IntegrationHealth,
    ReadResult,
    classify_exception,
)

# TEMP-DIAG holdings-price: temporary runtime logging to identify why
# yf.download() fails on the deployed HF Space (Holdings API_ERROR). Remove
# once the root cause is confirmed.
_diag = logging.getLogger("aara.holdings_price_diag")

_PROVIDER = "yfinance"

_FETCH_PERIOD = "1d"
_FETCH_TIMEOUT_SECONDS = 10


class LivePriceSource:
    def get_current_prices(
        self, symbols: Tuple[str, ...]
    ) -> "ReadResult[Dict[str, float]]":
        """Returns a ReadResult over {symbol: current_price} for every
        requested symbol. A HEALTHY result carries the full map (an empty
        dict for an empty `symbols` argument is a legitimate HEALTHY
        result). Any failure -- network error, timeout, empty response, or
        a missing/invalid price for even one requested symbol -- yields a
        non-HEALTHY result with value=None; callers must treat it as "fall
        back to the existing illustrative Holdings path," never as an
        error, and must never use a partial result."""
        if not symbols:
            return ReadResult.healthy({}, _PROVIDER)
        try:
            import yfinance as yf
        except Exception:
            return ReadResult.failed(
                IntegrationHealth.not_configured(
                    _PROVIDER, detail="yfinance is not importable"
                )
            )
        try:
            import curl_cffi as _cc  # noqa: F401
            _diag.warning("TEMP-DIAG holdings-price: fetching %d symbols one-by-one; "
                          "yfinance=%s curl_cffi=%s", len(symbols),
                          getattr(yf, "__version__", "?"), getattr(_cc, "__version__", "?"))
        except Exception:  # pragma: no cover - diagnostic only
            pass

        prices: Dict[str, float] = {}
        for symbol in symbols:
            # One ticker per call. A multi-symbol yf.download() assembles its
            # column set from yfinance's process-global shared state, so a
            # partially-failed batch can drop a requested symbol and pull in an
            # unrelated one another adapter fetched (e.g. SPY from the Morning
            # Brief market-quote source) -- the caller then KeyErrors on the
            # missing symbol. Per-symbol calls return that ticker's own frame
            # and keep one transient failure from corrupting the rest.
            try:
                frame = yf.download(
                    symbol,
                    period=_FETCH_PERIOD,
                    progress=False,
                    auto_adjust=True,
                    timeout=_FETCH_TIMEOUT_SECONDS,
                    # Synchronous: yfinance's threaded path coordinates through a
                    # per-call-reset process-global dict, so a still-running
                    # thread from a prior download() (e.g. the Morning Brief SPY
                    # quote) can satisfy this call's wait early and return that
                    # other ticker's frame. threads=False keeps each call's
                    # result its own.
                    threads=False,
                )
            except Exception as exc:
                _diag.warning("TEMP-DIAG holdings-price: yf.download(%s) RAISED %s: %r",
                              symbol, type(exc).__name__, exc)
                return ReadResult.failed(classify_exception(_PROVIDER, exc))

            if frame is None or getattr(frame, "empty", True) or "Close" not in frame:
                _diag.warning("TEMP-DIAG holdings-price: %s empty/missing response "
                              "(type=%s empty=%s cols=%s)", symbol, type(frame).__name__,
                              getattr(frame, "empty", None),
                              list(getattr(frame, "columns", []))[:8])
                return ReadResult.failed(
                    IntegrationHealth.unavailable(
                        _PROVIDER, detail="empty or missing price response"
                    )
                )

            try:
                close = frame["Close"]
                # single-ticker download: "Close" is a Series on older yfinance,
                # a 1-column (possibly MultiIndex) DataFrame on newer.
                if hasattr(close, "columns"):
                    if symbol not in close.columns:
                        # The frame is for a different ticker than requested
                        # (yfinance handed back a neighbouring request's
                        # result). Never fall back to column 0 -- that
                        # silently maps another symbol's price onto this one.
                        # Fail the whole batch, per this module's fail-safe.
                        _diag.warning(
                            "TEMP-DIAG holdings-price: %s frame is for %r, not requested symbol",
                            symbol, list(close.columns)[:8],
                        )
                        return ReadResult.failed(
                            IntegrationHealth.api_error(
                                _PROVIDER,
                                detail="price response was for a different symbol",
                            )
                        )
                    series = close[symbol]
                else:
                    series = close
                clean = series.dropna()
                if clean.empty:
                    _diag.warning("TEMP-DIAG holdings-price: %s no valid price; cols=%s",
                                  symbol, list(getattr(close, "columns", []))[:8])
                    return ReadResult.failed(
                        IntegrationHealth.api_error(
                            _PROVIDER, detail="no valid price for a requested symbol"
                        )
                    )
                price = float(clean.iloc[-1])
            except Exception as exc:
                _diag.warning("TEMP-DIAG holdings-price: %s extract RAISED %s: %r",
                              symbol, type(exc).__name__, exc)
                return ReadResult.failed(
                    IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
                )

            if not (price > 0.0):
                _diag.warning("TEMP-DIAG holdings-price: %s non-positive price %r", symbol, price)
                return ReadResult.failed(
                    IntegrationHealth.api_error(
                        _PROVIDER, detail="non-positive price for a requested symbol"
                    )
                )
            prices[symbol] = price

        _diag.warning("TEMP-DIAG holdings-price: OK %s", prices)
        return ReadResult.healthy(prices, _PROVIDER)
