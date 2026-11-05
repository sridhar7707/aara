"""ADR-080 §5.1 reproduction: several entries in one cycle must respect the
position cap and per-sector cap, even though each entry is evaluated against
the same per-cycle positions snapshot the loop in bot/main.py passes down.

This test must FAIL on the current code (the snapshot is never updated after a
buy fills) and PASS once the fix from ADR-080 lands.
"""
from __future__ import annotations

import pytest

from bot._main_cycle import _handle_entry, EntryContext
from bot.risk.risk_manager import RiskManager
from config import MAX_POSITIONS, MAX_SECTOR_POSITIONS, SECTOR_MAP

from tests.phase1a.test_decision_capture_integration import (  # reuse real fixtures
    _minimal_entry_ctx,
    chain,
    ledger_conn,
    trades_db,
    _clear_candidate_cache,
)

# Real symbols from SECTOR_MAP so the sector gate runs against real config.
TECH_CANDIDATES = ["AAPL", "MSFT", "NVDA"]
NON_TECH_HOLDINGS = ["JPM", "XOM", "UNH", "KO", "PG", "WMT", "CAT"]


class _CountingFillClient:
    """Records every buy so the test can count real orders placed in one cycle."""

    def __init__(self):
        self.buys: list[str] = []

    def buy(self, symbol, notional, limit_price=None):
        self.buys.append(symbol)
        return {"order_id": f"ord-{symbol}"}

    def wait_for_fill(self, order_id, timeout_secs=15):
        return 10.0

    def get_fill_price(self, order_id):
        return 100.0


class _NoDriversXgb:
    def explain(self, row):
        return []


def _held_positions(symbols):
    """Open-position placeholders with the attributes the gates read."""
    class _Pos:
        def __init__(self, sym):
            self.symbol = sym
            self.qty = 10
            self.market_value = 1_000.0
            self.avg_entry_price = 100.0
            self.unrealized_plpc = 0.0
    return {s: _Pos(s) for s in symbols}


@pytest.mark.xfail(strict=True, reason="ADR-080 §5.1: reproduces the stale per-cycle position snapshot; remove this marker in the fix commit")
def test_same_cycle_buys_respect_position_and_sector_caps(trades_db, ledger_conn, chain):
    assert all(SECTOR_MAP[s] == "Technology" for s in TECH_CANDIDATES)
    assert len(NON_TECH_HOLDINGS) == MAX_POSITIONS - 1  # 7 open, room for exactly 1 more

    # The per-cycle snapshot, shared across the whole symbol loop exactly as
    # bot/main.py does it (positions fetched once; never updated after a buy).
    positions = _held_positions(NON_TECH_HOLDINGS)
    client = _CountingFillClient()
    risk = RiskManager()

    for symbol in TECH_CANDIDATES:
        ctx = _minimal_entry_ctx(
            ledger_conn, chain,
            positions=positions,  # same dict object for every symbol this cycle
            available_cash=50_000.0, tradeable_capital=50_000.0, portfolio_value=100_000.0,
            xgb=_NoDriversXgb(),
        )
        _handle_entry(trades_db, client=client, risk=risk, symbol=symbol, ctx=ctx)

    # Correct behaviour: the cap of MAX_POSITIONS (8) with 7 open allows exactly
    # one more buy, and the Technology sector cap of MAX_SECTOR_POSITIONS (2)
    # would stop a second Technology buy anyway -- so at most one buy total.
    allowed_new = min(MAX_POSITIONS - len(NON_TECH_HOLDINGS), MAX_SECTOR_POSITIONS)
    assert len(client.buys) <= allowed_new, (
        f"{len(client.buys)} buys placed in one cycle ({client.buys}) with "
        f"{len(NON_TECH_HOLDINGS)} already open; caps allow at most {allowed_new}"
    )
    assert len(NON_TECH_HOLDINGS) + len(client.buys) <= MAX_POSITIONS


def test_correlated_pair_second_buy_blocked_after_first_fill(trades_db, ledger_conn, chain):
    """ADR-080 §5.2: once the first buy fills, the correlation gate must see it
    when evaluating a highly correlated second symbol in the same cycle.
    The placeholder insertion mirrors the fill registration in bot/main.py."""
    import numpy as np
    import pandas as pd
    from types import SimpleNamespace
    from bot._main_positions import BarData

    rng = np.random.default_rng(0)
    closes = 100 + np.cumsum(rng.normal(0, 1, 80))
    daily = pd.DataFrame({"close": closes})
    bars_map = {s: BarData(pd.DataFrame(), daily) for s in ("AAPL", "MSFT")}

    positions: dict = {}
    client = _CountingFillClient()
    risk = RiskManager()

    for symbol in ("AAPL", "MSFT"):
        ctx = _minimal_entry_ctx(
            ledger_conn, chain,
            positions=positions, bars_map=bars_map,
            available_cash=50_000.0, tradeable_capital=50_000.0, portfolio_value=100_000.0,
            xgb=_NoDriversXgb(),
        )
        before = len(client.buys)
        _handle_entry(trades_db, client=client, risk=risk, symbol=symbol, ctx=ctx)
        if len(client.buys) > before:  # fill registered, as bot/main.py does
            positions[symbol] = SimpleNamespace(symbol=symbol, qty=1.0, market_value=1_000.0,
                                                avg_entry_price=100.0, unrealized_plpc=0.0)

    assert client.buys == ["AAPL"], f"correlated second buy was not blocked: {client.buys}"
