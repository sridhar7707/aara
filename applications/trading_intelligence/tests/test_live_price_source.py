"""Tests for applications.trading_intelligence.adapters.live_price_source.

yfinance.download() is monkeypatched everywhere here -- these tests must
never make a real network call. Fake DataFrames are built with the same
shape the real yfinance.download() returns (a top-level "Close"/"Open"/...
MultiIndex column for multiple symbols, plain columns for a single
symbol) so the adapter's own parsing logic is exercised faithfully.

Post-ADR-061: get_current_prices() returns ReadResult[Dict[str, float]].
A HEALTHY result carries the full price map (an empty dict for no symbols
is a legitimate HEALTHY result); a non-HEALTHY result carries value=None
plus an IntegrationHealth naming the reason. A missing/invalid price for
even one requested symbol fails the whole batch.
"""
import ast
import inspect

import pandas as pd

from applications.platform.integrations import IntegrationStatus, ReadResult
from applications.trading_intelligence.adapters.live_price_source import LivePriceSource


def _multi_symbol_df(closes: dict) -> pd.DataFrame:
    close_df = pd.DataFrame({symbol: values for symbol, values in closes.items()})
    return pd.concat({"Close": close_df, "Open": close_df}, axis=1)


def _single_symbol_df(closes: list) -> pd.DataFrame:
    return pd.DataFrame({"Close": closes, "Open": closes})


def _prices(result):
    assert isinstance(result, ReadResult)
    assert result.health.status is IntegrationStatus.HEALTHY
    return result.value


def test_get_current_prices_returns_the_latest_close_for_every_symbol(monkeypatch):
    df = _multi_symbol_df({"AAPL": [330.0, 334.67], "GOOGL": [345.0, 347.41]})
    monkeypatch.setattr("yfinance.download", lambda *a, **kw: df)

    assert _prices(LivePriceSource().get_current_prices(("AAPL", "GOOGL"))) == {
        "AAPL": 334.67,
        "GOOGL": 347.41,
    }


def test_get_current_prices_handles_a_single_symbol(monkeypatch):
    df = _single_symbol_df([220.0, 228.41])
    monkeypatch.setattr("yfinance.download", lambda *a, **kw: df)

    assert _prices(LivePriceSource().get_current_prices(("BA",))) == {"BA": 228.41}


def test_get_current_prices_empty_symbols_is_a_healthy_empty_dict():
    result = LivePriceSource().get_current_prices(())
    assert result.health.status is IntegrationStatus.HEALTHY
    assert result.value == {}


def test_get_current_prices_is_unavailable_on_network_exception(monkeypatch):
    def _raise(*args, **kwargs):
        raise TimeoutError("network timeout")

    monkeypatch.setattr("yfinance.download", _raise)

    result = LivePriceSource().get_current_prices(("AAPL",))
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_get_current_prices_is_unavailable_on_empty_response(monkeypatch):
    monkeypatch.setattr("yfinance.download", lambda *a, **kw: pd.DataFrame())

    result = LivePriceSource().get_current_prices(("AAPL",))
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_get_current_prices_is_unavailable_when_download_returns_none(monkeypatch):
    monkeypatch.setattr("yfinance.download", lambda *a, **kw: None)

    result = LivePriceSource().get_current_prices(("AAPL",))
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_get_current_prices_is_api_error_when_a_symbol_has_no_valid_price(monkeypatch):
    """One requested symbol has an all-NaN Close column (e.g. an invalid
    or delisted ticker) -- the whole batch must fail with a classified
    reason, not just that symbol, so callers never render a real quantity
    next to a missing price."""
    df = _multi_symbol_df({"AAPL": [330.0, 334.67], "ZZZZ": [float("nan"), float("nan")]})
    monkeypatch.setattr("yfinance.download", lambda *a, **kw: df)

    result = LivePriceSource().get_current_prices(("AAPL", "ZZZZ"))
    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


def test_get_current_prices_is_api_error_when_a_price_is_zero(monkeypatch):
    df = _multi_symbol_df({"AAPL": [330.0, 0.0], "GOOGL": [345.0, 347.41]})
    monkeypatch.setattr("yfinance.download", lambda *a, **kw: df)

    result = LivePriceSource().get_current_prices(("AAPL", "GOOGL"))
    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


def test_get_current_prices_is_api_error_when_a_price_is_negative(monkeypatch):
    df = _multi_symbol_df({"AAPL": [330.0, -1.0], "GOOGL": [345.0, 347.41]})
    monkeypatch.setattr("yfinance.download", lambda *a, **kw: df)

    result = LivePriceSource().get_current_prices(("AAPL", "GOOGL"))
    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


# --- regression locks (unchanged) --------------------------------

def test_module_imports_no_protected_package():
    """AST-level regression lock: this adapter must never import bot,
    dashboard, database, scheduler, or ledger."""
    import applications.trading_intelligence.adapters.live_price_source as module

    source = inspect.getsource(module)
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
    """Isolation regression lock backing this module's own docstring
    claim: price-fetching must stay entirely separate from
    legacy_position_source.py's SQLite access."""
    import applications.trading_intelligence.adapters.live_price_source as module

    source = inspect.getsource(module)
    assert "sqlite3" not in source
