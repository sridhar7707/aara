"""Tests for applications.trading_intelligence.adapters.sentinel_governance_source."""
import datetime

from sentinel_engine.domain.decision import Decision
from sentinel_engine.governance.approval import Approval
from sentinel_engine.governance.approval_status import ApprovalStatus
from sentinel_engine.governance.policy import Policy
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.queries.decision_query import DecisionQuery
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.governance_service import GovernanceService

import pytest

from applications.trading_intelligence.adapters.sentinel_governance_source import (
    SentinelGovernanceSource,
)
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.approval_entry import ApprovalEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.services.decision_governance_query_service import (
    GovernanceSource,
)


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


def _make_policy(**overrides):
    defaults = dict(
        policy_id="pol-001",
        name="max_position_size",
        description="Caps single-position exposure as a percent of portfolio value.",
        enabled=True,
    )
    defaults.update(overrides)
    return Policy(**defaults)


def _make_approval(**overrides):
    defaults = dict(
        approval_id="apr-001",
        decision_id="dec-001",
        status=ApprovalStatus.APPROVED,
        approved_by="risk_officer",
        timestamp=datetime.datetime(2026, 8, 8, 9, 10, 0),
    )
    defaults.update(overrides)
    return Approval(**defaults)


def _make_wiring():
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()
    decision_service = DecisionService(ledger_repository, projection_repository)
    governance_service = GovernanceService(ledger_repository, projection_repository)
    decision_query = DecisionQuery(ledger_repository, projection_repository)
    source = SentinelGovernanceSource(decision_query)
    return decision_service, governance_service, source


class _BoomDecisionQuery:
    def get_decision_timeline(self, decision_id):
        raise OSError("simulated infrastructure failure")


def test_get_governance_translates_decision_query_exceptions():
    source = SentinelGovernanceSource(_BoomDecisionQuery())

    with pytest.raises(TradingIntelligenceReadError) as excinfo:
        source.get_governance("dec-001")

    assert isinstance(excinfo.value.__cause__, OSError)


def test_get_approvals_translates_decision_query_exceptions():
    source = SentinelGovernanceSource(_BoomDecisionQuery())

    with pytest.raises(TradingIntelligenceReadError) as excinfo:
        source.get_approvals("dec-001")

    assert isinstance(excinfo.value.__cause__, OSError)


def test_sentinel_governance_source_is_a_governance_source():
    _, _, source = _make_wiring()

    assert isinstance(source, GovernanceSource)


def test_get_governance_maps_summary_to_entry_correctly():
    decision_service, governance_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    governance_service.register_policy(_make_policy())
    governance_service.evaluate_policy("dec-001", "pol-001")

    result = source.get_governance("dec-001")

    assert len(result) == 1
    assert isinstance(result[0], GovernanceEntry)


def test_get_governance_preserves_policy_id():
    decision_service, governance_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    governance_service.register_policy(_make_policy(policy_id="pol-max-pos"))
    governance_service.evaluate_policy("dec-001", "pol-max-pos")

    result = source.get_governance("dec-001")

    assert result[0].policy_id == "pol-max-pos"


def test_get_governance_preserves_enabled():
    decision_service, governance_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    governance_service.register_policy(_make_policy(enabled=False))
    governance_service.evaluate_policy("dec-001", "pol-001")

    result = source.get_governance("dec-001")

    assert result[0].enabled is False


def test_get_governance_returns_empty_list_for_a_decision_with_no_governance():
    decision_service, _, source = _make_wiring()
    decision_service.create_decision(_make_decision())

    assert source.get_governance("dec-001") == []


def test_get_governance_returns_empty_list_for_a_missing_decision():
    _, _, source = _make_wiring()

    assert source.get_governance("missing-decision") == []


def test_get_governance_returns_multiple_entries_in_order():
    decision_service, governance_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    governance_service.register_policy(_make_policy(policy_id="pol-001"))
    governance_service.register_policy(_make_policy(policy_id="pol-002"))
    governance_service.evaluate_policy("dec-001", "pol-001")
    governance_service.evaluate_policy("dec-001", "pol-002")

    result = source.get_governance("dec-001")

    assert [entry.policy_id for entry in result] == ["pol-001", "pol-002"]


