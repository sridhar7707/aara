"""Tests for sentinel_engine.domain.decision_action."""
from sentinel_engine.domain.decision_action import DecisionAction


def test_all_expected_decision_actions_exist():
    assert DecisionAction.BUY == "BUY"
    assert DecisionAction.BUY_MORE == "BUY_MORE"
    assert DecisionAction.HOLD == "HOLD"
    assert DecisionAction.SELL == "SELL"
    assert DecisionAction.WAIT == "WAIT"


def test_decision_action_has_exactly_five_members():
    assert len(list(DecisionAction)) == 5


def test_decision_action_members_are_strings():
    for member in DecisionAction:
        assert isinstance(member.value, str)


def test_valid_decision_action_strings_are_recognized():
    assert DecisionAction.has_value("BUY") is True
    assert DecisionAction.has_value("BUY_MORE") is True
    assert DecisionAction.has_value("HOLD") is True
    assert DecisionAction.has_value("SELL") is True
    assert DecisionAction.has_value("WAIT") is True


def test_invalid_decision_action_string_is_rejected():
    assert DecisionAction.has_value("REJECT") is False
    assert DecisionAction.has_value("BUY MORE") is False
    assert DecisionAction.has_value("") is False


def test_buy_more_is_distinct_from_buy():
    """BUY MORE always refers to an existing position and requires the P0
    blank-slate reassessment behavior; it must never collapse into BUY."""
    assert DecisionAction.BUY != DecisionAction.BUY_MORE
    assert DecisionAction.BUY.value != DecisionAction.BUY_MORE.value
