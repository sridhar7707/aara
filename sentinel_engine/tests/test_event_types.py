"""Tests for sentinel_engine.events.event_types."""
from sentinel_engine.events.event_types import EventType


def test_all_expected_event_types_exist():
    assert EventType.CANDIDATE_EVALUATED == "CANDIDATE_EVALUATED"
    assert EventType.DECISION_CREATED == "DECISION_CREATED"
    assert EventType.RISK_EVALUATED == "RISK_EVALUATED"
    assert EventType.DECISION_EXECUTED == "DECISION_EXECUTED"
    assert EventType.DECISION_OUTCOME_RECORDED == "DECISION_OUTCOME_RECORDED"


def test_event_type_members_are_strings():
    for member in EventType:
        assert isinstance(member.value, str)


def test_valid_event_type_string_is_recognized():
    assert EventType.has_value("DECISION_CREATED") is True


def test_invalid_event_type_string_is_rejected():
    assert EventType.has_value("NOT_A_REAL_EVENT_TYPE") is False
