from __future__ import annotations
import re
import time
from typing import Any, Callable, TypeVar

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus, OrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestBarRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

import pandas as pd
from loguru import logger
from config import ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL
from bot.core.api_guard import call_with_retry

_T = TypeVar("_T")

MIN_NOTIONAL = 1.0   # Alpaca minimum notional for fractional orders
LIMIT_BUF    = 0.001  # 0.1% aggressive-limit buffer — fills in normal liquid conditions

# Real Alpaca API spelling is "canceled" (one L) — OrderStatus.CANCELED.value below,
# not the "cancelled" this client checked for pre-migration (see migration notes).
_ENDED_STATUSES = {
    OrderStatus.CANCELED.value, OrderStatus.EXPIRED.value,
    OrderStatus.REJECTED.value, OrderStatus.DONE_FOR_DAY.value,
}

_TIMEFRAME_UNITS = {
    "min": TimeFrameUnit.Minute, "minute": TimeFrameUnit.Minute,
    "hour": TimeFrameUnit.Hour, "day": TimeFrameUnit.Day,
    "week": TimeFrameUnit.Week, "month": TimeFrameUnit.Month,
}


def _parse_timeframe(spec: str) -> TimeFrame:
    """Parse strings like '5Min', '1Hour', '1Day' into a TimeFrame."""
    m = re.match(r"(\d+)([A-Za-z]+)", spec)
    if not m:
        raise ValueError(f"Unrecognized timeframe: {spec!r}")
    amount, unit_str = int(m.group(1)), m.group(2).lower()
    unit = _TIMEFRAME_UNITS.get(unit_str)
    if unit is None:
        raise ValueError(f"Unrecognized timeframe unit: {unit_str!r}")
    return TimeFrame(amount, unit)


