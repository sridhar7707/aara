"""Read-only, network-only adapter fetching one live index/ETF daily quote
(SPY) via yfinance, backing Morning Brief's Market Mood / Regime section
with a *factual* current-market clause (last price, previous close, %
move) alongside the existing persisted per-cycle regime label.

Sibling of adapters/live_price_source.py -- same provider (yfinance,
ADR-063 dependency), same ADR-061 IntegrationHealth / error-classification
contract, same "duplicate the primitive, never import the protected
package" convention (the last-two-Close %-move calculation is the one
dashboard/components/brief.py::_spy_pct_today and
dashboard/components/market_mood.py::_pct already use -- duplicated here,
never imported, since dashboard/ is ADR-002-protected). Kept separate
from LivePriceSource because that adapter serves Portfolio Intelligence
Holdings with `period="1d"` current price only; a previous close needs a
second bar.

This module never opens a database connection of any kind and never
touches trades.db -- it is a pure live market-data read.

Market-hours / staleness: yfinance daily bars are date-granular and the
last bar is still in progress during regular trading hours (ADR-040), so
`as_of` is the last Close bar's *date* and `is_today` is that date
compared against America/New_York -- the caller phrases the move as
"today" only when `is_today` is True, otherwise "last session". The UI
therefore never presents a weekend / pre-market figure as realtime.

Health contract (ADR-061 Category A): get_spy_quote() returns
ReadResult[MarketQuote]. A HEALTHY result carries a real MarketQuote. A
non-HEALTHY result carries value=None plus an IntegrationHealth naming the
reason: NOT_CONFIGURED (yfinance not importable), RATE_LIMITED (429 /
throttle signal), UNAVAILABLE (network / timeout / empty provider
response / fewer than two Close bars, i.e. no previous close), API_ERROR
(NaN / non-positive last price or previous close, or a malformed
response). No credential value is ever placed in IntegrationHealth.detail
(ADR-061 Section 2.9) -- yfinance uses no credentials. There is never a
fabricated fallback value: any failure yields value=None and the caller
appends nothing.

Production note: the deployed HF Space needs outbound network access to
the market data provider for this to return real data; otherwise
get_spy_quote() returns a non-HEALTHY result and Morning Brief's Market
Mood / Regime section shows the regime label alone -- the intended, safe
behavior, not a bug.
"""
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from applications.platform.integrations import (
    IntegrationHealth,
    ReadResult,
    classify_exception,
)

_PROVIDER = "yfinance_market_quote"

_SYMBOL = "SPY"
_FETCH_PERIOD = "2d"
_FETCH_TIMEOUT_SECONDS = 10

_NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class MarketQuote:
    """One index/ETF's latest daily quote. `as_of` is the ISO date
    (YYYY-MM-DD) of the last Close bar -- NOT a wall-clock instant, since
    yfinance daily bars are date-granular and in progress during RTH.
    `is_today` is that date == today in America/New_York."""

    symbol: str
    last: float
    previous_close: float
    pct_change: float
    as_of: str
    is_today: bool


def _ny_today() -> date:
    """Today's date in America/New_York. Isolated as a named helper so
    `is_today` is deterministic under test -- the same reason
    bootstrap._now_utc() and MorningBriefUI._now() exist."""
    return datetime.now(_NEW_YORK).date()


class LiveMarketQuoteSource:
    def get_spy_quote(self) -> "ReadResult[MarketQuote]":
        """Return a ReadResult over SPY's latest daily quote (last,
        previous close, % move, last-bar date, is_today). Any failure --
        yfinance not importable, network error, timeout, empty response,
        fewer than two Close bars, or a NaN / non-positive price -- yields
        a non-HEALTHY result with value=None; the caller must append
        nothing and leave the regime sentence unchanged, never a fabricated
        or partial figure."""
        try:
            import yfinance as yf
        except Exception:
            return ReadResult.failed(
                IntegrationHealth.not_configured(
                    _PROVIDER, detail="yfinance is not importable"
                )
            )

        try:
            data = yf.download(
                _SYMBOL,
                period=_FETCH_PERIOD,
                progress=False,
                auto_adjust=True,
                timeout=_FETCH_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            return ReadResult.failed(classify_exception(_PROVIDER, exc))

        if data is None or getattr(data, "empty", True) or "Close" not in data:
            return ReadResult.failed(
                IntegrationHealth.unavailable(
                    _PROVIDER, detail="empty or missing price response"
                )
            )

        close = data["Close"]
        if hasattr(close, "columns"):
            column = close[_SYMBOL] if _SYMBOL in close.columns else close.iloc[:, 0]
        else:
            column = close

        try:
            raw_len = len(column)
        except Exception as exc:
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )
        if raw_len < 2:
            return ReadResult.failed(
                IntegrationHealth.unavailable(
                    _PROVIDER, detail="fewer than two Close bars -- no previous close"
                )
            )

        try:
            clean = column.dropna()
        except Exception as exc:
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )
        if len(clean) < 2:
            # Raw response had >= 2 bars but NaN / missing values in the
            # last two -- malformed provider data, not "no history yet".
            return ReadResult.failed(
                IntegrationHealth.api_error(
                    _PROVIDER, detail="NaN or missing values in the last two Close bars"
                )
            )

        try:
            last = float(clean.iloc[-1])
            previous_close = float(clean.iloc[-2])
            bar_date = clean.index[-1]
        except Exception as exc:
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )

        if math.isnan(last) or math.isnan(previous_close):
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail="NaN price")
            )
        if not (last > 0.0):
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail="non-positive last price")
            )
        if not (previous_close > 0.0):
            return ReadResult.failed(
                IntegrationHealth.api_error(
                    _PROVIDER, detail="non-positive previous close"
                )
            )

        try:
            resolved_date = _to_iso_date(bar_date)
        except Exception as exc:
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )

        pct_change = (last - previous_close) / previous_close * 100.0

        return ReadResult.healthy(
            MarketQuote(
                symbol=_SYMBOL,
                last=last,
                previous_close=previous_close,
                pct_change=pct_change,
                as_of=resolved_date.isoformat(),
                is_today=resolved_date == _ny_today(),
            ),
            _PROVIDER,
        )


def _to_iso_date(value) -> date:
    """The last Close bar's own timestamp -> a calendar date. yfinance
    returns a pandas Timestamp on a DatetimeIndex; accept a date/datetime
    too. Anything else raises and is classified API_ERROR by the caller."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    to_pydatetime = getattr(value, "to_pydatetime", None)
    if callable(to_pydatetime):
        return to_pydatetime().date()
    date_attr = getattr(value, "date", None)
    if callable(date_attr):
        return date_attr()
    raise TypeError("unrecognised bar timestamp type: %s" % type(value).__name__)
