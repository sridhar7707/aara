"""Composition root for the AARA Wealth Intelligence application.

This is the only place in the codebase that constructs sentinel_engine
repositories, services, SentinelEngine, queries, or the investor-facing
application/presentation/UI layers. Every other module in this product
(and every sentinel_engine module) receives its collaborators through
dependency injection instead of constructing them itself.

Backend note: the LedgerStore/ProjectionRepository implementations below
are minimal in-memory placeholders, not a production persistence choice.
ADR-004 (sentinel-ledger-ownership-strategy) explicitly defers which
backend sentinel_engine's ledger should use until Phase 1A validation
completes, and states "No sentinel_engine/ledger/ backend implementation
should be started until this ADR is superseded." These classes live here
in applications/wealth_intelligence/, not in sentinel_engine/, purely so
build_application() has something concrete to wire today; they are
expected to be replaced once ADR-004 is resolved.
"""
from typing import Dict, List, Optional

from sentinel_engine.events.event import Event
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.queries.decision_center_query import DecisionCenterQuery
from sentinel_engine.queries.decision_query import DecisionQuery
from sentinel_engine.queries.morning_brief_query import MorningBriefQuery
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.services.governance_service import GovernanceService
from sentinel_engine.services.sentinel_engine import SentinelEngine

from applications.wealth_intelligence.application.investor_workspace import InvestorWorkspaceFacade
from applications.wealth_intelligence.presentation.investor_presenter import InvestorPresenter
from applications.wealth_intelligence.ui.investor_workspace import InvestorWorkspaceUI


class _InMemoryLedgerStore(LedgerStore):
    def __init__(self):
        self._events: List[Event] = []

    def append(self, event: Event) -> None:
        self._events.append(event)

    def read_all(self) -> List[Event]:
        return list(self._events)


class _InMemoryProjectionRepository(ProjectionRepository):
    def __init__(self):
        self._projections: Dict[str, DecisionProjection] = {}

    def save(self, projection: DecisionProjection) -> None:
        self._projections[projection.decision_id] = projection

    def get(self, decision_id: str) -> Optional[DecisionProjection]:
        return self._projections.get(decision_id)


def build_application() -> InvestorWorkspaceUI:
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()

    decision_service = DecisionService(ledger_repository, projection_repository)
    evidence_service = EvidenceService(ledger_repository, projection_repository)
    governance_service = GovernanceService(ledger_repository, projection_repository)

    # Write-side facade: not yet consumed by any UI, but composed here so the
    # full read/write object graph exists in one place per this commit's scope.
    SentinelEngine(decision_service, evidence_service, governance_service)

    decision_query = DecisionQuery(ledger_repository, projection_repository)
    morning_brief_query = MorningBriefQuery(ledger_repository, projection_repository)
    decision_center_query = DecisionCenterQuery(ledger_repository, projection_repository)

    workspace_facade = InvestorWorkspaceFacade(
        morning_brief_query, decision_query, decision_center_query,
    )
    presenter = InvestorPresenter(workspace_facade)

    return InvestorWorkspaceUI(presenter)
