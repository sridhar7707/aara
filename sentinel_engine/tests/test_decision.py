"""Tests for sentinel_engine.domain.decision.Decision."""
import datetime
import dataclasses

import pytest

from sentinel_engine.domain.action_source import ActionSource
from sentinel_engine.domain.decision import Decision
from sentinel_engine.domain.decision_action import DecisionAction


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


def test_decision_optional_fields_default_to_none():
    """Batch 2 + ADR-069 additive fields must not break existing callers that
    construct a Decision without them (legacy / unknown provenance)."""
    decision = _make_decision()
    assert decision.horizon is None
    assert decision.desired_allocation is None
    assert decision.minimum_viable_allocation is None
    assert decision.uncertainty is None
    assert decision.thesis is None
    assert decision.counterfactual is None
    assert decision.action_source is None


@pytest.mark.parametrize("source", [ActionSource.STRATEGY.value, ActionSource.SENTINEL.value])
def test_decision_accepts_action_source_when_provided(source):
    decision = _make_decision(action_source=source)
    assert decision.action_source == source


def test_decision_action_source_is_immutable():
    decision = _make_decision(action_source=ActionSource.SENTINEL.value)
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.action_source = ActionSource.STRATEGY.value


def test_legacy_decision_construction_without_action_source_still_valid():
    # no action_source kwarg -- exactly how every pre-ADR-069 caller builds one
    decision = Decision(
        decision_id="dec-legacy",
        symbol="AAPL",
        action="BUY",
        timestamp=datetime.datetime(2026, 8, 4, 12, 0, 0),
        confidence=0.5,
        evidence_reference="e",
        risk_reference="r",
    )
    assert decision.action_source is None


def test_decision_preserves_all_batch_2_fields_when_provided():
    decision = _make_decision(
        horizon="TACTICAL",
        desired_allocation=5000.0,
        minimum_viable_allocation=1500.0,
        uncertainty=0.4,
        thesis="Foundry capacity is the bottleneck through 2026.",
        counterfactual="Yes -- would open this position today at today's price.",
    )
    assert decision.horizon == "TACTICAL"
    assert decision.desired_allocation == 5000.0
    assert decision.minimum_viable_allocation == 1500.0
    assert decision.uncertainty == 0.4
    assert decision.thesis == "Foundry capacity is the bottleneck through 2026."
    assert decision.counterfactual == "Yes -- would open this position today at today's price."


@pytest.mark.parametrize("action", [
    DecisionAction.BUY,
    DecisionAction.BUY_MORE,
    DecisionAction.HOLD,
    DecisionAction.SELL,
    DecisionAction.WAIT,
])
def test_decision_accepts_each_p0_action(action):
    decision = _make_decision(action=action.value)
    assert decision.action == action.value


def test_buy_more_decision_is_distinguishable_from_buy_decision():
    buy = _make_decision(action=DecisionAction.BUY.value)
    buy_more = _make_decision(action=DecisionAction.BUY_MORE.value)
    assert buy.action != buy_more.action
