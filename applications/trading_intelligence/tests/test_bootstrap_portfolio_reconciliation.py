"""Tests for the Internal Portfolio vs Alpaca PAPER reconciliation:
bootstrap._compute_portfolio_reconciliation() (pure) and
bootstrap._with_portfolio_reconciliation_data() (attach-to-screen wiring),
plus a real-sqlite integration proof that the feature reuses the SAME
existing Holdings / Alpaca Paper source lineage -- no new adapter, no new
read.
"""
import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from applications.platform.integrations import IntegrationHealth, ReadResult
from applications.trading_intelligence import bootstrap
from applications.trading_intelligence.ui.portfolio_intelligence.mock_data import (
    build_mock_screen,
)
from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    AlpacaAccountSnapshot,
    AlpacaPosition,
    PortfolioHolding,
    PortfolioScreen,
    ReconciliationStatus,
)

_ACCOUNT_METHOD = (
    "applications.trading_intelligence.adapters."
    "alpaca_paper_source.AlpacaPaperSource.get_account"
)
_POSITIONS_METHOD = (
    "applications.trading_intelligence.adapters."
    "alpaca_paper_source.AlpacaPaperSource.get_positions"
)

_ACCOUNT = AlpacaAccountSnapshot(
    equity=100000.0, cash=50000.0, buying_power=100000.0, portfolio_value=100000.0,
)


def _ok(value):
    return ReadResult.healthy(value, "alpaca_paper")


def _down():
    return ReadResult.failed(IntegrationHealth.unavailable("alpaca_paper"))


def _holding(**overrides):
    defaults = dict(symbol="ZZZZ", quantity=1.0, price=1.0, market_value=1.0, weight_pct=100.0)
    defaults.update(overrides)
    return PortfolioHolding(**defaults)


def _position(**overrides):
    defaults = dict(
        symbol="ZZZZ", quantity=1.0, avg_entry_price=1.0, current_price=1.0,
        market_value=1.0, unrealized_pl=0.0, unrealized_plpc=0.0, side="long",
    )
    defaults.update(overrides)
    return AlpacaPosition(**defaults)


# --- _compute_portfolio_reconciliation() (pure function) ------------------


