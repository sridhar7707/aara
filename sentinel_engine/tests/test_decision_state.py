"""Tests for sentinel_engine.domain.decision_state."""
from sentinel_engine.domain.decision_state import DecisionState


def test_all_expected_decision_states_exist():
    assert DecisionState.DECISION_CREATED == "DECISION_CREATED"
    assert DecisionState.EVIDENCE_ATTACHED == "EVIDENCE_ATTACHED"
    assert DecisionState.GOVERNANCE_EVALUATED == "GOVERNANCE_EVALUATED"
    assert DecisionState.APPROVAL_RECORDED == "APPROVAL_RECORDED"


def test_decision_state_has_exactly_four_members():
    assert len(list(DecisionState)) == 4


def test_decision_state_members_are_strings():
    for member in DecisionState:
        assert isinstance(member.value, str)


def test_valid_decision_state_string_is_recognized():
    assert DecisionState.has_value("DECISION_CREATED") is True
    assert DecisionState.has_value("EVIDENCE_ATTACHED") is True
    assert DecisionState.has_value("GOVERNANCE_EVALUATED") is True
    assert DecisionState.has_value("APPROVAL_RECORDED") is True


def test_invalid_decision_state_string_is_rejected():
    assert DecisionState.has_value("NOT_A_REAL_STATE") is False


def test_decision_state_excludes_unreachable_event_types():
    """CANDIDATE_EVALUATED, RISK_EVALUATED, DECISION_EXECUTED, and
    DECISION_OUTCOME_RECORDED are declared EventType members but no current
    service transitions a decision into them -- they must stay out of
    DecisionState until a real service path produces them."""
    assert DecisionState.has_value("CANDIDATE_EVALUATED") is False
    assert DecisionState.has_value("RISK_EVALUATED") is False
    assert DecisionState.has_value("DECISION_EXECUTED") is False
    assert DecisionState.has_value("DECISION_OUTCOME_RECORDED") is False
