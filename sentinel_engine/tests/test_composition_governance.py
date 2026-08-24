"""Tests for sentinel_engine.composition.governance -- the ADR-045-authorized
temporary GovernanceService composition boundary."""
import ast
import datetime
import pathlib

from sentinel_engine.composition import evidence as evidence_composition
from sentinel_engine.composition import governance
from sentinel_engine.composition.governance import (
    _TemporaryLedgerStore,
    _TemporaryProjectionRepository,
    get_governance_service,
)
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.events.event import Event
from sentinel_engine.events.event_types import EventType
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.services.governance_service import GovernanceService


def _make_event(event_id="evt-001"):
    return Event(
        event_id=event_id,
        event_type=EventType.DECISION_CREATED,
        created_at=datetime.datetime(2026, 8, 24, 12, 0, 0),
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
        updated_at=datetime.datetime(2026, 8, 24, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionProjection(**defaults)


# -- Temporary LedgerStore: append/read_all only -----------------------------

def test_temporary_ledger_store_can_be_instantiated():
    _TemporaryLedgerStore()


def test_temporary_ledger_store_append_preserves_insertion_order():
    store = _TemporaryLedgerStore()
    first = _make_event("evt-001")
    second = _make_event("evt-002")

    store.append(first)
    store.append(second)

    assert store.read_all() == [first, second]


def test_temporary_ledger_store_read_all_does_not_expose_internal_list():
    store = _TemporaryLedgerStore()
    store.append(_make_event())

    result = store.read_all()
    result.append(_make_event("evt-injected"))

    assert len(store.read_all()) == 1


# -- Temporary ProjectionRepository: get/save only ---------------------------

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
    updated = _make_projection(status=DecisionState.GOVERNANCE_EVALUATED)

    repository.save(original)
    repository.save(updated)

    assert repository.get("dec-001").status == DecisionState.GOVERNANCE_EVALUATED


# -- advance_status(): inherited from ProjectionRepository, unmodified -------

def test_advance_status_is_a_noop_when_no_projection_exists():
    repository = _TemporaryProjectionRepository()

    repository.advance_status(
        "missing-decision", DecisionState.GOVERNANCE_EVALUATED,
        datetime.datetime(2026, 8, 24, 12, 0, 0),
    )

    assert repository.get("missing-decision") is None


def test_advance_status_updates_status_and_updated_at_when_projection_exists():
    repository = _TemporaryProjectionRepository()
    repository.save(_make_projection(status=DecisionState.DECISION_CREATED))
    new_time = datetime.datetime(2026, 8, 24, 13, 0, 0)

    repository.advance_status("dec-001", DecisionState.GOVERNANCE_EVALUATED, new_time)

    updated = repository.get("dec-001")
    assert updated.status == DecisionState.GOVERNANCE_EVALUATED
    assert updated.updated_at == new_time


# -- get_governance_service(): process-scoped singleton, wired to the -------
# -- dedicated repository pair -----------------------------------------------

def test_get_governance_service_returns_a_governance_service_instance():
    assert isinstance(get_governance_service(), GovernanceService)


def test_get_governance_service_returns_the_same_instance_repeatedly():
    first = get_governance_service()
    second = get_governance_service()

    assert first is second


def test_governance_service_from_accessor_evaluate_policy_writes_to_dedicated_ledger():
    service = get_governance_service()
    before = len(governance._ledger_repository.get_events())

    service.evaluate_policy("dec-composition-governance-test-001", "policy-does-not-exist")

    after = governance._ledger_repository.get_events()
    assert len(after) == before + 1
    assert after[-1].event_type == EventType.GOVERNANCE_EVALUATED


# -- Independence from the Evidence composition boundary (ADR-014 SS8) ------

def test_governance_composition_does_not_reuse_evidence_composition_repositories():
    assert governance._ledger_repository is not evidence_composition._ledger_repository
    assert governance._projection_repository is not evidence_composition._projection_repository


def test_governance_composition_does_not_reuse_evidence_service_instance():
    assert get_governance_service() is not evidence_composition.get_evidence_service()


def test_governance_composition_module_does_not_import_evidence_composition():
    source = pathlib.Path(governance.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "composition.evidence" not in module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert "composition.evidence" not in alias.name


# -- Import boundary: no bot/dashboard/scheduler/ledger/database/applications -

def test_governance_composition_module_does_not_import_forbidden_packages():
    forbidden_prefixes = ("bot", "dashboard", "scheduler", "ledger", "database", "applications")
    source = pathlib.Path(governance.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden_prefixes)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith(forbidden_prefixes)
