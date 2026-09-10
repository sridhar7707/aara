"""Pure query boundary for the historical "outcome by ensemble score" view.

``DecisionCalibrationQueryService`` folds an already-built Wave 2A
:class:`OutcomeLineage` (produced unchanged by
``DecisionOutcomeQueryService``) into a fixed set of ensemble-score
bands, each carrying a realized WIN / LOSS tally.

Purity contract -- this module has NONE of:

* database or file access, network, or any I/O;
* a Gradio / bot / dashboard / scheduler / sentinel_engine import;
* a clock, randomness, or any other non-deterministic input.

It answers one historical question -- "for CLOSED BUY decisions, how did
realized outcomes fall across recorded entry ensemble score?" -- and
makes no predictive-accuracy, probability-calibration, or
statistical-significance claim. The bands are a plain count.

Counted: an outcome is included only when

* ``status is OutcomeStatus.CLOSED``;
* ``entry_ensemble_score`` is not ``None`` and lies in ``[0.50, 1.00]``;
* ``outcome_direction`` is ``WIN`` or ``LOSS``.

Everything else -- OPEN / PARTIAL / AMBIGUOUS outcomes, FLAT outcomes,
a missing direction, a missing score, a score outside ``[0.50, 1.00]`` --
is excluded, never forced into a band.
"""
from typing import List, Optional, Tuple

from applications.trading_intelligence.contracts.decision_outcome_contract import (
    OutcomeDirection,
    OutcomeLineage,
    OutcomeStatus,
)
from applications.trading_intelligence.projections.calibration_band import CalibrationBand

# Deterministic bands. Lower bound inclusive; upper bound exclusive for
# every band except the last, whose 1.00 upper bound is inclusive. No
# other scale is used anywhere -- the repository has no prior score-band
# convention (verified 2026-09-10), so this is the single definition.
_BAND_SPECS: Tuple[Tuple[str, float, float], ...] = (
    ("0.50-0.55", 0.50, 0.55),
    ("0.55-0.60", 0.55, 0.60),
    ("0.60-0.65", 0.60, 0.65),
    ("0.65-1.00", 0.65, 1.00),
)

BAND_LABELS: Tuple[str, ...] = tuple(spec[0] for spec in _BAND_SPECS)

_FINAL_BAND_INDEX = len(_BAND_SPECS) - 1


def _band_index(score: float) -> Optional[int]:
    """Index of the band ``score`` falls in, or ``None`` when it lies
    outside every band (``score < 0.50`` or ``score > 1.00``)."""
    for index, (_, lower, upper) in enumerate(_BAND_SPECS):
        if index == _FINAL_BAND_INDEX:
            if lower <= score <= upper:
                return index
        elif lower <= score < upper:
            return index
    return None


class DecisionCalibrationQueryService:
    """Stateless. Mirrors ``CandidateDecisionQueryService``'s no-arg /
    single-method shape -- construct it and call :meth:`get_calibration`
    with data the caller already has."""

    def get_calibration(
        self, lineage: OutcomeLineage
    ) -> Tuple[CalibrationBand, ...]:
        """Return exactly one :class:`CalibrationBand` per entry in
        :data:`BAND_LABELS`, in that fixed order. Each band's ``wins`` /
        ``losses`` are independent tallies -- nothing is summed across
        bands."""
        wins: List[int] = [0] * len(_BAND_SPECS)
        losses: List[int] = [0] * len(_BAND_SPECS)

        for outcome in lineage.decisions:
            if outcome.status is not OutcomeStatus.CLOSED:
                continue
            score = outcome.entry_ensemble_score
            if score is None:
                continue
            direction = outcome.outcome_direction
            if direction is not OutcomeDirection.WIN and direction is not OutcomeDirection.LOSS:
                continue
            index = _band_index(score)
            if index is None:
                continue
            if direction is OutcomeDirection.WIN:
                wins[index] += 1
            else:
                losses[index] += 1

        return tuple(
            CalibrationBand(label=label, wins=wins[index], losses=losses[index])
            for index, label in enumerate(BAND_LABELS)
        )
