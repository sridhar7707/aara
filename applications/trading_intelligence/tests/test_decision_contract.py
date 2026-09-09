"""Tests for applications.trading_intelligence.contracts.decision_contract.DecisionContract."""
import datetime
import dataclasses

import pytest

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.governance.approval_status import ApprovalStatus

from applications.trading_intelligence.contracts.decision_contract import DecisionContract


def _make_contract(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        status=DecisionState.DECISION_CREATED,
        confidence=0.78,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
        updated_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionContract(**defaults)


def test_decision_contract_can_be_created_with_required_fields():
    contract = _make_contract()
    assert contract.decision_id == "dec-001"
    assert contract.symbol == "AAPL"
    assert contract.action == "BUY"
    assert contract.status == DecisionState.DECISION_CREATED
    assert contract.confidence == 0.78
    assert contract.evidence_reference == "evidence-001"
    assert contract.risk_reference == "risk-001"
    assert contract.updated_at == datetime.datetime(2026, 8, 4, 12, 0, 0)


def test_decision_contract_is_a_dataclass():
    assert dataclasses.is_dataclass(DecisionContract)


def test_decision_contract_is_immutable():
    contract = _make_contract()
    with pytest.raises(dataclasses.FrozenInstanceError):
        contract.status = DecisionState.APPROVAL_RECORDED


def test_decision_contract_requires_all_fields():
    with pytest.raises(TypeError):
        DecisionContract(decision_id="dec-001", symbol="AAPL")


def test_decision_contract_approval_status_defaults_to_none():
    contract = _make_contract()
    assert contract.approval_status is None


def test_decision_contract_approval_status_can_be_approved():
    contract = _make_contract(approval_status=ApprovalStatus.APPROVED)
    assert contract.approval_status is ApprovalStatus.APPROVED


def test_decision_contract_approval_status_can_be_rejected():
    contract = _make_contract(approval_status=ApprovalStatus.REJECTED)
    assert contract.approval_status is ApprovalStatus.REJECTED


def test_decision_contract_action_source_defaults_to_none():
    """ADR-070: additive optional field -- every existing construction that
    omits it must keep working, with action_source None."""
    contract = _make_contract()
    assert contract.action_source is None


def test_decision_contract_action_source_can_be_sentinel():
    contract = _make_contract(action_source="SENTINEL")
    assert contract.action_source == "SENTINEL"


def test_decision_contract_action_source_can_be_strategy():
    contract = _make_contract(action_source="STRATEGY")
    assert contract.action_source == "STRATEGY"


def test_decision_contract_action_source_is_carried_verbatim():
    """The contract only relays the string -- it does not validate it
    against ActionSource, normalise it, or default it."""
    contract = _make_contract(action_source="STRATEGY")
    assert contract.action_source == "STRATEGY"
    assert contract.action == "BUY"  # unrelated field untouched
