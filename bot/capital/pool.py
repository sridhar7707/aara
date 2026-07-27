"""CapitalPool — first-class managed capital concept.

The bot sizes positions against `pool.tradeable_cash`, not the full Alpaca account,
so the AI can never exceed its managed allocation. The ledger is append-only;
pool balance fields are kept in sync but can always be recomputed from ledger events.

Tables are created lazily — no changes to _main_db.py required.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from loguru import logger

from database.user_settings import get_setting as _get_setting

_logger = logger

_DDL_POOLS = """
CREATE TABLE IF NOT EXISTS capital_pools (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL DEFAULT 'default',
    status            TEXT NOT NULL DEFAULT 'active',
    allocated_amount  REAL NOT NULL DEFAULT 0.0,
    available_cash    REAL NOT NULL DEFAULT 0.0,
    invested_amount   REAL NOT NULL DEFAULT 0.0,
    reserve           REAL NOT NULL DEFAULT 0.0,
    realized_profit   REAL NOT NULL DEFAULT 0.0,
    profit_withdrawn  REAL NOT NULL DEFAULT 0.0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

_DDL_LEDGER = """
CREATE TABLE IF NOT EXISTS capital_ledger (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_id       INTEGER NOT NULL,
    event_type    TEXT NOT NULL,
    amount        REAL NOT NULL,
    balance_after REAL NOT NULL,
    symbol        TEXT,
    notes         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

_IDX_LEDGER = (
    "CREATE INDEX IF NOT EXISTS idx_capital_ledger_pool "
    "ON capital_ledger (pool_id, created_at)"
)

_SELECT_POOL = (
    "SELECT id, name, allocated_amount, available_cash, invested_amount, "
    "reserve, realized_profit, profit_withdrawn FROM capital_pools "
    "WHERE status = 'active' ORDER BY id ASC LIMIT 1"
)


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(_DDL_POOLS)
    conn.execute(_DDL_LEDGER)
    conn.execute(_IDX_LEDGER)
    # Migration: add profit_withdrawn for pools created before Phase 3
    try:
        conn.execute(
            "ALTER TABLE capital_pools ADD COLUMN profit_withdrawn REAL NOT NULL DEFAULT 0.0"
        )
    except sqlite3.OperationalError:
        pass  # column already exists


@dataclass
class CapitalPool:
    id: int
    name: str
    allocated_amount: float
    available_cash: float
    invested_amount: float
    reserve: float
    realized_profit: float
    profit_withdrawn: float = 0.0

    @property
    def withdrawable_profit(self) -> float:
        """Profit that has been earned but not yet withdrawn."""
        return max(0.0, self.realized_profit - self.profit_withdrawn)

    @property
    def tradeable_cash(self) -> float:
        """Cash available for new positions (available minus reserve)."""
        return max(0.0, self.available_cash - self.reserve)

    @property
    def total_value(self) -> float:
        """Available cash + current open-position cost basis."""
        return self.available_cash + self.invested_amount


def _row_to_pool(row: tuple) -> CapitalPool:
    return CapitalPool(
        id=row[0], name=row[1], allocated_amount=row[2], available_cash=row[3],
        invested_amount=row[4], reserve=row[5], realized_profit=row[6],
        profit_withdrawn=row[7] if len(row) > 7 else 0.0,
    )


def load_active_pool(
    conn: sqlite3.Connection, initial_amount: float = 1000.0
) -> CapitalPool:
    """Load the active pool, creating a default one if none exists."""
    _ensure_tables(conn)
    row = conn.execute(_SELECT_POOL).fetchone()
    if not row:
        cur = conn.execute(
            "INSERT INTO capital_pools "
            "(name, status, allocated_amount, available_cash) VALUES (?, 'active', ?, ?)",
            ("default", initial_amount, initial_amount),
        )
        append_ledger(conn, cur.lastrowid, "deposit", initial_amount, initial_amount,
                      notes="Initial allocation")
        conn.commit()
        row = conn.execute(_SELECT_POOL).fetchone()
    return _row_to_pool(row)


def update_on_buy(
    conn: sqlite3.Connection, pool_id: int, notional: float,
    symbol: str | None = None,
) -> None:
    """Move `notional` from available_cash to invested_amount on a BUY fill (atomic)."""
    in_tx = conn.in_transaction
    if not in_tx:
        conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE capital_pools SET "
            "available_cash  = available_cash  - ?, "
            "invested_amount = invested_amount + ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (notional, notional, pool_id),
        )
        row = conn.execute(
            "SELECT available_cash FROM capital_pools WHERE id = ?", (pool_id,)
        ).fetchone()
        append_ledger(conn, pool_id, "buy", -notional, row[0] if row else 0.0, symbol=symbol)
        if not in_tx:
            conn.commit()
    except Exception:
        if not in_tx:
            conn.rollback()
        raise


def update_on_sell(
    conn: sqlite3.Connection, pool_id: int, cost_basis: float, fill_value: float,
    symbol: str | None = None,
) -> None:
    """Return fill proceeds to available_cash; book realized P&L (atomic)."""
    pnl = fill_value - cost_basis
    in_tx = conn.in_transaction
    if not in_tx:
        conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE capital_pools SET "
            "available_cash  = available_cash  + ?, "
            "invested_amount = MAX(0.0, invested_amount - ?), "
            "realized_profit = realized_profit + ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (fill_value, cost_basis, pnl, pool_id),
        )
        row = conn.execute(
            "SELECT available_cash FROM capital_pools WHERE id = ?", (pool_id,)
        ).fetchone()
        append_ledger(conn, pool_id, "sell", fill_value, row[0] if row else 0.0, symbol=symbol)
        if not in_tx:
            conn.commit()
    except Exception:
        if not in_tx:
            conn.rollback()
        raise


def deposit(
    conn: sqlite3.Connection, pool_id: int, amount: float,
    notes: str | None = None,
) -> None:
    """Add funds to the pool and record a ledger deposit event (atomic)."""
    in_tx = conn.in_transaction
    if not in_tx:
        conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE capital_pools SET "
            "available_cash   = available_cash   + ?, "
            "allocated_amount = allocated_amount + ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (amount, amount, pool_id),
        )
        row = conn.execute(
            "SELECT available_cash FROM capital_pools WHERE id = ?", (pool_id,)
        ).fetchone()
        append_ledger(conn, pool_id, "deposit", amount, row[0] if row else 0.0, notes=notes)
        if not in_tx:
            conn.commit()
    except Exception:
        if not in_tx:
            conn.rollback()
        raise


def withdraw(
    conn: sqlite3.Connection, pool_id: int, amount: float,
    notes: str | None = None,
) -> None:
    """Remove funds from the pool (atomic).

    Attributes the withdrawal against realized profit first so that
    `withdrawable_profit` stays accurate after the user takes money out.
    """
    in_tx = conn.in_transaction
    if not in_tx:
        conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT available_cash, realized_profit, profit_withdrawn "
            "FROM capital_pools WHERE id = ?",
            (pool_id,),
        ).fetchone()
        if not row:
            if not in_tx:
                conn.rollback()
            return
        avail, realized, already_withdrawn = float(row[0]), float(row[1]), float(row[2])
        amount = min(amount, avail)  # can't withdraw more than is there
        profit_remaining = max(0.0, realized - already_withdrawn)
        profit_part = min(amount, profit_remaining)
        conn.execute(
            "UPDATE capital_pools SET "
            "available_cash   = MAX(0.0, available_cash   - ?), "
            "allocated_amount = MAX(0.0, allocated_amount - ?), "
            "profit_withdrawn = profit_withdrawn + ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (amount, amount, profit_part, pool_id),
        )
        row2 = conn.execute(
            "SELECT available_cash FROM capital_pools WHERE id = ?", (pool_id,)
        ).fetchone()
        append_ledger(conn, pool_id, "withdrawal", -amount, row2[0] if row2 else 0.0, notes=notes)
        if not in_tx:
            conn.commit()
    except Exception:
        if not in_tx:
            conn.rollback()
        raise


def set_reserve(conn: sqlite3.Connection, pool_id: int, reserve: float) -> None:
    """Update the cash reserve floor for the pool."""
    conn.execute(
        "UPDATE capital_pools SET reserve = ?, updated_at = datetime('now') WHERE id = ?",
        (reserve, pool_id),
    )
    conn.commit()


def append_ledger(
    conn: sqlite3.Connection,
    pool_id: int,
    event_type: str,
    amount: float,
    balance_after: float,
    symbol: str | None = None,
    notes: str | None = None,
) -> None:
    """Append an immutable event to the capital ledger."""
    conn.execute(
        "INSERT INTO capital_ledger "
        "(pool_id, event_type, amount, balance_after, symbol, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (pool_id, event_type, amount, balance_after, symbol, notes),
    )


def compute_tradeable_capital(con: sqlite3.Connection, portfolio_value: float) -> float:
    """Capital available for new positions. When reinvest_profits_only=true:
    tradeable = max(0, portfolio_value - initial_deposit). Computed once per
    cycle by bot/main.py and passed into _handle_entry, avoiding per-symbol
    DB reads. Extracted from bot/_main_cycle.py to keep that file under the
    project's 500-line limit — thematically a capital-allocation concern,
    not entry-gate logic."""
    if _get_setting("reinvest_profits_only", "false") != "true":
        return portfolio_value

    dep_str = _get_setting("initial_deposit", None)
    initial: float | None = None
    if dep_str:
        try:
            initial = float(dep_str)
        except Exception as exc:
            _logger.debug(f"compute_tradeable_capital: initial_deposit setting parse: {exc}")

    if initial is None:
        try:
            row = con.execute(
                "SELECT portfolio_value FROM portfolio_snapshots "
                "WHERE portfolio_value > 0 ORDER BY timestamp ASC LIMIT 1"
            ).fetchone()
            if row:
                initial = float(row[0])
        except Exception as exc:
            _logger.debug(f"compute_tradeable_capital: portfolio_snapshots read: {exc}")

    if initial is None:
        try:
            row = con.execute(
                "SELECT portfolio_value FROM trades "
                "WHERE portfolio_value > 0 ORDER BY id ASC LIMIT 1"
            ).fetchone()
            if row:
                initial = float(row[0])
        except Exception as exc:
            _logger.debug(f"compute_tradeable_capital: trades read: {exc}")

    if initial is None:
        _logger.warning(
            "reinvest_profits_only=true but initial deposit unknown "
            "(no initial_deposit setting and no portfolio history) — trading full portfolio"
        )
        return portfolio_value

    tradeable = max(0.0, portfolio_value - initial)
    _logger.debug(
        f"reinvest-profits-only: tradeable=${tradeable:.0f} "
        f"(portfolio=${portfolio_value:.0f}, deposit=${initial:.0f})"
    )
    return tradeable
