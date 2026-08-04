"""Tests for sentinel_engine.domain.decision.Decision."""
import datetime
import dataclasses

import pytest

from sentinel_engine.domain.decision import Decision


def _make_decision(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        timestamp=datetime.datetime(2026, 8, 4, 12, 0, 0),
        confidence=0.78,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
    )
    defaults.update(overrides)
    return Decision(**defaults)


def test_decision_can_be_created_with_required_fields():
    decision = _make_decision()
    assert decision.decision_id == "dec-001"
    assert decision.symbol == "AAPL"
    assert decision.action == "BUY"
    assert decision.timestamp == datetime.datetime(2026, 8, 4, 12, 0, 0)
    assert decision.confidence == 0.78
    assert decision.evidence_reference == "evidence-001"
    assert decision.risk_reference == "risk-001"


def test_decision_is_a_dataclass():
    assert dataclasses.is_dataclass(Decision)


def test_decision_is_immutable():
    decision = _make_decision()
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.action = "SELL"


def test_decision_requires_all_fields():
    with pytest.raises(TypeError):
        Decision(decision_id="dec-001", symbol="AAPL")
