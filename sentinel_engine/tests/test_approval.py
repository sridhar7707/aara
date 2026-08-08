"""Tests for sentinel_engine.governance.approval.Approval."""
import datetime
import dataclasses

import pytest

from sentinel_engine.governance.approval import Approval
from sentinel_engine.governance.approval_status import ApprovalStatus


def _make_approval(**overrides):
    defaults = dict(
        approval_id="apr-001",
        decision_id="dec-001",
        status=ApprovalStatus.APPROVED,
        approved_by="risk_officer",
        timestamp=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return Approval(**defaults)


def test_approval_can_be_created_with_required_fields():
    approval = _make_approval()
    assert approval.approval_id == "apr-001"
    assert approval.decision_id == "dec-001"
    assert approval.status == ApprovalStatus.APPROVED
    assert approval.approved_by == "risk_officer"
    assert approval.timestamp == datetime.datetime(2026, 8, 4, 12, 0, 0)


def test_approval_is_a_dataclass():
    assert dataclasses.is_dataclass(Approval)


def test_approval_is_immutable():
    approval = _make_approval()
    with pytest.raises(dataclasses.FrozenInstanceError):
        approval.status = ApprovalStatus.REJECTED


def test_approval_requires_all_fields():
    with pytest.raises(TypeError):
        Approval(approval_id="apr-001", decision_id="dec-001")
