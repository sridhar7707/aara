"""Read-only adapter over the legacy bot's earnings-proximity cache
(`trades.db`'s `earnings_cache` table), backing Sprint 7's descriptive
"Earnings Proximity" evidence.

Boundary decision, extending the legacy_news_cache_source.py /
legacy_recommendation_source.py / legacy_risk_state_source.py precedent to
a seventh table: `earnings_cache` is a plain application-state table
written by bot/_main_market.py, not one of the Sentinel Ledger event
tables. A new, additive module here may open its own SQLite connection to
trades.db and SELECT from earnings_cache, provided it never imports
bot.*/dashboard.*/database.*/scheduler.*/ledger.*, never writes, and never
touches any ADR-002-protected file.

Unlike news_cache/recommendations (dated, `(symbol, date)` primary key,
supporting a before/after comparison), `earnings_cache` is keyed on
`symbol` alone -- a single, continuously-refreshed current value per
symbol, not a time series. There is nothing to diff: this module exposes
exactly one current fact, `get_snapshot(symbol)`, and introduces no
date/diff logic.

`near_earnings` is stored as a SQLite INTEGER (0/1). Normalized to a real
Python `bool` at this boundary -- the same `bool(int(value))` convention
`trust_ledger_inspection_source.py::_to_bool()` already establishes for
this codebase's other INTEGER-as-boolean columns -- rather than passed
through as a raw int. Nothing here infers an earnings date, computes days
until earnings, or attaches any volatility/materiality/significance
meaning to the stored value; it is relayed exactly as the bot recorded it.

Health contract (ADR-061 Category A): get_snapshot() returns
ReadResult[EarningsSnapshot]. A HEALTHY result carries the matching row,
or (when no row exists for that symbol) HEALTHY with value=None -- a
genuine "not tracked" state. A non-HEALTHY result carries value=None plus
an IntegrationHealth naming the reason: UNAVAILABLE (trades.db is not
present, or is locked), API_ERROR (the earnings_cache table is missing).
"""
import os
import sqlite3
from dataclasses import dataclass
from typing import Optional

from applications.platform.integrations import IntegrationHealth, ReadResult

_PROVIDER = "trades_db_earnings"

_DB_PATH = "trades.db"

# Duplicated from bot/_main_market.py's own earnings_cache schema -- not
# imported, per this module's own docstring.
_SELECT_SNAPSHOT = (
    "SELECT symbol, near_earnings, cached_at FROM earnings_cache WHERE symbol = ?"
)


@dataclass(frozen=True)
class EarningsSnapshot:
    symbol: str
    near_earnings: Optional[bool]
    cached_at: Optional[str]


def _to_bool(value) -> Optional[bool]:
    """Mirrors trust_ledger_inspection_source.py::_to_bool() -- the
    established convention for this codebase's INTEGER-as-boolean
    columns. `None` stays `None` (a genuinely unrecorded value, never
    coerced to False)."""
    if value is None:
        return None
    return bool(int(value))


def _sqlite_health(exc: sqlite3.Error) -> IntegrationHealth:
    """Mirrors legacy_news_cache_source._sqlite_health: a locked or
    unreachable file is a transient UNAVAILABLE; every other sqlite error
    is API_ERROR. Only the exception's class name is recorded as detail,
    never its message (ADR-061 Section 2.9)."""
    message = str(exc).lower()
    if "locked" in message or "unable to open" in message or "disk i/o" in message:
        return IntegrationHealth.unavailable(_PROVIDER, detail=type(exc).__name__)
    return IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)


class LegacyEarningsSource:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def get_snapshot(self, symbol: str) -> "ReadResult[EarningsSnapshot]":
        """Returns a ReadResult over the cached earnings-proximity flag
        for `symbol`. HEALTHY with a real snapshot when the row exists;
        HEALTHY with value=None when no row matches that symbol (a
        genuine "not tracked" state, not an error); UNAVAILABLE when the
        database file is absent or locked; API_ERROR when the
        earnings_cache table is missing."""
        if not os.path.exists(self._db_path):
            return ReadResult.failed(
                IntegrationHealth.unavailable(_PROVIDER, detail="trades.db is not present")
            )
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        try:
            row = conn.execute(_SELECT_SNAPSHOT, (symbol,)).fetchone()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        finally:
            conn.close()

        if row is None:
            return ReadResult.empty(_PROVIDER)

        row_symbol, near_earnings, cached_at = row
        return ReadResult.healthy(
            EarningsSnapshot(
                symbol=row_symbol, near_earnings=_to_bool(near_earnings), cached_at=cached_at
            ),
            _PROVIDER,
        )
