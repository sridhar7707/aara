"""Sprint 7 -- Descriptive Evidence-State Diff.

Pure, deterministic comparison of two already-fetched `NewsCacheSnapshot`
instances for the same symbol: "evidence state changed from X to Y",
never "the change is material" or "the decision is invalid". Every field
on `NewsCacheSnapshotDiff` is a fact directly computable from the two
snapshots' own `headlines`/`fetch_date`/`cached_at` values -- none is
invented, weighted, or scored.

Deliberately does NOT reuse `sentinel_engine.evidence.evidence_analysis
.analyze_evidence()`: that module's `EvidenceAnalysis` describes a
`List[Evidence]` by polarity mix and per-source corroboration, both
dimensions that presuppose a `polarity` and a `source` on each item.
`news_cache.headlines_json` is a flat JSON array of bare headline
strings -- no per-headline id, polarity, source, or timestamp. Wrapping
each headline in a synthetic `Evidence` to satisfy `analyze_evidence()`'s
shape would mean inventing a polarity/source/evidence_type the stored
data does not carry, which is exactly the kind of invented semantics this
sprint's scope excludes. `evaluate_directional_validity()` (Sprint 4B.1)
is not used for the same reason -- it operates on the same polarity field.

No thresholds, no scoring, no materiality determination, no decision
invalidation, no alerts, no notifications, no re-evaluation triggers, no
new Sentinel events, no persistence, no I/O -- a pure, deterministic
transform of two in-memory `NewsCacheSnapshot` values.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

from applications.trading_intelligence.adapters.legacy_news_cache_source import (
    NewsCacheSnapshot,
)


@dataclass(frozen=True)
class NewsCacheSnapshotDiff:
    """Descriptive facts about what changed between two NewsCacheSnapshot
    instances for the same symbol. No verdict, no judgment."""

    symbol: str

    before_fetch_date: str
    after_fetch_date: str
    before_cached_at: Optional[str]
    after_cached_at: Optional[str]

    before_headline_count: int
    after_headline_count: int

    added_headlines: Tuple[str, ...]
    """Headlines present in `after` but not `before`, multiset-aware
    (a headline appearing twice in `after` but once in `before` counts as
    one addition) and in `after`'s original order."""

    removed_headlines: Tuple[str, ...]
    """Headlines present in `before` but not `after`, multiset-aware and
    in `before`'s original order."""

    is_identical: bool
    """True iff the two headline sequences are exactly equal, including
    order and duplicate counts."""

    same_headlines_reordered: bool
    """True iff the two headline sequences carry the same multiset of
    headlines but in a different order (so neither `added_headlines` nor
    `removed_headlines` is populated, yet `is_identical` is False)."""


def _ordered_multiset_difference(sequence: Sequence[str], excess: Counter) -> Tuple[str, ...]:
    """Items of `sequence` whose remaining count in `excess` is still
    positive, consumed left-to-right -- preserves `sequence`'s original
    order and respects duplicate counts rather than collapsing to a set."""
    remaining: Dict[str, int] = dict(excess)
    result = []
    for item in sequence:
        if remaining.get(item, 0) > 0:
            result.append(item)
            remaining[item] -= 1
    return tuple(result)


def diff_news_cache_snapshots(
    before: NewsCacheSnapshot, after: NewsCacheSnapshot
) -> NewsCacheSnapshotDiff:
    """Deterministically describe what changed between `before` and
    `after`. Raises `ValueError` if the two snapshots are not for the same
    symbol -- comparing evidence across different symbols is a caller
    error, not a describable change."""
    if before.symbol != after.symbol:
        raise ValueError(
            f"cannot diff snapshots for different symbols: "
            f"{before.symbol!r} vs {after.symbol!r}"
        )

    before_list = list(before.headlines)
    after_list = list(after.headlines)

    before_counts = Counter(before_list)
    after_counts = Counter(after_list)

    added_headlines = _ordered_multiset_difference(after_list, after_counts - before_counts)
    removed_headlines = _ordered_multiset_difference(before_list, before_counts - after_counts)

    is_identical = before_list == after_list
    same_headlines_reordered = (not is_identical) and (before_counts == after_counts)

    return NewsCacheSnapshotDiff(
        symbol=before.symbol,
        before_fetch_date=before.fetch_date,
        after_fetch_date=after.fetch_date,
        before_cached_at=before.cached_at,
        after_cached_at=after.cached_at,
        before_headline_count=len(before_list),
        after_headline_count=len(after_list),
        added_headlines=added_headlines,
        removed_headlines=removed_headlines,
        is_identical=is_identical,
        same_headlines_reordered=same_headlines_reordered,
    )
