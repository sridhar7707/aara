"""Read-only adapter over the legacy bot's NewsAPI L2 cache (`trades.db`'s
`news_cache` table), backing Sprint 7's descriptive evidence-state diff.

Boundary decision, extending the legacy_candidate_screening_source.py /
legacy_capital_source.py / legacy_regime_source.py / legacy_position_source.py
precedent to a fifth table: `news_cache` is a plain application-state table
written once per symbol per trading day by bot/strategy/sentiment.py's
`_news_db_set()` (schema DDL in bot/_main_db.py), not one of the Sentinel
Ledger event tables. A new, additive module here may open its own SQLite
connection to trades.db and SELECT from news_cache, provided it never
imports bot.*/dashboard.*/database.*/scheduler.*/ledger.*, never writes, and
never touches any ADR-002-protected file.

Sprint 7 scope note: Trust Ledger `decision_events.model_outputs` was
considered as an alternative evidence-snapshot source and deliberately
rejected for this sprint because ledger/ ownership (ADR-004) is still
deferred -- news_cache carries no such open-ownership question, since it
is (like screener_log) a plain legacy trades.db table this product already
has precedent for reading directly.

`headlines_json` is a flat JSON array of headline strings with no per-item
id, source, or timestamp -- so `NewsCacheSnapshot.headlines` is a plain
tuple of strings, not a richer per-headline record. Nothing here invents
structure the stored data doesn't carry.

Health contract (ADR-061 Category A): get_snapshot() returns
ReadResult[NewsCacheSnapshot]. A HEALTHY result carries the matching row,
or (when no row exists for that symbol/fetch_date) HEALTHY with
value=None -- a genuine "nothing cached yet" state. A non-HEALTHY result
carries value=None plus an IntegrationHealth naming the reason: UNAVAILABLE
(trades.db is not present, or is locked), API_ERROR (the news_cache table
is missing, or `headlines_json` is not valid JSON).
"""
import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Optional, Tuple

from applications.platform.integrations import IntegrationHealth, ReadResult

_PROVIDER = "trades_db_news_cache"

_DB_PATH = "trades.db"

# Duplicated from bot/_main_db.py's own news_cache schema -- not imported,
# per this module's own docstring.
_SELECT_SNAPSHOT = (
    "SELECT headlines_json, cached_at FROM news_cache WHERE symbol = ? AND fetch_date = ?"
)


@dataclass(frozen=True)
class NewsCacheSnapshot:
    symbol: str
    fetch_date: str
    headlines: Tuple[str, ...]
    cached_at: Optional[str]


def _sqlite_health(exc: sqlite3.Error) -> IntegrationHealth:
    """Mirrors legacy_candidate_screening_source._sqlite_health: a locked
    or unreachable file is a transient UNAVAILABLE; every other sqlite
    error is API_ERROR. Only the exception's class name is recorded as
    detail, never its message (ADR-061 Section 2.9)."""
    message = str(exc).lower()
    if "locked" in message or "unable to open" in message or "disk i/o" in message:
        return IntegrationHealth.unavailable(_PROVIDER, detail=type(exc).__name__)
    return IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)


class LegacyNewsCacheSource:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def get_snapshot(self, symbol: str, fetch_date: str) -> "ReadResult[NewsCacheSnapshot]":
        """Returns a ReadResult over the cached headlines for `symbol` on
        `fetch_date`. HEALTHY with a real snapshot when the row exists;
        HEALTHY with value=None when no row matches that symbol/date pair
        (a genuine "not cached" state, not an error); UNAVAILABLE when the
        database file is absent or locked; API_ERROR when the news_cache
        table is missing or `headlines_json` is not valid JSON."""
        if not os.path.exists(self._db_path):
            return ReadResult.failed(
                IntegrationHealth.unavailable(_PROVIDER, detail="trades.db is not present")
            )
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        try:
            row = conn.execute(_SELECT_SNAPSHOT, (symbol, fetch_date)).fetchone()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        finally:
            conn.close()

        if row is None:
            return ReadResult.empty(_PROVIDER)

        headlines_json, cached_at = row
        try:
            headlines = tuple(json.loads(headlines_json))
        except (TypeError, ValueError) as exc:
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )

        return ReadResult.healthy(
            NewsCacheSnapshot(
                symbol=symbol, fetch_date=fetch_date, headlines=headlines, cached_at=cached_at
            ),
            _PROVIDER,
        )
