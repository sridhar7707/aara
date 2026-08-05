import pytest

from bot.decision_engine.decision_state import (
    DecisionState,
    InvalidStateTransitionError,
    transition,
)


def test_enum_has_all_expected_values():
    assert {s.name for s in DecisionState} == {
        "OBSERVED",
        "EVALUATING",
        "RECOMMENDED",
        "APPROVED",
        "REJECTED",
        "EXECUTED",
    }


def test_valid_transition_observed_to_evaluating():
    assert transition(DecisionState.OBSERVED, DecisionState.EVALUATING) == DecisionState.EVALUATING


def test_valid_transition_evaluating_to_recommended():
    assert transition(DecisionState.EVALUATING, DecisionState.RECOMMENDED) == DecisionState.RECOMMENDED


def test_invalid_transition_rejected():
    with pytest.raises(InvalidStateTransitionError):
        transition(DecisionState.OBSERVED, DecisionState.APPROVED)


def test_rejected_state_is_terminal():
    with pytest.raises(InvalidStateTransitionError):
        transition(DecisionState.REJECTED, DecisionState.EVALUATING)


def test_decision_intelligence_cannot_transition_to_executed():
    with pytest.raises(InvalidStateTransitionError):
        transition(DecisionState.APPROVED, DecisionState.EXECUTED)
