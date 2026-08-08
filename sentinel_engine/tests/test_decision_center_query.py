"""Tests for sentinel_engine.queries.decision_center_query.DecisionCenterQuery."""
import datetime

from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.services.governance_service import GovernanceService
from sentinel_engine.domain.decision import Decision
from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.governance.policy import Policy
from sentinel_engine.governance.approval import Approval
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.events.event import Event
from sentinel_engine.events.event_types import EventType
from sentinel_engine.governance.approval_status import ApprovalStatus
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository
from sentinel_engine.queries.decision_center_query import DecisionCenterQuery


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


def _make_decision(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        timestamp=datetime.datetime(2026, 8, 6, 12, 0, 0),
        confidence=0.78,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
    )
    defaults.update(overrides)
    return Decision(**defaults)


def _make_evidence(**overrides):
    defaults = dict(
        evidence_id="ev-001",
        evidence_type="NEWS_SENTIMENT",
        source="newsapi",
        data={"score": 0.62},
        collected_at=datetime.datetime(2026, 8, 6, 12, 1, 0),
    )
    defaults.update(overrides)
    return Evidence(**defaults)


def _make_policy(**overrides):
    defaults = dict(
        policy_id="pol-001",
        name="max_position_size",
        description="Caps single-position exposure as a percent of portfolio value.",
        enabled=True,
    )
    defaults.update(overrides)
    return Policy(**defaults)


def _make_approval(**overrides):
    defaults = dict(
        approval_id="apr-001",
        decision_id="dec-001",
        status=ApprovalStatus.APPROVED,
        approved_by="risk_officer",
        timestamp=datetime.datetime(2026, 8, 6, 12, 2, 0),
    )
    defaults.update(overrides)
    return Approval(**defaults)


def _make_wiring():
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()
    decision_service = DecisionService(ledger_repository, projection_repository)
    evidence_service = EvidenceService(ledger_repository, projection_repository)
    governance_service = GovernanceService(ledger_repository, projection_repository)
    query = DecisionCenterQuery(ledger_repository, projection_repository)
    return decision_service, evidence_service, governance_service, query, ledger_repository, projection_repository


def test_get_decision_center_returns_complete_lifecycle_view():
    decision_service, evidence_service, governance_service, query, _, _ = _make_wiring()
    decision_id = "dec-001"

    # GovernanceService.evaluate_policy() stamps its event with the real
    # wall clock, so decision/evidence timestamps are anchored just before
    # "now" and the approval timestamp is captured just after
    # evaluate_policy() runs, keeping every step monotonic regardless of
    # when the test actually executes.
    now = datetime.datetime.utcnow()
    decision_service.create_decision(
        _make_decision(decision_id=decision_id, timestamp=now - datetime.timedelta(minutes=2))
    )
    evidence_service.associate_evidence(
        decision_id, _make_evidence(collected_at=now - datetime.timedelta(minutes=1))
    )
    governance_service.register_policy(_make_policy())
    governance_service.evaluate_policy(decision_id, "pol-001")
    governance_service.record_approval(
        _make_approval(
            decision_id=decision_id,
            timestamp=datetime.datetime.utcnow() + datetime.timedelta(minutes=1),
        )
    )

    view = query.get_decision_center(decision_id)

    assert view is not None
    assert view.decision_id == decision_id
    assert view.lifecycle_status == DecisionState.APPROVAL_RECORDED
    assert view.symbol == "AAPL"
    assert view.action == "BUY"

    assert len(view.timeline) == 4
    assert [event.event_type for event in view.timeline] == [
        EventType.DECISION_CREATED,
        EventType.EVIDENCE_ATTACHED,
        EventType.GOVERNANCE_EVALUATED,
        EventType.APPROVAL_RECORDED,
    ]

    assert len(view.evidence) == 1
    assert view.evidence[0].evidence_id == "ev-001"
    assert view.evidence[0].evidence_type == "NEWS_SENTIMENT"
    assert view.evidence[0].source == "newsapi"

    assert len(view.governance_evaluations) == 1
    assert view.governance_evaluations[0].policy_id == "pol-001"
    assert view.governance_evaluations[0].enabled is True

    assert len(view.approvals) == 1
    assert view.approvals[0].approval_id == "apr-001"
    assert view.approvals[0].status == ApprovalStatus.APPROVED
    assert view.approvals[0].approved_by == "risk_officer"


def test_get_decision_center_returns_none_for_missing_decision():
    _, _, _, query, _, _ = _make_wiring()

    assert query.get_decision_center("missing-decision") is None


def test_get_decision_center_isolates_decisions():
    decision_service, evidence_service, _, query, _, _ = _make_wiring()

    decision_service.create_decision(_make_decision(decision_id="dec-001", symbol="AAPL"))
    evidence_service.associate_evidence("dec-001", _make_evidence(evidence_id="ev-001"))

    decision_service.create_decision(_make_decision(decision_id="dec-002", symbol="MSFT"))

    view_one = query.get_decision_center("dec-001")
    view_two = query.get_decision_center("dec-002")

    assert view_one.decision_id == "dec-001"
    assert view_one.symbol == "AAPL"
    assert len(view_one.timeline) == 2
    assert all(event.payload["decision_id"] == "dec-001" for event in view_one.timeline)
    assert len(view_one.evidence) == 1

    assert view_two.decision_id == "dec-002"
    assert view_two.symbol == "MSFT"
    assert len(view_two.timeline) == 1
    assert all(event.payload["decision_id"] == "dec-002" for event in view_two.timeline)
    assert view_two.evidence == []


def test_get_decision_center_orders_timeline_by_created_at_not_append_order():
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()
    projection_repository.save(
        DecisionProjection(
            decision_id="dec-001",
            symbol="AAPL",
            action="BUY",
            status=DecisionState.EVIDENCE_ATTACHED,
            confidence=0.78,
            evidence_reference="evidence-001",
            risk_reference="risk-001",
            updated_at=datetime.datetime(2026, 8, 6, 12, 1, 0),
        )
    )

    later_event = Event(
        event_id="evt-later",
        event_type=EventType.EVIDENCE_ATTACHED,
        created_at=datetime.datetime(2026, 8, 6, 12, 1, 0),
        payload={
            "decision_id": "dec-001",
            "evidence_id": "ev-001",
            "evidence_type": "NEWS_SENTIMENT",
            "source": "newsapi",
        },
    )
    earlier_event = Event(
        event_id="evt-earlier",
        event_type=EventType.DECISION_CREATED,
        created_at=datetime.datetime(2026, 8, 6, 12, 0, 0),
        payload={
            "decision_id": "dec-001",
            "symbol": "AAPL",
            "action": "BUY",
            "confidence": 0.78,
            "evidence_reference": "evidence-001",
            "risk_reference": "risk-001",
        },
    )

    # Appended out of chronological order on purpose.
    ledger_repository.save_event(later_event)
    ledger_repository.save_event(earlier_event)

    query = DecisionCenterQuery(ledger_repository, projection_repository)
    view = query.get_decision_center("dec-001")

    assert [event.event_id for event in view.timeline] == ["evt-earlier", "evt-later"]
    assert all(
        view.timeline[i].created_at <= view.timeline[i + 1].created_at
        for i in range(len(view.timeline) - 1)
    )
