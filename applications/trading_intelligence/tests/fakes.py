"""Shared test fakes for applications.trading_intelligence integration tests.

Not production code -- test infrastructure only. Suitable for wiring the
real SentinelProjectionDecisionSource -> DecisionQueryService ->
DecisionCenterController chain against something that behaves like a real
ProjectionRepository backend without being one (no database, no persistence
beyond the life of the test).
"""
from typing import Dict, Optional

from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.repositories.projection_repository import ProjectionRepository


class InMemoryProjectionRepository(ProjectionRepository):
    def __init__(self):
        self._projections: Dict[str, DecisionProjection] = {}

    def save(self, projection: DecisionProjection) -> None:
        self._projections[projection.decision_id] = projection

    def get(self, decision_id: str) -> Optional[DecisionProjection]:
        return self._projections.get(decision_id)
