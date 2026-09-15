"""Decision Quality Cross-Linking -- read-only collaborator backing Decision
Center's calibration-band context (which historical confidence band a
decision's own MODEL_ENSEMBLE.ensemble score falls in).

Mirrors trades_db_decision_outcome_source.py's own "Error translation" rule
exactly: a genuinely non-HEALTHY DecisionOutcomeQueryService.get_lineage()
read becomes a TradingIntelligenceReadError; a HEALTHY read is then folded
through the frozen DecisionCalibrationQueryService verbatim.

Adds no second outcome-derivation or calibration-banding path. The SAME
DecisionOutcomeQueryService.get_lineage() this product's Decision -> Outcome
linkage and Performance & Learning already exercise, and the SAME
DecisionCalibrationQueryService.get_calibration() / get_band_for_score()
Performance & Learning's Model Confidence Calibration area already
exercises, are reused unchanged -- this module computes nothing new about
band boundaries, win/loss counts, or win rate.
"""
from __future__ import annotations

from typing import Optional

from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.calibration_band_context import (
    CalibrationBandContext,
)
from applications.trading_intelligence.services.decision_calibration_query_service import (
    DecisionCalibrationQueryService,
)
from applications.trading_intelligence.services.decision_outcome_query_service import (
    DecisionOutcomeQueryService,
)


class TradesDbDecisionCalibrationSource:
    def __init__(
        self,
        outcome_query_service: DecisionOutcomeQueryService,
        calibration_query_service: DecisionCalibrationQueryService,
    ):
        self._outcome_query_service = outcome_query_service
        self._calibration_query_service = calibration_query_service

    def get_band_context(self, score: Optional[float]) -> Optional[CalibrationBandContext]:
        """The real CalibrationBandContext for `score`, or None when `score`
        is None, lies outside every band, or the read is HEALTHY but yields
        no matching band (mirrors get_band_for_score's own None cases).
        Raises TradingIntelligenceReadError only for a genuinely non-HEALTHY
        lineage read -- checked via get_lineage()'s own ReadResult.health,
        matching TradesDbDecisionOutcomeSource.get_outcome()'s identical
        rationale."""
        lineage_result = self._outcome_query_service.get_lineage()
        if not lineage_result.health.is_healthy:
            raise TradingIntelligenceReadError(
                f"decision calibration read failed: {lineage_result.health.status.name}"
            )
        lineage = lineage_result.value
        band = self._calibration_query_service.get_band_for_score(lineage, score)
        if band is None:
            return None
        bands = self._calibration_query_service.get_calibration(lineage)
        total_outcomes = sum(b.n for b in bands)
        return CalibrationBandContext(band=band, total_outcomes=total_outcomes)
