"""Illustrative-only data for Portfolio Intelligence -- MVP.

No sentinel_engine/bot/dashboard import: no Sentinel-side portfolio
contract exists or is proposed (docs/products/AARA_TRADING_INTELLIGENCE_
UI_SPECIFICATION.md Section 2 -- "Future Sentinel Engine inputs: none
proposed"), and bot/capital/pool.py is ADR-002-protected. This module is
the sole data source for this screen; every value below is a hand-picked,
deterministic illustrative number, not derived from any real account.

Internally consistent by construction (not required, but avoids a
nonsensical illustrative snapshot): holdings' market_value sums to
invested_amount, available_cash + invested_amount = allocated_amount, and
weight_pct sums to 100.0 across holdings.
"""
from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    CapitalSummary,
    PortfolioHolding,
    PortfolioScreen,
)

_MOCK_HOLDINGS = (
    PortfolioHolding(
        symbol="GOOGL", quantity=60, price=172.90, market_value=10374.00, weight_pct=27.5,
    ),
    PortfolioHolding(
        symbol="AAPL", quantity=42, price=228.50, market_value=9597.00, weight_pct=25.4,
    ),
    PortfolioHolding(
        symbol="MSFT", quantity=18, price=412.30, market_value=7421.40, weight_pct=19.7,
    ),
    PortfolioHolding(
        symbol="TSLA", quantity=30, price=245.60, market_value=7368.00, weight_pct=19.5,
    ),
    PortfolioHolding(
        symbol="NVDA", quantity=25, price=118.75, market_value=2968.75, weight_pct=7.9,
    ),
)

_MOCK_CAPITAL = CapitalSummary(
    allocated_amount=50000.00,
    available_cash=12270.85,
    invested_amount=37729.15,
    reserve=2000.00,
    realized_profit=3450.20,
)


def build_mock_screen() -> PortfolioScreen:
    return PortfolioScreen(capital=_MOCK_CAPITAL, holdings=_MOCK_HOLDINGS)
