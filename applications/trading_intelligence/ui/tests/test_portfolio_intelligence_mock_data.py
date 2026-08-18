from applications.trading_intelligence.ui.portfolio_intelligence.mock_data import build_mock_screen


def test_build_mock_screen_returns_a_non_empty_screen():
    screen = build_mock_screen()

    assert not screen.is_empty
    assert len(screen.holdings) == 5


def test_mock_holdings_market_value_sums_to_invested_amount():
    screen = build_mock_screen()

    total_market_value = sum(holding.market_value for holding in screen.holdings)

    assert round(total_market_value, 2) == round(screen.capital.invested_amount, 2)


def test_mock_holdings_weight_pct_sums_to_one_hundred():
    screen = build_mock_screen()

    total_weight = sum(holding.weight_pct for holding in screen.holdings)

    assert round(total_weight, 1) == 100.0


def test_mock_capital_available_cash_plus_invested_equals_allocated():
    screen = build_mock_screen()
    capital = screen.capital

    assert round(capital.available_cash + capital.invested_amount, 2) == round(
        capital.allocated_amount, 2
    )


def test_mock_capital_reserve_does_not_exceed_available_cash():
    screen = build_mock_screen()

    assert screen.capital.reserve <= screen.capital.available_cash
