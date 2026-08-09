"""Tests for applications.trading_intelligence.services.decision_governance_query_service."""
import datetime

import pytest

from applications.trading_intelligence.projections.approval_entry import ApprovalEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.services.decision_governance_query_service import (
    DecisionGovernanceQueryService,
    GovernanceSource,
)
from sentinel_engine.governance.approval_status import ApprovalStatus


def _make_governance_entry(**overrides):
    defaults = dict(
        policy_id="pol-001",
        enabled=True,
        evaluated_at=datetime.datetime(2026, 8, 8, 9, 5, 0),
    )
    defaults.update(overrides)
    return GovernanceEntry(**defaults)


def _make_approval_entry(**overrides):
    defaults = dict(
        status=ApprovalStatus.APPROVED,
        approved_by="risk_officer",
        approved_at=datetime.datetime(2026, 8, 8, 9, 10, 0),
    )
    defaults.update(overrides)
    return ApprovalEntry(**defaults)


class _InMemoryGovernanceSource(GovernanceSource):
    """Minimal conforming implementation used only to exercise the service --
    not a real source, matching decision_evidence_query_service's own test
    pattern."""

    def __init__(self, governance_by_decision=None, approvals_by_decision=None):
        self._governance_by_decision = governance_by_decision or {}
        self._approvals_by_decision = approvals_by_decision or {}

    def get_governance(self, decision_id):
        return list(self._governance_by_decision.get(decision_id, []))

    def get_approvals(self, decision_id):
        return list(self._approvals_by_decision.get(decision_id, []))


def test_governance_source_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        GovernanceSource()


def test_incomplete_governance_source_subclass_cannot_be_instantiated():
    class _Incomplete(GovernanceSource):
        pass  # get_governance/get_approvals deliberately not implemented

    with pytest.raises(TypeError):
        _Incomplete()


def test_get_governance_returns_empty_list_when_source_has_no_governance():
    service = DecisionGovernanceQueryService(_InMemoryGovernanceSource())

    assert service.get_governance("dec-001") == []


def test_get_governance_returns_entries_from_the_source():
    entry = _make_governance_entry()
    source = _InMemoryGovernanceSource(governance_by_decision={"dec-001": [entry]})
    service = DecisionGovernanceQueryService(source)

    result = service.get_governance("dec-001")

    assert result == [entry]


def test_get_governance_returns_multiple_entries():
    entry_a = _make_governance_entry(policy_id="pol-001")
    entry_b = _make_governance_entry(policy_id="pol-002")
    source = _InMemoryGovernanceSource(governance_by_decision={"dec-001": [entry_a, entry_b]})
    service = DecisionGovernanceQueryService(source)

    result = service.get_governance("dec-001")

    assert result == [entry_a, entry_b]


def test_get_approvals_returns_empty_list_when_source_has_no_approvals():
    service = DecisionGovernanceQueryService(_InMemoryGovernanceSource())

    assert service.get_approvals("dec-001") == []


def test_get_approvals_returns_entries_from_the_source():
    entry = _make_approval_entry()
    source = _InMemoryGovernanceSource(approvals_by_decision={"dec-001": [entry]})
    service = DecisionGovernanceQueryService(source)

    result = service.get_approvals("dec-001")

    assert result == [entry]


def test_get_governance_delegates_to_the_injected_source_not_a_shared_default():
    source_a = _InMemoryGovernanceSource(governance_by_decision={"dec-001": [_make_governance_entry()]})
    source_b = _InMemoryGovernanceSource()
    service_a = DecisionGovernanceQueryService(source_a)
    service_b = DecisionGovernanceQueryService(source_b)

    assert service_a.get_governance("dec-001") == [_make_governance_entry()]
    assert service_b.get_governance("dec-001") == []


def test_get_approvals_delegates_to_the_injected_source_not_a_shared_default():
    source_a = _InMemoryGovernanceSource(approvals_by_decision={"dec-001": [_make_approval_entry()]})
    source_b = _InMemoryGovernanceSource()
    service_a = DecisionGovernanceQueryService(source_a)
    service_b = DecisionGovernanceQueryService(source_b)

    assert service_a.get_approvals("dec-001") == [_make_approval_entry()]
    assert service_b.get_approvals("dec-001") == []