class AlpacaClient:
    def __init__(self):
        if not ALPACA_KEY or not ALPACA_SECRET:
            logger.error(
                "ALPACA_KEY/ALPACA_SECRET is EMPTY — Alpaca calls will fail and the account "
                "value will read $0.00. Set these as environment/Space secrets."
            )
        _paper = "paper" in ALPACA_BASE_URL
        self.api = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=_paper)
        self._data = StockHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET)
        # Inject a 30s timeout so a hung Alpaca connection fails fast instead
        # of waiting the OS-default ~2 min, which wastes an entire 5-min cycle.
        for _client in (self.api, self._data):
            try:
                _orig = _client._session.send
                def _send_timeout(*a, _orig=_orig, **kw):
                    kw.setdefault("timeout", 30)
                    return _orig(*a, **kw)
                _client._session.send = _send_timeout
            except AttributeError:
                pass
        logger.info(
            f"Alpaca connected — mode: {'paper' if _paper else 'live'}, "
            f"url={ALPACA_BASE_URL}, key=...{ALPACA_KEY[-4:] if ALPACA_KEY else 'MISSING'}"
        )

    def _r(self, fn: Callable[..., _T], *args: Any,
           _label: str = "", _rate_limit_only: bool = False, **kwargs: Any) -> _T:
        """Retry wrapper for all Alpaca REST calls — exponential back-off on 429/503."""
        return call_with_retry(
            fn, *args,
            _label=f"Alpaca/{_label or getattr(fn, '__name__', '')}",
            _max_retries=3,
            _base_delay=1.0,
            _rate_limit_only=_rate_limit_only,
            **kwargs,
        )

    def get_account(self) -> Any:
        return self._r(self.api.get_account, _label="get_account")

    def get_account_summary(self) -> tuple[float, float]:
        """Single API call returning (portfolio_value, available_cash)."""
        acct = self.get_account()
        return float(acct.portfolio_value), float(acct.cash)

    def get_portfolio_value(self) -> float:
        return float(self.get_account().portfolio_value)

    def get_cash(self) -> float:
        return float(self.get_account().cash)

    def get_positions(self) -> dict:
        positions = self._r(self.api.get_all_positions, _label="get_all_positions")
        return {p.symbol: p for p in positions}

    def get_latest_price(self, symbol: str) -> float:
        req = StockLatestBarRequest(symbol_or_symbols=symbol)
        bars = self._r(self._data.get_stock_latest_bar, req, _label=f"get_latest_bar/{symbol}")
        bar = bars.get(symbol) if bars else None
        if bar is None:
            logger.debug(f"No bar data returned for {symbol}")
            raise ValueError("Price data unavailable")
        return bar.close

    def get_bars(self, symbol: str, timeframe: str = "5Min", limit: int = 100) -> pd.DataFrame:
        req = StockBarsRequest(
            symbol_or_symbols=symbol, timeframe=_parse_timeframe(timeframe), limit=limit,
        )
        bars = self._r(self._data.get_stock_bars, req, _label=f"get_bars/{symbol}")
        df = bars.df
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level="symbol")
        df.index = pd.to_datetime(df.index, utc=True)
        return df

    def buy(self, symbol: str, notional: float, limit_price: float | None = None) -> dict | None:
        """
        Submit a buy order.
        If limit_price is given, uses a limit order at (limit_price × 1.001) — aggressive
        enough to fill on liquid names while avoiding the full bid-ask cost of a market order.
        Falls back to a market order when limit_price is None.
        """
        if notional < MIN_NOTIONAL:
            logger.warning(f"BUY skipped {symbol} — notional ${notional:.2f} below ${MIN_NOTIONAL} minimum")
            return None
        try:
            if limit_price is not None and limit_price > 0:
                effective_limit = round(limit_price * (1 + LIMIT_BUF), 2)
                qty = round(notional / effective_limit, 6)
                order_data = LimitOrderRequest(
                    symbol=symbol, qty=qty, side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY, limit_price=effective_limit,
                )
                order = self._r(
                    self.api.submit_order, order_data=order_data,
                    _label=f"buy_limit/{symbol}", _rate_limit_only=True,
                )
                logger.info(f"BUY {symbol} qty={qty:.4f} limit=${effective_limit:.2f} order_id={order.id}")
            else:
                order_data = MarketOrderRequest(
                    symbol=symbol, notional=round(notional, 2),
                    side=OrderSide.BUY, time_in_force=TimeInForce.DAY,
                )
                order = self._r(
                    self.api.submit_order, order_data=order_data,
                    _label=f"buy_market/{symbol}", _rate_limit_only=True,
                )
                logger.info(f"BUY {symbol} notional=${notional:.2f} (market) order_id={order.id}")
            return {"order_id": order.id, "symbol": symbol, "side": "buy", "notional": notional}
        except Exception as e:
            logger.error(f"BUY failed {symbol}: {e}")
            return None

    def sell(self, symbol: str, qty: float | None = None,
             limit_price: float | None = None) -> dict | None:
        """
        Submit a sell order.
        qty: pass the float quantity to avoid an extra get_positions() API call.
             If omitted, fetches positions internally (legacy path).
        limit_price: if given, uses a limit order at (limit_price × 0.999).
        """
        try:
            if qty is None:
                positions = self.get_positions()
                if symbol not in positions:
                    logger.warning(f"SELL skipped — no position in {symbol}")
                    return None
                qty = float(positions[symbol].qty)
            else:
                qty = float(qty)

            if qty <= 0:
                logger.warning(f"SELL skipped {symbol} — qty={qty}")
                return None

            if limit_price is not None and limit_price > 0:
                effective_limit = round(limit_price * (1 - LIMIT_BUF), 2)
                order_data = LimitOrderRequest(
                    symbol=symbol, qty=qty, side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY, limit_price=effective_limit,
                )
                order = self._r(
                    self.api.submit_order, order_data=order_data,
                    _label=f"sell_limit/{symbol}", _rate_limit_only=True,
                )
                logger.info(f"SELL {symbol} qty={qty:.4f} limit=${effective_limit:.2f} order_id={order.id}")
            else:
                order_data = MarketOrderRequest(
                    symbol=symbol, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.DAY,
                )
                order = self._r(
                    self.api.submit_order, order_data=order_data,
                    _label=f"sell_market/{symbol}", _rate_limit_only=True,
                )
                logger.info(f"SELL {symbol} qty={qty:.4f} (market) order_id={order.id}")
            return {"order_id": order.id, "symbol": symbol, "side": "sell", "qty": qty}
        except Exception as e:
            logger.error(f"SELL failed {symbol}: {e}")
            return None

    def wait_for_fill(self, order_id: str, timeout_secs: int = 15) -> float:
        """Poll until filled or timeout; returns actual filled qty (may be partial).

        Returns 0.0 when nothing was filled. On timeout: cancels the remaining
        unfilled portion and returns however many shares filled before the deadline.
        Callers must use the returned qty — not the original order qty — when
        deciding how many shares remain to sell/buy, because a partial fill leaves
        the difference in an indeterminate state until the next reconcile cycle.
        """
        deadline = time.monotonic() + timeout_secs
        while time.monotonic() < deadline:
            try:
                order = self.api.get_order_by_id(order_id)
                filled_qty = float(getattr(order, "filled_qty", 0) or 0)
                if order.status == OrderStatus.FILLED.value:
                    return filled_qty
                if order.status in _ENDED_STATUSES:
                    logger.warning(
                        f"Order {order_id} ended as {order.status} — filled_qty={filled_qty}"
                    )
                    return filled_qty
                # partially_filled: keep polling until deadline
            except Exception as e:
                logger.warning(f"Order status poll failed ({order_id}): {e}")
            time.sleep(2)
        # Timeout — read partial fill qty before cancelling remaining
        filled_qty = 0.0
        try:
            order = self.api.get_order_by_id(order_id)
            filled_qty = float(getattr(order, "filled_qty", 0) or 0)
        except Exception as e:
            logger.warning(f"Could not read order {order_id} before cancel: {e}")
        try:
            self.api.cancel_order_by_id(order_id)
            logger.warning(
                f"Order {order_id} timed out after {timeout_secs}s — cancelled "
                f"(filled_qty={filled_qty})"
            )
        except Exception as e:
            logger.warning(f"Could not cancel order {order_id}: {e}")
        return filled_qty

    def sell_market(self, symbol: str, qty: float) -> dict | None:
        """Market sell — used as stop-loss escalation when a limit sell times out."""
        try:
            order_data = MarketOrderRequest(
                symbol=symbol, qty=float(qty), side=OrderSide.SELL, time_in_force=TimeInForce.DAY,
            )
            order = self._r(
                self.api.submit_order, order_data=order_data,
                _label=f"sell_market_escalation/{symbol}", _rate_limit_only=True,
            )
            logger.warning(f"SELL MARKET {symbol} qty={qty:.4f} (stop escalation) order_id={order.id}")
            return {"order_id": order.id, "symbol": symbol, "side": "sell", "qty": qty}
        except Exception as e:
            logger.error(f"Market sell escalation failed {symbol}: {e}")
            return None

    def get_open_order_symbols(self) -> tuple[set[str], set[str]]:
        """Return (buy_symbols, sell_symbols) with pending open orders.
        One API call serves both the buy-duplicate guard and the sell-duplicate guard.
        Separating sides prevents double-selling — submitting a second sell on a symbol
        that already has a pending sell order could create an unintended short position.
        """
        try:
            req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
            orders = self._r(self.api.get_orders, filter=req, _label="list_open_orders")
            buy_syms  = {o.symbol for o in orders if o.side == OrderSide.BUY}
            sell_syms = {o.symbol for o in orders if o.side == OrderSide.SELL}
            return buy_syms, sell_syms
        except Exception as e:
            logger.warning(f"Could not fetch open orders: {e}")
            return set(), set()

    def get_fill_price(self, order_id: str) -> float | None:
        """Return the actual average fill price of a completed order.
        Records real execution price (not limit estimate) for accurate P&L and slippage tracking.
        Returns None if the order hasn't filled or the field is absent — caller falls back to estimate.
        """
        try:
            order = self._r(self.api.get_order_by_id, order_id, _label="get_fill_price")
            filled_avg = getattr(order, "filled_avg_price", None)
            if filled_avg and float(filled_avg) > 0:
                return float(filled_avg)
        except Exception as e:
            logger.debug(f"Could not get fill price for {order_id}: {e}")
        return None

    def get_position_value(self, symbol: str, positions: dict | None = None) -> float:
        pos = positions if positions is not None else self.get_positions()
        if symbol not in pos:
            return 0.0
        return float(pos[symbol].market_value)

    def get_position_pnl_pct(self, symbol: str, positions: dict | None = None) -> float:
        pos = positions if positions is not None else self.get_positions()
        if symbol not in pos:
            return 0.0
        return float(pos[symbol].unrealized_plpc)
