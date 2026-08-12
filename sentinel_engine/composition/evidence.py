"""ADR-013-authorized temporary composition boundary for EvidenceService.

Constructs the process-scoped EvidenceService required by the ADR-009
trust-decision evidence flow, using a minimal in-memory LedgerStore/
ProjectionRepository pair. Per ADR-013: non-production, non-durable,
process-local. This is not the production Sentinel repository
architecture -- that choice remains deferred to ADR-004. The temporary
repositories exist solely because no existing implementation legally
satisfies EvidenceService's mandatory constructor dependencies.
"""
from typing import Dict, List, Optional

from sentinel_engine.events.event import Event
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository
from sentinel_engine.services.evidence_service import EvidenceService


class _TemporaryLedgerStore(LedgerStore):
    def __init__(self):
        self._events: List[Event] = []

    def append(self, event: Event) -> None:
        self._events.append(event)

    def read_all(self) -> List[Event]:
        return list(self._events)


class _TemporaryProjectionRepository(ProjectionRepository):
    def __init__(self):
        self._projections: Dict[str, DecisionProjection] = {}

    def save(self, projection: DecisionProjection) -> None:
        self._projections[projection.decision_id] = projection

    def get(self, decision_id: str) -> Optional[DecisionProjection]:
        return self._projections.get(decision_id)


_ledger_repository = LedgerRepository(_TemporaryLedgerStore())
_projection_repository = _TemporaryProjectionRepository()
_evidence_service = EvidenceService(_ledger_repository, _projection_repository)


def get_evidence_service() -> EvidenceService:
    return _evidence_service