def test_get_approvals_maps_summary_to_entry_correctly():
    decision_service, governance_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    governance_service.record_approval(_make_approval())

    result = source.get_approvals("dec-001")

    assert len(result) == 1
    assert isinstance(result[0], ApprovalEntry)


def test_get_approvals_preserves_approval_id():
    decision_service, governance_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    governance_service.record_approval(_make_approval(approval_id="apr-xyz"))

    result = source.get_approvals("dec-001")

    assert result[0].approval_id == "apr-xyz"


def test_get_approvals_preserves_status():
    decision_service, governance_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    governance_service.record_approval(_make_approval(status=ApprovalStatus.REJECTED))

    result = source.get_approvals("dec-001")

    assert result[0].status == ApprovalStatus.REJECTED


def test_get_approvals_preserves_approved_by():
    decision_service, governance_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    governance_service.record_approval(_make_approval(approved_by="cro"))

    result = source.get_approvals("dec-001")

    assert result[0].approved_by == "cro"


def test_get_approvals_preserves_approved_at():
    decision_service, governance_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    approved_at = datetime.datetime(2026, 8, 8, 9, 10, 0)
    governance_service.record_approval(_make_approval(timestamp=approved_at))

    result = source.get_approvals("dec-001")

    assert result[0].approved_at == approved_at


def test_get_approvals_returns_empty_list_for_a_decision_with_no_approvals():
    decision_service, _, source = _make_wiring()
    decision_service.create_decision(_make_decision())

    assert source.get_approvals("dec-001") == []


def test_get_approvals_returns_empty_list_for_a_missing_decision():
    _, _, source = _make_wiring()

    assert source.get_approvals("missing-decision") == []


def test_get_governance_never_calls_a_write_operation():
    """Read-only: mirrors test_sentinel_evidence_source.py's own
    write-forbidding regression test -- setup writes through real
    repositories first, then wraps the same underlying data in
    read-delegating, write-forbidding fakes and exercises get_governance()
    against those; any write call fails the test."""
    real_store = _InMemoryLedgerStore()
    real_ledger_repository = LedgerRepository(real_store)
    real_projection_repository = _InMemoryProjectionRepository()
    decision_service = DecisionService(real_ledger_repository, real_projection_repository)
    governance_service = GovernanceService(real_ledger_repository, real_projection_repository)
    decision_service.create_decision(_make_decision())
    governance_service.register_policy(_make_policy())
    governance_service.evaluate_policy("dec-001", "pol-001")

    class _AssertNoAppendStore(LedgerStore):
        def append(self, event):
            raise AssertionError("SentinelGovernanceSource must never append ledger events")

        def read_all(self):
            return real_store.read_all()

    class _AssertNoSaveProjectionRepository(ProjectionRepository):
        def get(self, decision_id):
            return real_projection_repository.get(decision_id)

        def save(self, projection):
            raise AssertionError("SentinelGovernanceSource must never save a projection")

    read_only_query = DecisionQuery(
        LedgerRepository(_AssertNoAppendStore()),
        _AssertNoSaveProjectionRepository(),
    )
    source = SentinelGovernanceSource(read_only_query)

    result = source.get_governance("dec-001")

    assert len(result) == 1


def test_get_approvals_never_calls_a_write_operation():
    real_store = _InMemoryLedgerStore()
    real_ledger_repository = LedgerRepository(real_store)
    real_projection_repository = _InMemoryProjectionRepository()
    decision_service = DecisionService(real_ledger_repository, real_projection_repository)
    governance_service = GovernanceService(real_ledger_repository, real_projection_repository)
    decision_service.create_decision(_make_decision())
    governance_service.record_approval(_make_approval())

    class _AssertNoAppendStore(LedgerStore):
        def append(self, event):
            raise AssertionError("SentinelGovernanceSource must never append ledger events")

        def read_all(self):
            return real_store.read_all()

    class _AssertNoSaveProjectionRepository(ProjectionRepository):
        def get(self, decision_id):
            return real_projection_repository.get(decision_id)

        def save(self, projection):
            raise AssertionError("SentinelGovernanceSource must never save a projection")

    read_only_query = DecisionQuery(
        LedgerRepository(_AssertNoAppendStore()),
        _AssertNoSaveProjectionRepository(),
    )
    source = SentinelGovernanceSource(read_only_query)

    result = source.get_approvals("dec-001")

    assert len(result) == 1
