"""Tests for applications.trading_intelligence.adapters.sentinel_audit_source."""
import datetime

from sentinel_engine.domain.decision import Decision
from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.queries.decision_query import DecisionQuery
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService

import pytest

from applications.trading_intelligence.adapters.sentinel_audit_source import SentinelAuditSource
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.audit_entry import AuditEntry


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
        timestamp=datetime.datetime(2026, 8, 8, 9, 0, 0),
        confidence=0.82,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
    )
    defaults.update(overrides)
    return Decision(**defaults)


def _make_evidence(**overrides):
    defaults = dict(
        evidence_id="ev-001",
        evidence_type="NEWS_SENTIMENT",
        source="newsapi",
        data={"score": 0.62},
        collected_at=datetime.datetime(2026, 8, 8, 9, 5, 0),
    )
    defaults.update(overrides)
    return Evidence(**defaults)


def _make_wiring():
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()
    decision_service = DecisionService(ledger_repository, projection_repository)
    evidence_service = EvidenceService(ledger_repository, projection_repository)
    decision_query = DecisionQuery(ledger_repository, projection_repository)
    source = SentinelAuditSource(decision_query)
    return decision_service, evidence_service, source


class _BoomDecisionQuery:
    def get_decision_timeline(self, decision_id):
        raise TimeoutError("simulated infrastructure failure")


def test_get_audit_trail_translates_decision_query_exceptions():
    source = SentinelAuditSource(_BoomDecisionQuery())

    with pytest.raises(TradingIntelligenceReadError) as excinfo:
        source.get_audit_trail("dec-001")

    assert isinstance(excinfo.value.__cause__, TimeoutError)


def test_get_audit_trail_maps_event_to_entry_correctly():
    decision_service, _, source = _make_wiring()
    decision_service.create_decision(_make_decision())

    result = source.get_audit_trail("dec-001")

    assert len(result) == 1
    assert isinstance(result[0], AuditEntry)


def test_get_audit_trail_preserves_event_type():
    decision_service, _, source = _make_wiring()
    decision_service.create_decision(_make_decision())

    result = source.get_audit_trail("dec-001")

    assert result[0].event_type == "DECISION_CREATED"


def test_get_audit_trail_preserves_created_at():
    decision_service, _, source = _make_wiring()
    created_at = datetime.datetime(2026, 8, 8, 9, 0, 0)
    decision_service.create_decision(_make_decision(timestamp=created_at))

    result = source.get_audit_trail("dec-001")

    assert result[0].created_at == created_at


def test_get_audit_trail_returns_empty_list_for_a_decision_with_no_events():
    _, _, source = _make_wiring()

    assert source.get_audit_trail("missing-decision") == []


def test_get_audit_trail_returns_multiple_events_in_chronological_order():
    decision_service, evidence_service, source = _make_wiring()
    decision_service.create_decision(_make_decision(
        timestamp=datetime.datetime(2026, 8, 8, 9, 0, 0),
    ))
    evidence_service.associate_evidence("dec-001", _make_evidence(
        collected_at=datetime.datetime(2026, 8, 8, 9, 5, 0),
    ))

    result = source.get_audit_trail("dec-001")

    assert [entry.event_type for entry in result] == ["DECISION_CREATED", "EVIDENCE_ATTACHED"]
    assert [entry.created_at for entry in result] == [
        datetime.datetime(2026, 8, 8, 9, 0, 0),
        datetime.datetime(2026, 8, 8, 9, 5, 0),
    ]


def test_get_audit_trail_does_not_reorder_events_from_the_timeline():
    """The adapter must pass timeline.events through as-is -- DecisionQuery
    already sorts them (see its own docstring/tests) -- rather than applying
    any ordering of its own."""
    later = datetime.datetime(2026, 8, 8, 9, 30, 0)
    earlier = datetime.datetime(2026, 8, 8, 9, 0, 0)

    class _Event:
        def __init__(self, event_type, created_at):
            self.event_type = event_type
            self.created_at = created_at

    class _Timeline:
        events = [_Event("GOVERNANCE_EVALUATED", later), _Event("DECISION_CREATED", earlier)]

    class _StubDecisionQuery:
        def get_decision_timeline(self, decision_id):
            return _Timeline()

    source = SentinelAuditSource(_StubDecisionQuery())

    result = source.get_audit_trail("dec-001")

    assert [entry.event_type for entry in result] == ["GOVERNANCE_EVALUATED", "DECISION_CREATED"]


def test_get_audit_trail_never_calls_a_write_operation():
    """Read-only: mirrors test_sentinel_evidence_source.py's own
    write-forbidding regression test."""
    real_store = _InMemoryLedgerStore()
    real_ledger_repository = LedgerRepository(real_store)
    real_projection_repository = _InMemoryProjectionRepository()
    decision_service = DecisionService(real_ledger_repository, real_projection_repository)
    decision_service.create_decision(_make_decision())

    class _AssertNoAppendStore(LedgerStore):
        def append(self, event):
            raise AssertionError("SentinelAuditSource must never append ledger events")

        def read_all(self):
            return real_store.read_all()

    class _AssertNoSaveProjectionRepository(ProjectionRepository):
        def get(self, decision_id):
            return real_projection_repository.get(decision_id)

        def save(self, projection):
            raise AssertionError("SentinelAuditSource must never save a projection")

    read_only_query = DecisionQuery(
        LedgerRepository(_AssertNoAppendStore()),
        _AssertNoSaveProjectionRepository(),
    )
    source = SentinelAuditSource(read_only_query)

    result = source.get_audit_trail("dec-001")

    assert len(result) == 1
