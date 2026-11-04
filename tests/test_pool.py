"""Tests for bot/capital/pool.py — all tests use an in-memory SQLite DB."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import os
os.environ.setdefault("_BOT_LOG_HANDLER_ADDED", "1")

from bot.capital.pool import (
    CapitalPool,
    append_ledger,
    deposit,
    load_active_pool,
    reconcile_pool,
    set_reserve,
    update_on_buy,
    update_on_sell,
    withdraw,
)


@pytest.fixture
def mem_db():
    con = sqlite3.connect(":memory:")
    yield con
    con.close()


@pytest.fixture
def pool_db(mem_db):
    """mem_db with an active pool of $5000 already loaded."""
    pool = load_active_pool(mem_db, 5000.0)
    return mem_db, pool


# ── 1. load_active_pool creates default ───────────────────────────────────────

def test_load_active_pool_creates_default(mem_db):
    pool = load_active_pool(mem_db, 5000.0)
    assert pool.allocated_amount == 5000.0
    assert pool.available_cash == 5000.0
    row = mem_db.execute("SELECT event_type FROM capital_ledger").fetchone()
    assert row is not None
    assert row[0] == "deposit"


# ── 2. load_active_pool returns existing ──────────────────────────────────────

def test_load_active_pool_returns_existing(mem_db):
    p1 = load_active_pool(mem_db, 5000.0)
    p2 = load_active_pool(mem_db, 9999.0)   # different amount — must be ignored
    assert p2.id == p1.id
    assert p2.allocated_amount == 5000.0
    count = mem_db.execute("SELECT COUNT(*) FROM capital_pools").fetchone()[0]
    assert count == 1


# ── 3. update_on_buy moves cash to invested ───────────────────────────────────

def test_update_on_buy_moves_cash_to_invested(pool_db):
    con, pool = pool_db
    update_on_buy(con, pool.id, 1000.0)
    row = con.execute(
        "SELECT available_cash, invested_amount FROM capital_pools WHERE id=?",
        (pool.id,),
    ).fetchone()
    assert row[0] == pytest.approx(4000.0)
    assert row[1] == pytest.approx(1000.0)


# ── 4. update_on_sell books profit ────────────────────────────────────────────

def test_update_on_sell_books_pnl(pool_db):
    con, pool = pool_db
    update_on_buy(con, pool.id, 1000.0)
    update_on_sell(con, pool.id, cost_basis=1000.0, fill_value=1200.0)
    row = con.execute(
        "SELECT available_cash, invested_amount, realized_profit FROM capital_pools WHERE id=?",
        (pool.id,),
    ).fetchone()
    assert row[0] == pytest.approx(5200.0)
    assert row[1] == pytest.approx(0.0)
    assert row[2] == pytest.approx(200.0)


# ── 5. update_on_sell books loss ──────────────────────────────────────────────

def test_update_on_sell_loss(pool_db):
    con, pool = pool_db
    update_on_buy(con, pool.id, 1000.0)
    update_on_sell(con, pool.id, cost_basis=1000.0, fill_value=800.0)
    row = con.execute(
        "SELECT realized_profit FROM capital_pools WHERE id=?", (pool.id,)
    ).fetchone()
    assert row[0] == pytest.approx(-200.0)


# ── 6. ledger entry on buy ────────────────────────────────────────────────────

def test_ledger_entry_on_buy(pool_db):
    con, pool = pool_db
    con.execute("DELETE FROM capital_ledger")
    update_on_buy(con, pool.id, 1000.0)
    row = con.execute(
        "SELECT event_type, amount FROM capital_ledger WHERE event_type='buy'"
    ).fetchone()
    assert row is not None
    assert row[0] == "buy"
    assert row[1] == pytest.approx(-1000.0)


# ── 7. ledger entry on sell ───────────────────────────────────────────────────

def test_ledger_entry_on_sell(pool_db):
    con, pool = pool_db
    con.execute("DELETE FROM capital_ledger")
    update_on_buy(con, pool.id, 1000.0)
    update_on_sell(con, pool.id, cost_basis=1000.0, fill_value=1200.0)
    row = con.execute(
        "SELECT event_type FROM capital_ledger WHERE event_type='sell'"
    ).fetchone()
    assert row is not None
    assert row[0] == "sell"


# ── 8. deposit increases cash and allocated ───────────────────────────────────

def test_deposit_increases_cash_and_allocated(pool_db):
    con, pool = pool_db
    deposit(con, pool.id, 500.0)
    row = con.execute(
        "SELECT available_cash, allocated_amount FROM capital_pools WHERE id=?",
        (pool.id,),
    ).fetchone()
    assert row[0] == pytest.approx(5500.0)
    assert row[1] == pytest.approx(5500.0)


# ── 9. withdraw decreases cash ────────────────────────────────────────────────

def test_withdraw_decreases_cash(pool_db):
    con, pool = pool_db
    withdraw(con, pool.id, 300.0)
    row = con.execute(
        "SELECT available_cash FROM capital_pools WHERE id=?", (pool.id,)
    ).fetchone()
    assert row[0] == pytest.approx(4700.0)


# ── 10. withdraw tracks profit_withdrawn ──────────────────────────────────────

def test_withdraw_tracks_profit_withdrawn(pool_db):
    con, pool = pool_db
    update_on_buy(con, pool.id, 1000.0)
    update_on_sell(con, pool.id, cost_basis=1000.0, fill_value=1200.0)  # realized_profit = 200
    withdraw(con, pool.id, 200.0)
    row = con.execute(
        "SELECT profit_withdrawn FROM capital_pools WHERE id=?", (pool.id,)
    ).fetchone()
    assert row[0] == pytest.approx(200.0)


# ── 11. withdrawable_profit property ──────────────────────────────────────────

def test_withdrawable_profit_property():
    pool = CapitalPool(
        id=1, name="test", allocated_amount=5000.0, available_cash=5000.0,
        invested_amount=0.0, reserve=0.0,
        realized_profit=500.0, profit_withdrawn=200.0,
    )
    assert pool.withdrawable_profit == pytest.approx(300.0)


# ── 12. tradeable_cash respects reserve ───────────────────────────────────────

def test_tradeable_cash_respects_reserve():
    pool = CapitalPool(
        id=1, name="test", allocated_amount=5000.0, available_cash=3000.0,
        invested_amount=0.0, reserve=500.0,
        realized_profit=0.0, profit_withdrawn=0.0,
    )
    assert pool.tradeable_cash == pytest.approx(2500.0)


# ── 13. set_reserve updates DB ────────────────────────────────────────────────

def test_set_reserve_updates_db(pool_db):
    con, pool = pool_db
    set_reserve(con, pool.id, 750.0)
    reloaded = load_active_pool(con)
    assert reloaded.reserve == pytest.approx(750.0)


# ── 14. ledger symbol tracking ────────────────────────────────────────────────

def test_ledger_symbol_tracking(pool_db):
    con, pool = pool_db
    update_on_buy(con, pool.id, 500.0, symbol="AAPL")
    row = con.execute(
        "SELECT symbol FROM capital_ledger WHERE event_type='buy'"
    ).fetchone()
    assert row is not None
    assert row[0] == "AAPL"


# ── 15. atomic buy/sell sequence ──────────────────────────────────────────────

def test_atomic_buy_sell_sequence(pool_db):
    con, pool = pool_db
    update_on_buy(con, pool.id, 1000.0, symbol="TSLA")
    update_on_sell(con, pool.id, cost_basis=1000.0, fill_value=1100.0, symbol="TSLA")
    row = con.execute(
        "SELECT available_cash, invested_amount FROM capital_pools WHERE id=?",
        (pool.id,),
    ).fetchone()
    assert row[1] == pytest.approx(0.0)       # invested back to zero
    assert row[0] == pytest.approx(5100.0)    # original 5000 + 100 profit


# ── 16. reconcile_pool (ADR-075) ──────────────────────────────────────────────

def test_reconcile_pool_no_drift_writes_nothing(pool_db):
    """Within tolerance of both real figures -- no write, no ledger entry,
    returns False. Keeps capital_ledger free of per-cycle noise once the
    pool is already in sync."""
    con, pool = pool_db
    before = con.execute(
        "SELECT available_cash, invested_amount, updated_at FROM capital_pools WHERE id=?",
        (pool.id,),
    ).fetchone()

    changed = reconcile_pool(con, pool.id, real_available_cash=5000.0, real_invested_cost_basis=0.0)

    assert changed is False
    after = con.execute(
        "SELECT available_cash, invested_amount, updated_at FROM capital_pools WHERE id=?",
        (pool.id,),
    ).fetchone()
    assert after == before
    ledger_count = con.execute(
        "SELECT COUNT(*) FROM capital_ledger WHERE event_type='reconcile'"
    ).fetchone()[0]
    assert ledger_count == 0


def test_reconcile_pool_cash_drift_corrects_and_logs(pool_db):
    """This is the exact production bug: available_cash stuck stale while
    real cash is materially higher. Reconciliation corrects it and records
    one ledger entry explaining the correction."""
    con, pool = pool_db

    changed = reconcile_pool(con, pool.id, real_available_cash=7500.0, real_invested_cost_basis=0.0)

    assert changed is True
    row = con.execute(
        "SELECT available_cash FROM capital_pools WHERE id=?", (pool.id,)
    ).fetchone()
    assert row[0] == pytest.approx(7500.0)
    ledger_row = con.execute(
        "SELECT amount, balance_after FROM capital_ledger WHERE event_type='reconcile'"
    ).fetchone()
    assert ledger_row is not None
    assert ledger_row[0] == pytest.approx(2500.0)   # the drift amount
    assert ledger_row[1] == pytest.approx(7500.0)


def test_reconcile_pool_invested_drift_corrects(pool_db):
    """invested_amount drift alone (cash already correct) is also
    detected and corrected independently of the cash figure."""
    con, pool = pool_db
    update_on_buy(con, pool.id, 1000.0)  # available=4000, invested=1000

    # Real cost basis of open positions is actually 1500 (e.g. a position
    # opened outside _pool_buy's own tracking) -- cash is already correct.
    changed = reconcile_pool(con, pool.id, real_available_cash=4000.0, real_invested_cost_basis=1500.0)

    assert changed is True
    row = con.execute(
        "SELECT available_cash, invested_amount FROM capital_pools WHERE id=?",
        (pool.id,),
    ).fetchone()
    assert row[0] == pytest.approx(4000.0)   # unchanged
    assert row[1] == pytest.approx(1500.0)   # corrected


def test_reconcile_pool_both_drift_single_ledger_entry(pool_db):
    """Both figures drifting at once still produces exactly one ledger
    entry, not two -- the correction is a single atomic true-up."""
    con, pool = pool_db

    changed = reconcile_pool(con, pool.id, real_available_cash=6000.0, real_invested_cost_basis=900.0)

    assert changed is True
    count = con.execute(
        "SELECT COUNT(*) FROM capital_ledger WHERE event_type='reconcile'"
    ).fetchone()[0]
    assert count == 1


def test_reconcile_pool_never_touches_allocated_or_reserve(pool_db):
    """ADR-075 Section 2: allocated_amount/reserve/realized_profit/
    profit_withdrawn are never written by reconciliation."""
    con, pool = pool_db
    set_reserve(con, pool.id, 250.0)
    update_on_buy(con, pool.id, 1000.0)
    update_on_sell(con, pool.id, cost_basis=1000.0, fill_value=1200.0)  # realized_profit=200
    before = con.execute(
        "SELECT allocated_amount, reserve, realized_profit, profit_withdrawn "
        "FROM capital_pools WHERE id=?", (pool.id,),
    ).fetchone()

    reconcile_pool(con, pool.id, real_available_cash=9999.0, real_invested_cost_basis=1234.0)

    after = con.execute(
        "SELECT allocated_amount, reserve, realized_profit, profit_withdrawn "
        "FROM capital_pools WHERE id=?", (pool.id,),
    ).fetchone()
    assert after == before


def test_reconcile_pool_missing_pool_id_returns_false(mem_db):
    """A nonexistent pool_id is a no-op, not an error."""
    assert reconcile_pool(mem_db, 999, real_available_cash=100.0, real_invested_cost_basis=0.0) is False
