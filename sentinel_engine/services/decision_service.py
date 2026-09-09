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
                "horizon": decision.horizon,
                "desired_allocation": decision.desired_allocation,
                "minimum_viable_allocation": decision.minimum_viable_allocation,
                "uncertainty": decision.uncertainty,
                "thesis": decision.thesis,
                "counterfactual": decision.counterfactual,
                "action_source": decision.action_source,
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

    def record_execution(self, decision_id: str, payload: dict) -> Optional[Event]:
        """ADR-065: records an already-completed execution outcome (a
        successful fill, a risk rejection, or an executor/order failure --
        distinguished by payload["outcome"], not by separate DecisionState
        members) as a DECISION_EXECUTED event, and advances the projection.

        Idempotent per decision_id: if a DECISION_EXECUTED event already
        exists for this decision_id in this ledger, returns None without
        appending a second one or re-advancing the projection. This is the
        ADR-065-authorized idempotency guard -- it protects against a
        retried report call producing a duplicate ledger event, not against
        a duplicate trade (RiskManager/PaperExecutor are never called by
        this method or anything it calls).

        Mirrors GovernanceService.evaluate_policy()/record_approval(): the
        event is constructed here (not by the caller or the adapter), saved
        to the ledger, and the projection is advanced via
        ProjectionRepository.advance_status(), which itself no-ops if no
        projection was ever seeded for decision_id -- the same established
        behavior ADR-013/ADR-045 already rely on for EVIDENCE_ATTACHED and
        GOVERNANCE_EVALUATED.
        """
        already_recorded = any(
            existing.event_type == EventType.DECISION_EXECUTED
            and existing.payload.get("decision_id") == decision_id
            for existing in self._ledger_repository.get_events()
        )
        if already_recorded:
            return None

        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.DECISION_EXECUTED,
            created_at=payload["timestamp"],
            payload=payload,
        )
        self._ledger_repository.save_event(event)

        self._projection_repository.advance_status(
            decision_id, DecisionState.DECISION_EXECUTED, payload["timestamp"],
        )

        return event
