"""Tests for applications.trading_intelligence.ui.decision_center.gradio_view.

Uses a fake DecisionCenterController -- no real query service/adapter/
sentinel_engine wiring -- since this file only tests Gradio-facing
rendering/mapping, not the controller itself (already tested in
test_decision_center_controller.py).
"""
import datetime

import gradio as gr

from applications.trading_intelligence.projections.decision_view import DecisionState, DecisionView
from applications.trading_intelligence.ui.decision_center.gradio_view import DecisionCenterUI
from applications.trading_intelligence.ui.decision_center.screen import (
    DecisionCenterScreen,
    DecisionDetailArea,
    DecisionListArea,
)


def _make_select_event(row_value, selected=True):
    return gr.SelectData(
        target=None,
        data={"index": (0, 0), "value": row_value[0] if row_value else None,
              "row_value": row_value, "selected": selected},
    )


def _make_view(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        status=DecisionState.DECISION_CREATED,
        confidence=0.82,
        updated_at=datetime.datetime(2026, 8, 8, 9, 0, 0),
    )
    defaults.update(overrides)
    return DecisionView(**defaults)


class _FakeController:
    def __init__(self, screen=None, detail_area=None):
        self._screen = screen
        self._detail_area = detail_area
        self.load_screen_calls = []
        self.load_decision_detail_calls = []

    def load_screen(self, decision_ids, selected_id=None):
        self.load_screen_calls.append((decision_ids, selected_id))
        return self._screen

    def load_decision_detail(self, decision_id):
        self.load_decision_detail_calls.append(decision_id)
        return self._detail_area


def test_decision_center_ui_can_be_constructed():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    assert isinstance(demo, gr.Blocks)


def test_render_screen_calls_controller_with_known_decision_ids():
    view = _make_view()
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[view]),
        detail_area=DecisionDetailArea(decision=view),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-001", "dec-002"])

    ui._render_screen()

    assert controller.load_screen_calls == [(["dec-001", "dec-002"], None)]


def test_render_screen_maps_list_rows_and_detail_fields():
    view = _make_view(status=DecisionState.APPROVAL_RECORDED, confidence=0.91)
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[view]),
        detail_area=DecisionDetailArea(decision=view),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-001"])

    list_rows, symbol, action, status, confidence, updated = ui._render_screen()

    assert list_rows == [["dec-001", "AAPL", "BUY", "Approval Recorded", "91%"]]
    assert symbol == "AAPL"
    assert action == "BUY"
    assert status == "Approval Recorded"
    assert confidence == "91%"
    assert updated == "2026-08-08 09:00 UTC"


def test_render_screen_handles_empty_decision_list():
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[]),
        detail_area=DecisionDetailArea(decision=None),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, [])

    list_rows, symbol, action, status, confidence, updated = ui._render_screen()

    assert list_rows == []
    assert symbol == "-"
    assert action == "-"
    assert status == "-"
    assert confidence == "-"
    assert updated == "-"


def test_render_detail_calls_controller_with_the_given_decision_id():
    view = _make_view(decision_id="dec-002", symbol="MSFT")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view))
    ui = DecisionCenterUI(controller, ["dec-002"])

    ui._render_detail("dec-002")

    assert controller.load_decision_detail_calls == ["dec-002"]


def test_render_detail_maps_fields_from_the_returned_decision():
    view = _make_view(
        symbol="NVDA", action="SELL", status=DecisionState.EVIDENCE_ATTACHED, confidence=0.74,
    )
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view))
    ui = DecisionCenterUI(controller, ["dec-001"])

    symbol, action, status, confidence, updated = ui._render_detail("dec-001")

    assert symbol == "NVDA"
    assert action == "SELL"
    assert status == "Evidence Attached"
    assert confidence == "74%"


def test_render_detail_returns_missing_values_for_blank_decision_id():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    result = ui._render_detail("")

    assert result == ("-", "-", "-", "-", "-")
    assert controller.load_decision_detail_calls == []


def test_render_detail_handles_missing_decision():
    controller = _FakeController(detail_area=DecisionDetailArea(decision=None))
    ui = DecisionCenterUI(controller, ["dec-001"])

    result = ui._render_detail("missing-decision")

    assert result == ("-", "-", "-", "-", "-")


def test_row_select_calls_controller_with_the_id_from_the_selected_row():
    view = _make_view(decision_id="dec-002", symbol="MSFT")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view))
    ui = DecisionCenterUI(controller, ["dec-001", "dec-002"])
    row = ["dec-002", "MSFT", "HOLD", "Decision Created", "82%"]

    ui._on_row_select(_make_select_event(row))

    assert controller.load_decision_detail_calls == ["dec-002"]


def test_row_select_renders_the_selected_decision_detail():
    view = _make_view(
        decision_id="dec-003", symbol="NVDA", action="SELL",
        status=DecisionState.APPROVAL_RECORDED, confidence=0.91,
    )
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view))
    ui = DecisionCenterUI(controller, ["dec-003"])
    row = ["dec-003", "NVDA", "SELL", "Approval Recorded", "91%"]

    symbol, action, status, confidence, updated = ui._on_row_select(_make_select_event(row))

    assert symbol == "NVDA"
    assert action == "SELL"
    assert status == "Approval Recorded"
    assert confidence == "91%"


def test_row_select_handles_deselection_without_crashing():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    result = ui._on_row_select(_make_select_event(["dec-001"], selected=False))

    assert result == ("-", "-", "-", "-", "-")
    assert controller.load_decision_detail_calls == []


def test_row_select_handles_missing_row_value_without_crashing():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, [])

    result = ui._on_row_select(_make_select_event(None))

    assert result == ("-", "-", "-", "-", "-")
    assert controller.load_decision_detail_calls == []
