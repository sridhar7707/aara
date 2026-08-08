"""Tests for sentinel_engine.queries.morning_brief_query.MorningBriefQuery."""
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
from sentinel_engine.queries.morning_brief_query import MorningBriefQuery


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


def _make_repositories():
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()
    return ledger_repository, projection_repository


def test_get_brief_returns_zeroed_summary_for_empty_system():
    ledger_repository, projection_repository = _make_repositories()
    query = MorningBriefQuery(ledger_repository, projection_repository)

    brief = query.get_brief()

    assert brief.total_decisions == 0
    assert brief.decisions_by_status == {}
    assert brief.recent_decisions == []
    assert brief.pending_governance_count == 0
    assert brief.pending_approval_count == 0
    assert brief.latest_activity_timestamp is None


def test_get_brief_summarizes_decisions_across_lifecycle_states():
    ledger_repository, projection_repository = _make_repositories()
    decision_service = DecisionService(ledger_repository, projection_repository)
    evidence_service = EvidenceService(ledger_repository, projection_repository)
    governance_service = GovernanceService(ledger_repository, projection_repository)

    # dec-001: DECISION_CREATED only.
    decision_service.create_decision(_make_decision(decision_id="dec-001"))

    # dec-002: through EVIDENCE_ATTACHED.
    decision_service.create_decision(_make_decision(decision_id="dec-002"))
    evidence_service.associate_evidence(
        "dec-002", _make_evidence(evidence_id="ev-002")
    )

    # dec-003: through GOVERNANCE_EVALUATED.
    decision_service.create_decision(_make_decision(decision_id="dec-003"))
    evidence_service.associate_evidence(
        "dec-003", _make_evidence(evidence_id="ev-003")
    )
    governance_service.register_policy(_make_policy())
    governance_service.evaluate_policy("dec-003", "pol-001")

    # dec-004: through APPROVAL_RECORDED.
    decision_service.create_decision(_make_decision(decision_id="dec-004"))
    evidence_service.associate_evidence(
        "dec-004", _make_evidence(evidence_id="ev-004")
    )
    governance_service.evaluate_policy("dec-004", "pol-001")
    governance_service.record_approval(
        _make_approval(decision_id="dec-004", approval_id="apr-004")
    )

    query = MorningBriefQuery(ledger_repository, projection_repository)
    brief = query.get_brief()

    assert brief.total_decisions == 4
    assert brief.decisions_by_status == {
        DecisionState.DECISION_CREATED: 1,
        DecisionState.EVIDENCE_ATTACHED: 1,
        DecisionState.GOVERNANCE_EVALUATED: 1,
        DecisionState.APPROVAL_RECORDED: 1,
    }
    # Pending governance: dec-001 (created only) and dec-002 (evidence only).
    assert brief.pending_governance_count == 2
    # Pending approval: everyone except dec-004.
    assert brief.pending_approval_count == 3


def test_get_brief_orders_recent_activity_by_created_at_not_insertion_order():
    ledger_repository, projection_repository = _make_repositories()

    projection_repository.save(
        DecisionProjection(
            decision_id="dec-early",
            symbol="AAPL",
            action="BUY",
            status=DecisionState.DECISION_CREATED,
            confidence=0.78,
            evidence_reference="evidence-001",
            risk_reference="risk-001",
            updated_at=datetime.datetime(2026, 8, 6, 9, 0, 0),
        )
    )
    projection_repository.save(
        DecisionProjection(
            decision_id="dec-late",
            symbol="MSFT",
            action="BUY",
            status=DecisionState.DECISION_CREATED,
            confidence=0.65,
            evidence_reference="evidence-002",
            risk_reference="risk-002",
            updated_at=datetime.datetime(2026, 8, 6, 11, 0, 0),
        )
    )

    later_event = Event(
        event_id="evt-late",
        event_type=EventType.DECISION_CREATED,
        created_at=datetime.datetime(2026, 8, 6, 11, 0, 0),
        payload={
            "decision_id": "dec-late",
            "symbol": "MSFT",
            "action": "BUY",
            "confidence": 0.65,
            "evidence_reference": "evidence-002",
            "risk_reference": "risk-002",
        },
    )
    earlier_event = Event(
        event_id="evt-early",
        event_type=EventType.DECISION_CREATED,
        created_at=datetime.datetime(2026, 8, 6, 9, 0, 0),
        payload={
            "decision_id": "dec-early",
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

    query = MorningBriefQuery(ledger_repository, projection_repository)
    brief = query.get_brief()

    assert [item.decision_id for item in brief.recent_decisions] == [
        "dec-late",
        "dec-early",
    ]
    assert brief.latest_activity_timestamp == datetime.datetime(2026, 8, 6, 11, 0, 0)


def test_get_brief_ignores_events_for_decisions_without_a_saved_projection():
    ledger_repository, projection_repository = _make_repositories()
    decision_service = DecisionService(ledger_repository, projection_repository)

    decision_service.create_decision(_make_decision(decision_id="dec-001"))

    stray_event = Event(
        event_id="evt-stray",
        event_type=EventType.EVIDENCE_ATTACHED,
        created_at=datetime.datetime(2026, 8, 6, 12, 5, 0),
        payload={
            "decision_id": "dec-999",
            "evidence_id": "ev-999",
            "evidence_type": "NEWS_SENTIMENT",
            "source": "newsapi",
        },
    )
    ledger_repository.save_event(stray_event)

    query = MorningBriefQuery(ledger_repository, projection_repository)
    brief = query.get_brief()

    assert brief.total_decisions == 1
    assert brief.decisions_by_status == {DecisionState.DECISION_CREATED: 1}
    assert [item.decision_id for item in brief.recent_decisions] == ["dec-001"]
    assert brief.pending_governance_count == 1
    assert brief.pending_approval_count == 1


def test_get_brief_keeps_two_known_decisions_independently_counted():
    ledger_repository, projection_repository = _make_repositories()
    decision_service = DecisionService(ledger_repository, projection_repository)
    governance_service = GovernanceService(ledger_repository, projection_repository)

    decision_service.create_decision(_make_decision(decision_id="dec-001"))

    decision_service.create_decision(_make_decision(decision_id="dec-002"))
    governance_service.register_policy(_make_policy())
    governance_service.evaluate_policy("dec-002", "pol-001")
    governance_service.record_approval(
        _make_approval(decision_id="dec-002", approval_id="apr-002")
    )

    query = MorningBriefQuery(ledger_repository, projection_repository)
    brief = query.get_brief()

    assert brief.total_decisions == 2
    assert brief.decisions_by_status == {
        DecisionState.DECISION_CREATED: 1,
        DecisionState.APPROVAL_RECORDED: 1,
    }
    assert brief.pending_governance_count == 1
    assert brief.pending_approval_count == 1
