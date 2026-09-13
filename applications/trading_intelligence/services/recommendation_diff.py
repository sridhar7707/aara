"""Sprint 7 -- Descriptive "Recommendation Since Decision" diff.

Pure, deterministic comparison of two already-fetched
`RecommendationSnapshot` instances for the same symbol: "the recommendation
was X, is now Y", never "the change is material" or "the recommendation is
invalidated". Every field on `RecommendationDiff` is a fact directly
computable from the two snapshots' own `recommendation`/`confidence`
values -- none is invented, weighted, or scored.

`is_unchanged` is plain string equality on `recommendation`
(`before_recommendation == after_recommendation`) -- confidence drift
alone never flips it. No thresholds, no scoring, no materiality
determination, no decision invalidation, no alerts, no notifications, no
re-evaluation triggers, no new Sentinel events, no persistence, no I/O --
mirrors news_cache_snapshot_diff.py's own scope discipline exactly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from applications.trading_intelligence.adapters.legacy_recommendation_source import (
    RecommendationSnapshot,
)


@dataclass(frozen=True)
class RecommendationDiff:
    """Descriptive facts about what changed between two
    RecommendationSnapshot instances for the same symbol. No verdict, no
    judgment."""

    symbol: str

    before_prediction_date: str
    after_prediction_date: str

    before_recommendation: Optional[str]
    after_recommendation: Optional[str]

    before_confidence: Optional[float]
    after_confidence: Optional[float]

    is_unchanged: bool
    """True iff `before_recommendation == after_recommendation`. Plain
    equality only -- confidence is never consulted."""


def diff_recommendation_snapshots(
    before: RecommendationSnapshot, after: RecommendationSnapshot
) -> RecommendationDiff:
    """Deterministically describe what changed between `before` and
    `after`. Raises `ValueError` if the two snapshots are not for the same
    symbol -- comparing recommendations across different symbols is a
    caller error, not a describable change."""
    if before.symbol != after.symbol:
        raise ValueError(
            f"cannot diff recommendation snapshots for different symbols: "
            f"{before.symbol!r} vs {after.symbol!r}"
        )

    return RecommendationDiff(
        symbol=before.symbol,
        before_prediction_date=before.prediction_date,
        after_prediction_date=after.prediction_date,
        before_recommendation=before.recommendation,
        after_recommendation=after.recommendation,
        before_confidence=before.confidence,
        after_confidence=after.confidence,
        is_unchanged=before.recommendation == after.recommendation,
    )
