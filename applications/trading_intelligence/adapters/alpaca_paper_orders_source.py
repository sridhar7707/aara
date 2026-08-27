"""Read-only adapter over Alpaca's Paper Trading recent-order history,
backing Portfolio Intelligence's "ALPACA PAPER -- RECENT ORDERS" section.

Boundary decision (recorded, same dependency class as
adapters/alpaca_paper_source.py and adapters/alpaca_news_source.py -- an
external broker API, not a local trades.db table -- and NOT authorized by
silent extension of any prior precedent): READ-ONLY observation only.
get_recent_orders() issues GET /orders calls (via alpaca-py
TradingClient.get_orders); this module never calls submit_order/
cancel_order/replace_order/close_position/close_all_positions or any other
order-placing/cancelling/modifying method, never calls
get_account_activities() or get_portfolio_history(), never opens a
database connection, and never writes anything anywhere (see the
regression-lock tests in tests/test_alpaca_paper_orders_source.py).

This module intentionally does NOT import bot.execution.alpaca_client
(bot/ is ADR-002-protected, and that module also implements order
submission) -- it instantiates its own independent alpaca-py
TradingClient, the same "duplicate the primitive, never import the
protected package" convention adapters/alpaca_paper_source.py already
uses. It also does not import adapters/alpaca_paper_source.py itself:
the recent-orders channel's availability is deliberately independent of
the account/positions channel's. Credentials come from the top-level
`config` module (config.py, NOT under bot/ and therefore not
ADR-002-protected).

Paper-only, by construction, with the same two independent layers as
adapters/alpaca_paper_source.py:
  1. The TradingClient is constructed with paper=True unconditionally --
     hard-coded, never inferred from config. This adapter can never
     physically reach a live-trading endpoint.
  2. ALPACA_BASE_URL is additionally checked for the literal substring
     "paper" before any client is created; if absent, the environment is
     not confirmed paper and get_recent_orders() returns None (the safe
     unavailable path) rather than proceeding on an unverified
     assumption.

Never fabricates. On missing config.py, missing credentials, an SDK
import failure, a network/API error, or a malformed provider row,
get_recent_orders() returns None and the caller falls back to the
existing honest unavailable message. A successful read that matched no
orders returns an empty AlpacaOrdersSnapshot -- a real "nothing to
report" result, distinct from None.

Two GET calls, merged and deduplicated by order id:
  1. OPEN orders -- no time filter, defensive per-call cap.
  2. CLOSED orders -- bounded to the last 14 days, defensive per-call cap.
Result is ordered deterministically newest-first by (submitted_at,
order_id). If either call returns as many rows as the cap, the snapshot's
`truncated` flag is set so the UI can say "showing the N most recent"
explicitly. Working/pending orders are included and flagged
(AlpacaOrder.is_working); the broker's own `status`/`side` strings are
preserved verbatim. client_order_id, order_class, legs, and any strategy
metadata are never read into the projection; order_id is retained only
for dedupe/stable ordering, never surfaced as a decision identifier.

Production note: identical limitation to the other two Alpaca adapters --
the deployed Trading Intelligence HF Space has no Alpaca credentials or
outbound network configured today, so this returns None there and the
section stays unavailable. Locally, with ALPACA_KEY/ALPACA_SECRET present
via .env, it reads real Alpaca paper orders immediately.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    from config import ALPACA_BASE_URL, ALPACA_KEY, ALPACA_SECRET
except ImportError:
    # config.py (top-level, not part of this product) is not staged in the
    # deployed Trading Intelligence HF Space -- see
    # adapters/alpaca_paper_source.py's own note on the same fallback.
    # Falling back to empty credentials keeps the Space from crashing at
    # import time; get_recent_orders() then returns None (the expected,
    # documented unavailable path) rather than raising.
    ALPACA_KEY = ""
    ALPACA_SECRET = ""
    ALPACA_BASE_URL = ""

from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    AlpacaOrder,
    AlpacaOrdersSnapshot,
)

_CLOSED_WINDOW_DAYS = 14
_PER_CALL_CAP = 50

# Alpaca order statuses that mean the order is still live/working at the
# broker rather than in a terminal state. Used only to tag rows returned by
# the CLOSED query; every row the OPEN query returns is treated as working
# regardless of this set (see get_recent_orders). Verbatim status strings
# are still preserved on the projection unchanged either way.
_WORKING_STATUSES = frozenset({
    "new",
    "accepted",
    "pending_new",
    "accepted_for_bidding",
    "pending_cancel",
    "pending_replace",
    "calculated",
    "held",
    "partially_filled",
})


def _is_paper_environment(base_url: str) -> bool:
    return "paper" in (base_url or "").lower()


def _coerce_optional_str(value) -> str:
    """Provider-value passthrough: absent -> "" (legitimate for a market
    order's limit_price, an unfilled order's filled_quantity, a notional
    order's quantity), otherwise the value's own string form unchanged."""
    if value is None:
        return ""
    return str(value)


class AlpacaPaperOrdersSource:
    def __init__(
        self,
        api_key: str = ALPACA_KEY,
        api_secret: str = ALPACA_SECRET,
        base_url: str = ALPACA_BASE_URL,
        closed_window_days: int = _CLOSED_WINDOW_DAYS,
        per_call_cap: int = _PER_CALL_CAP,
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url
        self._closed_window_days = closed_window_days
        self._per_call_cap = per_call_cap

    def _build_client(self):
        """Returns a paper-only TradingClient, or None if credentials are
        missing or the configured environment isn't confirmed paper --
        never raises, never falls back to live."""
        if not self._api_key or not self._api_secret:
            return None
        if not _is_paper_environment(self._base_url):
            return None
        try:
            from alpaca.trading.client import TradingClient

            return TradingClient(self._api_key, self._api_secret, paper=True)
        except Exception:
            return None

    def get_recent_orders(self) -> Optional[AlpacaOrdersSnapshot]:
        """Returns Alpaca's own broker-side recent Paper orders (open +
        last-14-days closed), merged, deduped by order id, newest-first.
        Returns None only when credentials/environment aren't confirmed
        paper, either network call fails, or any row is malformed --
        callers must treat None as "fall back to the existing unavailable
        section," never as an error, and must never use a partial result.
        An empty snapshot is a real "connected, no recent orders" state,
        not None."""
        client = self._build_client()
        if client is None:
            return None

        try:
            from alpaca.common.enums import Sort
            from alpaca.trading.enums import QueryOrderStatus
            from alpaca.trading.requests import GetOrdersRequest

            open_request = GetOrdersRequest(
                status=QueryOrderStatus.OPEN,
                limit=self._per_call_cap,
                direction=Sort.DESC,
                nested=False,
            )
            closed_request = GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                after=datetime.now(timezone.utc)
                - timedelta(days=self._closed_window_days),
                limit=self._per_call_cap,
                direction=Sort.DESC,
                nested=False,
            )
            open_raw = list(client.get_orders(filter=open_request))
            closed_raw = list(client.get_orders(filter=closed_request))
        except Exception:
            return None

        try:
            merged = {}
            for raw in open_raw:
                order = self._parse_order(raw, forced_working=True)
                merged[order.order_id] = order
            for raw in closed_raw:
                order = self._parse_order(raw, forced_working=False)
                if order.order_id in merged:
                    continue
                merged[order.order_id] = order
        except Exception:
            return None

        ordered = tuple(
            sorted(
                merged.values(),
                key=lambda o: (o.submitted_at, o.order_id),
                reverse=True,
            )
        )
        truncated = (
            len(open_raw) >= self._per_call_cap
            or len(closed_raw) >= self._per_call_cap
        )
        return AlpacaOrdersSnapshot(orders=ordered, truncated=truncated)

    @staticmethod
    def _parse_order(raw, forced_working: bool) -> AlpacaOrder:
        """Projects one provider order row onto AlpacaOrder. Raises on any
        malformed/absent identity, sort, or broker-verbatim field -- the
        caller turns any exception here into a whole-result None, never a
        partial list."""
        order_id = str(raw.id)
        symbol = raw.symbol
        if not order_id or not symbol:
            raise ValueError("order row missing id/symbol")

        submitted_at = raw.submitted_at
        if not isinstance(submitted_at, datetime):
            raise ValueError("order row missing submitted_at")

        filled_at = raw.filled_at
        if filled_at is not None and not isinstance(filled_at, datetime):
            raise ValueError("order row has a malformed filled_at")

        side_raw = raw.side
        side = side_raw.value if hasattr(side_raw, "value") else str(side_raw)
        status_raw = raw.status
        status = status_raw.value if hasattr(status_raw, "value") else str(status_raw)
        if not side or not status:
            raise ValueError("order row missing side/status")

        type_raw = getattr(raw, "order_type", None)
        if type_raw is None:
            type_raw = getattr(raw, "type", None)
        order_type = type_raw.value if hasattr(type_raw, "value") else str(type_raw or "")

        return AlpacaOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=_coerce_optional_str(raw.qty),
            filled_quantity=_coerce_optional_str(raw.filled_qty),
            status=status,
            submitted_at=submitted_at,
            filled_at=filled_at,
            limit_price=_coerce_optional_str(raw.limit_price),
            is_working=forced_working or status in _WORKING_STATUSES,
        )
