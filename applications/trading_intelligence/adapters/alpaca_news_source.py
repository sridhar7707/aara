"""Read-only adapter over Alpaca's News API (alpaca-py NewsClient), backing
Morning Brief's "Overnight Holdings News" section with real, recent news
headlines for the account's current holdings when available.

Boundary decision (recorded, same dependency class as
adapters/alpaca_paper_source.py -- an external broker/market API rather
than a local trades.db table): READ-ONLY observation only.
get_overnight_holdings_news() issues a single GET (NewsClient.get_news);
this module never calls submit_order/cancel_order/replace_order or any
other order-placing/cancelling method, never opens a database connection,
and never writes anything anywhere (see the regression-lock tests in
tests/test_alpaca_news_source.py).

This module intentionally does NOT import bot.execution.alpaca_client
(bot/ is ADR-002-protected, and that module also implements order
submission) -- it instantiates its own independent alpaca-py NewsClient,
the same "duplicate the primitive, never import the protected package"
convention adapters/alpaca_paper_source.py already uses. Credentials come
from the top-level `config` module (config.py, NOT under bot/ and
therefore not ADR-002-protected) -- the same ALPACA_KEY/ALPACA_SECRET the
paper adapter reads.

Unlike adapters/alpaca_paper_source.py there is no paper/live base_url
gate here: Alpaca's News API is market data with no paper-vs-live
distinction, so credential presence is the only precondition. Nothing
this adapter can reach places, cancels, or modifies an order.

News is SOURCE / EVIDENCE data only. This adapter reads and filters
headlines to the current holdings symbols; it never scores an article,
ranks by conviction, infers an action, or produces anything a decision
path consumes as authority. It is not a second decision authority.

Never fabricates. On missing credentials, a network/API error, or a
malformed provider response, get_overnight_holdings_news() returns None
and the caller falls back to the existing honest unavailable message
("No Evidence/news producer exists yet -- ..."). An empty holdings list,
or a successful fetch that matched no article, returns an empty
OvernightHoldingsNews -- a real "nothing to report" result, distinct
from None.

Production note: identical limitation to adapters/alpaca_paper_source.py
-- the deployed Trading Intelligence HF Space has no Alpaca credentials
or outbound network configured today, so this returns None there and the
section stays unavailable. Locally, with ALPACA_KEY/ALPACA_SECRET present
via .env, it reads real Alpaca news immediately.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence, Tuple

try:
    from config import ALPACA_KEY, ALPACA_SECRET
except ImportError:
    # config.py (top-level, not part of this product) is not staged in the
    # deployed Trading Intelligence HF Space -- see
    # adapters/alpaca_paper_source.py's own note on the same fallback.
    # Falling back to empty credentials keeps the Space from crashing at
    # import time; get_overnight_holdings_news() then returns None (the
    # expected, documented unavailable path) rather than raising.
    ALPACA_KEY = ""
    ALPACA_SECRET = ""

_DEFAULT_LOOKBACK_HOURS = 24
_DEFAULT_MAX_ITEMS = 20


@dataclass(frozen=True)
class HoldingsNewsItem:
    headline: str
    symbols: Tuple[str, ...]
    source: str
    created_at: str
    url: str


@dataclass(frozen=True)
class OvernightHoldingsNews:
    items: Tuple[HoldingsNewsItem, ...]

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0


@dataclass(frozen=True)
class _AlpacaNewsCredentials:
    key: str
    secret: str


class AlpacaNewsSource:
    def __init__(
        self,
        api_key: str = ALPACA_KEY,
        api_secret: str = ALPACA_SECRET,
        lookback_hours: int = _DEFAULT_LOOKBACK_HOURS,
        max_items: int = _DEFAULT_MAX_ITEMS,
    ):
        self._credentials = _AlpacaNewsCredentials(key=api_key, secret=api_secret)
        self._lookback_hours = lookback_hours
        self._max_items = max_items

    def _build_client(self):
        """Returns an alpaca-py NewsClient, or None if credentials are
        missing or the SDK import fails -- never raises."""
        creds = self._credentials
        if not creds.key or not creds.secret:
            return None
        try:
            from alpaca.data.historical.news import NewsClient
            return NewsClient(creds.key, creds.secret)
        except Exception:
            return None

    def get_overnight_holdings_news(
        self, symbols: Sequence[str]
    ) -> Optional[OvernightHoldingsNews]:
        """Returns recent Alpaca news filtered to `symbols` (the account's
        current holdings), newest first. Returns None only when
        credentials are missing, the network call fails, or the response
        is malformed -- callers must treat None as "fall back to the
        existing unavailable section," never as an error.

        An empty `symbols` returns an empty OvernightHoldingsNews without
        any network call (no holdings -> nothing to report). A successful
        fetch that matches no article also returns an empty
        OvernightHoldingsNews. Neither is an error, and neither is None.
        """
        wanted = tuple(dict.fromkeys(str(s).upper() for s in symbols if s))
        if not wanted:
            return OvernightHoldingsNews(items=())

        client = self._build_client()
        if client is None:
            return None

        try:
            from alpaca.data.requests import NewsRequest

            request = NewsRequest(
                symbols=",".join(wanted),
                start=datetime.now(timezone.utc) - timedelta(hours=self._lookback_hours),
                sort="desc",
                limit=self._max_items,
                exclude_contentless=True,
            )
            response = client.get_news(request)
            articles = self._extract_articles(response)
            if articles is None:
                return None
            items = self._to_items(articles, set(wanted))
        except Exception:
            return None

        return OvernightHoldingsNews(items=items[: self._max_items])

    @staticmethod
    def _extract_articles(response):
        """Pulls the raw article list out of whatever get_news() returned
        (an alpaca-py NewsSet, a raw dict, or a bare list). Returns None
        -- signalling a malformed response the caller must treat as
        unavailable -- when the shape is unrecognised."""
        data = getattr(response, "data", None)
        if isinstance(data, dict):
            articles = data.get("news")
            return list(articles) if isinstance(articles, (list, tuple)) else None
        if isinstance(response, dict):
            articles = response.get("news")
            return list(articles) if isinstance(articles, (list, tuple)) else None
        if isinstance(response, (list, tuple)):
            return list(response)
        return None

    def _to_items(self, articles, wanted_upper) -> Tuple[HoldingsNewsItem, ...]:
        parsed = []
        for article in articles:
            raw_symbols = self._field(article, "symbols") or ()
            article_symbols = tuple(str(s).upper() for s in raw_symbols)
            matched = tuple(s for s in article_symbols if s in wanted_upper)
            if not matched:
                continue
            headline = self._field(article, "headline")
            if not headline or not str(headline).strip():
                continue
            created_at = self._field(article, "created_at")
            parsed.append(
                (
                    self._sort_key(created_at),
                    HoldingsNewsItem(
                        headline=str(headline).strip(),
                        symbols=matched,
                        source=str(self._field(article, "source") or "").strip(),
                        created_at=self._coerce_ts(created_at),
                        url=str(self._field(article, "url") or "").strip(),
                    ),
                )
            )
        parsed.sort(key=lambda pair: pair[0], reverse=True)
        return tuple(item for _, item in parsed)

    @staticmethod
    def _field(article, name):
        if isinstance(article, dict):
            return article.get(name)
        return getattr(article, name, None)

    @staticmethod
    def _coerce_ts(value) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _sort_key(value) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value or "")
