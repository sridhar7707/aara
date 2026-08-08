"""Tests for applications.trading_intelligence.bootstrap.build_application().

Uses monkeypatch to track how many times each collaborator class is
constructed and what arguments it receives, mirroring
applications.wealth_intelligence.tests.test_bootstrap's pattern -- the
returned DecisionCenterUI never exposes its repositories/services directly,
so verifying "exactly one shared instance" requires observing construction
itself rather than introspecting the final graph.
"""
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.services.governance_service import GovernanceService
from sentinel_engine.services.sentinel_engine import SentinelEngine

from applications.trading_intelligence.adapters.sentinel_projection_decision_source import (
    SentinelProjectionDecisionSource,
)
from applications.trading_intelligence.bootstrap import (
    _InMemoryProjectionRepository,
    build_application,
)
from applications.trading_intelligence.services.decision_query_service import DecisionQueryService
from applications.trading_intelligence.ui.decision_center.controller import DecisionCenterController
from applications.trading_intelligence.ui.decision_center.gradio_view import DecisionCenterUI


def _track_constructor_calls(monkeypatch, cls):
    calls = []
    original_init = cls.__init__

    def wrapped_init(self, *args, **kwargs):
        calls.append({"self": self, "args": args, "kwargs": kwargs})
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(cls, "__init__", wrapped_init)
    return calls


def test_build_application_returns_decision_center_ui():
    ui = build_application()

    assert isinstance(ui, DecisionCenterUI)


def test_build_application_constructs_exactly_one_ledger_repository(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, LedgerRepository)

    build_application()

    assert len(calls) == 1


def test_build_application_constructs_exactly_one_projection_repository(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, _InMemoryProjectionRepository)

    build_application()

    assert len(calls) == 1


def test_build_application_services_share_the_same_repositories(monkeypatch):
    ledger_calls = _track_constructor_calls(monkeypatch, LedgerRepository)
    projection_calls = _track_constructor_calls(monkeypatch, _InMemoryProjectionRepository)
    decision_service_calls = _track_constructor_calls(monkeypatch, DecisionService)
    evidence_service_calls = _track_constructor_calls(monkeypatch, EvidenceService)
    governance_service_calls = _track_constructor_calls(monkeypatch, GovernanceService)

    build_application()

    ledger_repository = ledger_calls[0]["self"]
    projection_repository = projection_calls[0]["self"]

    for calls in (decision_service_calls, evidence_service_calls, governance_service_calls):
        assert len(calls) == 1
        assert calls[0]["args"][0] is ledger_repository
        assert calls[0]["args"][1] is projection_repository


def test_build_application_constructs_sentinel_engine_once_with_shared_services(monkeypatch):
    decision_service_calls = _track_constructor_calls(monkeypatch, DecisionService)
    evidence_service_calls = _track_constructor_calls(monkeypatch, EvidenceService)
    governance_service_calls = _track_constructor_calls(monkeypatch, GovernanceService)
    sentinel_engine_calls = _track_constructor_calls(monkeypatch, SentinelEngine)

    build_application()

    assert len(sentinel_engine_calls) == 1
    call = sentinel_engine_calls[0]
    assert call["args"][0] is decision_service_calls[0]["self"]
    assert call["args"][1] is evidence_service_calls[0]["self"]
    assert call["args"][2] is governance_service_calls[0]["self"]


def test_build_application_read_chain_shares_the_same_projection_repository(monkeypatch):
    projection_calls = _track_constructor_calls(monkeypatch, _InMemoryProjectionRepository)
    source_calls = _track_constructor_calls(monkeypatch, SentinelProjectionDecisionSource)

    build_application()

    projection_repository = projection_calls[0]["self"]
    assert len(source_calls) == 1
    assert source_calls[0]["args"][0] is projection_repository


def test_build_application_wires_query_service_and_controller_once(monkeypatch):
    query_service_calls = _track_constructor_calls(monkeypatch, DecisionQueryService)
    controller_calls = _track_constructor_calls(monkeypatch, DecisionCenterController)

    build_application()

    assert len(query_service_calls) == 1
    assert len(controller_calls) == 1
    assert controller_calls[0]["args"][0] is query_service_calls[0]["self"]


def test_build_application_does_not_duplicate_the_object_graph(monkeypatch):
    ledger_calls = _track_constructor_calls(monkeypatch, LedgerRepository)
    projection_calls = _track_constructor_calls(monkeypatch, _InMemoryProjectionRepository)
    decision_service_calls = _track_constructor_calls(monkeypatch, DecisionService)
    evidence_service_calls = _track_constructor_calls(monkeypatch, EvidenceService)
    governance_service_calls = _track_constructor_calls(monkeypatch, GovernanceService)
    sentinel_engine_calls = _track_constructor_calls(monkeypatch, SentinelEngine)
    source_calls = _track_constructor_calls(monkeypatch, SentinelProjectionDecisionSource)
    query_service_calls = _track_constructor_calls(monkeypatch, DecisionQueryService)
    controller_calls = _track_constructor_calls(monkeypatch, DecisionCenterController)

    build_application()

    assert len(ledger_calls) == 1
    assert len(projection_calls) == 1
    assert len(decision_service_calls) == 1
    assert len(evidence_service_calls) == 1
    assert len(governance_service_calls) == 1
    assert len(sentinel_engine_calls) == 1
    assert len(source_calls) == 1
    assert len(query_service_calls) == 1
    assert len(controller_calls) == 1

    repository_instances = {ledger_calls[0]["self"], projection_calls[0]["self"]}
    assert len(repository_instances) == 2  # exactly one of each, never duplicated


def test_build_application_seeds_three_decisions_across_the_full_decision_state_range():
    ui = build_application()

    list_rows, *_detail = ui._render_screen()

    assert len(list_rows) == 3
    statuses = {row[0]: row[3] for row in list_rows}
    assert statuses["dec-seed-001"] == "Decision Created"
    assert statuses["dec-seed-002"] == "Evidence Attached"
    assert statuses["dec-seed-003"] == "Approval Recorded"


def test_build_application_seeded_decisions_are_reachable_by_id():
    """The seed data is produced entirely through the real Sentinel Engine
    write path (DecisionService/EvidenceService/GovernanceService), then
    read back through Trading Intelligence's own read-only chain -- proving
    the vertical slice actually renders Sentinel Engine data, not
    hand-built projections standing in for it."""
    ui = build_application()

    symbol, action, status, confidence, _updated = ui._render_detail("dec-seed-003")

    assert symbol == "NVDA"
    assert action == "SELL"
    assert status == "Approval Recorded"
    assert confidence == "91%"
