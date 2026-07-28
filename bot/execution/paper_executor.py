"""Phase 1A Sprint 5 -- a genuinely separate paper-trading fill engine.

Safety property: this file's own source never imports or references
alpaca.trading.client.TradingClient or .submit_order() -- there is no
seam here through which a real order could ever be placed, regardless of
what EXECUTION_BACKEND or ALPACA_BASE_URL say. (Note: importing anything
from the alpaca-py package transitively loads alpaca.trading into
sys.modules regardless -- that's a packaging quirk of the SDK itself, not
something any amount of care in this file can avoid. The property that
actually matters, and that IS achievable, is that nothing in this file's
own code ever calls it.)

self.api is None (see Executor protocol) -- no TradingClient handle
exists here to misuse. Market data (get_bars/get_latest_price) still
uses real prices via alpaca.data (read-only), imported only through
bot.execution.timeframe, never bot.execution.alpaca_client -- importing
from that module would pull in its top-level alpaca.trading imports too.

Owns its own SQLite file (data/paper_portfolio.db), separate from both
bot/trades.db and data/trust_ledger.db.
"""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestBarRequest, StockBarsRequest
from loguru import logger

from config import ALPACA_KEY, ALPACA_SECRET
from bot.execution.timeframe import parse_timeframe

DEFAULT_PAPER_DB_PATH = "data/paper_portfolio.db"
STARTING_BALANCE = 1000.0

# Matches cost_model_v1, bootstrapped in Sprint 1 (scripts/phase1a_bootstrap_ledger.py).
# Kept as local constants rather than reading the ledger DB -- PaperExecutor's
# no-arg construction matches AlpacaClient's and shouldn't need ledger
# connectivity just to exist.
SPREAD_ASSUMPTION = 0.001
SLIPPAGE_ASSUMPTION = 0.001


@dataclass
class _PaperPosition:
    qty: float
    avg_entry_price: float
    market_value: float
    unrealized_plpc: float


@dataclass
class _PaperAccount:
    portfolio_value: float
    cash: float
    equity: float
    status: str = "ACTIVE"
    trading_blocked: bool = False
    account_blocked: bool = False
    pattern_day_trader: bool = False


