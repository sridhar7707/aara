"""Tests for sentinel_engine.governance.approval_status."""
from sentinel_engine.governance.approval_status import ApprovalStatus


def test_all_expected_approval_statuses_exist():
    assert ApprovalStatus.APPROVED == "APPROVED"
    assert ApprovalStatus.REJECTED == "REJECTED"


def test_approval_status_has_exactly_two_members():
    assert len(list(ApprovalStatus)) == 2


def test_approval_status_members_are_strings():
    for member in ApprovalStatus:
        assert isinstance(member.value, str)


def test_valid_approval_status_string_is_recognized():
    assert ApprovalStatus.has_value("APPROVED") is True
    assert ApprovalStatus.has_value("REJECTED") is True


def test_invalid_approval_status_string_is_rejected():
    assert ApprovalStatus.has_value("PENDING") is False
