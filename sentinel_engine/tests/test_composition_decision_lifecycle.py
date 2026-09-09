"""Tests for sentinel_engine.composition.decision_lifecycle -- the ADR-067
SS3.C shared composition pair for the causal decision lifecycle.
"""
import ast
import datetime
import pathlib

from sentinel_engine.composition import decision_lifecycle as lifecycle
from sentinel_engine.composition import evidence as evidence_composition
from sentinel_engine.composition import governance as governance_composition
from sentinel_engine.composition import execution as execution_composition
from sentinel_engine.composition.decision_lifecycle import (
    _LifecycleLedgerStore,
    _LifecycleProjectionRepository,
    get_decision_service,
    get_evidence_service,
    get_governance_service,
)
from sentinel_engine.domain.decision import Decision
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.events.event import Event
from sentinel_engine.events.event_types import EventType
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.services.governance_service import GovernanceService


_TS = datetime.datetime(2026, 9, 8, 12, 0, 0)


def _make_decision(decision_id="dec-lifecycle-001", action="BUY"):
    return Decision(
        decision_id=decision_id,
        symbol="AAPL",
        action=action,
        timestamp=_TS,
        confidence=0.72,
        evidence_reference="cand-001",
        risk_reference="pending",
    )


def _make_evidence(evidence_id="ev-001"):
    return Evidence(
        evidence_id=evidence_id,
        evidence_type="MODEL_OUTPUT",
        source="xgboost",
        data={"signal": "BUY", "confidence": 0.7, "metadata": {}},
        collected_at=_TS,
    )


# -- temporary in-memory implementations -----------------------------------

def test_lifecycle_ledger_store_append_preserves_order_and_copies_out():
    store = _LifecycleLedgerStore()
    a = Event(event_id="e1", event_type=EventType.DECISION_CREATED, created_at=_TS, payload={})
    b = Event(event_id="e2", event_type=EventType.EVIDENCE_ATTACHED, created_at=_TS, payload={})
    store.append(a)
    store.append(b)
    out = store.read_all()
    assert out == [a, b]
    out.append(Event(event_id="e3", event_type=EventType.DECISION_EXECUTED, created_at=_TS, payload={}))
    assert store.read_all() == [a, b]


def test_lifecycle_projection_repository_get_save_roundtrip():
    repo = _LifecycleProjectionRepository()
    assert repo.get("missing") is None
    proj = DecisionProjection(
        decision_id="dec-1", symbol="AAPL", action="BUY",
        status=DecisionState.DECISION_CREATED, confidence=0.7,
        evidence_reference="e", risk_reference="r", updated_at=_TS,
    )
    repo.save(proj)
    assert repo.get("dec-1") == proj


# -- one shared pair ------------------------------------------------------

def test_all_three_services_share_one_ledger_and_projection_pair():
    ds, es, gs = get_decision_service(), get_evidence_service(), get_governance_service()
    assert ds._ledger_repository is es._ledger_repository is gs._ledger_repository
    assert ds._projection_repository is es._projection_repository is gs._projection_repository
    assert ds._ledger_repository is lifecycle._ledger_repository
    assert ds._projection_repository is lifecycle._projection_repository


def test_accessors_are_process_scoped_singletons_returning_correct_types():
    assert get_decision_service() is get_decision_service()
    assert get_evidence_service() is get_evidence_service()
    assert get_governance_service() is get_governance_service()
    assert isinstance(get_decision_service(), DecisionService)
    assert isinstance(get_evidence_service(), EvidenceService)
    assert isinstance(get_governance_service(), GovernanceService)


def test_the_three_repointed_composition_modules_expose_this_shared_pair():
    assert evidence_composition._ledger_repository is lifecycle._ledger_repository
    assert governance_composition._ledger_repository is lifecycle._ledger_repository
    assert execution_composition._ledger_repository is lifecycle._ledger_repository
    assert evidence_composition.get_evidence_service() is get_evidence_service()
    assert governance_composition.get_governance_service() is get_governance_service()
    assert execution_composition.get_decision_service_for_execution_reporting() is get_decision_service()


# -- one coherent projection walks the lifecycle ------------------------------

def test_one_decision_projection_walks_created_evidence_governance_executed():
    ds, es, gs = get_decision_service(), get_evidence_service(), get_governance_service()
    did = "dec-lifecycle-walk-001"

    ds.create_decision(_make_decision(decision_id=did))
    assert ds.get_projection(did).status == DecisionState.DECISION_CREATED

    es.associate_evidence(did, _make_evidence("ev-walk-1"))
    assert ds.get_projection(did).status == DecisionState.EVIDENCE_ATTACHED

    gs.evaluate_policy(did, "policy-unregistered")
    assert ds.get_projection(did).status == DecisionState.GOVERNANCE_EVALUATED

    ds.record_execution(did, {
        "decision_id": did, "symbol": "AAPL", "action": "BUY", "side": "buy",
        "outcome": "FILLED", "is_paper": True, "timestamp": _TS,
    })
    assert ds.get_projection(did).status == DecisionState.DECISION_EXECUTED

    event_types = [e.event_type for e in lifecycle._ledger_repository.get_events()
                   if e.payload.get("decision_id") == did]
    assert EventType.DECISION_CREATED in event_types
    assert EventType.EVIDENCE_ATTACHED in event_types
    assert EventType.GOVERNANCE_EVALUATED in event_types
    assert EventType.DECISION_EXECUTED in event_types


def test_advance_status_still_no_ops_when_no_projection_was_seeded():
    ds = get_decision_service()
    ds.record_execution("dec-never-created-xyz", {
        "decision_id": "dec-never-created-xyz", "symbol": "AAPL", "action": "BUY",
        "side": "buy", "outcome": "REJECTED", "is_paper": True, "timestamp": _TS,
    })
    assert ds.get_projection("dec-never-created-xyz") is None


# -- boundary --------------------------------------------------------------

def test_decision_lifecycle_module_imports_no_forbidden_packages():
    forbidden = ("bot", "dashboard", "scheduler", "ledger", "database", "applications")
    source = pathlib.Path(lifecycle.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden)
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(forbidden)
