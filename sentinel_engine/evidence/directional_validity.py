"""Sentinel directional-validity analysis -- Master Roadmap Sprint 4B.1.

Exposes, as an explicit queryable fact, whether an Evidence item's polarity
was evaluated against the same action the Decision it is attached to
actually took.

Why this exists: `sentinel_engine.adapters.evidence_adapter` assigns
`polarity` relative to a fixed action hypothesis -- "BUY" -> SUPPORTING,
"SELL" -> CONTRADICTING, "HOLD"/other -> None (ADR-068 B1) -- and ADR-068's
own "Accepted scope -- exactly, and only" excludes `WAIT`, `BUY_MORE`, any
`SELL` / exit-path `Decision`, and position lifecycle. `record_decision_safe()`
in `bot/_main_trust_decisions.py` nonetheless calls that adapter
unconditionally for both the entry path and the exit path (via
`record_exit_decision_safe()`), so a real SELL Decision's evidence can carry
a polarity that was computed against a BUY hypothesis it never represents.
This module turns that mismatch into a checkable fact instead of a silent
assumption -- it does not resolve it.

This module deliberately does NOT:

* change `evidence_adapter`'s polarity assignment or SELL/exit-path
  behavior. The mismatch described above is left exactly as it is; fixing
  it is out of scope for this slice.
* wire into `bot/_main_trust_decisions.py`, `record_decision_safe()`, or
  `record_exit_decision_safe()`. No production call site is touched or
  imported.
* produce a confidence, uncertainty, quality, reliability, freshness,
  relevance, or corroboration result, weighted or otherwise. It answers
  exactly one factual question per evidence item: did the hypothesis its
  polarity was evaluated against match the Decision's actual action?
* invent meaning for HOLD, WAIT, or BUY_MORE beyond plain string equality.
  `decision_action` and `polarity_hypothesis_action` are compared as
  opaque strings, exactly as `sentinel_engine.domain.decision.Decision`
  itself treats `action` (no validation-in-the-domain-object convention;
  see that module's own docstring). Any semantic content for those
  actions belongs to the later Trading Decision Intelligence work.
* hardcode "BUY" as the hypothesis anywhere in this module. Today's only
  production hypothesis is always "BUY" (ADR-068), but this module takes
  `polarity_hypothesis_action` as an explicit input rather than assuming
  it, so it stays correct if a future, separately-authorized change gives
  SELL/exit-path evidence its own hypothesis.

Only SUPPORTING/CONTRADICTING polarity is "directional" -- a `None` (or any
unrecognised) polarity, per the same convention used in
`sentinel_engine.evidence.evidence_analysis`, has no direction to evaluate,
so hypothesis-match is reported as not applicable (`None`), never coerced
to True or False.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.evidence.evidence_polarity import EvidencePolarity


def _is_directional(polarity: Optional[str]) -> bool:
    """True iff `polarity` is exactly SUPPORTING or CONTRADICTING -- any
    other value (`None` or an unrecognised string) has no direction to
    evaluate against any hypothesis."""
    return polarity in (EvidencePolarity.SUPPORTING.value, EvidencePolarity.CONTRADICTING.value)


@dataclass(frozen=True)
class DirectionalValidity:
    """Purely descriptive. No judgment about whether the evidence is
    correct, strong, or trustworthy -- only whether the *direction* its
    polarity was scored on matches what the Decision actually did.
    """
    evidence_id: str
    polarity: Optional[str]
    is_directional: bool
    polarity_hypothesis_action: str
    decision_action: str

    hypothesis_matches_decision_action: Optional[bool]
    """True/False when `is_directional` is True; `None` when the polarity
    carries no direction to begin with -- match/mismatch is not applicable
    to non-directional evidence."""


def evaluate_directional_validity(
    evidence: Evidence,
    decision_action: str,
    polarity_hypothesis_action: str,
) -> DirectionalValidity:
    """`polarity_hypothesis_action` is the action `evidence.polarity` was
    actually evaluated against at the point it was assigned (today, always
    "BUY" per ADR-068 -- see the module docstring). This function accepts
    it as a caller-supplied fact rather than assuming a value, since
    comparing the stated hypothesis against `decision_action` -- without
    this module ever guessing what the hypothesis was -- is the point.
    """
    directional = _is_directional(evidence.polarity)
    return DirectionalValidity(
        evidence_id=evidence.evidence_id,
        polarity=evidence.polarity,
        is_directional=directional,
        polarity_hypothesis_action=polarity_hypothesis_action,
        decision_action=decision_action,
        hypothesis_matches_decision_action=(
            (polarity_hypothesis_action == decision_action) if directional else None
        ),
    )


def analyze_directional_validity(
    evidence: List[Evidence],
    decision_action: str,
    polarity_hypothesis_action: str,
) -> Tuple[DirectionalValidity, ...]:
    """One `DirectionalValidity` per item in `evidence`, in input order.

    Every item is checked against the SAME `decision_action` /
    `polarity_hypothesis_action` pair -- matching how
    `sentinel_engine.adapters.evidence_adapter.to_evidence_records()`
    assigns one hypothesis for an entire `model_outputs` batch today, not a
    per-item hypothesis. There is no existing per-item hypothesis to
    justify a different shape here.
    """
    return tuple(
        evaluate_directional_validity(item, decision_action, polarity_hypothesis_action)
        for item in evidence
    )
