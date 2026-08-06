"""Associates Evidence objects with decisions, kept separate from Decision
domain logic (only decision_id references cross the boundary).

Association state stays in-memory and private. Emits EVIDENCE_ATTACHED
domain events through LedgerRepository and advances the decision's
projection only through ProjectionRepository.advance_status() — this
service never constructs, mutates, or saves a DecisionProjection itself.
"""
import uuid
from typing import Dict, List

from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.events.event import Event
from sentinel_engine.events.event_types import EventType
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository


class EvidenceService:
    def __init__(
        self,
        ledger_repository: LedgerRepository,
        projection_repository: ProjectionRepository,
    ):
        self._evidence_by_decision: Dict[str, List[Evidence]] = {}
        self._ledger_repository = ledger_repository
        self._projection_repository = projection_repository

    def associate_evidence(self, decision_id: str, evidence: Evidence) -> None:
        self._evidence_by_decision.setdefault(decision_id, []).append(evidence)

        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.EVIDENCE_ATTACHED,
            created_at=evidence.collected_at,
            payload={
                "decision_id": decision_id,
                "evidence_id": evidence.evidence_id,
                "evidence_type": evidence.evidence_type,
                "source": evidence.source,
            },
        )
        self._ledger_repository.save_event(event)

        self._projection_repository.advance_status(
            decision_id, EventType.EVIDENCE_ATTACHED.value, evidence.collected_at,
        )

    def get_evidence_for_decision(self, decision_id: str) -> List[Evidence]:
        return list(self._evidence_by_decision.get(decision_id, []))
