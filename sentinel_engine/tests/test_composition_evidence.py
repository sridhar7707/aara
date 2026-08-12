"""Tests for sentinel_engine.composition.evidence -- the ADR-013-authorized
temporary EvidenceService composition boundary."""
import datetime

from sentinel_engine.composition.evidence import (
    _TemporaryLedgerStore,
    _TemporaryProjectionRepository,
    get_evidence_service,
)
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.events.event import Event
from sentinel_engine.events.event_types import EventType
from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.projections.decision_projection import DecisionProjection


def _make_event(event_id="evt-001"):
    return Event(
        event_id=event_id,
        event_type=EventType.DECISION_CREATED,
        created_at=datetime.datetime(2026, 8, 12, 12, 0, 0),
        payload={"decision_id": "dec-001"},
    )


def _make_projection(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        status=DecisionState.DECISION_CREATED,
        confidence=0.78,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
        updated_at=datetime.datetime(2026, 8, 12, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionProjection(**defaults)


def _make_evidence(evidence_id="ev-001"):
    return Evidence(
        evidence_id=evidence_id,
        evidence_type="MODEL_OUTPUT",
        source="xgboost",
        data={"signal": "BUY", "confidence": 0.7, "metadata": {}},
        collected_at=datetime.datetime(2026, 8, 12, 12, 0, 0),
    )


def test_temporary_ledger_store_can_be_instantiated():
    _TemporaryLedgerStore()


def test_temporary_ledger_store_append_preserves_insertion_order():
    store = _TemporaryLedgerStore()
    first = _make_event("evt-001")
    second = _make_event("evt-002")

    store.append(first)
    store.append(second)

    assert store.read_all() == [first, second]


def test_temporary_ledger_store_read_all_returns_equivalent_contents():
    store = _TemporaryLedgerStore()
    event = _make_event()

    store.append(event)

    assert store.read_all() == [event]


def test_temporary_ledger_store_read_all_does_not_expose_internal_list():
    store = _TemporaryLedgerStore()
    store.append(_make_event())

    result = store.read_all()
    result.append(_make_event("evt-injected"))

    assert len(store.read_all()) == 1


def test_temporary_projection_repository_can_be_instantiated():
    _TemporaryProjectionRepository()


def test_temporary_projection_repository_get_returns_none_when_absent():
    repository = _TemporaryProjectionRepository()

    assert repository.get("missing-decision") is None


def test_temporary_projection_repository_save_then_get_returns_it():
    repository = _TemporaryProjectionRepository()
    projection = _make_projection()

    repository.save(projection)

    assert repository.get("dec-001") == projection


def test_temporary_projection_repository_save_replaces_existing_projection():
    repository = _TemporaryProjectionRepository()
    original = _make_projection(status=DecisionState.DECISION_CREATED)
    updated = _make_projection(status=DecisionState.EVIDENCE_ATTACHED)

    repository.save(original)
    repository.save(updated)

    assert repository.get("dec-001").status == DecisionState.EVIDENCE_ATTACHED


def test_get_evidence_service_returns_the_same_instance_repeatedly():
    first = get_evidence_service()
    second = get_evidence_service()

    assert first is second


def test_evidence_service_from_accessor_can_associate_evidence_end_to_end():
    service = get_evidence_service()
    evidence = _make_evidence()

    service.associate_evidence("dec-composition-test-001", evidence)

    assert service.get_evidence_for_decision("dec-composition-test-001") == [evidence]
