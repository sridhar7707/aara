"""One decision's calibration-band lookup result -- Decision Center's
Decision Quality Cross-Linking sprint.

Framework-independent, stdlib-only: no bot, dashboard, scheduler, database,
ledger, sentinel_engine, or Gradio import. Wraps an existing
:class:`CalibrationBand` (services/decision_calibration_query_service.py)
unchanged, plus the total outcome count across ALL bands so a consumer can
apply the SAME ``CALIBRATION_MIN_OUTCOMES``-based display floor Performance
& Learning already uses (ui/performance_learning/screen.py) -- this module
computes nothing new about wins/losses/win_rate; both are carried through
verbatim from the frozen service.
"""
from dataclasses import dataclass

from applications.trading_intelligence.projections.calibration_band import CalibrationBand


@dataclass(frozen=True)
class CalibrationBandContext:
    """``band`` is the CalibrationBand a decision's own MODEL_ENSEMBLE.ensemble
    score falls into (see services/decision_calibration_query_service.py's
    ``get_band_for_score``). ``total_outcomes`` is the qualifying CLOSED
    WIN/LOSS outcome count summed across ALL FOUR bands -- not just this
    one -- matching Performance & Learning's own
    ``calibration_total_outcomes`` definition exactly, so the same
    CALIBRATION_MIN_OUTCOMES floor decides whether a real per-band figure is
    shown anywhere in this product."""

    band: CalibrationBand
    total_outcomes: int
