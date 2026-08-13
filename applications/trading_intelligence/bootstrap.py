"""Composition root for the AARA Trading Intelligence application.

Only place in this product that constructs sentinel_engine repositories,
services, SentinelEngine, or the Trading Intelligence read-side adapter/
query-service/controller/UI chain. Every other module receives its
collaborators through dependency injection instead of constructing them
itself, mirroring applications.wealth_intelligence.bootstrap's pattern.

Backend note: the LedgerStore/ProjectionRepository implementations below
are minimal in-memory placeholders, not a production persistence choice.
ADR-004 (sentinel-ledger-ownership-strategy) explicitly defers which
backend sentinel_engine's ledger should use until Phase 1A validation
completes. These classes live here in applications/trading_intelligence/,
not in sentinel_engine/, purely so build_application() has something
concrete to wire today; they are expected to be replaced once ADR-004 is
resolved.

Seed data: Decision Center is read-only (SentinelProjectionDecisionSource
never calls ProjectionRepository.save() -- see its own tests), so this
module seeds a handful of decisions through the real Sentinel Engine
write path (DecisionService/EvidenceService/GovernanceService via the
SentinelEngine facade) before building the read-side chain -- the same
way a real caller (a future signal-generation adapter) would produce
decisions. This is illustrative seed data for a first visible slice, not
real trading data.
"""
from datetime import datetime
from typing import Dict, List, Optional

from sentinel_engine.domain.decision import Decision
from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.events.event import Event
from sentinel_engine.governance.approval import Approval
from sentinel_engine.governance.approval_status import ApprovalStatus
from sentinel_engine.governance.policy import Policy
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.queries.decision_query import DecisionQuery
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.services.governance_service import GovernanceService
from sentinel_engine.services.sentinel_engine import SentinelEngine

from applications.trading_intelligence.adapters.sentinel_evidence_source import SentinelEvidenceSource
from applications.trading_intelligence.adapters.sentinel_governance_source import (
    SentinelGovernanceSource,
)
from applications.trading_intelligence.adapters.sentinel_projection_decision_source import (
    SentinelProjectionDecisionSource,
)
from applications.trading_intelligence.services.decision_evidence_query_service import (
    DecisionEvidenceQueryService,
)
from applications.trading_intelligence.services.decision_governance_query_service import (
    DecisionGovernanceQueryService,
)
from applications.trading_intelligence.services.decision_query_service import DecisionQueryService
from applications.trading_intelligence.ui.decision_center.controller import DecisionCenterController
from applications.trading_intelligence.ui.decision_center.gradio_view import DecisionCenterUI


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


def _seed_decisions(engine: SentinelEngine) -> List[str]:
    """Drive three decisions through the real Sentinel Engine write path,
    each stopped at a different lifecycle stage, so the first visible
    Decision Center screen demonstrates DecisionState's full range with
    genuine engine-produced data rather than hand-built projections.

    Each decision gets its own fixed timestamp(s), staggered across a single
    illustrative trading morning and advancing chronologically within a
    decision's own lifecycle (create -> evidence -> approval), rather than
    every event across all three decisions sharing one identical instant --
    still fully deterministic (fixed datetime literals, no randomness), just
    no longer visually flat. confidence is similarly given a genuine spread
    (0.54 / 0.71 / 0.91) instead of clustering in the 60-90% band. Governance
    evaluation's own displayed timestamp remains real-clock
    (GovernanceService.evaluate_policy() stamps datetime.utcnow() internally,
    not a caller-supplied value) -- unaffected by any of this, and out of
    scope to change without touching sentinel_engine."""
    decision_ids: List[str] = []

    # dec-seed-001: DECISION_CREATED only.
    created_001 = datetime(2026, 8, 8, 8, 12, 0)
    engine.create_decision(Decision(
        decision_id="dec-seed-001", symbol="AAPL", action="BUY",
        timestamp=created_001, confidence=0.71,
        evidence_reference="evidence-seed-001", risk_reference="risk-seed-001",
    ))
    decision_ids.append("dec-seed-001")

    # dec-seed-002: through EVIDENCE_ATTACHED.
    created_002 = datetime(2026, 8, 8, 8, 47, 0)
    evidence_attached_002 = datetime(2026, 8, 8, 8, 52, 0)
    engine.create_decision(Decision(
        decision_id="dec-seed-002", symbol="MSFT", action="HOLD",
        timestamp=created_002, confidence=0.54,
        evidence_reference="evidence-seed-002", risk_reference="risk-seed-002",
    ))
    engine.attach_evidence("dec-seed-002", Evidence(
        evidence_id="ev-seed-002", evidence_type="NEWS_SENTIMENT", source="newsapi",
        data={"score": 0.58}, collected_at=evidence_attached_002,
    ))
    decision_ids.append("dec-seed-002")

    # dec-seed-003: through APPROVAL_RECORDED (full lifecycle).
    created_003 = datetime(2026, 8, 8, 9, 5, 0)
    evidence_attached_003 = datetime(2026, 8, 8, 9, 11, 0)
    approved_003 = datetime(2026, 8, 8, 9, 34, 0)
    engine.create_decision(Decision(
        decision_id="dec-seed-003", symbol="NVDA", action="SELL",
        timestamp=created_003, confidence=0.91,
        evidence_reference="evidence-seed-003", risk_reference="risk-seed-003",
    ))
    engine.attach_evidence("dec-seed-003", Evidence(
        evidence_id="ev-seed-003", evidence_type="NEWS_SENTIMENT", source="newsapi",
        data={"score": 0.74}, collected_at=evidence_attached_003,
    ))
    engine.register_policy(Policy(
        policy_id="pol-seed-001", name="max_position_size",
        description="Caps single-position exposure as a percent of portfolio value.",
        enabled=True,
    ))
    engine.evaluate_policy("dec-seed-003", "pol-seed-001")
    engine.record_approval(Approval(
        approval_id="apr-seed-001", decision_id="dec-seed-003",
        status=ApprovalStatus.APPROVED, approved_by="risk_officer", timestamp=approved_003,
    ))
    decision_ids.append("dec-seed-003")

    return decision_ids


def build_application() -> DecisionCenterUI:
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()

    decision_service = DecisionService(ledger_repository, projection_repository)
    evidence_service = EvidenceService(ledger_repository, projection_repository)
    governance_service = GovernanceService(ledger_repository, projection_repository)
    engine = SentinelEngine(decision_service, evidence_service, governance_service)

    decision_ids = _seed_decisions(engine)

    source = SentinelProjectionDecisionSource(projection_repository)
    query_service = DecisionQueryService(source)

    decision_query = DecisionQuery(ledger_repository, projection_repository)
    evidence_source = SentinelEvidenceSource(decision_query)
    evidence_query_service = DecisionEvidenceQueryService(evidence_source)

    governance_source = SentinelGovernanceSource(decision_query)
    governance_query_service = DecisionGovernanceQueryService(governance_source)

    controller = DecisionCenterController(
        query_service, evidence_query_service, governance_query_service,
    )

    return DecisionCenterUI(controller, decision_ids)
