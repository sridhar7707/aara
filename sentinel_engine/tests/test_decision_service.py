"""Tests for sentinel_engine.services.decision_service.DecisionService."""
import datetime

from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.domain.decision import Decision
from sentinel_engine.domain.decision_action import DecisionAction
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


def test_create_decision_preserves_batch_2_optional_fields_in_event_payload():
    service, ledger_repository, _ = _make_service()
    decision = _make_decision(
        horizon="TACTICAL",
        desired_allocation=5000.0,
        minimum_viable_allocation=1500.0,
        uncertainty=0.4,
        thesis="Foundry capacity is the bottleneck through 2026.",
        counterfactual="Yes.",
    )

    service.create_decision(decision)

    payload = ledger_repository.get_events()[0].payload
    assert payload["horizon"] == "TACTICAL"
    assert payload["desired_allocation"] == 5000.0
    assert payload["minimum_viable_allocation"] == 1500.0
    assert payload["uncertainty"] == 0.4
    assert payload["thesis"] == "Foundry capacity is the bottleneck through 2026."
    assert payload["counterfactual"] == "Yes."


def test_create_decision_carries_action_source_into_the_event_payload():
    """ADR-069: provenance is observable in the causal lifecycle via the
    DECISION_CREATED payload passthrough (same treatment ADR-066 gave the
    optional fields). The DecisionProjection is intentionally unchanged."""
    service, ledger_repository, _ = _make_service()

    service.create_decision(_make_decision(decision_id="dec-sentinel", action_source="SENTINEL"))
    service.create_decision(_make_decision(decision_id="dec-strategy", action_source="STRATEGY"))
    service.create_decision(_make_decision(decision_id="dec-legacy"))  # no action_source

    by_id = {e.payload["decision_id"]: e.payload for e in ledger_repository.get_events()}
    assert by_id["dec-sentinel"]["action_source"] == "SENTINEL"
    assert by_id["dec-strategy"]["action_source"] == "STRATEGY"
    assert by_id["dec-legacy"]["action_source"] is None


def test_wait_decision_produces_an_ordinary_decision_created_event():
    """WAIT is a recommendation/decision outcome, never an execution order
    -- DecisionService depends only on LedgerRepository/ProjectionRepository
    (see __init__), so there is no executor for a WAIT decision, or any
    other decision, to reach through this service."""
    service, ledger_repository, projection_repository = _make_service()
    decision = _make_decision(action=DecisionAction.WAIT.value)

    event = service.create_decision(decision)

    assert event.event_type == EventType.DECISION_CREATED
    assert event.payload["action"] == "WAIT"
    projection = projection_repository.get("dec-001")
    assert projection is not None
    assert projection.action == "WAIT"


def test_buy_more_decision_is_recorded_distinctly_from_buy():
    service, _, projection_repository = _make_service()
    service.create_decision(_make_decision(decision_id="dec-buy", action=DecisionAction.BUY.value))
    service.create_decision(_make_decision(decision_id="dec-buy-more", action=DecisionAction.BUY_MORE.value))

    assert projection_repository.get("dec-buy").action == "BUY"
    assert projection_repository.get("dec-buy-more").action == "BUY_MORE"


# -- record_execution() (ADR-065) --------------------------------------------

def _execution_payload(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        side="buy",
        outcome="FILLED",
        is_paper=True,
        timestamp=datetime.datetime(2026, 9, 4, 14, 30, 0),
        fill_price=192.31,
    )
    defaults.update(overrides)
    return defaults


def test_record_execution_returns_a_decision_executed_event():
    service, _, _ = _make_service()

    event = service.record_execution("dec-001", _execution_payload())

    assert event.event_type == EventType.DECISION_EXECUTED
    assert event.payload["decision_id"] == "dec-001"
    assert event.payload["outcome"] == "FILLED"


def test_record_execution_saves_event_to_ledger_repository():
    service, ledger_repository, _ = _make_service()

    service.record_execution("dec-001", _execution_payload())

    events = ledger_repository.get_events()
    assert len(events) == 1
    assert events[0].event_type == EventType.DECISION_EXECUTED


def test_record_execution_advances_existing_projection_to_decision_executed():
    service, _, projection_repository = _make_service()
    service.create_decision(_make_decision(decision_id="dec-001"))

    service.record_execution("dec-001", _execution_payload())

    projection = projection_repository.get("dec-001")
    assert projection.status == DecisionState.DECISION_EXECUTED


def test_record_execution_is_a_noop_when_no_projection_was_ever_seeded():
    """Mirrors ADR-013 SS13 / ADR-045 SS3 item 11: advance_status() no-ops
    if no projection exists. The event still appends to the ledger."""
    service, ledger_repository, projection_repository = _make_service()

    service.record_execution("dec-never-created", _execution_payload(decision_id="dec-never-created"))

    assert projection_repository.get("dec-never-created") is None
    assert len(ledger_repository.get_events()) == 1


def test_record_execution_represents_risk_rejection_via_outcome_field_not_a_new_state():
    service, ledger_repository, _ = _make_service()

    service.record_execution("dec-001", _execution_payload(
        outcome="REJECTED", reason="risk.approve_buy() declined", fill_price=None,
    ))

    event = ledger_repository.get_events()[0]
    assert event.event_type == EventType.DECISION_EXECUTED
    assert event.payload["outcome"] == "REJECTED"
    assert event.payload["reason"] == "risk.approve_buy() declined"


def test_record_execution_represents_executor_failure_via_outcome_field():
    service, ledger_repository, _ = _make_service()

    service.record_execution("dec-001", _execution_payload(outcome="FAILED", reason="order never filled"))

    event = ledger_repository.get_events()[0]
    assert event.payload["outcome"] == "FAILED"
    assert event.payload["reason"] == "order never filled"


def test_record_execution_is_idempotent_for_the_same_decision_id():
    """A retried report call (scheduler retry, duplicate cycle, application
    restart) must not append a second DECISION_EXECUTED event for the same
    decision_id -- ADR-065's idempotency guard."""
    service, ledger_repository, _ = _make_service()

    first = service.record_execution("dec-001", _execution_payload())
    second = service.record_execution("dec-001", _execution_payload())

    assert first is not None
    assert second is None
    assert len(ledger_repository.get_events()) == 1


def test_record_execution_does_not_affect_a_different_decision_id():
    service, ledger_repository, _ = _make_service()

    service.record_execution("dec-001", _execution_payload())
    service.record_execution("dec-002", _execution_payload(decision_id="dec-002"))

    assert len(ledger_repository.get_events()) == 2
