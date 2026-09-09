"""Tests for sentinel_engine.composition.execution -- the ADR-065-authorized
temporary DecisionService (execution-outcome reporting) composition
boundary."""
import ast
import datetime
import pathlib

from sentinel_engine.composition import evidence as evidence_composition
from sentinel_engine.composition import governance as governance_composition
from sentinel_engine.composition import execution
from sentinel_engine.composition.execution import (
    _TemporaryLedgerStore,
    _TemporaryProjectionRepository,
    get_decision_service_for_execution_reporting,
)
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.events.event import Event
from sentinel_engine.events.event_types import EventType
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.services.decision_service import DecisionService


def _make_event(event_id="evt-001"):
    return Event(
        event_id=event_id,
        event_type=EventType.DECISION_EXECUTED,
        created_at=datetime.datetime(2026, 9, 4, 12, 0, 0),
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
        updated_at=datetime.datetime(2026, 9, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionProjection(**defaults)


# -- Temporary LedgerStore: append/read_all only -----------------------------

def test_temporary_ledger_store_append_preserves_insertion_order():
    store = _TemporaryLedgerStore()
    first = _make_event("evt-001")
    second = _make_event("evt-002")

    store.append(first)
    store.append(second)

    assert store.read_all() == [first, second]


# -- Temporary ProjectionRepository: get/save only ---------------------------

def test_temporary_projection_repository_save_then_get_returns_it():
    repository = _TemporaryProjectionRepository()
    projection = _make_projection()

    repository.save(projection)

    assert repository.get("dec-001") == projection


def test_temporary_projection_repository_get_returns_none_when_absent():
    repository = _TemporaryProjectionRepository()

    assert repository.get("missing-decision") is None


# -- advance_status(): inherited from ProjectionRepository, unmodified -------

def test_advance_status_is_a_noop_when_no_projection_exists():
    repository = _TemporaryProjectionRepository()

    repository.advance_status(
        "missing-decision", DecisionState.DECISION_EXECUTED,
        datetime.datetime(2026, 9, 4, 12, 0, 0),
    )

    assert repository.get("missing-decision") is None


# -- get_decision_service_for_execution_reporting(): process-scoped ---------

def test_accessor_returns_a_decision_service_instance():
    assert isinstance(get_decision_service_for_execution_reporting(), DecisionService)


def test_accessor_returns_the_same_instance_repeatedly():
    first = get_decision_service_for_execution_reporting()
    second = get_decision_service_for_execution_reporting()

    assert first is second


def test_record_execution_from_accessor_writes_to_dedicated_ledger():
    service = get_decision_service_for_execution_reporting()
    before = len(execution._ledger_repository.get_events())

    service.record_execution("dec-composition-execution-test-001", {
        "decision_id": "dec-composition-execution-test-001",
        "symbol": "AAPL", "action": "BUY", "side": "buy", "outcome": "FILLED",
        "is_paper": True, "timestamp": datetime.datetime(2026, 9, 4, 12, 0, 0),
    })

    after = execution._ledger_repository.get_events()
    assert len(after) == before + 1
    assert after[-1].event_type == EventType.DECISION_EXECUTED


# -- Independence from the Evidence/Governance composition boundaries -------

def test_execution_composition_does_not_reuse_other_compositions_repositories():
    assert execution._ledger_repository is not evidence_composition._ledger_repository
    assert execution._ledger_repository is not governance_composition._ledger_repository
    assert execution._projection_repository is not evidence_composition._projection_repository
    assert execution._projection_repository is not governance_composition._projection_repository


def test_execution_composition_module_does_not_import_other_compositions():
    source = pathlib.Path(execution.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "composition.evidence" not in module
            assert "composition.governance" not in module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert "composition.evidence" not in alias.name
                assert "composition.governance" not in alias.name


# -- Import boundary: no bot/dashboard/scheduler/ledger/database/applications -

def test_execution_composition_module_does_not_import_forbidden_packages():
    forbidden_prefixes = ("bot", "dashboard", "scheduler", "ledger", "database", "applications")
    source = pathlib.Path(execution.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden_prefixes)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith(forbidden_prefixes)
