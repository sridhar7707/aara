"""Shared fixtures for tests/phase1a/.

CI has no Alpaca credentials configured (correctly -- it shouldn't hold
live trading keys), so ALPACA_KEY/ALPACA_SECRET are empty strings there.
alpaca-py's REST client base class raises ValueError("You must supply a
method of authentication") the moment TradingClient or
StockHistoricalDataClient is constructed with an empty key/secret --
before any network call is attempted, purely a presence check. AlpacaClient
and PaperExecutor (the latter for real-price market data reads) both bind
ALPACA_KEY/ALPACA_SECRET at their own module import time, so patching
config.ALPACA_KEY directly has no effect on the already-bound names --
each importing module's own binding needs patching instead.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _fake_alpaca_credentials(monkeypatch):
    import bot.execution.alpaca_client as alpaca_client_mod
    import bot.execution.paper_executor as paper_executor_mod

    for mod in (alpaca_client_mod, paper_executor_mod):
        monkeypatch.setattr(mod, "ALPACA_KEY", "test_key")
        monkeypatch.setattr(mod, "ALPACA_SECRET", "test_secret")
