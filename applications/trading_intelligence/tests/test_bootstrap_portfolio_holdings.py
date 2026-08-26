"""Tests for bootstrap._build_portfolio_holdings -- the pure calculation
combining real open positions (LegacyPositionSource) with real current
prices (LivePriceSource) into PortfolioHolding rows. Both inputs are
already-real by the time this runs; this only covers the arithmetic.
"""
import pytest

from applications.trading_intelligence.adapters.legacy_position_source import OpenPosition
from applications.trading_intelligence.bootstrap import _build_portfolio_holdings


def test_market_value_is_quantity_times_current_price_not_entry_price():
    positions = (OpenPosition(symbol="AAPL", quantity=10.0, entry_price=200.0),)
    prices = {"AAPL": 250.0}

    holdings = _build_portfolio_holdings(positions, prices)

    assert holdings[0].price == 250.0
    assert holdings[0].market_value == 2500.0


def test_weight_pct_sums_to_100_across_holdings():
    positions = (
        OpenPosition(symbol="AAPL", quantity=10.0, entry_price=200.0),
        OpenPosition(symbol="MSFT", quantity=5.0, entry_price=300.0),
    )
    prices = {"AAPL": 100.0, "MSFT": 100.0}

    holdings = _build_portfolio_holdings(positions, prices)

    assert {h.symbol: h.market_value for h in holdings} == {"AAPL": 1000.0, "MSFT": 500.0}
    weights = {h.symbol: h.weight_pct for h in holdings}
    assert weights["AAPL"] == pytest.approx(66.6666, abs=0.01)
    assert weights["MSFT"] == pytest.approx(33.3333, abs=0.01)
    assert sum(weights.values()) == pytest.approx(100.0, abs=0.001)


def test_weight_pct_is_zero_when_total_market_value_is_zero():
    positions = (OpenPosition(symbol="AAPL", quantity=0.0, entry_price=200.0),)
    prices = {"AAPL": 100.0}

    holdings = _build_portfolio_holdings(positions, prices)

    assert holdings[0].market_value == 0.0
    assert holdings[0].weight_pct == 0.0


def test_returns_empty_tuple_for_no_positions():
    assert _build_portfolio_holdings((), {}) == ()


def test_quantity_is_preserved_from_the_open_position():
    positions = (OpenPosition(symbol="AAPL", quantity=19.11, entry_price=315.01),)
    prices = {"AAPL": 334.67}

    holdings = _build_portfolio_holdings(positions, prices)

    assert holdings[0].quantity == 19.11
