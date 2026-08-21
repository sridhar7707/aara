"""Tests for applications.trading_intelligence.services.decision_query_service."""
import datetime

import pytest

from sentinel_engine.domain.decision_state import DecisionState

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
        status=DecisionState.DECISION_CREATED,
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

    def list_decisions(self, decision_ids):
        return [self._decisions[d] for d in decision_ids if d in self._decisions]


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
    assert view.status == DecisionState.DECISION_CREATED


def test_get_decision_view_delegates_to_the_injected_source_not_a_shared_default():
    source_a = _InMemoryDecisionSource({"dec-001": _make_contract()})
    source_b = _InMemoryDecisionSource()
    service_a = DecisionQueryService(source_a)
    service_b = DecisionQueryService(source_b)

    assert service_a.get_decision_view("dec-001") is not None
    assert service_b.get_decision_view("dec-001") is None


def test_incomplete_decision_source_subclass_cannot_be_instantiated():
    class _Incomplete(DecisionSource):
        pass  # get_decision/list_decisions deliberately not implemented

    with pytest.raises(TypeError):
        _Incomplete()


def test_list_decision_views_returns_empty_list_when_no_ids_requested():
    service = DecisionQueryService(_InMemoryDecisionSource())

    assert service.list_decision_views([]) == []


def test_list_decision_views_returns_empty_list_when_source_has_no_matches():
    service = DecisionQueryService(_InMemoryDecisionSource())

    assert service.list_decision_views(["missing-1", "missing-2"]) == []


def test_list_decision_views_returns_multiple_views():
    contract_a = _make_contract(decision_id="dec-001", symbol="AAPL")
    contract_b = _make_contract(decision_id="dec-002", symbol="MSFT")
    source = _InMemoryDecisionSource({"dec-001": contract_a, "dec-002": contract_b})
    service = DecisionQueryService(source)

    views = service.list_decision_views(["dec-001", "dec-002"])

    assert [v.decision_id for v in views] == ["dec-001", "dec-002"]
    assert [v.symbol for v in views] == ["AAPL", "MSFT"]


def test_list_decision_views_skips_ids_the_source_does_not_have():
    source = _InMemoryDecisionSource({"dec-001": _make_contract()})
    service = DecisionQueryService(source)

    views = service.list_decision_views(["dec-001", "missing-decision"])

    assert len(views) == 1
    assert views[0].decision_id == "dec-001"


def test_get_decision_view_still_works_after_list_support_added():
    contract = _make_contract()
    service = DecisionQueryService(_InMemoryDecisionSource({"dec-001": contract}))

    view = service.get_decision_view("dec-001")

    assert view is not None
    assert view.decision_id == "dec-001"


def test_get_decision_references_returns_the_raw_evidence_and_risk_reference():
    contract = _make_contract(evidence_reference="evidence-001", risk_reference="risk-001")
    service = DecisionQueryService(_InMemoryDecisionSource({"dec-001": contract}))

    references = service.get_decision_references("dec-001")

    assert references == ("evidence-001", "risk-001")


def test_get_decision_references_returns_none_when_source_has_no_decision():
    service = DecisionQueryService(_InMemoryDecisionSource())

    assert service.get_decision_references("missing-decision") is None
