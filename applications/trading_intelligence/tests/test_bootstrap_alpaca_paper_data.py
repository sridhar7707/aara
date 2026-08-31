"""Tests for bootstrap._with_alpaca_paper_data -- attaching real Alpaca
Paper account/positions to a PortfolioScreen independently of Capital
Summary/Holdings' own real/illustrative state.

Post-ADR-061 (Category A / Amendment 1): the adapter methods return
ReadResult. The attach-only-when-both-healthy rule is unchanged; the
screen also carries an `alpaca_health` IntegrationHealth on every path.
"""
from unittest.mock import patch

from applications.platform.integrations import (
    IntegrationHealth,
    IntegrationStatus,
    ReadResult,
)
from applications.trading_intelligence.bootstrap import _with_alpaca_paper_data
from applications.trading_intelligence.ui.portfolio_intelligence.mock_data import build_mock_screen
from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    AlpacaAccountSnapshot,
    AlpacaPosition,
)

_ACCOUNT = AlpacaAccountSnapshot(equity=100018.33, cash=59869.06, buying_power=351894.19, portfolio_value=100018.33)
_POSITION = AlpacaPosition(
    symbol="AAPL", quantity=19.11, avg_entry_price=315.01, current_price=310.21,
    market_value=5928.53, unrealized_pl=-91.78, unrealized_plpc=-0.0152, side="long",
)

_ACCOUNT_METHOD = (
    "applications.trading_intelligence.adapters."
    "alpaca_paper_source.AlpacaPaperSource.get_account"
)
_POSITIONS_METHOD = (
    "applications.trading_intelligence.adapters."
    "alpaca_paper_source.AlpacaPaperSource.get_positions"
)


def _ok(value):
    return ReadResult.healthy(value, "alpaca_paper")


def _down():
    return ReadResult.failed(IntegrationHealth.unavailable("alpaca_paper"))


def test_attaches_account_and_positions_when_both_available():
    screen = build_mock_screen()
    with patch(_ACCOUNT_METHOD, return_value=_ok(_ACCOUNT)), patch(
        _POSITIONS_METHOD, return_value=_ok((_POSITION,))
    ):
        result = _with_alpaca_paper_data(screen)

    assert result.alpaca_account == _ACCOUNT
    assert result.alpaca_positions == (_POSITION,)
    assert result.alpaca_is_available is True
    assert result.alpaca_health.status is IntegrationStatus.HEALTHY


def test_records_health_and_stays_unavailable_when_account_unavailable():
    screen = build_mock_screen()
    with patch(_ACCOUNT_METHOD, return_value=_down()):
        result = _with_alpaca_paper_data(screen)

    assert result.alpaca_is_available is False
    assert result.alpaca_account is None
    assert result.alpaca_health.status is IntegrationStatus.UNAVAILABLE
    # capital / holdings are never touched by the Alpaca attachment
    assert result.capital == screen.capital
    assert result.holdings == screen.holdings


def test_stays_unavailable_when_account_available_but_positions_are_not():
    """All-or-nothing: an account snapshot without a matching positions
    fetch must not be presented as a connected-but-empty account."""
    screen = build_mock_screen()
    with patch(_ACCOUNT_METHOD, return_value=_ok(_ACCOUNT)), patch(
        _POSITIONS_METHOD, return_value=_down()
    ):
        result = _with_alpaca_paper_data(screen)

    assert result.alpaca_is_available is False
    assert result.alpaca_account is None
    assert result.alpaca_health.status is IntegrationStatus.UNAVAILABLE
    assert result.capital == screen.capital
    assert result.holdings == screen.holdings


def test_attaches_a_genuinely_empty_positions_tuple_when_account_has_no_positions():
    screen = build_mock_screen()
    with patch(_ACCOUNT_METHOD, return_value=_ok(_ACCOUNT)), patch(
        _POSITIONS_METHOD, return_value=_ok(())
    ):
        result = _with_alpaca_paper_data(screen)

    assert result.alpaca_is_available is True
    assert result.alpaca_positions == ()
    assert result.alpaca_health.status is IntegrationStatus.HEALTHY


def test_does_not_alter_the_screens_existing_capital_or_holdings():
    """Alpaca attachment must never touch Capital Summary/Holdings --
    the two are independent concepts, never merged."""
    screen = build_mock_screen()
    with patch(_ACCOUNT_METHOD, return_value=_ok(_ACCOUNT)), patch(
        _POSITIONS_METHOD, return_value=_ok((_POSITION,))
    ):
        result = _with_alpaca_paper_data(screen)

    assert result.capital == screen.capital
    assert result.holdings == screen.holdings
