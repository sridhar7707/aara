"""Sprint 7 -- read-only collaborator backing Decision Center's "Evidence
Since Decision" section.

Translates LegacyNewsCacheSource's ADR-061 ReadResult contract into the
TradingIntelligenceReadError contract DecisionCenterController's existing
per-concern try/except pattern expects, mirroring
trades_db_decision_adapters.py's own "Error translation" rule exactly: a
genuinely non-HEALTHY read becomes a TradingIntelligenceReadError; a
HEALTHY-but-empty read (a real "nothing cached for that date" result, not
a failure) returns None instead of raising, so the caller renders an
honest not-cached message rather than an error.

Purely descriptive, exactly like the news_cache_snapshot_diff.py module it
composes: no materiality, severity, urgency, invalidation, alerts,
re-evaluation, confidence, thesis, or counterfactual is introduced here or
anywhere downstream of this module.

``now_provider`` defaults to a plain ``datetime.now(timezone.utc)`` call --
the same convention bootstrap.py's own ``_now_utc()`` already uses -- no
new clock/timezone abstraction is introduced. A caller may inject a fixed
provider for deterministic tests, mirroring MorningBriefUI._now()'s
existing overridable-callable precedent.

Does not modify LegacyNewsCacheSource, NewsCacheSnapshot,
diff_news_cache_snapshots(), or NewsCacheSnapshotDiff -- all reused
verbatim. No bot/, sentinel_engine, or schema involvement; no write of any
kind.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from applications.trading_intelligence.adapters.legacy_news_cache_source import (
    LegacyNewsCacheSource,
)
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.services.news_cache_snapshot_diff import (
    NewsCacheSnapshotDiff,
    diff_news_cache_snapshots,
)


def _default_now_utc() -> datetime:
    return datetime.now(timezone.utc)


class TradesDbNewsCacheDiffSource:
    def __init__(
        self,
        news_cache_source: LegacyNewsCacheSource,
        now_provider: Callable[[], datetime] = _default_now_utc,
    ):
        self._news_cache_source = news_cache_source
        self._now_provider = now_provider

    def get_diff(
        self, symbol: str, decision_timestamp: datetime
    ) -> Optional[NewsCacheSnapshotDiff]:
        """Compares the cached headlines on file for `symbol` on
        `decision_timestamp`'s own date against today's date (from
        `now_provider`). Returns the real `NewsCacheSnapshotDiff` only when
        both snapshots are real; `None` when either is a genuine
        "nothing cached for that date" result (HEALTHY, value=None) --
        never an exception for that case. A same-day decision compares the
        identical underlying row to itself, naturally yielding
        `is_identical=True` with no special-case logic. Raises
        TradingIntelligenceReadError only for a genuinely non-HEALTHY read
        (e.g. trades.db locked or malformed)."""
        before_date = decision_timestamp.date().isoformat()
        after_date = self._now_provider().date().isoformat()

        before_result = self._news_cache_source.get_snapshot(symbol, before_date)
        if not before_result.health.is_healthy:
            raise TradingIntelligenceReadError(
                f"news_cache read failed for {symbol!r} on {before_date!r}: "
                f"{before_result.health.status.name}"
            )

        after_result = self._news_cache_source.get_snapshot(symbol, after_date)
        if not after_result.health.is_healthy:
            raise TradingIntelligenceReadError(
                f"news_cache read failed for {symbol!r} on {after_date!r}: "
                f"{after_result.health.status.name}"
            )

        if before_result.value is None or after_result.value is None:
            return None

        return diff_news_cache_snapshots(before_result.value, after_result.value)
