"""Read-only adapter over the legacy bot's per-cycle recommendation log
(`trades.db`'s `recommendations` table), backing Sprint 7's descriptive
"Recommendation Since Decision" evidence.

Boundary decision, extending the legacy_news_cache_source.py /
legacy_candidate_screening_source.py / legacy_capital_source.py /
legacy_regime_source.py / legacy_position_source.py precedent to a sixth
table: `recommendations` is a plain application-state table written every
bot cycle, for every evaluated symbol, by bot/main.py via
bot/db/trade_log.py::log_recommendation() ("Record per-symbol
recommendation for every cycle so Rec History widget shows what the bot
was thinking even when no trade fires") -- not one of the Sentinel Ledger
event tables. A new, additive module here may open its own SQLite
connection to trades.db and SELECT from recommendations, provided it
never imports bot.*/dashboard.*/database.*/scheduler.*/ledger.*, never
writes, and never touches any ADR-002-protected file.

The application-layer snapshot carries only the fields this vigilance
comparison needs (symbol, prediction_date, recommendation, confidence) --
`prev_recommendation`, `price_at_recommendation`, and `created_at` are
real columns on the row but are not read here, since the before/after
comparison this module backs already derives its own "before" value from
a separate dated row (see trades_db_recommendation_diff_source.py), not
from the bot's own single-row `prev_recommendation` convenience field.

Health contract (ADR-061 Category A): get_snapshot() returns
ReadResult[RecommendationSnapshot]. A HEALTHY result carries the matching
row, or (when no row exists for that symbol/prediction_date) HEALTHY with
value=None -- a genuine "nothing recorded yet" state. A non-HEALTHY result
carries value=None plus an IntegrationHealth naming the reason: UNAVAILABLE
(trades.db is not present, or is locked), API_ERROR (the recommendations
table is missing).
"""
import os
import sqlite3
from dataclasses import dataclass
from typing import Optional

from applications.platform.integrations import IntegrationHealth, ReadResult

_PROVIDER = "trades_db_recommendation"

_DB_PATH = "trades.db"

# Duplicated from bot/_main_db.py's own recommendations schema -- not
# imported, per this module's own docstring.
_SELECT_SNAPSHOT = (
    "SELECT recommendation, confidence FROM recommendations "
    "WHERE symbol = ? AND prediction_date = ?"
)


@dataclass(frozen=True)
class RecommendationSnapshot:
    symbol: str
    prediction_date: str
    recommendation: Optional[str]
    confidence: Optional[float]


def _sqlite_health(exc: sqlite3.Error) -> IntegrationHealth:
    """Mirrors legacy_news_cache_source._sqlite_health: a locked or
    unreachable file is a transient UNAVAILABLE; every other sqlite error
    is API_ERROR. Only the exception's class name is recorded as detail,
    never its message (ADR-061 Section 2.9)."""
    message = str(exc).lower()
    if "locked" in message or "unable to open" in message or "disk i/o" in message:
        return IntegrationHealth.unavailable(_PROVIDER, detail=type(exc).__name__)
    return IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)


class LegacyRecommendationSource:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def get_snapshot(
        self, symbol: str, prediction_date: str
    ) -> "ReadResult[RecommendationSnapshot]":
        """Returns a ReadResult over the recorded recommendation for
        `symbol` on `prediction_date`. HEALTHY with a real snapshot when
        the row exists; HEALTHY with value=None when no row matches that
        symbol/date pair (a genuine "not recorded" state, not an error);
        UNAVAILABLE when the database file is absent or locked; API_ERROR
        when the recommendations table is missing."""
        if not os.path.exists(self._db_path):
            return ReadResult.failed(
                IntegrationHealth.unavailable(_PROVIDER, detail="trades.db is not present")
            )
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        try:
            row = conn.execute(_SELECT_SNAPSHOT, (symbol, prediction_date)).fetchone()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        finally:
            conn.close()

        if row is None:
            return ReadResult.empty(_PROVIDER)

        recommendation, confidence = row
        return ReadResult.healthy(
            RecommendationSnapshot(
                symbol=symbol,
                prediction_date=prediction_date,
                recommendation=recommendation,
                confidence=confidence,
            ),
            _PROVIDER,
        )
