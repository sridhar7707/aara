"""Sprint 7 -- read-only collaborator backing Decision Center's "Earnings
Proximity" evidence.

Translates LegacyEarningsSource's ADR-061 ReadResult contract into the
TradingIntelligenceReadError contract DecisionCenterController's existing
per-concern try/except pattern expects, mirroring
trades_db_news_cache_diff_source.py's / trades_db_recommendation_diff_source.py's
own "Error translation" rule exactly: a genuinely non-HEALTHY read becomes
a TradingIntelligenceReadError; a HEALTHY-but-empty read (a real "not
tracked" result, not a failure) returns None instead of raising, so the
caller renders an honest not-tracked message rather than an error.

Unlike its two siblings, there is no before/after comparison here --
earnings_cache is a single current value per symbol, not a dated time
series -- so this collaborator has no diff step and no now_provider; it
is the thinnest possible translation layer.

Does not modify LegacyEarningsSource or EarningsSnapshot -- both reused
verbatim. No bot/, sentinel_engine, or schema involvement; no write of any
kind.
"""
from __future__ import annotations

from typing import Optional

from applications.trading_intelligence.adapters.legacy_earnings_source import (
    EarningsSnapshot,
    LegacyEarningsSource,
)
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError


class TradesDbEarningsSource:
    def __init__(self, earnings_source: LegacyEarningsSource):
        self._earnings_source = earnings_source

    def get_snapshot(self, symbol: str) -> Optional[EarningsSnapshot]:
        """Returns the real EarningsSnapshot for `symbol` when a row
        exists; `None` when a HEALTHY read simply found nothing tracked
        for that symbol (never an exception for that case). Raises
        TradingIntelligenceReadError only for a genuinely non-HEALTHY read
        (e.g. trades.db locked or malformed)."""
        result = self._earnings_source.get_snapshot(symbol)
        if not result.health.is_healthy:
            raise TradingIntelligenceReadError(
                f"earnings_cache read failed for {symbol!r}: {result.health.status.name}"
            )
        return result.value
