"""Tests for Alpaca Paper recent-orders wiring in bootstrap:

- _with_alpaca_orders_data -- attaching a real AlpacaOrdersSnapshot to a
  PortfolioScreen independently of Capital Summary/Holdings AND of the
  Alpaca account/positions attachment.
- _build_portfolio_intelligence_ui -- that the orders attachment happens
  on all four return paths, and that nothing else changes.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from applications.trading_intelligence import bootstrap
from applications.trading_intelligence.bootstrap import (
    _build_portfolio_intelligence_ui,
    _with_alpaca_orders_data,
)
from applications.trading_intelligence.ui.portfolio_intelligence.mock_data import build_mock_screen
from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    AlpacaAccountSnapshot,
    AlpacaOrder,
    AlpacaOrdersSnapshot,
    AlpacaPosition,
)

_ORDER = AlpacaOrder(
    order_id="ord-1",
    symbol="AAPL",
    side="buy",
    order_type="market",
    quantity="10",
    filled_quantity="10",
    status="filled",
    submitted_at=datetime(2026, 8, 27, 14, 0, tzinfo=timezone.utc),
    filled_at=datetime(2026, 8, 27, 14, 1, tzinfo=timezone.utc),
    limit_price="",
    is_working=False,
)
_SNAPSHOT = AlpacaOrdersSnapshot(orders=(_ORDER,), truncated=False)

_ORDERS_METHOD = (
    "applications.trading_intelligence.adapters."
    "alpaca_paper_orders_source.AlpacaPaperOrdersSource.get_recent_orders"
)
_ACCOUNT_GET = (
    "applications.trading_intelligence.adapters."
    "alpaca_paper_source.AlpacaPaperSource.get_account"
)
_POSITIONS_GET = (
    "applications.trading_intelligence.adapters."
    "alpaca_paper_source.AlpacaPaperSource.get_positions"
)


# --- _with_alpaca_orders_data ----------------------------------------


def test_attaches_orders_snapshot_when_available():
    screen = build_mock_screen()
    with patch(_ORDERS_METHOD, return_value=_SNAPSHOT):
        result = _with_alpaca_orders_data(screen)

    assert result.alpaca_orders == _SNAPSHOT
    assert result.alpaca_orders_available is True


def test_attaches_a_genuinely_empty_snapshot_as_a_real_state():
    screen = build_mock_screen()
    empty = AlpacaOrdersSnapshot(orders=(), truncated=False)
    with patch(_ORDERS_METHOD, return_value=empty):
        result = _with_alpaca_orders_data(screen)

    assert result.alpaca_orders_available is True
    assert result.alpaca_orders.is_empty


def test_leaves_screen_unchanged_when_orders_are_unavailable():
    screen = build_mock_screen()
    with patch(_ORDERS_METHOD, return_value=None):
        result = _with_alpaca_orders_data(screen)

    assert result == screen
    assert result.alpaca_orders_available is False


def test_does_not_alter_capital_holdings_or_alpaca_account():
    screen = build_mock_screen()
    with patch(_ORDERS_METHOD, return_value=_SNAPSHOT):
        result = _with_alpaca_orders_data(screen)

    assert result.capital == screen.capital
    assert result.holdings == screen.holdings
    assert result.alpaca_account == screen.alpaca_account
    assert result.alpaca_positions == screen.alpaca_positions


def test_orders_channel_is_independent_of_the_account_channel():
    """A real orders snapshot must attach even when the account/positions
    read is unavailable, and vice versa."""
    screen = build_mock_screen()
    with patch(_ACCOUNT_GET, return_value=None), patch(
        _POSITIONS_GET, return_value=None
    ), patch(_ORDERS_METHOD, return_value=_SNAPSHOT):
        after_account = bootstrap._with_alpaca_paper_data(screen)
        result = _with_alpaca_orders_data(after_account)

    assert result.alpaca_is_available is False
    assert result.alpaca_orders_available is True


# --- _build_portfolio_intelligence_ui: all four return paths -----------


@pytest.fixture
def _no_alpaca_account(monkeypatch):
    """Silence the account/positions channel so these tests reason about
    the orders attachment alone."""
    monkeypatch.setattr(bootstrap.AlpacaPaperSource, "get_account", lambda self: None)
    monkeypatch.setattr(bootstrap.AlpacaPaperSource, "get_positions", lambda self: None)


def _patch_legacy(monkeypatch, *, capital, positions, prices):
    monkeypatch.setattr(
        bootstrap.LegacyCapitalSource, "get_capital_summary", lambda self: capital
    )
    monkeypatch.setattr(
        bootstrap.LegacyPositionSource, "get_open_positions", lambda self: positions
    )
    monkeypatch.setattr(
        bootstrap.LivePriceSource, "get_current_prices", lambda self, symbols: prices
    )


_CAPITAL = None  # filled per-test from the mock screen


def _real_capital():
    return build_mock_screen().capital


def _open_positions():
    from applications.trading_intelligence.adapters.legacy_position_source import OpenPosition

    return (OpenPosition(symbol="AAPL", quantity=1.0, entry_price=1.0),)


@pytest.mark.parametrize(
    "capital,positions,prices,expect_capital_real,expect_holdings_real",
    [
        (None, None, None, False, False),                         # path 1: no capital
        ("REAL", None, None, True, False),                        # path 2: no positions
        ("REAL", "POS", None, True, False),                       # path 3: no prices
        ("REAL", "POS", {"AAPL": 2.0}, True, True),               # path 4: fully real
    ],
)
def test_orders_are_attached_on_every_return_path(
    monkeypatch, _no_alpaca_account, capital, positions, prices,
    expect_capital_real, expect_holdings_real,
):
    resolved_capital = _real_capital() if capital == "REAL" else None
    resolved_positions = _open_positions() if positions == "POS" else positions
    _patch_legacy(
        monkeypatch, capital=resolved_capital, positions=resolved_positions, prices=prices
    )
    monkeypatch.setattr(
        bootstrap.AlpacaPaperOrdersSource, "get_recent_orders", lambda self: _SNAPSHOT
    )

    ui = _build_portfolio_intelligence_ui()

    assert ui._screen.alpaca_orders == _SNAPSHOT
    assert ui._screen.alpaca_orders_available is True
    assert ui._capital_is_real is expect_capital_real
    assert ui._holdings_is_real is expect_holdings_real


@pytest.mark.parametrize(
    "capital,positions,prices",
    [
        (None, None, None),
        ("REAL", None, None),
        ("REAL", "POS", None),
        ("REAL", "POS", {"AAPL": 2.0}),
    ],
)
def test_orders_unavailable_leaves_every_return_path_on_none(
    monkeypatch, _no_alpaca_account, capital, positions, prices,
):
    resolved_capital = _real_capital() if capital == "REAL" else None
    resolved_positions = _open_positions() if positions == "POS" else positions
    _patch_legacy(
        monkeypatch, capital=resolved_capital, positions=resolved_positions, prices=prices
    )
    monkeypatch.setattr(
        bootstrap.AlpacaPaperOrdersSource, "get_recent_orders", lambda self: None
    )

    ui = _build_portfolio_intelligence_ui()

    assert ui._screen.alpaca_orders is None
    assert ui._screen.alpaca_orders_available is False


def test_disclosure_semantics_are_unchanged_by_the_orders_attachment(monkeypatch, _no_alpaca_account):
    """Orders are never counted toward Real/Partial/Illustrative -- a fully
    illustrative screen with a real orders snapshot still renders the exact
    illustrative disclosure."""
    from applications.trading_intelligence.ui.portfolio_intelligence.gradio_view import (
        _ILLUSTRATIVE_DATA_HTML,
    )

    _patch_legacy(monkeypatch, capital=None, positions=None, prices=None)
    monkeypatch.setattr(
        bootstrap.AlpacaPaperOrdersSource, "get_recent_orders", lambda self: _SNAPSHOT
    )

    demo = _build_portfolio_intelligence_ui().build()
    html_values = [
        block.value
        for block in demo.blocks.values()
        if hasattr(block, "value") and isinstance(getattr(block, "value", None), str)
    ]

    assert _ILLUSTRATIVE_DATA_HTML in html_values
