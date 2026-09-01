"""Tests for
applications.trading_intelligence.adapters.live_market_quote_source.

yfinance.download() is monkeypatched everywhere -- these tests must never
make a real network call. Fake DataFrames use a real DatetimeIndex so
`as_of` / `is_today` are exercised faithfully; `_ny_today` is monkeypatched
so `is_today` is deterministic.

Contract (ADR-061, mirroring LivePriceSource): get_spy_quote() returns
ReadResult[MarketQuote]; a non-HEALTHY result carries value=None plus an
IntegrationHealth naming the reason. There is never a fabricated fallback.
"""
import ast
import inspect
from datetime import date

import pandas as pd

from applications.platform.integrations import IntegrationStatus, ReadResult
from applications.trading_intelligence.adapters import live_market_quote_source as mod
from applications.trading_intelligence.adapters.live_market_quote_source import (
    LiveMarketQuoteSource,
    MarketQuote,
)

_IDX = pd.to_datetime(["2026-08-31", "2026-09-01"])


def _multi_df(closes, index=_IDX):
    """MultiIndex ('Close'/'Open', ticker) columns -- the shape recent
    yfinance returns for yf.download('SPY', ...)."""
    close_df = pd.DataFrame({"SPY": closes}, index=index)
    return pd.concat({"Close": close_df, "Open": close_df}, axis=1)


def _single_df(closes, index=_IDX):
    """Plain single-level 'Close'/'Open' columns."""
    return pd.DataFrame({"Close": closes, "Open": closes}, index=index)


def _patch(monkeypatch, df, today=date(2026, 9, 1)):
    monkeypatch.setattr("yfinance.download", lambda *a, **kw: df)
    monkeypatch.setattr(mod, "_ny_today", lambda: today)


def _healthy(result):
    assert isinstance(result, ReadResult)
    assert result.health.status is IntegrationStatus.HEALTHY
    return result.value


def test_healthy_two_row_calculation_multi_index(monkeypatch):
    _patch(monkeypatch, _multi_df([508.10, 512.34]))

    q = _healthy(LiveMarketQuoteSource().get_spy_quote())

    assert isinstance(q, MarketQuote)
    assert q.symbol == "SPY"
    assert q.last == 512.34
    assert q.previous_close == 508.10
    assert abs(q.pct_change - ((512.34 - 508.10) / 508.10 * 100)) < 1e-9
    assert f"{q.pct_change:+.2f}%" == "+0.83%"
    assert q.as_of == "2026-09-01"
    assert q.is_today is True


def test_single_symbol_dataframe_shape(monkeypatch):
    _patch(monkeypatch, _single_df([220.0, 228.41]))

    q = _healthy(LiveMarketQuoteSource().get_spy_quote())
    assert q.last == 228.41
    assert q.previous_close == 220.0


def test_positive_negative_and_near_zero_percentage(monkeypatch):
    _patch(monkeypatch, _single_df([100.0, 102.5]))
    assert _healthy(LiveMarketQuoteSource().get_spy_quote()).pct_change == 2.5

    _patch(monkeypatch, _single_df([100.0, 97.0]))
    assert _healthy(LiveMarketQuoteSource().get_spy_quote()).pct_change == -3.0

    _patch(monkeypatch, _single_df([100.0, 100.0]))
    q = _healthy(LiveMarketQuoteSource().get_spy_quote())
    assert q.pct_change == 0.0
    assert f"{q.pct_change:+.2f}%" == "+0.00%"


def test_last_and_previous_are_the_final_two_closes(monkeypatch):
    idx = pd.to_datetime(["2026-08-27", "2026-08-28", "2026-08-31", "2026-09-01"])
    _patch(monkeypatch, _single_df([500.0, 505.0, 508.10, 512.34], index=idx))

    q = _healthy(LiveMarketQuoteSource().get_spy_quote())
    assert q.last == 512.34
    assert q.previous_close == 508.10  # iloc[-2], not the oldest bar


