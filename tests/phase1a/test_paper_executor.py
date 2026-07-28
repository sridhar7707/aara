"""Tests for bot/execution/paper_executor.py, base.py, factory.py, and
timeframe.py (Phase 1A Sprint 5)."""
from __future__ import annotations

import ast
import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bot.execution.paper_executor import PaperExecutor  # noqa: E402


@pytest.fixture
def executor(tmp_path, monkeypatch):
    db_path = str(tmp_path / "paper_portfolio.db")
    ex = PaperExecutor(db_path=db_path)
    monkeypatch.setattr(ex, "get_latest_price", lambda symbol: 100.0)
    return ex


# ── safety property: source-level, not sys.modules (see design note in
# paper_executor.py's own docstring for why sys.modules can't be used here --
# the alpaca-py SDK loads alpaca.trading as a packaging side effect of
# importing ANYTHING from the alpaca package, regardless of what this file
# does). What IS achievable and IS tested: this file's own source never
# names TradingClient or .submit_order. ──────────────────────────────────

def test_paper_executor_source_never_references_trading_client():
    """AST-based, not substring search -- a substring check would false-
    positive on this module's own docstring, which explicitly documents
    that it never uses TradingClient/.submit_order."""
    import bot.execution.paper_executor as mod
    tree = ast.parse(inspect.getsource(mod))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "alpaca.trading" not in node.module, f"found alpaca.trading import: {node.module}"
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "alpaca.trading" not in alias.name, f"found alpaca.trading import: {alias.name}"
        if isinstance(node, ast.Name):
            assert node.id != "TradingClient"
        if isinstance(node, ast.Attribute):
            assert node.attr != "submit_order"


def test_paper_executor_api_attribute_is_none(executor):
    assert executor.api is None


# ── starting balance / account ────────────────────────────────────────────

def test_starting_balance_is_1000(executor):
    acct = executor.get_account()
    assert acct.cash == 1000.0
    assert acct.portfolio_value == 1000.0
    assert acct.status == "ACTIVE"
    assert acct.trading_blocked is False


def test_fresh_executor_has_no_positions(executor):
    assert executor.get_positions() == {}


# ── buy ────────────────────────────────────────────────────────────────────

def test_buy_deducts_cash_and_creates_position(executor):
    result = executor.buy("AAPL", 500.0)
    assert result is not None
    assert result["symbol"] == "AAPL"
    assert result["side"] == "buy"

    positions = executor.get_positions()
    assert "AAPL" in positions
    assert positions["AAPL"].qty > 0
    cash = executor.get_cash()
    assert cash == pytest.approx(500.0, abs=0.01)


def test_buy_rejects_notional_exceeding_cash(executor):
    result = executor.buy("AAPL", 2000.0)  # more than the $1000 starting balance
    assert result is None
    assert executor.get_cash() == 1000.0


def test_buy_applies_spread_and_slippage_above_quoted_price(executor):
    """Buyer should pay slightly MORE than the raw quoted price (100.0)."""
    executor.buy("AAPL", 500.0)
    fill_price = executor.get_fill_price(
        executor._conn.execute("SELECT order_id FROM paper_fills LIMIT 1").fetchone()[0]
    )
    assert fill_price > 100.0


def test_second_buy_averages_up_position(executor):
    executor.buy("AAPL", 300.0)
    executor.buy("AAPL", 300.0)
    positions = executor.get_positions()
    assert positions["AAPL"].qty > 0
    # cash should reflect both buys
    assert executor.get_cash() == pytest.approx(400.0, abs=0.01)


# ── sell ───────────────────────────────────────────────────────────────────

def test_sell_full_position_credits_cash_and_removes_position(executor):
    executor.buy("AAPL", 500.0)
    qty = executor.get_positions()["AAPL"].qty

    result = executor.sell("AAPL", qty=qty)
    assert result is not None
    assert result["side"] == "sell"
    assert "AAPL" not in executor.get_positions()
    assert executor.get_cash() > 500.0  # got proceeds back (minus spread/slippage)


def test_sell_partial_position_reduces_qty(executor):
    executor.buy("AAPL", 500.0)
    full_qty = executor.get_positions()["AAPL"].qty
    executor.sell("AAPL", qty=full_qty / 2)
    remaining = executor.get_positions()["AAPL"].qty
    assert remaining == pytest.approx(full_qty / 2, rel=1e-6)


def test_sell_applies_spread_and_slippage_below_quoted_price(executor):
    """Seller should receive slightly LESS than the raw quoted price."""
    executor.buy("AAPL", 500.0)
    qty = executor.get_positions()["AAPL"].qty
    executor.sell("AAPL", qty=qty)
    order_id = executor._conn.execute(
        "SELECT order_id FROM paper_fills WHERE side='sell' LIMIT 1"
    ).fetchone()[0]
    fill_price = executor.get_fill_price(order_id)
    assert fill_price < 100.0


def test_sell_no_position_returns_none(executor):
    assert executor.sell("MSFT", qty=1.0) is None


def test_sell_market_is_equivalent_to_sell(executor):
    executor.buy("AAPL", 500.0)
    qty = executor.get_positions()["AAPL"].qty
    result = executor.sell_market("AAPL", qty)
    assert result is not None
    assert "AAPL" not in executor.get_positions()


# ── fills are synchronous ───────────────────────────────────────────────────

def test_wait_for_fill_returns_full_qty_immediately(executor):
    result = executor.buy("AAPL", 500.0)
    filled = executor.wait_for_fill(result["order_id"])
    assert filled > 0


def test_get_open_order_symbols_always_empty(executor):
    executor.buy("AAPL", 500.0)
    buy_syms, sell_syms = executor.get_open_order_symbols()
    assert buy_syms == set()
    assert sell_syms == set()


# ── round-trip P&L sanity ───────────────────────────────────────────────────

def test_round_trip_at_same_price_loses_money_to_costs(executor):
    """Buying and immediately selling at the same quoted price should lose
    a small amount to spread+slippage on both legs -- proves costs are
    actually being applied, not just present in the code."""
    executor.buy("AAPL", 500.0)
    qty = executor.get_positions()["AAPL"].qty
    executor.sell("AAPL", qty=qty)
    assert executor.get_cash() < 500.0 + 500.0  # started with 1000, should have less than 1000 back
