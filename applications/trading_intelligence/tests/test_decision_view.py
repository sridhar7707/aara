"""Tests for applications.trading_intelligence.projections.decision_view.DecisionView."""
import datetime
import dataclasses

import pytest

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.governance.approval_status import ApprovalStatus

from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.projections.decision_view import DecisionView


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


def test_decision_view_is_a_dataclass():
    assert dataclasses.is_dataclass(DecisionView)


def test_decision_view_is_immutable():
    view = DecisionView.from_contract(_make_contract())
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.status = DecisionState.APPROVAL_RECORDED


def test_from_contract_maps_fields_correctly():
    contract = _make_contract()

    view = DecisionView.from_contract(contract)

    assert view.decision_id == "dec-001"
    assert view.symbol == "AAPL"
    assert view.action == "BUY"
    assert view.status == DecisionState.DECISION_CREATED
    assert view.confidence == 0.78
    assert view.updated_at == datetime.datetime(2026, 8, 4, 12, 0, 0)


def test_from_contract_does_not_carry_internal_references():
    """The view is a UI-facing read model, not a passthrough of the contract --
    evidence_reference/risk_reference are internal pointers the UI doesn't need."""
    view = DecisionView.from_contract(_make_contract())

    assert not hasattr(view, "evidence_reference")
    assert not hasattr(view, "risk_reference")


def test_from_contract_maps_approval_status_when_present():
    contract = _make_contract(approval_status=ApprovalStatus.REJECTED)

    view = DecisionView.from_contract(contract)

    assert view.approval_status is ApprovalStatus.REJECTED


def test_from_contract_defaults_approval_status_to_none():
    view = DecisionView.from_contract(_make_contract())

    assert view.approval_status is None
