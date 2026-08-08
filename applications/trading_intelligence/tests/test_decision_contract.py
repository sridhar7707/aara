"""Tests for applications.trading_intelligence.contracts.decision_contract.DecisionContract."""
import datetime
import dataclasses

import pytest

from sentinel_engine.domain.decision_state import DecisionState

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