class PaperExecutor:
    def __init__(self, db_path: str = DEFAULT_PAPER_DB_PATH):
        self.api = None
        self._data = StockHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET)
        self._conn = sqlite3.connect(db_path)
        self._init_schema()
        logger.info(f"PaperExecutor active — db={db_path}, starting_balance=${STARTING_BALANCE:.2f}")

    def _init_schema(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS paper_account "
            "(id INTEGER PRIMARY KEY CHECK (id=1), cash REAL NOT NULL, starting_balance REAL NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS paper_positions "
            "(symbol TEXT PRIMARY KEY, qty REAL NOT NULL, avg_entry_price REAL NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS paper_fills "
            "(order_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, side TEXT NOT NULL, "
            "qty REAL NOT NULL, price REAL NOT NULL, notional REAL NOT NULL, filled_at TEXT NOT NULL)"
        )
        if self._conn.execute("SELECT 1 FROM paper_account WHERE id=1").fetchone() is None:
            self._conn.execute(
                "INSERT INTO paper_account (id, cash, starting_balance) VALUES (1, ?, ?)",
                (STARTING_BALANCE, STARTING_BALANCE),
            )
        self._conn.commit()

    # ── market data: real, read-only (alpaca.data, never alpaca.trading) ──

    def get_latest_price(self, symbol: str) -> float:
        req = StockLatestBarRequest(symbol_or_symbols=symbol)
        bars = self._data.get_stock_latest_bar(req)
        bar = bars.get(symbol) if bars else None
        if bar is None:
            raise ValueError("Price data unavailable")
        return bar.close

    def get_bars(self, symbol: str, timeframe: str = "5Min", limit: int = 100) -> pd.DataFrame:
        req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=parse_timeframe(timeframe), limit=limit)
        bars = self._data.get_stock_bars(req)
        df = bars.df
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level="symbol")
        df.index = pd.to_datetime(df.index, utc=True)
        return df

    # ── account / positions: simulated, from paper_portfolio.db ──

    def _cash(self) -> float:
        return float(self._conn.execute("SELECT cash FROM paper_account WHERE id=1").fetchone()[0])

    def get_positions(self) -> dict:
        rows = self._conn.execute("SELECT symbol, qty, avg_entry_price FROM paper_positions").fetchall()
        result = {}
        for symbol, qty, avg_entry_price in rows:
            try:
                current_price = self.get_latest_price(symbol)
            except ValueError:
                current_price = avg_entry_price  # price feed unavailable -- last-resort fallback
            market_value = qty * current_price
            unrealized_plpc = (current_price - avg_entry_price) / avg_entry_price if avg_entry_price > 0 else 0.0
            result[symbol] = _PaperPosition(
                qty=qty, avg_entry_price=avg_entry_price,
                market_value=market_value, unrealized_plpc=unrealized_plpc,
            )
        return result

    def get_account(self) -> _PaperAccount:
        cash = self._cash()
        positions_value = sum(p.market_value for p in self.get_positions().values())
        portfolio_value = cash + positions_value
        return _PaperAccount(portfolio_value=portfolio_value, cash=cash, equity=portfolio_value)

    def get_account_summary(self) -> tuple[float, float]:
        acct = self.get_account()
        return acct.portfolio_value, acct.cash

    def get_portfolio_value(self) -> float:
        return self.get_account().portfolio_value

    def get_cash(self) -> float:
        return self._cash()

    def get_position_value(self, symbol: str, positions: dict | None = None) -> float:
        pos = positions if positions is not None else self.get_positions()
        return pos[symbol].market_value if symbol in pos else 0.0

    def get_position_pnl_pct(self, symbol: str, positions: dict | None = None) -> float:
        pos = positions if positions is not None else self.get_positions()
        return pos[symbol].unrealized_plpc if symbol in pos else 0.0

    # ── orders: simulated, immediate full fills, never touches alpaca.trading ──

    def buy(self, symbol: str, notional: float, limit_price: float | None = None) -> dict | None:
        if notional <= 0:
            return None
        fill_price = limit_price if limit_price and limit_price > 0 else self.get_latest_price(symbol)
        fill_price *= (1 + SPREAD_ASSUMPTION / 2 + SLIPPAGE_ASSUMPTION)  # buyer pays a bit more
        cash = self._cash()
        if notional > cash:
            logger.warning(f"PAPER BUY skipped {symbol} — notional ${notional:.2f} exceeds cash ${cash:.2f}")
            return None
        qty = notional / fill_price
        order_id = f"paper-{uuid.uuid4().hex[:12]}"

        existing = self._conn.execute(
            "SELECT qty, avg_entry_price FROM paper_positions WHERE symbol=?", (symbol,)
        ).fetchone()
        if existing:
            old_qty, old_avg = existing
            new_qty = old_qty + qty
            new_avg = (old_qty * old_avg + qty * fill_price) / new_qty
        else:
            new_qty, new_avg = qty, fill_price
        self._conn.execute(
            "INSERT INTO paper_positions (symbol, qty, avg_entry_price) VALUES (?,?,?) "
            "ON CONFLICT(symbol) DO UPDATE SET qty=excluded.qty, avg_entry_price=excluded.avg_entry_price",
            (symbol, new_qty, new_avg),
        )
        self._conn.execute("UPDATE paper_account SET cash = cash - ? WHERE id=1", (notional,))
        self._record_fill(order_id, symbol, "buy", qty, fill_price, notional)
        self._conn.commit()
        logger.info(f"PAPER BUY {symbol} qty={qty:.4f} @ ${fill_price:.2f} (order {order_id})")
        return {"order_id": order_id, "symbol": symbol, "side": "buy", "notional": notional}

    def sell(self, symbol: str, qty: float | None = None, limit_price: float | None = None) -> dict | None:
        row = self._conn.execute(
            "SELECT qty, avg_entry_price FROM paper_positions WHERE symbol=?", (symbol,)
        ).fetchone()
        if row is None:
            logger.warning(f"PAPER SELL skipped — no position in {symbol}")
            return None
        held_qty, _avg_entry = row
        qty = float(qty) if qty is not None else held_qty
        if qty <= 0 or qty > held_qty + 1e-9:
            logger.warning(f"PAPER SELL skipped {symbol} — qty={qty} (held={held_qty})")
            return None

        fill_price = limit_price if limit_price and limit_price > 0 else self.get_latest_price(symbol)
        fill_price *= (1 - SPREAD_ASSUMPTION / 2 - SLIPPAGE_ASSUMPTION)  # seller receives a bit less
        notional = qty * fill_price
        order_id = f"paper-{uuid.uuid4().hex[:12]}"

        remaining = held_qty - qty
        if remaining <= 1e-9:
            self._conn.execute("DELETE FROM paper_positions WHERE symbol=?", (symbol,))
        else:
            self._conn.execute("UPDATE paper_positions SET qty=? WHERE symbol=?", (remaining, symbol))
        self._conn.execute("UPDATE paper_account SET cash = cash + ? WHERE id=1", (notional,))
        self._record_fill(order_id, symbol, "sell", qty, fill_price, notional)
        self._conn.commit()
        logger.info(f"PAPER SELL {symbol} qty={qty:.4f} @ ${fill_price:.2f} (order {order_id})")
        return {"order_id": order_id, "symbol": symbol, "side": "sell", "qty": qty}

    def sell_market(self, symbol: str, qty: float) -> dict | None:
        return self.sell(symbol, qty=qty, limit_price=None)

    def _record_fill(self, order_id: str, symbol: str, side: str, qty: float, price: float, notional: float) -> None:
        self._conn.execute(
            "INSERT INTO paper_fills (order_id, symbol, side, qty, price, notional, filled_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (order_id, symbol, side, qty, price, notional, datetime.now(timezone.utc).isoformat()),
        )

    def wait_for_fill(self, order_id: str, timeout_secs: int = 15) -> float:
        """Paper fills are synchronous, set immediately in buy()/sell() --
        no polling needed, just look up what was already recorded."""
        row = self._conn.execute("SELECT qty FROM paper_fills WHERE order_id=?", (order_id,)).fetchone()
        return float(row[0]) if row else 0.0

    def get_fill_price(self, order_id: str) -> float | None:
        row = self._conn.execute("SELECT price FROM paper_fills WHERE order_id=?", (order_id,)).fetchone()
        return float(row[0]) if row else None

    def get_open_order_symbols(self) -> tuple[set[str], set[str]]:
        """Paper fills are always immediate and complete -- there is never
        an open/pending order to report."""
        return set(), set()
