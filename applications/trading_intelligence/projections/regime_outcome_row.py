"""One row of the "realized outcomes by entry market regime" breakdown.

Framework-independent, stdlib-only: no bot, dashboard, scheduler,
database, ledger, sentinel_engine, or sentinel import; no Gradio. Built
by services/decision_regime_outcome_query_service.py from already-derived
Wave 2A ``DecisionOutcome`` records -- it recomputes nothing about the
outcomes themselves (Wave 2A owns WIN/LOSS/FLAT and CLOSED semantics) and
invents no regime vocabulary (the ``entry_regime`` string is used
verbatim, exactly as every other Trading Intelligence surface renders a
regime).

A ``RegimeOutcomeRow`` is a plain historical tally: how many CLOSED BUY
decisions whose recorded entry regime was ``regime`` went on to a
realized WIN vs LOSS. It is a count only -- not a predictive measure, not
a probability, not a calibration, and it is not evidence that the regime
caused the outcome. FLAT outcomes and any outcome without a recorded
direction are never counted, so ``n == wins + losses`` always holds.
"""
from dataclasses import dataclass
from typing import Optional

# The explicit bucket for a decision whose entry regime was never recorded
# (``None`` / blank). Rendered like any "not recorded" state elsewhere in
# Performance & Learning; the row is never silently dropped.
REGIME_NOT_RECORDED_LABEL = "Not recorded"


@dataclass(frozen=True)
class RegimeOutcomeRow:
    """Realized WIN/LOSS tally for one entry-regime group.

    ``regime`` is the verbatim ``DecisionOutcome.entry_regime`` string, or
    :data:`REGIME_NOT_RECORDED_LABEL` when it was ``None`` / blank.
    ``wins`` and ``losses`` are counts of CLOSED BUY decision outcomes in
    that group.
    """

    regime: str
    wins: int
    losses: int

    @property
    def n(self) -> int:
        """Total counted outcomes in this group -- always ``wins + losses``
        (FLAT / direction-less outcomes are excluded upstream)."""
        return self.wins + self.losses

    @property
    def win_rate(self) -> Optional[float]:
        """``wins / (wins + losses)``, or ``None`` when the group counted no
        outcomes. ``None`` -- never ``0.0`` -- for an empty group, so a
        group with no history is never shown as a 0% win rate."""
        total = self.wins + self.losses
        if total == 0:
            return None
        return self.wins / total
