"""Tests for sentinel_engine.services.decision_service.DecisionService."""
import datetime

from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.domain.decision import Decision
from sentinel_engine.domain.decision_state import DecisionState
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


def _make_service():
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()
    service = DecisionService(ledger_repository, projection_repository)
    return service, ledger_repository, projection_repository


def test_create_decision_returns_a_decision_created_event():
    service, _, _ = _make_service()
    decision = _make_decision()

    event = service.create_decision(decision)

    assert event.event_type == EventType.DECISION_CREATED
    assert event.payload["decision_id"] == "dec-001"
    assert event.payload["symbol"] == "AAPL"
    assert event.payload["action"] == "BUY"


def test_create_decision_saves_event_to_ledger_repository():
    service, ledger_repository, _ = _make_service()
    decision = _make_decision()

    service.create_decision(decision)

    events = ledger_repository.get_events()
    assert len(events) == 1
    assert events[0].event_type == EventType.DECISION_CREATED


def test_create_decision_saves_projection_with_created_status():
    service, _, projection_repository = _make_service()
    decision = _make_decision()

    service.create_decision(decision)

    projection = projection_repository.get("dec-001")
    assert projection is not None
    assert projection.symbol == "AAPL"
    assert projection.action == "BUY"
    assert projection.status == DecisionState.DECISION_CREATED


def test_get_projection_returns_none_for_unknown_decision():
    service, _, _ = _make_service()

    assert service.get_projection("missing-decision") is None


def test_get_projection_returns_saved_projection():
    service, _, _ = _make_service()
    decision = _make_decision()
    service.create_decision(decision)

    projection = service.get_projection("dec-001")

    assert projection is not None
    assert projection.decision_id == "dec-001"