def test_as_of_comes_from_the_final_bar_timestamp(monkeypatch):
    idx = pd.to_datetime(["2026-08-28", "2026-08-29"])
    _patch(monkeypatch, _single_df([505.0, 507.0], index=idx), today=date(2026, 9, 3))

    q = _healthy(LiveMarketQuoteSource().get_spy_quote())
    assert q.as_of == "2026-08-29"  # the last bar, not "today"
    assert q.is_today is False


def test_is_today_true_and_false_against_new_york(monkeypatch):
    df = _single_df([508.10, 512.34])  # last bar dated 2026-09-01

    _patch(monkeypatch, df, today=date(2026, 9, 1))
    assert _healthy(LiveMarketQuoteSource().get_spy_quote()).is_today is True

    _patch(monkeypatch, df, today=date(2026, 9, 2))
    assert _healthy(LiveMarketQuoteSource().get_spy_quote()).is_today is False


def test_fewer_than_two_rows_is_unavailable_value_none(monkeypatch):
    _patch(monkeypatch, _single_df([512.34], index=pd.to_datetime(["2026-09-01"])))

    result = LiveMarketQuoteSource().get_spy_quote()
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_none_response_is_unavailable(monkeypatch):
    _patch(monkeypatch, None)

    result = LiveMarketQuoteSource().get_spy_quote()
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_empty_dataframe_is_unavailable(monkeypatch):
    _patch(monkeypatch, pd.DataFrame())

    result = LiveMarketQuoteSource().get_spy_quote()
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_missing_close_column_is_unavailable(monkeypatch):
    _patch(monkeypatch, pd.DataFrame({"Open": [1.0, 2.0]}, index=_IDX))

    result = LiveMarketQuoteSource().get_spy_quote()
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_download_exception_is_classified_unavailable(monkeypatch):
    def _raise(*a, **kw):
        raise TimeoutError("network timeout")

    monkeypatch.setattr("yfinance.download", _raise)

    result = LiveMarketQuoteSource().get_spy_quote()
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_throttle_exception_is_rate_limited(monkeypatch):
    def _raise(*a, **kw):
        raise Exception("HTTP 429 Too Many Requests")

    monkeypatch.setattr("yfinance.download", _raise)

    result = LiveMarketQuoteSource().get_spy_quote()
    assert result.value is None
    assert result.health.status is IntegrationStatus.RATE_LIMITED


def test_nan_in_the_last_two_bars_is_api_error(monkeypatch):
    _patch(monkeypatch, _single_df([508.10, float("nan")]))

    result = LiveMarketQuoteSource().get_spy_quote()
    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


def test_zero_last_price_is_api_error(monkeypatch):
    _patch(monkeypatch, _single_df([508.10, 0.0]))

    result = LiveMarketQuoteSource().get_spy_quote()
    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


def test_negative_last_price_is_api_error(monkeypatch):
    _patch(monkeypatch, _single_df([508.10, -1.0]))

    result = LiveMarketQuoteSource().get_spy_quote()
    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


def test_non_positive_previous_close_is_api_error(monkeypatch):
    _patch(monkeypatch, _single_df([0.0, 512.34]))

    result = LiveMarketQuoteSource().get_spy_quote()
    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


def test_no_fabricated_fallback_on_any_failure(monkeypatch):
    """Every failure path yields value=None -- never a zeroed or
    placeholder MarketQuote."""
    one_row = _single_df([1.0], index=pd.to_datetime(["2026-09-01"]))
    for df in (None, pd.DataFrame(), one_row, _single_df([508.10, 0.0])):
        _patch(monkeypatch, df)
        result = LiveMarketQuoteSource().get_spy_quote()
        assert result.value is None
        assert result.health.status is not IntegrationStatus.HEALTHY


def test_module_imports_no_protected_package():
    source = inspect.getsource(mod)
    tree = ast.parse(source)
    forbidden = ("bot", "dashboard", "database", "scheduler", "ledger")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), (
                    f"forbidden import {alias.name!r}"
                )
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.startswith(forbidden), (
                f"forbidden import from {module_name!r}"
            )


def test_module_never_touches_sqlite():
    assert "sqlite3" not in inspect.getsource(mod)
