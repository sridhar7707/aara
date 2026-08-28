from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    CapitalSummary,
    PortfolioHolding,
    PortfolioScreen,
)


def _make_capital(**overrides):
    defaults = dict(
        allocated_amount=50000.0,
        available_cash=12270.85,
        invested_amount=37729.15,
        reserve=2000.0,
        realized_profit=3450.20,
    )
    defaults.update(overrides)
    return CapitalSummary(**defaults)


def test_total_value_is_available_cash_plus_invested_amount():
    capital = _make_capital(available_cash=100.0, invested_amount=400.0)

    assert capital.total_value == 500.0


def test_tradeable_cash_is_available_cash_minus_reserve():
    capital = _make_capital(available_cash=100.0, reserve=40.0)

    assert capital.tradeable_cash == 60.0


def test_tradeable_cash_floors_at_zero_when_reserve_exceeds_available_cash():
    capital = _make_capital(available_cash=10.0, reserve=40.0)

    assert capital.tradeable_cash == 0.0


def test_cash_and_invested_weight_pct_sum_to_one_hundred():
    capital = _make_capital(available_cash=250.0, invested_amount=750.0)

    assert capital.cash_weight_pct == 25.0
    assert capital.invested_weight_pct == 75.0
    assert capital.cash_weight_pct + capital.invested_weight_pct == 100.0


def test_weight_pct_is_zero_when_total_value_is_zero():
    capital = _make_capital(available_cash=0.0, invested_amount=0.0)

    assert capital.cash_weight_pct == 0.0
    assert capital.invested_weight_pct == 0.0


def test_portfolio_screen_is_empty_only_when_holdings_is_an_empty_tuple():
    screen = PortfolioScreen(capital=_make_capital(), holdings=())

    assert screen.is_empty
    assert screen.empty_state_message == "No holdings recorded yet."


def test_portfolio_screen_is_not_empty_with_holdings():
    holding = PortfolioHolding(
        symbol="AAPL", quantity=10, price=100.0, market_value=1000.0, weight_pct=100.0,
    )
    screen = PortfolioScreen(capital=_make_capital(), holdings=(holding,))

    assert not screen.is_empty


def test_default_screen_is_fully_unavailable_not_empty():
    screen = PortfolioScreen()

    assert screen.capital is None
    assert screen.holdings is None
    assert screen.capital_is_available is False
    assert screen.holdings_is_available is False
    assert screen.is_empty is False  # unavailable, not "connected with zero holdings"


def test_capital_is_available_reflects_whether_capital_was_supplied():
    assert PortfolioScreen(capital=_make_capital()).capital_is_available is True
    assert PortfolioScreen(capital=None).capital_is_available is False


def test_holdings_is_available_true_for_empty_tuple_false_for_none():
    assert PortfolioScreen(capital=_make_capital(), holdings=()).holdings_is_available is True
    assert PortfolioScreen(capital=_make_capital(), holdings=None).holdings_is_available is False
    holding = PortfolioHolding(
        symbol="AAPL", quantity=1, price=1.0, market_value=1.0, weight_pct=100.0,
    )
    assert PortfolioScreen(
        capital=_make_capital(), holdings=(holding,)
    ).holdings_is_available is True


def test_is_empty_is_false_when_holdings_is_none():
    screen = PortfolioScreen(capital=_make_capital(), holdings=None)

    assert screen.is_empty is False
