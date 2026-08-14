"""Tests for applications.trading_intelligence.adapters.sentinel_projection_decision_source."""
import datetime

import pytest

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.events.event import Event
from sentinel_engine.events.event_types import EventType
from sentinel_engine.governance.approval_status import ApprovalStatus
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.queries.decision_query import DecisionQuery
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository

from applications.trading_intelligence.adapters.sentinel_projection_decision_source import (
    SentinelProjectionDecisionSource,
)
from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.services.decision_query_service import DecisionSource


class _InMemoryProjectionRepository(ProjectionRepository):
    """Minimal conforming fake -- no real backend, matching the pattern
    sentinel_engine's own 82 tests already use."""

    def __init__(self):
        self._projections = {}

    def save(self, projection):
        self._projections[projection.decision_id] = projection

    def get(self, decision_id):
        return self._projections.get(decision_id)


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


def test_sentinel_projection_decision_source_is_a_decision_source():
    source = SentinelProjectionDecisionSource(_InMemoryProjectionRepository())
    assert isinstance(source, DecisionSource)


class _BoomProjectionRepository(ProjectionRepository):
    def save(self, projection):
        raise AssertionError("must never be called")

    def get(self, decision_id):
        raise ConnectionError("simulated infrastructure failure")


def test_get_decision_translates_repository_exceptions():
    source = SentinelProjectionDecisionSource(_BoomProjectionRepository())

    with pytest.raises(TradingIntelligenceReadError) as excinfo:
        source.get_decision("dec-001")

    assert isinstance(excinfo.value.__cause__, ConnectionError)


def test_list_decisions_does_not_translate_repository_exceptions():
    """Deliberate scope boundary (Slice 5): only the single-decision detail
    read path is covered. list_decisions() (the Decision List/top-table
    path) is untouched until a future slice designs its own error
    semantics -- this test locks that decision in so it isn't silently
    changed later."""
    source = SentinelProjectionDecisionSource(_BoomProjectionRepository())

    with pytest.raises(ConnectionError):
        source.list_decisions(["dec-001"])


def test_get_decision_returns_none_when_repository_has_no_projection():
    source = SentinelProjectionDecisionSource(_InMemoryProjectionRepository())

    assert source.get_decision("missing-decision") is None


def test_get_decision_returns_a_decision_contract():
    repository = _InMemoryProjectionRepository()
    repository.save(_make_projection())
    source = SentinelProjectionDecisionSource(repository)

    result = source.get_decision("dec-001")

    assert isinstance(result, DecisionContract)


def test_get_decision_maps_every_field_correctly():
    repository = _InMemoryProjectionRepository()
    repository.save(_make_projection())
    source = SentinelProjectionDecisionSource(repository)

    result = source.get_decision("dec-001")

    assert result.decision_id == "dec-001"
    assert result.symbol == "AAPL"
    assert result.action == "BUY"
    assert result.status == DecisionState.DECISION_CREATED
    assert result.confidence == 0.78
    assert result.evidence_reference == "evidence-001"
    assert result.risk_reference == "risk-001"
    assert result.updated_at == datetime.datetime(2026, 8, 4, 12, 0, 0)


def test_get_decision_reads_from_the_injected_repository_not_a_shared_default():
    repo_a = _InMemoryProjectionRepository()
    repo_a.save(_make_projection())
    repo_b = _InMemoryProjectionRepository()
    source_a = SentinelProjectionDecisionSource(repo_a)
    source_b = SentinelProjectionDecisionSource(repo_b)

    assert source_a.get_decision("dec-001") is not None
    assert source_b.get_decision("dec-001") is None


def test_source_only_calls_get_never_save():
    """Read-only: the adapter must never call ProjectionRepository.save()."""

    class _AssertNoSaveRepository(ProjectionRepository):
        def __init__(self):
            self._projections = {"dec-001": _make_projection()}

        def get(self, decision_id):
            return self._projections.get(decision_id)

        def save(self, projection):
            raise AssertionError("SentinelProjectionDecisionSource must never call save()")

    source = SentinelProjectionDecisionSource(_AssertNoSaveRepository())

    source.get_decision("dec-001")
    source.list_decisions(["dec-001"])


def test_list_decisions_returns_empty_list_when_no_ids_requested():
    source = SentinelProjectionDecisionSource(_InMemoryProjectionRepository())

    assert source.list_decisions([]) == []


def test_list_decisions_returns_empty_list_when_repository_has_no_matches():
    source = SentinelProjectionDecisionSource(_InMemoryProjectionRepository())

    assert source.list_decisions(["missing-1", "missing-2"]) == []


def test_list_decisions_returns_multiple_contracts():
    repository = _InMemoryProjectionRepository()
    repository.save(_make_projection(decision_id="dec-001", symbol="AAPL"))
    repository.save(_make_projection(decision_id="dec-002", symbol="MSFT"))
    source = SentinelProjectionDecisionSource(repository)

    results = source.list_decisions(["dec-001", "dec-002"])

    assert [r.decision_id for r in results] == ["dec-001", "dec-002"]
    assert [r.symbol for r in results] == ["AAPL", "MSFT"]
    assert all(isinstance(r, DecisionContract) for r in results)


