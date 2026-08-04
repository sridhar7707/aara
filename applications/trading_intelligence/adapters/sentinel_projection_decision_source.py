"""Read-only DecisionSource implementation backed by a Sentinel Engine
ProjectionRepository.

Per TRADING_INTELLIGENCE_SENTINEL_READ_INTEGRATION_DESIGN.md's recommended
direction (Option A): wraps a ProjectionRepository directly rather than
introducing a new sentinel_engine-side read service. No database, no ledger,
no bot, no dashboard connection -- only sentinel_engine's own storage-agnostic
repository abstraction.

list_decisions() takes an explicit decision_ids list rather than enumerating
"all" projections -- ProjectionRepository only exposes get(decision_id)/save(),
with no enumeration method, and this adapter must not add one to Sentinel
Engine. See DecisionSource's own docstring for the same constraint stated at
the abstraction level.
"""
from typing import List, Optional

from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.repositories.projection_repository import ProjectionRepository

from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.services.decision_query_service import DecisionSource


class SentinelProjectionDecisionSource(DecisionSource):
    def __init__(self, projection_repository: ProjectionRepository):
        self._projection_repository = projection_repository

    def get_decision(self, decision_id: str) -> Optional[DecisionContract]:
        projection = self._projection_repository.get(decision_id)
        if projection is None:
            return None
        return self._to_contract(projection)

    def list_decisions(self, decision_ids: List[str]) -> List[DecisionContract]:
        contracts = []
        for decision_id in decision_ids:
            projection = self._projection_repository.get(decision_id)
            if projection is not None:
                contracts.append(self._to_contract(projection))
        return contracts

    @staticmethod
    def _to_contract(projection: DecisionProjection) -> DecisionContract:
        return DecisionContract(
            decision_id=projection.decision_id,
            symbol=projection.symbol,
            action=projection.action,
            status=projection.status,
            confidence=projection.confidence,
            evidence_reference=projection.evidence_reference,
            risk_reference=projection.risk_reference,
            updated_at=projection.updated_at,
        )
