"""Tests for bot/execution/supervised.py (REQ-200/202, architecture only).

Proves the structural no-op guarantee: buy/sell/sell_market never place a
real order (no Alpaca TradingClient order call happens), while reads still
delegate through to a real AlpacaClient instance.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bot.execution.supervised import SupervisedExecutor  # noqa: E402


def test_buy_never_places_an_order(monkeypatch):
    executor = SupervisedExecutor()

    def _boom(*a, **k):
        raise AssertionError("SupervisedExecutor.buy must never reach a real order call")
    monkeypatch.setattr(executor._reader, "buy", _boom)

    result = executor.buy("AAPL", 100.0)
    assert result is None


def test_sell_never_places_an_order(monkeypatch):
    executor = SupervisedExecutor()

    def _boom(*a, **k):
        raise AssertionError("SupervisedExecutor.sell must never reach a real order call")
    monkeypatch.setattr(executor._reader, "sell", _boom)

    result = executor.sell("AAPL", qty=1.0)
    assert result is None


def test_sell_market_never_places_an_order(monkeypatch):
    executor = SupervisedExecutor()
    monkeypatch.setattr(
        executor._reader, "sell",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not be called")),
    )
    assert executor.sell_market("AAPL", 1.0) is None


def test_wait_for_fill_and_fill_price_are_always_empty():
    executor = SupervisedExecutor()
    assert executor.wait_for_fill("any-order-id") == 0.0
    assert executor.get_fill_price("any-order-id") is None


def test_get_open_order_symbols_always_empty():
    executor = SupervisedExecutor()
    assert executor.get_open_order_symbols() == (set(), set())


def test_reads_delegate_to_real_alpaca_client(monkeypatch):
    executor = SupervisedExecutor()
    monkeypatch.setattr(executor._reader, "get_portfolio_value", lambda: 12345.0)
    assert executor.get_portfolio_value() == 12345.0


def test_satisfies_executor_protocol():
    from bot.execution.base import Executor
    assert isinstance(SupervisedExecutor(), Executor)
