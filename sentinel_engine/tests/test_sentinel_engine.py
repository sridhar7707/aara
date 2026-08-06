"""Tests for sentinel_engine.services.sentinel_engine.SentinelEngine."""
import datetime

from sentinel_engine.services.sentinel_engine import SentinelEngine
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.services.governance_service import GovernanceService
from sentinel_engine.domain.decision import Decision
from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.governance.policy import Policy
from sentinel_engine.governance.approval import Approval
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


def _make_decision(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        timestamp=datetime.datetime(2026, 8, 4, 12, 0, 0),
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
        collected_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
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
        status="APPROVED",
        approved_by="risk_officer",
        timestamp=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return Approval(**defaults)


def _make_engine():
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()
    decision_service = DecisionService(ledger_repository, projection_repository)
    evidence_service = EvidenceService(ledger_repository, projection_repository)
    governance_service = GovernanceService(ledger_repository, projection_repository)
    return SentinelEngine(decision_service, evidence_service, governance_service)


def test_engine_can_be_constructed():
    engine = _make_engine()

    assert engine is not None


def test_create_decision_delegates_to_decision_service():
    engine = _make_engine()
    decision = _make_decision()

    event = engine.create_decision(decision)

    assert event.event_type == EventType.DECISION_CREATED
    projection = engine.get_decision_projection("dec-001")
    assert projection is not None
    assert projection.status == EventType.DECISION_CREATED.value


def test_get_decision_projection_returns_none_for_unknown_decision():
    engine = _make_engine()

    assert engine.get_decision_projection("missing-decision") is None


def test_attach_evidence_delegates_to_evidence_service():
    engine = _make_engine()
    evidence = _make_evidence()

    engine.attach_evidence("dec-001", evidence)

    assert engine.get_evidence("dec-001") == [evidence]


def test_get_evidence_returns_empty_list_when_none_attached():
    engine = _make_engine()

    assert engine.get_evidence("dec-001") == []


def test_register_policy_and_query_is_policy_enabled():
    engine = _make_engine()
    engine.register_policy(_make_policy(enabled=False))

    assert engine.is_policy_enabled("pol-001") is False


def test_is_policy_enabled_returns_false_for_unknown_policy():
    engine = _make_engine()

    assert engine.is_policy_enabled("missing-policy") is False


def test_evaluate_policy_delegates_to_governance_service():
    engine = _make_engine()
    engine.register_policy(_make_policy(enabled=True))

    assert engine.evaluate_policy("dec-001", "pol-001") is True


def test_evaluate_policy_returns_false_for_unknown_policy():
    engine = _make_engine()

    assert engine.evaluate_policy("dec-001", "missing-policy") is False


def test_record_approval_and_query_get_approval():
    engine = _make_engine()
    approval = _make_approval()

    engine.record_approval(approval)

    assert engine.get_approval("dec-001") == approval


def test_get_approval_returns_none_when_not_recorded():
    engine = _make_engine()

    assert engine.get_approval("dec-001") is None
