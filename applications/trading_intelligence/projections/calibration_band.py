"""One row of the historical "outcome by ensemble score" view.

Framework-independent, stdlib-only: no bot, dashboard, scheduler,
database, ledger, sentinel_engine, or sentinel import; no Gradio. Built
by services/decision_calibration_query_service.py from already-derived
Wave 2A ``DecisionOutcome`` records -- it recomputes nothing about the
outcomes themselves (Wave 2A owns WIN/LOSS/FLAT and CLOSED semantics).

A ``CalibrationBand`` is a plain realized tally: how many CLOSED BUY
decisions whose recorded entry ensemble score fell in this band went on
to a realized WIN vs LOSS. It is a historical count only -- not a
predictive-accuracy measure, not a probability statement, and not a claim
of statistical significance. FLAT outcomes and any outcome without a
recorded direction or score are never counted (they are filtered out
before a band is built), so ``n == wins + losses`` always holds.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CalibrationBand:
    """Realized WIN/LOSS tally for one ensemble-score band.

    ``label`` is the band's score range (lower bound inclusive; upper
    bound exclusive except for the final band, whose upper bound of 1.00
    is inclusive). ``wins`` and ``losses`` are counts of CLOSED BUY
    decision outcomes whose ``entry_ensemble_score`` fell in this band.
    """

    label: str
    wins: int
    losses: int

    @property
    def n(self) -> int:
        """Total counted outcomes in this band -- always ``wins + losses``
        (FLAT / direction-less / score-less outcomes are excluded upstream)."""
        return self.wins + self.losses

    @property
    def win_rate(self) -> Optional[float]:
        """``wins / (wins + losses)``, or ``None`` when the band counted no
        outcomes. ``None`` -- never ``0.0`` -- for an empty band, so a band
        with no history is never shown as a 0% win rate."""
        total = self.wins + self.losses
        if total == 0:
            return None
        return self.wins / total
