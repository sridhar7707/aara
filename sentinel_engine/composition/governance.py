"""ADR-045 SS2.1-authorized temporary composition boundary for
GovernanceService.

Constructs the process-scoped GovernanceService required by the ADR-045
trust-decision governance-evaluation flow, using a minimal in-memory
LedgerStore/ProjectionRepository pair dedicated to this boundary alone.
Per ADR-045: non-production, non-durable, process-local, and independent
of sentinel_engine/composition/evidence.py -- ADR-014 SS8 forbids reusing
that module's singleton or repositories for GovernanceService, so this
module constructs its own, separate pair rather than importing or
extending the Evidence composition boundary. This is not the production
Sentinel repository architecture -- that choice remains deferred to
ADR-004.
"""
from typing import Dict, List, Optional

from sentinel_engine.events.event import Event
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository
from sentinel_engine.services.governance_service import GovernanceService


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
_governance_service = GovernanceService(_ledger_repository, _projection_repository)


def get_governance_service() -> GovernanceService:
    return _governance_service
