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
    _clear_candidate_cache,  # autouse fixture: must stay imported, not unused
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
    when evaluating a highly correlated second symbol in the same cycle."""
    import numpy as np
    import pandas as pd
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
        _handle_entry(trades_db, client=client, risk=risk, symbol=symbol, ctx=ctx)

    assert client.buys == ["AAPL"], f"correlated second buy was not blocked: {client.buys}"


def test_pending_buy_order_counts_toward_position_cap(trades_db, ledger_conn, chain):
    """ADR-080 §5.3: a submitted-but-unfilled buy counts toward MAX_POSITIONS.
    7 open + 1 pending (BAC, not held) = 8 = cap, so AAPL must be blocked."""
    positions = _held_positions(NON_TECH_HOLDINGS)
    client = _CountingFillClient()
    ctx = _minimal_entry_ctx(
        ledger_conn, chain,
        positions=positions, buy_order_syms={"BAC"},
        available_cash=50_000.0, tradeable_capital=50_000.0, portfolio_value=100_000.0,
        xgb=_NoDriversXgb(),
    )
    _handle_entry(trades_db, client=client, risk=RiskManager(), symbol="AAPL", ctx=ctx)
    assert client.buys == [], "pending order did not count toward the position cap"


def test_filled_position_not_double_counted_when_pending_clears(trades_db, ledger_conn, chain):
    """ADR-080 §5.4: a symbol that is both pending and now in the positions
    snapshot (its fill has appeared) must count once. 6 real + AAPL (real, still
    listed as pending) = 7 -> MSFT is still allowed; double counting would give 8."""
    positions = _held_positions(NON_TECH_HOLDINGS[:6] + ["AAPL"])
    client = _CountingFillClient()
    ctx = _minimal_entry_ctx(
        ledger_conn, chain,
        positions=positions, buy_order_syms={"AAPL"},
        available_cash=50_000.0, tradeable_capital=50_000.0, portfolio_value=100_000.0,
        xgb=_NoDriversXgb(),
    )
    _handle_entry(trades_db, client=client, risk=RiskManager(), symbol="MSFT", ctx=ctx)
    assert client.buys == ["MSFT"], f"pending symbol double-counted: {client.buys}"


class _TimeoutFirstClient(_CountingFillClient):
    """First order times out unfilled (wait_for_fill -> 0); later orders fill."""

    def wait_for_fill(self, order_id, timeout_secs=15):
        return 0.0 if order_id == f"ord-{self.buys[0]}" else 10.0


def test_timed_out_order_fails_closed_for_the_rest_of_the_cycle(trades_db, ledger_conn, chain):
    """Fail closed: a timed-out order's cancel result is unknown, so the symbol stays
    pending for the rest of the cycle and blocks the same symbol and one cap slot."""
    positions = _held_positions(NON_TECH_HOLDINGS)
    buy_order_syms: set = set()
    client = _TimeoutFirstClient()
    risk = RiskManager()
    for symbol in ("AAPL", "MSFT"):
        ctx = _minimal_entry_ctx(
            ledger_conn, chain,
            positions=positions, buy_order_syms=buy_order_syms,
            available_cash=50_000.0, tradeable_capital=50_000.0, portfolio_value=100_000.0,
            xgb=_NoDriversXgb(),
        )
        _handle_entry(trades_db, client=client, risk=risk, symbol=symbol, ctx=ctx)
    # 7 open + AAPL pending = 8 = MAX_POSITIONS, so MSFT must be blocked.
    assert client.buys == ["AAPL"], f"timed-out order did not hold its cap slot: {client.buys}"
    assert "AAPL" in buy_order_syms and "AAPL" not in positions


def test_fill_registered_even_if_trade_log_write_fails(trades_db, ledger_conn, chain, monkeypatch):
    """Review finding: a confirmed fill must be counted by later gates even if the
    DB/ledger write after it raises."""
    import bot._main_cycle as mc

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated log_trade failure")

    monkeypatch.setattr(mc, "log_trade", _boom)
    positions = _held_positions(NON_TECH_HOLDINGS)
    client = _CountingFillClient()
    risk = RiskManager()
    ctx = _minimal_entry_ctx(
        ledger_conn, chain,
        positions=positions,
        available_cash=50_000.0, tradeable_capital=50_000.0, portfolio_value=100_000.0,
        xgb=_NoDriversXgb(),
    )
    with pytest.raises(RuntimeError):
        _handle_entry(trades_db, client=client, risk=risk, symbol="AAPL", ctx=ctx)
    assert client.buys == ["AAPL"] and "AAPL" in positions

    ctx2 = _minimal_entry_ctx(
        ledger_conn, chain,
        positions=positions,
        available_cash=50_000.0, tradeable_capital=50_000.0, portfolio_value=100_000.0,
        xgb=_NoDriversXgb(),
    )
    _handle_entry(trades_db, client=client, risk=risk, symbol="MSFT", ctx=ctx2)
    assert client.buys == ["AAPL"], f"later symbol not blocked after failed write: {client.buys}"
