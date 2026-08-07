"""Tests for applications.wealth_intelligence.bootstrap.build_application().

Uses monkeypatch to track how many times each collaborator class is
constructed and what arguments it receives. build_application() returns
only the top-level InvestorWorkspaceUI -- repositories and services are
never stored on any object reachable from that return value -- so
verifying "exactly one shared instance" requires observing construction
itself rather than introspecting the final graph.
"""
from applications.wealth_intelligence.bootstrap import (
    _InMemoryProjectionRepository,
    build_application,
)
from applications.wealth_intelligence.ui.investor_workspace import InvestorWorkspaceUI
from sentinel_engine.queries.decision_center_query import DecisionCenterQuery
from sentinel_engine.queries.decision_query import DecisionQuery
from sentinel_engine.queries.morning_brief_query import MorningBriefQuery
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.services.governance_service import GovernanceService
from sentinel_engine.services.sentinel_engine import SentinelEngine


def _track_constructor_calls(monkeypatch, cls):
    calls = []
    original_init = cls.__init__

    def wrapped_init(self, *args, **kwargs):
        calls.append({"self": self, "args": args, "kwargs": kwargs})
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(cls, "__init__", wrapped_init)
    return calls


def test_build_application_returns_investor_workspace_ui():
    ui = build_application()

    assert isinstance(ui, InvestorWorkspaceUI)


def test_build_application_constructs_exactly_one_ledger_repository(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, LedgerRepository)

    build_application()

    assert len(calls) == 1


def test_build_application_constructs_exactly_one_projection_repository(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, _InMemoryProjectionRepository)

    build_application()

    assert len(calls) == 1


def test_build_application_queries_share_the_same_repositories(monkeypatch):
    ledger_calls = _track_constructor_calls(monkeypatch, LedgerRepository)
    projection_calls = _track_constructor_calls(monkeypatch, _InMemoryProjectionRepository)
    decision_query_calls = _track_constructor_calls(monkeypatch, DecisionQuery)
    morning_brief_calls = _track_constructor_calls(monkeypatch, MorningBriefQuery)
    decision_center_calls = _track_constructor_calls(monkeypatch, DecisionCenterQuery)

    build_application()

    ledger_repository = ledger_calls[0]["self"]
    projection_repository = projection_calls[0]["self"]

    # DecisionQuery is constructed twice: once directly for the facade, and
    # once internally by DecisionCenterQuery (sentinel_engine's
    # decision_center_query.py composes its own DecisionQuery) -- both
    # calls must still share the one repository pair.
    assert len(decision_query_calls) == 2
    for call in decision_query_calls:
        assert call["args"][0] is ledger_repository
        assert call["args"][1] is projection_repository

    assert len(morning_brief_calls) == 1
    assert morning_brief_calls[0]["args"][0] is ledger_repository
    assert morning_brief_calls[0]["args"][1] is projection_repository

    assert len(decision_center_calls) == 1
    assert decision_center_calls[0]["args"][0] is ledger_repository
    assert decision_center_calls[0]["args"][1] is projection_repository


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


def test_build_application_does_not_duplicate_the_object_graph(monkeypatch):
    ledger_calls = _track_constructor_calls(monkeypatch, LedgerRepository)
    projection_calls = _track_constructor_calls(monkeypatch, _InMemoryProjectionRepository)
    decision_service_calls = _track_constructor_calls(monkeypatch, DecisionService)
    evidence_service_calls = _track_constructor_calls(monkeypatch, EvidenceService)
    governance_service_calls = _track_constructor_calls(monkeypatch, GovernanceService)
    decision_query_calls = _track_constructor_calls(monkeypatch, DecisionQuery)
    morning_brief_calls = _track_constructor_calls(monkeypatch, MorningBriefQuery)
    decision_center_calls = _track_constructor_calls(monkeypatch, DecisionCenterQuery)
    sentinel_engine_calls = _track_constructor_calls(monkeypatch, SentinelEngine)

    build_application()

    assert len(ledger_calls) == 1
    assert len(projection_calls) == 1
    assert len(decision_service_calls) == 1
    assert len(evidence_service_calls) == 1
    assert len(governance_service_calls) == 1
    assert len(decision_query_calls) == 2  # standalone + DecisionCenterQuery's internal one
    assert len(morning_brief_calls) == 1
    assert len(decision_center_calls) == 1
    assert len(sentinel_engine_calls) == 1

    repository_instances = {ledger_calls[0]["self"], projection_calls[0]["self"]}
    assert len(repository_instances) == 2  # exactly one of each, never duplicated
