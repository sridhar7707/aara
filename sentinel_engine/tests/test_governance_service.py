"""Tests for sentinel_engine.services.governance_service.GovernanceService."""
import datetime

from sentinel_engine.services.governance_service import GovernanceService
from sentinel_engine.governance.policy import Policy
from sentinel_engine.governance.approval import Approval


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
        status="APPROVED",
        approved_by="risk_officer",
        timestamp=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return Approval(**defaults)


def test_get_policy_returns_none_when_not_registered():
    service = GovernanceService()

    assert service.get_policy("missing-policy") is None


def test_register_policy_then_get_policy_returns_it():
    service = GovernanceService()
    policy = _make_policy()

    service.register_policy(policy)

    assert service.get_policy("pol-001") == policy


def test_is_policy_enabled_reflects_the_policy_flag():
    service = GovernanceService()
    service.register_policy(_make_policy(enabled=False))

    assert service.is_policy_enabled("pol-001") is False


def test_is_policy_enabled_returns_false_for_unknown_policy():
    service = GovernanceService()

    assert service.is_policy_enabled("missing-policy") is False


def test_get_approval_returns_none_when_not_recorded():
    service = GovernanceService()

    assert service.get_approval("dec-001") is None


def test_record_approval_then_get_approval_returns_it():
    service = GovernanceService()
    approval = _make_approval()

    service.record_approval(approval)

    assert service.get_approval("dec-001") == approval


def test_governance_service_does_not_expose_internal_storage_attributes():
    service = GovernanceService()

    assert not hasattr(service, "policies")
    assert not hasattr(service, "approvals")
