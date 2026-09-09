"""ADR-067 SS3.C — one shared, process-scoped Sentinel composition pair for the
causal decision lifecycle.

Constructs exactly one temporary in-memory LedgerStore + ProjectionRepository +
LedgerRepository, and from that single pair one DecisionService, one
EvidenceService, and one GovernanceService. Sharing the pair is what lets a
single DecisionProjection walk the full lifecycle
DECISION_CREATED -> EVIDENCE_ATTACHED -> GOVERNANCE_EVALUATED -> DECISION_EXECUTED
(impossible while each service had its own dedicated, never-seeded pair).

ADR-067 SS12 narrowly supersedes the "dedicated, non-shared instance" language of
ADR-013 SS7, ADR-014 SS8, and ADR-045 SS2.1 -- only for this shared pair, only for
the causal lifecycle. Event *content* remains governed by its originating ADR
(evidence by ADR-009/012/013, governance evaluation by ADR-014/045, execution
outcome by ADR-065); this module governs only the shared pair's existence and the
DecisionProjection lifecycle across those events. All other provisions of those
ADRs remain in force -- in particular ADR-045 SS3's prohibition on operative
Policy registration and record_approval() wiring, which this module does not
touch.

Not the production Sentinel repository architecture; ADR-004 remains deferred.
Process-local and non-durable: separate OS processes (CLI vs scheduler/HTTP)
keep separate in-memory state, exactly as ADR-013 SS14 / ADR-045 already accept.
No bot import; bot -> sentinel_engine only.
"""
from typing import Dict, List, Optional

from sentinel_engine.events.event import Event
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.services.governance_service import GovernanceService


class _LifecycleLedgerStore(LedgerStore):
    def __init__(self):
        self._events: List[Event] = []

    def append(self, event: Event) -> None:
        self._events.append(event)

    def read_all(self) -> List[Event]:
        return list(self._events)


class _LifecycleProjectionRepository(ProjectionRepository):
    def __init__(self):
        self._projections: Dict[str, DecisionProjection] = {}

    def save(self, projection: DecisionProjection) -> None:
        self._projections[projection.decision_id] = projection

    def get(self, decision_id: str) -> Optional[DecisionProjection]:
        return self._projections.get(decision_id)


_ledger_repository = LedgerRepository(_LifecycleLedgerStore())
_projection_repository = _LifecycleProjectionRepository()
_decision_service = DecisionService(_ledger_repository, _projection_repository)
_evidence_service = EvidenceService(_ledger_repository, _projection_repository)
_governance_service = GovernanceService(_ledger_repository, _projection_repository)


def get_decision_service() -> DecisionService:
    return _decision_service


def get_evidence_service() -> EvidenceService:
    return _evidence_service


def get_governance_service() -> GovernanceService:
    return _governance_service
