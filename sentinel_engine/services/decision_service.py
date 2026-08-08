"""Coordinates Decision domain objects: creates events, persists them via
repository abstractions, and maintains the DecisionProjection read model.

Storage-implementation independent: only depends on the repository
abstractions from sentinel_engine.repositories, never on a concrete backend.
"""
import uuid
from typing import Optional

from sentinel_engine.domain.decision import Decision
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.events.event import Event
from sentinel_engine.events.event_types import EventType
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository


class DecisionService:
    def __init__(
        self,
        ledger_repository: LedgerRepository,
        projection_repository: ProjectionRepository,
    ):
        self._ledger_repository = ledger_repository
        self._projection_repository = projection_repository

    def create_decision(self, decision: Decision) -> Event:
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.DECISION_CREATED,
            created_at=decision.timestamp,
            payload={
                "decision_id": decision.decision_id,
                "symbol": decision.symbol,
                "action": decision.action,
                "confidence": decision.confidence,
                "evidence_reference": decision.evidence_reference,
                "risk_reference": decision.risk_reference,
            },
        )
        self._ledger_repository.save_event(event)

        projection = DecisionProjection(
            decision_id=decision.decision_id,
            symbol=decision.symbol,
            action=decision.action,
            status=DecisionState.DECISION_CREATED,
            confidence=decision.confidence,
            evidence_reference=decision.evidence_reference,
            risk_reference=decision.risk_reference,
            updated_at=decision.timestamp,
        )
        self._projection_repository.save(projection)

        return event

    def get_projection(self, decision_id: str) -> Optional[DecisionProjection]:
        return self._projection_repository.get(decision_id)
