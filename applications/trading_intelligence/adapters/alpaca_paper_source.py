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
     not confirmed to be paper and both methods report NOT_CONFIGURED
     (the existing safe-unavailable path) rather than ever proceeding on
     an unverified assumption. This is a defensive, belt-and-suspenders
     check on top of (1), not a substitute for it.
Together these mean: this adapter cannot be misconfigured into reading
live data, and will not silently fall back from paper to live or from
live to paper -- an unconfirmed environment is simply unavailable. A
non-paper base URL is reported as NOT_CONFIGURED and can never become
HEALTHY or AUTH_FAILED.

Credentials are never logged: only a boolean "configured" state and,
where useful, the last 4 characters of the account number (already
public within the paper account's own dashboard, not a secret) are ever
surfaced -- the API key and secret themselves are never written to any
log, exception message, IntegrationHealth.detail, or return value
(ADR-061 Section 2.9).

Health contract (ADR-061 Category A): each read method returns
ReadResult[T]. A HEALTHY result carries a real value (an empty tuple of
positions for a flat account is a legitimate HEALTHY result). A
non-HEALTHY result carries value=None plus an IntegrationHealth naming
the reason: NOT_CONFIGURED (missing credentials / unconfirmed paper
environment / SDK not importable), AUTH_FAILED (401/403), RATE_LIMITED
(429), UNAVAILABLE (network/timeout/5xx), API_ERROR (malformed response).

Production note: identical class of limitation to every other adapter in
this product -- the deployed Trading Intelligence HF Space has no
credentials or outbound network configuration for Alpaca today. Locally,
where ALPACA_KEY/ALPACA_SECRET are present via .env, this adapter reads
real data immediately. In production, until credentials and network
access are separately provisioned, both methods report NOT_CONFIGURED,
and callers fall back to the existing unavailable section -- this is the
intended, safe behavior, not a bug.
"""
from dataclasses import dataclass
from typing import Tuple

try:
    from config import ALPACA_BASE_URL, ALPACA_KEY, ALPACA_SECRET
except ImportError:
    # config.py (top-level, not part of this product) is not staged in
    # the deployed Trading Intelligence HF Space -- see
    # .github/workflows/deploy_trading_intelligence.yml, which stages
    # only applications/, sentinel_engine/, and brand/logos/. Falling
    # back to empty credentials here is the correct, safe behavior: the
    # Space has no Alpaca Space secrets configured today either (see this
    # module's own "Production note" below), so get_account()/
    # get_positions() would already report NOT_CONFIGURED regardless --
    # this only prevents that expected, documented gap from crashing the
    # entire Space at import time instead.
    ALPACA_KEY = ""
    ALPACA_SECRET = ""
    ALPACA_BASE_URL = ""

from applications.platform.integrations import (
    IntegrationHealth,
    ReadResult,
    classify_exception,
)
from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    AlpacaAccountSnapshot,
    AlpacaPosition,
)

_PROVIDER = "alpaca_paper"


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

    def _client_or_health(self):
        """Returns ``(client, None)`` on success, or ``(None, IntegrationHealth)``
        describing why a paper-only TradingClient could not be built --
        never raises, never falls back to live."""
        creds = self._credentials
        if not creds.key or not creds.secret:
            return None, IntegrationHealth.not_configured(
                _PROVIDER, detail="ALPACA_KEY / ALPACA_SECRET not set"
            )
        if not _is_paper_environment(creds.base_url):
            return None, IntegrationHealth.not_configured(
                _PROVIDER, detail="ALPACA_BASE_URL is not a paper endpoint"
            )
        try:
            from alpaca.trading.client import TradingClient
        except Exception:
            return None, IntegrationHealth.not_configured(
                _PROVIDER, detail="alpaca-py SDK is not importable"
            )
        try:
            return TradingClient(creds.key, creds.secret, paper=True), None
        except ImportError:
            return None, IntegrationHealth.not_configured(
                _PROVIDER, detail="alpaca-py SDK is not importable"
            )
        except Exception as exc:
            return None, classify_exception(_PROVIDER, exc)

    def get_account(self) -> "ReadResult[AlpacaAccountSnapshot]":
        """Returns a ReadResult over the real Alpaca Paper account
        snapshot. A HEALTHY result always carries a real snapshot. Any
        failure yields value=None plus an IntegrationHealth naming the
        reason -- callers must treat a non-HEALTHY result as "fall back to
        the existing unavailable section," never as an error."""
        client, health = self._client_or_health()
        if client is None:
            return ReadResult.failed(health)
        try:
            account = client.get_account()
        except Exception as exc:
            return ReadResult.failed(classify_exception(_PROVIDER, exc))
        try:
            snapshot = AlpacaAccountSnapshot(
                equity=float(account.equity),
                cash=float(account.cash),
                buying_power=float(account.buying_power),
                portfolio_value=float(account.portfolio_value),
            )
        except Exception as exc:
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )
        return ReadResult.healthy(snapshot, _PROVIDER)

    def get_positions(self) -> "ReadResult[Tuple[AlpacaPosition, ...]]":
        """Returns a ReadResult over every open Alpaca Paper position,
        ordered by symbol. A HEALTHY result with an empty tuple is a
        legitimate real state (connected, zero open positions), distinct
        from a non-HEALTHY result (value=None) which means the read could
        not be completed -- callers must never use a partial result."""
        client, health = self._client_or_health()
        if client is None:
            return ReadResult.failed(health)
        try:
            positions = client.get_all_positions()
        except Exception as exc:
            return ReadResult.failed(classify_exception(_PROVIDER, exc))
        try:
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
        except Exception as exc:
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )
        return ReadResult.healthy(
            tuple(sorted(parsed, key=lambda pos: pos.symbol)), _PROVIDER
        )
