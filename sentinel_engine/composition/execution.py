"""ADR-065-authorized temporary composition boundary for
DecisionService.record_execution() (execution-outcome reporting).

Constructs the process-scoped DecisionService required by the ADR-065
bot-to-Sentinel execution-outcome-reporting flow, using a minimal in-memory
LedgerStore/ProjectionRepository pair dedicated to this boundary alone.
Following ADR-013/ADR-045's established convention -- each integration gets
its own dedicated, independent temporary repository pair, never reusing
another ADR's instance -- this module constructs its own pair rather than
importing or extending sentinel_engine/composition/evidence.py or
governance.py. This is not the production Sentinel repository architecture;
that choice remains deferred to ADR-004.

The accessor is deliberately named for its one authorized purpose
(execution-outcome reporting), not as a general-purpose DecisionService
composition root -- mirroring ADR-013 SS7's and ADR-045 SS10's own
statement that their modules "shall not become a general-purpose Sentinel
composition root."
"""
from typing import Dict, List, Optional

from sentinel_engine.events.event import Event
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository
from sentinel_engine.services.decision_service import DecisionService


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
_decision_service = DecisionService(_ledger_repository, _projection_repository)


def get_decision_service_for_execution_reporting() -> DecisionService:
    return _decision_service
