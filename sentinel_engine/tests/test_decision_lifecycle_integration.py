"""End-to-end proof that a decision's full lifecycle — creation, evidence
attachment, governance evaluation, and approval — is driven entirely through
the SentinelEngine facade and produces an ordered, consistent ledger trail.
"""
import datetime

from sentinel_engine.services.sentinel_engine import SentinelEngine
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.services.governance_service import GovernanceService
from sentinel_engine.domain.decision import Decision
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.governance.policy import Policy
from sentinel_engine.governance.approval import Approval
from sentinel_engine.governance.approval_status import ApprovalStatus
from sentinel_engine.events.event_types import EventType
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository


class _InMemoryLedgerStore(LedgerStore):
    def __init__(self):
        self._events = []

    def append(self, event):
        self._events.append(event)

    def read_all(self):
        return list(self._events)


class _InMemoryProjectionRepository(ProjectionRepository):
    def __init__(self):
        self._projections = {}

    def save(self, projection):
        self._projections[projection.decision_id] = projection

    def get(self, decision_id):
        return self._projections.get(decision_id)


def _make_engine():
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()
    decision_service = DecisionService(ledger_repository, projection_repository)
    evidence_service = EvidenceService(ledger_repository, projection_repository)
    governance_service = GovernanceService(ledger_repository, projection_repository)
    engine = SentinelEngine(decision_service, evidence_service, governance_service)
    return engine, ledger_repository


def test_decision_lifecycle_produces_ordered_ledger_trail_and_final_projection():
    engine, ledger_repository = _make_engine()

    decision_id = "dec-001"
    # GovernanceService.evaluate_policy() stamps its event with the real
    # wall clock (datetime.utcnow()), so decision/evidence timestamps are
    # anchored just before "now" and the approval timestamp is captured
    # just after evaluate_policy() runs, keeping every step monotonic
    # without depending on hardcoded values racing the real clock.
    now = datetime.datetime.utcnow()
    decision = Decision(
        decision_id=decision_id,
        symbol="AAPL",
        action="BUY",
        timestamp=now - datetime.timedelta(minutes=2),
        confidence=0.78,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
    )
    evidence = Evidence(
        evidence_id="ev-001",
        evidence_type="NEWS_SENTIMENT",
        source="newsapi",
        data={"score": 0.62},
        collected_at=now - datetime.timedelta(minutes=1),
    )
    policy = Policy(
        policy_id="pol-001",
        name="max_position_size",
        description="Caps single-position exposure as a percent of portfolio value.",
        enabled=True,
    )

    engine.create_decision(decision)
    engine.attach_evidence(decision_id, evidence)
    engine.register_policy(policy)
    engine.evaluate_policy(decision_id, policy.policy_id)

    approval = Approval(
        approval_id="apr-001",
        decision_id=decision_id,
        status=ApprovalStatus.APPROVED,
        approved_by="risk_officer",
        timestamp=datetime.datetime.utcnow() + datetime.timedelta(minutes=1),
    )
    engine.record_approval(approval)

    projection = engine.get_decision_projection(decision_id)

    events = [
        event
        for event in ledger_repository.get_events()
        if event.payload.get("decision_id") == decision_id
    ]

    assert len(events) == 4
    assert events[0].event_type == EventType.DECISION_CREATED
    assert events[1].event_type == EventType.EVIDENCE_ATTACHED
    assert events[2].event_type == EventType.GOVERNANCE_EVALUATED
    assert events[3].event_type == EventType.APPROVAL_RECORDED

    assert all(event.payload.get("decision_id") == decision_id for event in events)

    assert all(
        events[i].created_at <= events[i + 1].created_at
        for i in range(len(events) - 1)
    )

    assert projection is not None
    assert projection.status == DecisionState.APPROVAL_RECORDED