def test_list_decisions_skips_ids_the_repository_does_not_have():
    repository = _InMemoryProjectionRepository()
    repository.save(_make_projection(decision_id="dec-001"))
    source = SentinelProjectionDecisionSource(repository)

    results = source.list_decisions(["dec-001", "missing-decision"])

    assert len(results) == 1
    assert results[0].decision_id == "dec-001"


def test_list_decisions_never_calls_save():
    class _AssertNoSaveRepository(ProjectionRepository):
        def __init__(self):
            self._projections = {"dec-001": _make_projection()}

        def get(self, decision_id):
            return self._projections.get(decision_id)

        def save(self, projection):
            raise AssertionError("list_decisions must never call save()")

    source = SentinelProjectionDecisionSource(_AssertNoSaveRepository())

    source.list_decisions(["dec-001", "missing"])


class _InMemoryLedgerStore(LedgerStore):
    """Minimal LedgerStore fake -- mirrors bootstrap.py's own
    _InMemoryLedgerStore, needed here only to construct a real DecisionQuery
    for the approval_status tests below."""

    def __init__(self):
        self._events = []

    def append(self, event):
        self._events.append(event)

    def read_all(self):
        return list(self._events)


def _make_decision_query(events=()):
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()
    for event in events:
        ledger_repository.save_event(event)
    return ledger_repository, projection_repository


def _make_approval_recorded_event(decision_id, status, approved_at):
    return Event(
        event_id=f"evt-{decision_id}",
        event_type=EventType.APPROVAL_RECORDED,
        created_at=approved_at,
        payload={
            "decision_id": decision_id,
            "approval_id": f"apr-{decision_id}",
            "status": status,
            "approved_by": "risk_officer",
        },
    )


def test_approval_status_is_none_when_no_decision_query_provided():
    """Backward compatibility: every existing construction of this class
    passes only a ProjectionRepository -- approval_status must stay None,
    exactly as before this collaborator existed."""
    repository = _InMemoryProjectionRepository()
    repository.save(_make_projection())
    source = SentinelProjectionDecisionSource(repository)

    result = source.get_decision("dec-001")

    assert result.approval_status is None


def test_approval_status_is_none_when_decision_query_has_no_approval():
    ledger_repository, projection_repository = _make_decision_query()
    projection_repository.save(_make_projection())
    decision_query = DecisionQuery(ledger_repository, projection_repository)
    source = SentinelProjectionDecisionSource(projection_repository, decision_query)

    result = source.get_decision("dec-001")

    assert result.approval_status is None


def test_get_decision_populates_approved_verdict_from_decision_query():
    approved_at = datetime.datetime(2026, 8, 8, 9, 34, 0)
    event = _make_approval_recorded_event("dec-001", ApprovalStatus.APPROVED, approved_at)
    ledger_repository, projection_repository = _make_decision_query([event])
    projection_repository.save(_make_projection())
    decision_query = DecisionQuery(ledger_repository, projection_repository)
    source = SentinelProjectionDecisionSource(projection_repository, decision_query)

    result = source.get_decision("dec-001")

    assert result.approval_status is ApprovalStatus.APPROVED


def test_get_decision_populates_rejected_verdict_from_decision_query():
    rejected_at = datetime.datetime(2026, 8, 8, 10, 4, 0)
    event = _make_approval_recorded_event("dec-001", ApprovalStatus.REJECTED, rejected_at)
    ledger_repository, projection_repository = _make_decision_query([event])
    projection_repository.save(_make_projection())
    decision_query = DecisionQuery(ledger_repository, projection_repository)
    source = SentinelProjectionDecisionSource(projection_repository, decision_query)

    result = source.get_decision("dec-001")

    assert result.approval_status is ApprovalStatus.REJECTED


def test_list_decisions_populates_approval_status_for_each_decision():
    approved_event = _make_approval_recorded_event(
        "dec-001", ApprovalStatus.APPROVED, datetime.datetime(2026, 8, 8, 9, 34, 0)
    )
    rejected_event = _make_approval_recorded_event(
        "dec-002", ApprovalStatus.REJECTED, datetime.datetime(2026, 8, 8, 10, 4, 0)
    )
    ledger_repository, projection_repository = _make_decision_query(
        [approved_event, rejected_event]
    )
    projection_repository.save(_make_projection(decision_id="dec-001", symbol="AAPL"))
    projection_repository.save(_make_projection(decision_id="dec-002", symbol="MSFT"))
    decision_query = DecisionQuery(ledger_repository, projection_repository)
    source = SentinelProjectionDecisionSource(projection_repository, decision_query)

    results = source.list_decisions(["dec-001", "dec-002"])

    verdicts = {r.decision_id: r.approval_status for r in results}
    assert verdicts["dec-001"] is ApprovalStatus.APPROVED
    assert verdicts["dec-002"] is ApprovalStatus.REJECTED
