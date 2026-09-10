"""Pure query boundary for the "realized outcomes by entry market regime"
breakdown.

``DecisionRegimeOutcomeQueryService`` folds an already-built Wave 2A
:class:`OutcomeLineage` (produced unchanged by
``DecisionOutcomeQueryService``) into one :class:`RegimeOutcomeRow` per
distinct entry regime, each carrying a realized WIN / LOSS tally.

Purity contract -- this module has NONE of:

* database or file access, network, or any I/O;
* a Gradio / bot / dashboard / scheduler / sentinel_engine import;
* a clock, randomness, or any other non-deterministic input.

Eligibility mirrors ``DecisionCalibrationQueryService`` (Sprint 4 Item #1)
exactly, minus the ensemble-score gate, which does not apply here. An
outcome is counted only when

* ``status is OutcomeStatus.CLOSED``;
* ``outcome_direction`` is ``WIN`` or ``LOSS``.

OPEN / PARTIAL / AMBIGUOUS outcomes, FLAT outcomes, and a missing
direction are excluded. ``entry_regime`` is used verbatim (no
normalisation, no invented vocabulary); ``None`` / blank lands in the
explicit :data:`REGIME_NOT_RECORDED_LABEL` bucket, never dropped.

This is a historical realized-outcome breakdown -- it makes no
predictive, probability, or calibration claim, and a regime appearing
with a higher win rate is not evidence of a causal effect.
"""
from typing import Dict, List, Tuple

from applications.trading_intelligence.contracts.decision_outcome_contract import (
    OutcomeDirection,
    OutcomeLineage,
    OutcomeStatus,
)
from applications.trading_intelligence.projections.regime_outcome_row import (
    REGIME_NOT_RECORDED_LABEL,
    RegimeOutcomeRow,
)


class DecisionRegimeOutcomeQueryService:
    """Stateless. Mirrors ``DecisionCalibrationQueryService``'s no-arg /
    single-method shape -- construct it and call
    :meth:`get_regime_outcomes` with data the caller already has."""

    def get_regime_outcomes(
        self, lineage: OutcomeLineage
    ) -> Tuple[RegimeOutcomeRow, ...]:
        """One :class:`RegimeOutcomeRow` per regime that carried at least
        one eligible (CLOSED, WIN/LOSS) outcome. Real regime labels are
        sorted alphabetically; the "not recorded" bucket, when present, is
        always last. Each row's ``wins`` / ``losses`` are independent
        tallies -- nothing is summed across regimes."""
        wins: Dict[str, int] = {}
        losses: Dict[str, int] = {}

        for outcome in lineage.decisions:
            if outcome.status is not OutcomeStatus.CLOSED:
                continue
            direction = outcome.outcome_direction
            if direction is not OutcomeDirection.WIN and direction is not OutcomeDirection.LOSS:
                continue
            label = (outcome.entry_regime or "").strip() or REGIME_NOT_RECORDED_LABEL
            if direction is OutcomeDirection.WIN:
                wins[label] = wins.get(label, 0) + 1
            else:
                losses[label] = losses.get(label, 0) + 1

        labels = set(wins) | set(losses)
        real = sorted(label for label in labels if label != REGIME_NOT_RECORDED_LABEL)
        ordered: List[str] = real
        if REGIME_NOT_RECORDED_LABEL in labels:
            ordered = real + [REGIME_NOT_RECORDED_LABEL]

        return tuple(
            RegimeOutcomeRow(
                regime=label,
                wins=wins.get(label, 0),
                losses=losses.get(label, 0),
            )
            for label in ordered
        )
