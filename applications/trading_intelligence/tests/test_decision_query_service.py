"""Tests for applications.trading_intelligence.services.decision_query_service."""
import datetime

import pytest

from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.services.decision_query_service import (
    DecisionQueryService,
    DecisionSource,
)


def _make_contract(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        status="DECISION_CREATED",
        confidence=0.78,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
        updated_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionContract(**defaults)


class _InMemoryDecisionSource(DecisionSource):
    """Minimal conforming implementation used only to exercise the service --
    not a real source, per the task's 'do not implement source' constraint."""

    def __init__(self, decisions=None):
        self._decisions = decisions or {}

    def get_decision(self, decision_id):
        return self._decisions.get(decision_id)


def test_decision_source_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        DecisionSource()


def test_get_decision_view_returns_none_when_source_has_no_decision():
    service = DecisionQueryService(_InMemoryDecisionSource())

    assert service.get_decision_view("missing-decision") is None


def test_get_decision_view_returns_a_view_built_from_the_source_contract():
    contract = _make_contract()
    source = _InMemoryDecisionSource({"dec-001": contract})
    service = DecisionQueryService(source)

    view = service.get_decision_view("dec-001")

    assert view is not None
    assert view.decision_id == "dec-001"
    assert view.symbol == "AAPL"
    assert view.status == "DECISION_CREATED"


def test_get_decision_view_delegates_to_the_injected_source_not_a_shared_default():
    source_a = _InMemoryDecisionSource({"dec-001": _make_contract()})
    source_b = _InMemoryDecisionSource()
    service_a = DecisionQueryService(source_a)
    service_b = DecisionQueryService(source_b)

    assert service_a.get_decision_view("dec-001") is not None
    assert service_b.get_decision_view("dec-001") is None


def test_incomplete_decision_source_subclass_cannot_be_instantiated():
    class _Incomplete(DecisionSource):
        pass  # get_decision deliberately not implemented

    with pytest.raises(TypeError):
        _Incomplete()