def test_matched_when_quantities_agree_exactly():
    rows = bootstrap._compute_portfolio_reconciliation(
        holdings=(_holding(symbol="AAPL", quantity=10.0, market_value=1900.0),),
        alpaca_positions=(_position(symbol="AAPL", quantity=10.0, market_value=1901.0),),
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.status is ReconciliationStatus.MATCHED
    assert row.internal_quantity == 10.0
    assert row.alpaca_quantity == 10.0
    assert row.quantity_difference == 0.0
    # market values are each side's own real, already-computed figure --
    # carried through verbatim, never reconciled/averaged/recomputed.
    assert row.internal_market_value == 1900.0
    assert row.alpaca_market_value == 1901.0


def test_quantity_difference_reports_the_real_signed_difference():
    rows = bootstrap._compute_portfolio_reconciliation(
        holdings=(_holding(symbol="AAPL", quantity=10.0),),
        alpaca_positions=(_position(symbol="AAPL", quantity=6.0),),
    )
    row = rows[0]
    assert row.status is ReconciliationStatus.QUANTITY_DIFFERENCE
    assert row.internal_quantity == 10.0
    assert row.alpaca_quantity == 6.0
    assert row.quantity_difference == 4.0


def test_internal_only_when_symbol_absent_from_alpaca():
    rows = bootstrap._compute_portfolio_reconciliation(
        holdings=(_holding(symbol="BAC", quantity=5.0),),
        alpaca_positions=(),
    )
    row = rows[0]
    assert row.status is ReconciliationStatus.INTERNAL_ONLY
    assert row.internal_quantity == 5.0
    assert row.alpaca_quantity is None
    assert row.quantity_difference is None
    assert row.alpaca_market_value is None


def test_broker_only_when_symbol_absent_internally():
    rows = bootstrap._compute_portfolio_reconciliation(
        holdings=(),
        alpaca_positions=(_position(symbol="TSLA", quantity=3.0),),
    )
    row = rows[0]
    assert row.status is ReconciliationStatus.BROKER_ONLY
    assert row.internal_quantity is None
    assert row.alpaca_quantity == 3.0
    assert row.quantity_difference is None
    assert row.internal_market_value is None


def test_multiple_symbols_are_ordered_alphabetically_and_independent():
    rows = bootstrap._compute_portfolio_reconciliation(
        holdings=(
            _holding(symbol="TSLA", quantity=1.0),
            _holding(symbol="AAPL", quantity=2.0),
            _holding(symbol="BAC", quantity=5.0),
        ),
        alpaca_positions=(
            _position(symbol="MSFT", quantity=3.0),
            _position(symbol="AAPL", quantity=2.0),
        ),
    )
    assert [row.symbol for row in rows] == ["AAPL", "BAC", "MSFT", "TSLA"]
    by_symbol = {row.symbol: row for row in rows}
    assert by_symbol["AAPL"].status is ReconciliationStatus.MATCHED
    assert by_symbol["BAC"].status is ReconciliationStatus.INTERNAL_ONLY
    assert by_symbol["MSFT"].status is ReconciliationStatus.BROKER_ONLY
    assert by_symbol["TSLA"].status is ReconciliationStatus.INTERNAL_ONLY


def test_both_sides_empty_yields_an_empty_tuple():
    rows = bootstrap._compute_portfolio_reconciliation(holdings=(), alpaca_positions=())
    assert rows == ()


def test_never_invents_a_tolerance_a_close_enough_match_is_still_a_difference():
    """No fuzzy/tolerance comparison is ever introduced -- any numeric
    disagreement, however small, is QUANTITY_DIFFERENCE, never silently
    treated as MATCHED."""
    rows = bootstrap._compute_portfolio_reconciliation(
        holdings=(_holding(symbol="AAPL", quantity=10.0),),
        alpaca_positions=(_position(symbol="AAPL", quantity=10.0001),),
    )
    assert rows[0].status is ReconciliationStatus.QUANTITY_DIFFERENCE


# --- _with_portfolio_reconciliation_data() (attach-to-screen wiring) ------


def test_reconciliation_unavailable_when_holdings_is_none():
    screen = PortfolioScreen(capital=build_mock_screen().capital, holdings=None)
    with patch(_ACCOUNT_METHOD, return_value=_ok(_ACCOUNT)), patch(
        _POSITIONS_METHOD, return_value=_ok((_position(symbol="AAPL"),))
    ):
        result = bootstrap._with_alpaca_paper_data(screen)
        result = bootstrap._with_portfolio_reconciliation_data(result)

    assert result.reconciliation is None
    assert result.reconciliation_is_available is False


def test_reconciliation_unavailable_when_alpaca_is_unavailable():
    screen = build_mock_screen()  # real holdings, no Alpaca data yet
    with patch(_ACCOUNT_METHOD, return_value=_down()):
        result = bootstrap._with_alpaca_paper_data(screen)
        result = bootstrap._with_portfolio_reconciliation_data(result)

    assert result.reconciliation is None
    assert result.reconciliation_is_available is False
    # Holdings itself is untouched by this attachment.
    assert result.holdings == screen.holdings


def test_reconciliation_populated_when_both_sources_are_real():
    """Uses build_mock_screen()'s own real holdings (GOOGL/AAPL/MSFT/TSLA/
    NVDA) against a controlled Alpaca fixture -- proving the reconciliation
    reads the SAME screen.holdings the Holdings table already renders, not
    a second, independent read."""
    mock = build_mock_screen()
    alpaca_positions = (
        _position(symbol="AAPL", quantity=42.0),   # matches mock holding exactly
        _position(symbol="MSFT", quantity=10.0),   # differs from mock holding (18)
        _position(symbol="AMZN", quantity=5.0),    # broker only
    )
    with patch(_ACCOUNT_METHOD, return_value=_ok(_ACCOUNT)), patch(
        _POSITIONS_METHOD, return_value=_ok(alpaca_positions)
    ):
        result = bootstrap._with_alpaca_paper_data(mock)
        result = bootstrap._with_portfolio_reconciliation_data(result)

    assert result.reconciliation_is_available is True
    by_symbol = {row.symbol: row for row in result.reconciliation}
    assert by_symbol["AAPL"].status is ReconciliationStatus.MATCHED
    assert by_symbol["MSFT"].status is ReconciliationStatus.QUANTITY_DIFFERENCE
    assert by_symbol["MSFT"].quantity_difference == 18.0 - 10.0
    assert by_symbol["AMZN"].status is ReconciliationStatus.BROKER_ONLY
    # GOOGL/TSLA/NVDA are internal-only (present in the mock holdings, not
    # in this Alpaca fixture).
    for symbol in ("GOOGL", "TSLA", "NVDA"):
        assert by_symbol[symbol].status is ReconciliationStatus.INTERNAL_ONLY


def test_reconciliation_does_not_disturb_orders_or_account_attachment():
    """Regression guard: adding the reconciliation attachment step must not
    change what _with_alpaca_paper_data/_with_alpaca_orders_data already
    attach."""
    mock = build_mock_screen()
    with patch(_ACCOUNT_METHOD, return_value=_ok(_ACCOUNT)), patch(
        _POSITIONS_METHOD, return_value=_ok((_position(symbol="AAPL", quantity=42.0),))
    ):
        with_alpaca = bootstrap._with_alpaca_paper_data(mock)
        with_reconciliation = bootstrap._with_portfolio_reconciliation_data(with_alpaca)

    assert with_reconciliation.alpaca_account == with_alpaca.alpaca_account
    assert with_reconciliation.alpaca_positions == with_alpaca.alpaca_positions
    assert with_reconciliation.alpaca_orders == with_alpaca.alpaca_orders


# --- Full integration: real sqlite trades.db + real adapter chain --------


_DDL = """
CREATE TABLE capital_pools (
    id INTEGER PRIMARY KEY, allocated_amount REAL, available_cash REAL,
    invested_amount REAL, reserve REAL, realized_profit REAL, status TEXT
);
CREATE TABLE position_state (symbol TEXT, shares REAL, entry_price REAL);
CREATE TABLE portfolio_snapshots (
    timestamp TEXT PRIMARY KEY, portfolio_value REAL, available_cash REAL,
    open_positions INTEGER
);
"""


def _make_snapshot_db():
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.executescript(_DDL)
    conn.execute(
        "INSERT INTO capital_pools "
        "(allocated_amount, available_cash, invested_amount, reserve, realized_profit, status) "
        "VALUES (50000.0, 12345.67, 37000.0, 654.33, 1200.5, 'active')"
    )
    # The SAME position_state table Holdings' own LegacyPositionSource
    # already reads -- no new table, no new adapter.
    conn.execute(
        "INSERT INTO position_state (symbol, shares, entry_price) VALUES ('AAPL', 10.0, 190.0)"
    )
    conn.execute(
        "INSERT INTO position_state (symbol, shares, entry_price) VALUES ('MSFT', 4.0, 410.0)"
    )
    conn.commit()
    conn.close()
    return path


def test_seeded_snapshot_reconciliation_uses_the_real_holdings_and_alpaca_source_lineage():
    """End-to-end proof (task requirement #12): a real sqlite trades.db
    drives Holdings via the existing LegacyPositionSource + LivePriceSource
    chain, a controlled Alpaca fixture drives the broker side, and
    _build_portfolio_intelligence_screen() -- the real, production
    screen_provider -- produces a reconciliation from those SAME two
    already-wired sources. No new reader, no new table."""
    db_path = _make_snapshot_db()
    prices_method = (
        "applications.trading_intelligence.adapters."
        "live_price_source.LivePriceSource.get_current_prices"
    )
    try:
        with patch(prices_method, return_value=_ok({"AAPL": 200.0, "MSFT": 420.0})), \
             patch(_ACCOUNT_METHOD, return_value=_ok(_ACCOUNT)), \
             patch(
                 _POSITIONS_METHOD,
                 return_value=_ok((
                     _position(symbol="AAPL", quantity=10.0, market_value=2000.0),
                     _position(symbol="MSFT", quantity=6.0, market_value=2520.0),
                 )),
             ):
            screen = bootstrap._build_portfolio_intelligence_screen(db_path=db_path)

        assert screen.holdings is not None
        assert {h.symbol for h in screen.holdings} == {"AAPL", "MSFT"}
        assert screen.reconciliation_is_available is True
        by_symbol = {row.symbol: row for row in screen.reconciliation}
        # 10 internal shares (position_state) vs 10 Alpaca shares -> MATCHED
        assert by_symbol["AAPL"].status is ReconciliationStatus.MATCHED
        assert by_symbol["AAPL"].internal_quantity == 10.0
        assert by_symbol["AAPL"].alpaca_quantity == 10.0
        # 4 internal shares (position_state) vs 6 Alpaca shares -> QUANTITY_DIFFERENCE
        assert by_symbol["MSFT"].status is ReconciliationStatus.QUANTITY_DIFFERENCE
        assert by_symbol["MSFT"].internal_quantity == 4.0
        assert by_symbol["MSFT"].alpaca_quantity == 6.0
        assert by_symbol["MSFT"].quantity_difference == -2.0
    finally:
        os.remove(db_path)


def test_seeded_snapshot_reconciliation_unavailable_when_holdings_prices_fail():
    """Same real sqlite snapshot, but the live-price leg of Holdings fails
    -- Holdings becomes unavailable (existing behavior, unchanged), and
    the reconciliation must honestly follow it into unavailable rather
    than reconciling against a partial/fabricated Holdings state."""
    db_path = _make_snapshot_db()
    prices_method = (
        "applications.trading_intelligence.adapters."
        "live_price_source.LivePriceSource.get_current_prices"
    )
    try:
        with patch(prices_method, return_value=_down()), \
             patch(_ACCOUNT_METHOD, return_value=_ok(_ACCOUNT)), \
             patch(_POSITIONS_METHOD, return_value=_ok((_position(symbol="AAPL"),))):
            screen = bootstrap._build_portfolio_intelligence_screen(db_path=db_path)

        assert screen.holdings is None
        assert screen.reconciliation_is_available is False
    finally:
        os.remove(db_path)
