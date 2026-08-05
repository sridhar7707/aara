"""Tests for applications.trading_intelligence.ui.decision_center.controller."""
import datetime

from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.services.decision_query_service import (
    DecisionQueryService,
    DecisionSource,
)
from applications.trading_intelligence.ui.decision_center.controller import (
    DecisionCenterController,
)


class _InMemoryDecisionSource(DecisionSource):
    """Fake DecisionSource -- the real DecisionQueryService is used, only its
    dependency is faked, matching this codebase's established test pattern."""

    def __init__(self, decisions=None):
        self._decisions = decisions or {}

    def get_decision(self, decision_id):
        return self._decisions.get(decision_id)

    def list_decisions(self, decision_ids):
        return [self._decisions[d] for d in decision_ids if d in self._decisions]


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


def _make_controller(decisions=None):
    query_service = DecisionQueryService(_InMemoryDecisionSource(decisions or {}))
    return DecisionCenterController(query_service)


def test_load_decisions_returns_a_decision_list_area():
    controller = _make_controller({"dec-001": _make_contract()})

    list_area = controller.load_decisions(["dec-001"])

    assert list_area.is_empty is False
    assert list_area.decisions[0].decision_id == "dec-001"


def test_load_decisions_handles_empty_results():
    controller = _make_controller()

    list_area = controller.load_decisions(["missing-1"])

    assert list_area.is_empty is True
    assert list_area.empty_state_message == "No decisions recorded yet."


def test_load_decision_detail_returns_a_decision_detail_area():
    controller = _make_controller({"dec-001": _make_contract()})

    detail_area = controller.load_decision_detail("dec-001")

    assert detail_area.is_empty is False
    assert detail_area.decision.decision_id == "dec-001"


def test_load_decision_detail_handles_missing_decision():
    controller = _make_controller()

    detail_area = controller.load_decision_detail("missing-decision")

    assert detail_area.is_empty is True


def test_load_decisions_with_multiple_decisions_returns_them_all():
    controller = _make_controller({
        "dec-001": _make_contract(decision_id="dec-001", symbol="AAPL"),
        "dec-002": _make_contract(decision_id="dec-002", symbol="MSFT"),
        "dec-003": _make_contract(decision_id="dec-003", symbol="NVDA"),
    })

    list_area = controller.load_decisions(["dec-001", "dec-002", "dec-003"])

    assert [d.decision_id for d in list_area.decisions] == ["dec-001", "dec-002", "dec-003"]


def test_load_screen_selects_first_decision_by_default():
    controller = _make_controller({
        "dec-001": _make_contract(decision_id="dec-001", symbol="AAPL"),
        "dec-002": _make_contract(decision_id="dec-002", symbol="MSFT"),
    })

    screen = controller.load_screen(["dec-001", "dec-002"])

    assert screen.list_area.decisions[0].decision_id == "dec-001"
    assert screen.detail_area.decision.decision_id == "dec-001"


def test_load_screen_selects_explicit_decision_when_given():
    controller = _make_controller({
        "dec-001": _make_contract(decision_id="dec-001", symbol="AAPL"),
        "dec-002": _make_contract(decision_id="dec-002", symbol="MSFT"),
    })

    screen = controller.load_screen(["dec-001", "dec-002"], selected_id="dec-002")

    assert screen.detail_area.decision.decision_id == "dec-002"


def test_load_screen_handles_fully_empty_state():
    controller = _make_controller()

    screen = controller.load_screen([])

    assert screen.list_area.is_empty is True
    assert screen.detail_area.is_empty is True
