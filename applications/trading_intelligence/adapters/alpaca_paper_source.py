"""Read-only adapter over Alpaca's Paper Trading account/positions,
backing Portfolio Intelligence's "Alpaca Paper Account" section.

Boundary decision (recorded, new dependency class -- explicitly NOT
authorized by silent extension of any prior precedent): this is the
first adapter in this product to reach an external broker API rather
than a local trades.db SQLite table. It is READ-ONLY observation only --
get_account() and get_all_positions() are GET calls with no side effects;
this module never calls submit_order/cancel_order/replace_order or any
other order-placing/cancelling method, and never will (see the
regression-lock test asserting this in tests/test_alpaca_paper_source.py).

This module intentionally does NOT import bot.execution.alpaca_client
(bot/ is ADR-002-protected, and that module also implements order
submission -- buy()/sell()/sell_market() -- which is out of scope and
must never be reachable from this read-only adapter). Instead it
instantiates its own, independent alpaca-py TradingClient directly, the
same "duplicate the primitive, never import the protected package"
convention already used by every SQLite-backed adapter in this product.
Credentials are read from the top-level `config` module (config.py,
NOT under bot/ and therefore not ADR-002-protected) -- the same
ALPACA_KEY/ALPACA_SECRET/ALPACA_BASE_URL bot/execution/alpaca_client.py
itself reads, but never imported from that protected module.

Paper-only, by construction, with two independent layers:
  1. The alpaca-py TradingClient is constructed with paper=True
     unconditionally -- hard-coded, never inferred from ALPACA_BASE_URL
     or any other config value. This adapter can never physically reach
     a live-trading endpoint, regardless of how config.py or its
     environment variables are set.
  2. ALPACA_BASE_URL is additionally checked for the literal substring
     "paper" before any call is attempted; if absent, the environment is
     not confirmed to be paper and both methods return None (the existing
     safe-unavailable path) rather than ever proceeding on an unverified
     assumption. This is a defensive, belt-and-suspenders check on top of
     (1), not a substitute for it.
Together these mean: this adapter cannot be misconfigured into reading
live data, and will not silently fall back from paper to live or from
live to paper -- an unconfirmed environment is simply unavailable.

Credentials are never logged: only a boolean "configured" state and,
where useful, the last 4 characters of the account number (already
public within the paper account's own dashboard, not a secret) are ever
surfaced -- the API key and secret themselves are never written to any
log, exception message, or return value.

Production note: identical class of limitation to every other adapter in
this product -- the deployed Trading Intelligence HF Space has no
credentials or outbound network configuration for Alpaca today. Locally,
where ALPACA_KEY/ALPACA_SECRET are present via .env, this adapter reads
real data immediately. In production, until credentials and network
access are separately provisioned, both methods will consistently return
None, and callers fall back to the existing unavailable section -- this
is the intended, safe behavior, not a bug.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from config import ALPACA_BASE_URL, ALPACA_KEY, ALPACA_SECRET

from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    AlpacaAccountSnapshot,
    AlpacaPosition,
)


@dataclass(frozen=True)
class _AlpacaCredentials:
    key: str
    secret: str
    base_url: str


def _is_paper_environment(base_url: str) -> bool:
    return "paper" in (base_url or "").lower()


class AlpacaPaperSource:
    def __init__(
        self,
        api_key: str = ALPACA_KEY,
        api_secret: str = ALPACA_SECRET,
        base_url: str = ALPACA_BASE_URL,
    ):
        self._credentials = _AlpacaCredentials(key=api_key, secret=api_secret, base_url=base_url)

    def _build_client(self):
        """Returns a paper-only TradingClient, or None if credentials are
        missing or the configured environment isn't confirmed paper --
        never raises, never falls back to live."""
        creds = self._credentials
        if not creds.key or not creds.secret:
            return None
        if not _is_paper_environment(creds.base_url):
            return None
        try:
            from alpaca.trading.client import TradingClient
            return TradingClient(creds.key, creds.secret, paper=True)
        except Exception:
            return None

    def get_account(self) -> Optional[AlpacaAccountSnapshot]:
        """Returns the real Alpaca Paper account snapshot, or None if
        credentials/environment aren't confirmed paper, the network call
        fails, or the response is malformed -- callers must treat None as
        "fall back to the existing unavailable section," never as an
        error."""
        client = self._build_client()
        if client is None:
            return None
        try:
            account = client.get_account()
            return AlpacaAccountSnapshot(
                equity=float(account.equity),
                cash=float(account.cash),
                buying_power=float(account.buying_power),
                portfolio_value=float(account.portfolio_value),
            )
        except Exception:
            return None

    def get_positions(self) -> Optional[Tuple[AlpacaPosition, ...]]:
        """Returns every open Alpaca Paper position, ordered by symbol --
        an empty tuple is a legitimate real result (connected, zero open
        positions). Returns None only when credentials/environment aren't
        confirmed paper, the network call fails, or the response can't be
        parsed -- callers must treat None as "fall back to the existing
        unavailable section," never as an error, and must never use a
        partial result."""
        client = self._build_client()
        if client is None:
            return None
        try:
            positions = client.get_all_positions()
            parsed = tuple(
                AlpacaPosition(
                    symbol=p.symbol,
                    quantity=float(p.qty),
                    avg_entry_price=float(p.avg_entry_price),
                    current_price=float(p.current_price),
                    market_value=float(p.market_value),
                    unrealized_pl=float(p.unrealized_pl),
                    unrealized_plpc=float(p.unrealized_plpc),
                    side=str(p.side.value) if hasattr(p.side, "value") else str(p.side),
                )
                for p in positions
            )
        except Exception:
            return None
        return tuple(sorted(parsed, key=lambda pos: pos.symbol))
