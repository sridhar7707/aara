"""Tests for sentinel_engine.events.event_types."""
from sentinel_engine.events.event_types import EventType


def test_all_expected_event_types_exist():
    assert EventType.CANDIDATE_EVALUATED == "CANDIDATE_EVALUATED"
    assert EventType.DECISION_CREATED == "DECISION_CREATED"
    assert EventType.RISK_EVALUATED == "RISK_EVALUATED"
    assert EventType.DECISION_EXECUTED == "DECISION_EXECUTED"
    assert EventType.DECISION_OUTCOME_RECORDED == "DECISION_OUTCOME_RECORDED"


def test_evidence_and_governance_lifecycle_event_types_exist():
    assert EventType.EVIDENCE_ATTACHED == "EVIDENCE_ATTACHED"
    assert EventType.GOVERNANCE_EVALUATED == "GOVERNANCE_EVALUATED"
    assert EventType.APPROVAL_RECORDED == "APPROVAL_RECORDED"


def test_event_type_members_are_strings():
    for member in EventType:
        assert isinstance(member.value, str)


def test_valid_event_type_string_is_recognized():
    assert EventType.has_value("DECISION_CREATED") is True
    assert EventType.has_value("EVIDENCE_ATTACHED") is True
    assert EventType.has_value("GOVERNANCE_EVALUATED") is True
    assert EventType.has_value("APPROVAL_RECORDED") is True


def test_invalid_event_type_string_is_rejected():
    assert EventType.has_value("NOT_A_REAL_EVENT_TYPE") is False
