"""Tests for sentinel_engine.services.evidence_service.EvidenceService."""
import datetime

from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.events.event_types import EventType
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.projections.decision_projection import DecisionProjection
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


def _make_evidence(evidence_id="ev-001", **overrides):
    defaults = dict(
        evidence_id=evidence_id,
        evidence_type="NEWS_SENTIMENT",
        source="newsapi",
        data={"score": 0.62},
        collected_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return Evidence(**defaults)


def _make_projection(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        status=DecisionState.DECISION_CREATED,
        confidence=0.78,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
        updated_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionProjection(**defaults)


def _make_service():
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()
    service = EvidenceService(ledger_repository, projection_repository)
    return service, ledger_repository, projection_repository


def test_get_evidence_for_decision_returns_empty_list_when_none_associated():
    service, _, _ = _make_service()

    assert service.get_evidence_for_decision("dec-001") == []


def test_associate_evidence_then_get_evidence_for_decision_returns_it():
    service, _, _ = _make_service()
    evidence = _make_evidence()

    service.associate_evidence("dec-001", evidence)

    assert service.get_evidence_for_decision("dec-001") == [evidence]


def test_associate_evidence_accumulates_multiple_items_for_the_same_decision():
    service, _, _ = _make_service()
    first = _make_evidence("ev-001")
    second = _make_evidence("ev-002")

    service.associate_evidence("dec-001", first)
    service.associate_evidence("dec-001", second)

    assert service.get_evidence_for_decision("dec-001") == [first, second]


def test_evidence_is_isolated_per_decision():
    service, _, _ = _make_service()
    evidence = _make_evidence()

    service.associate_evidence("dec-001", evidence)

    assert service.get_evidence_for_decision("dec-002") == []


def test_get_evidence_for_decision_returns_a_copy_not_the_internal_list():
    service, _, _ = _make_service()
    service.associate_evidence("dec-001", _make_evidence())

    result = service.get_evidence_for_decision("dec-001")
    result.append(_make_evidence("ev-injected"))

    assert len(service.get_evidence_for_decision("dec-001")) == 1


def test_evidence_service_does_not_expose_internal_storage_attribute():
    service, _, _ = _make_service()

    assert not hasattr(service, "evidence_by_decision")


def test_associate_evidence_writes_evidence_attached_event_with_correct_payload():
    service, ledger_repository, _ = _make_service()
    evidence = _make_evidence()

    service.associate_evidence("dec-001", evidence)

    events = ledger_repository.get_events()
    assert len(events) == 1
    assert events[0].event_type == EventType.EVIDENCE_ATTACHED
    assert events[0].payload["decision_id"] == "dec-001"
    assert events[0].payload["evidence_id"] == "ev-001"
    assert events[0].payload["evidence_type"] == "NEWS_SENTIMENT"
    assert events[0].payload["source"] == "newsapi"


def test_associate_evidence_preserves_evidence_data_in_event_payload():
    """ADR-036: evidence.data must survive into the EVIDENCE_ATTACHED
    payload -- previously discarded here, the sole point Evidence.data was
    lost before ever reaching the durable ledger."""
    service, ledger_repository, _ = _make_service()
    evidence = _make_evidence(data={"raw_score": 0.42, "headlines": ["A headline"]})

    service.associate_evidence("dec-001", evidence)

    events = ledger_repository.get_events()
    assert events[0].payload["data"] == {"raw_score": 0.42, "headlines": ["A headline"]}


def test_associate_evidence_advances_projection_status_when_projection_exists():
    service, _, projection_repository = _make_service()
    projection_repository.save(_make_projection())
    evidence = _make_evidence()

    service.associate_evidence("dec-001", evidence)

    projection = projection_repository.get("dec-001")
    assert projection is not None
    assert projection.status == DecisionState.EVIDENCE_ATTACHED
    assert projection.updated_at == evidence.collected_at
    # Unrelated fields preserved by the read-modify-write, not overwritten.
    assert projection.symbol == "AAPL"
    assert projection.action == "BUY"
    assert projection.confidence == 0.78


def test_associate_evidence_does_not_create_a_projection_when_none_exists():
    service, _, projection_repository = _make_service()
    evidence = _make_evidence()

    service.associate_evidence("dec-001", evidence)

    assert projection_repository.get("dec-001") is None
