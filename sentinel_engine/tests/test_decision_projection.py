"""Tests for sentinel_engine.projections.decision_projection.DecisionProjection."""
import datetime
import dataclasses

import pytest

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.projections.decision_projection import DecisionProjection


def _make_projection(**overrides):
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
    return DecisionProjection(**defaults)


def test_decision_projection_can_be_created_with_required_fields():
    projection = _make_projection()
    assert projection.decision_id == "dec-001"
    assert projection.symbol == "AAPL"
    assert projection.action == "BUY"
    assert projection.status == DecisionState.DECISION_CREATED
    assert projection.confidence == 0.78
    assert projection.evidence_reference == "evidence-001"
    assert projection.risk_reference == "risk-001"
    assert projection.updated_at == datetime.datetime(2026, 8, 4, 12, 0, 0)


def test_decision_projection_is_a_dataclass():
    assert dataclasses.is_dataclass(DecisionProjection)


def test_decision_projection_is_immutable():
    projection = _make_projection()
    with pytest.raises(dataclasses.FrozenInstanceError):
        projection.status = DecisionState.APPROVAL_RECORDED


def test_decision_projection_requires_all_fields():
    with pytest.raises(TypeError):
        DecisionProjection(decision_id="dec-001", symbol="AAPL")
