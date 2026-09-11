"""Sentinel evidence analysis -- Master Roadmap Sprint 4 foundation slice.

Describes the ``Evidence`` already attached to a Decision: counts, polarity
mix, agreement/disagreement facts, corroboration by distinct source, type/
source distribution, and (optionally) elapsed age relative to a supplied
reference timestamp.

This module deliberately does NOT compute a confidence score, an uncertainty
score, or a relevance score, and never will inside this slice:

* No `ensemble_confidence` / `ensemble_score` / `bot.strategy.ensemble`
  import or reuse of any kind -- those are the legacy, model-weighted
  concept this module must stay independent of.
* No "Sentinel confidence" or "Sentinel uncertainty" result. A later,
  separate methodology slice decides how (or whether) to combine the facts
  produced here into `Decision.confidence` / `Decision.uncertainty`. This
  module hands that later slice raw primitives, not a verdict.
* No relevance signal. The current `Evidence` model gives no field that
  distinguishes one piece of evidence's topical relevance from another --
  `evidence_type` is uniform in production ("MODEL_OUTPUT" for all three
  models) and `data` is an untyped, source-specific bag not safe to
  introspect generically. Relevance is left for a later slice once the
  Evidence model (not touched here) has something to found it on.
* No source-reliability weighting, no freshness penalty/staleness
  threshold, no model-specific weighting. None of those are already
  established as a fixed rule in this repository, and inventing one here
  would smuggle a methodology decision into what is meant to be a pure
  descriptive layer.
* No persistence, no I/O, no database, no network, no model invocation.
  Every function here is a pure, deterministic transform of an in-memory
  `List[Evidence]` (and, for age, a supplied reference `datetime`).

"Neutral" evidence is any item whose `polarity` is not exactly
`EvidencePolarity.SUPPORTING.value` or `EvidencePolarity.CONTRADICTING.value`
-- this includes `None` (the documented no-polarity default) and any other
string. Mirrors the existing convention in
`sentinel_engine.adapters.evidence_adapter._polarity_for_signal`: an
unrecognised value is never a third named category, never raises, and is
simply not counted as directional.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.evidence.evidence_polarity import EvidencePolarity


def evidence_age(evidence: Evidence, reference_timestamp: datetime) -> timedelta:
    """Elapsed time between `evidence.collected_at` and `reference_timestamp`.

    A pure subtraction -- `reference_timestamp - evidence.collected_at` --
    with no clamping, no rounding, and no staleness judgment. Can be
    negative (evidence collected after the reference instant); that is
    returned as-is rather than treated as an error or clamped to zero, since
    no existing convention in this repository defines what "in the future"
    should mean for evidence age.
    """
    return reference_timestamp - evidence.collected_at


@dataclass(frozen=True)
class EvidenceAge:
    """One evidence item's elapsed age relative to the analysis's reference
    timestamp. Only ever produced when `analyze_evidence` is called with a
    `reference_timestamp`."""
    evidence_id: str
    age: timedelta


@dataclass(frozen=True)
class EvidenceAnalysis:
    """Descriptive facts about a Decision's attached evidence -- no score,
    no verdict, no confidence, no uncertainty. Every field here is directly
    countable or computable from the existing `Evidence` fields
    (`polarity`, `source`, `evidence_type`, `collected_at`); none is
    invented or weighted.
    """
    total_count: int
    supporting_count: int
    contradicting_count: int
    neutral_count: int

    agreement_ratio: Optional[float]
    """`abs(supporting_count - contradicting_count) / directional_count`,
    where `directional_count = supporting_count + contradicting_count`.
    Ranges from 0.0 (evenly split -- maximum disagreement) to 1.0
    (unanimous, one-sided). `None` when `directional_count == 0`: with no
    supporting or contradicting evidence at all, agreement is mathematically
    undefined, not zero."""

    contradiction_present: bool
    """True iff at least one CONTRADICTING item exists, regardless of how
    much SUPPORTING evidence is also present."""

    unresolved_disagreement_present: bool
    """True iff the evidence set contains at least one SUPPORTING item AND
    at least one CONTRADICTING item at the same time -- genuine conflict,
    not merely the presence of some contradicting evidence."""

    corroborating_source_count: int
    """Count of *distinct* `source` values among SUPPORTING evidence.
    Corroboration is about independent sources agreeing, not raw item
    count -- two SUPPORTING items from the same `source` corroborate
    nothing that one didn't already say."""

    evidence_type_distribution: Dict[str, int] = field(default_factory=dict)
    evidence_source_distribution: Dict[str, int] = field(default_factory=dict)

    ages: Tuple[EvidenceAge, ...] = ()
    """One `EvidenceAge` per input evidence item, in input order. Empty
    unless `analyze_evidence` was called with a `reference_timestamp`."""


def _polarity_bucket(polarity: Optional[str]) -> str:
    """"SUPPORTING" / "CONTRADICTING" pass through; anything else (`None`
    or any unrecognised string) is "NEUTRAL" -- never a third named
    category, never raised on."""
    if polarity == EvidencePolarity.SUPPORTING.value:
        return EvidencePolarity.SUPPORTING.value
    if polarity == EvidencePolarity.CONTRADICTING.value:
        return EvidencePolarity.CONTRADICTING.value
    return "NEUTRAL"


def analyze_evidence(
    evidence: List[Evidence],
    reference_timestamp: Optional[datetime] = None,
) -> EvidenceAnalysis:
    """Pure, deterministic analysis of `evidence`. Never mutates the input
    list or any `Evidence` item. Calling this twice with the same input
    (and the same `reference_timestamp`) returns equal results.

    `reference_timestamp` is optional: omit it to get every field except
    `ages` (left as the empty tuple); supply the Decision's own timestamp
    (or any other instant) to additionally get each item's elapsed age.
    """
    items = list(evidence)

    supporting_count = 0
    contradicting_count = 0
    neutral_count = 0
    corroborating_sources: set = set()
    type_distribution: Dict[str, int] = {}
    source_distribution: Dict[str, int] = {}

    for item in items:
        bucket = _polarity_bucket(item.polarity)
        if bucket == EvidencePolarity.SUPPORTING.value:
            supporting_count += 1
            corroborating_sources.add(item.source)
        elif bucket == EvidencePolarity.CONTRADICTING.value:
            contradicting_count += 1
        else:
            neutral_count += 1

        type_distribution[item.evidence_type] = type_distribution.get(item.evidence_type, 0) + 1
        source_distribution[item.source] = source_distribution.get(item.source, 0) + 1

    directional_count = supporting_count + contradicting_count
    agreement_ratio = (
        abs(supporting_count - contradicting_count) / directional_count
        if directional_count > 0
        else None
    )

    ages: Tuple[EvidenceAge, ...] = ()
    if reference_timestamp is not None:
        ages = tuple(
            EvidenceAge(evidence_id=item.evidence_id, age=evidence_age(item, reference_timestamp))
            for item in items
        )

    return EvidenceAnalysis(
        total_count=len(items),
        supporting_count=supporting_count,
        contradicting_count=contradicting_count,
        neutral_count=neutral_count,
        agreement_ratio=agreement_ratio,
        contradiction_present=contradicting_count > 0,
        unresolved_disagreement_present=supporting_count > 0 and contradicting_count > 0,
        corroborating_source_count=len(corroborating_sources),
        evidence_type_distribution=type_distribution,
        evidence_source_distribution=source_distribution,
        ages=ages,
    )
