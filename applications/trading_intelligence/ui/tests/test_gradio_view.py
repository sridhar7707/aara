"""Tests for applications.trading_intelligence.ui.decision_center.gradio_view.

Uses a fake DecisionCenterController -- no real query service/adapter/
sentinel_engine wiring -- since this file only tests Gradio-facing
rendering/mapping, not the controller itself (already tested in
test_decision_center_controller.py).
"""
import datetime

import gradio as gr

from applications.trading_intelligence.projections.approval_entry import ApprovalEntry, ApprovalStatus
from applications.trading_intelligence.projections.decision_view import DecisionState, DecisionView
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.ui.decision_center.gradio_view import DecisionCenterUI
from applications.trading_intelligence.ui.decision_center.screen import (
    DecisionCenterScreen,
    DecisionDetailArea,
    DecisionListArea,
    ReadStatus,
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


def _make_entry(**overrides):
    defaults = dict(
        evidence_type="NEWS_SENTIMENT",
        source="newsapi",
        attached_at=datetime.datetime(2026, 8, 8, 9, 5, 0),
    )
    defaults.update(overrides)
    return EvidenceEntry(**defaults)


def _make_governance_entry(**overrides):
    defaults = dict(
        policy_id="pol-001",
        enabled=True,
        evaluated_at=datetime.datetime(2026, 8, 8, 9, 6, 0),
    )
    defaults.update(overrides)
    return GovernanceEntry(**defaults)


def _make_approval_entry(**overrides):
    defaults = dict(
        status=ApprovalStatus.APPROVED,
        approved_by="risk_officer",
        approved_at=datetime.datetime(2026, 8, 8, 9, 7, 0),
    )
    defaults.update(overrides)
    return ApprovalEntry(**defaults)


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

    (
        list_rows, symbol, action, status, confidence, updated,
        evidence_rows, governance_rows, approval_rows,
    ) = ui._render_screen()

    assert list_rows == [["dec-001", "AAPL", "BUY", "Approval Recorded", "91%"]]
    assert symbol == "AAPL"
    assert action == "BUY"
    assert status == "Approval Recorded"
    assert confidence == "91%"
    assert updated == "2026-08-08 09:00 UTC"
    assert evidence_rows == []
    assert governance_rows == []
    assert approval_rows == []


def test_render_screen_handles_empty_decision_list():
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[]),
        detail_area=DecisionDetailArea(decision=None),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, [])

    (
        list_rows, symbol, action, status, confidence, updated,
        evidence_rows, governance_rows, approval_rows,
    ) = ui._render_screen()

    assert list_rows == []
    assert symbol == "-"
    assert action == "-"
    assert status == "-"
    assert confidence == "-"
    assert updated == "-"
    assert evidence_rows == []
    assert governance_rows == []
    assert approval_rows == []


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

    (
        symbol, action, status, confidence, updated,
        evidence_rows, governance_rows, approval_rows,
    ) = ui._render_detail("dec-001")

    assert symbol == "NVDA"
    assert action == "SELL"
    assert status == "Evidence Attached"
    assert confidence == "74%"
    assert evidence_rows == []
    assert governance_rows == []
    assert approval_rows == []


def test_render_detail_returns_missing_values_for_blank_decision_id():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    result = ui._render_detail("")

    assert result == ("-", "-", "-", "-", "-", [], [], [])
    assert controller.load_decision_detail_calls == []


def test_render_detail_handles_missing_decision():
    controller = _FakeController(detail_area=DecisionDetailArea(decision=None))
    ui = DecisionCenterUI(controller, ["dec-001"])

    result = ui._render_detail("missing-decision")

    assert result == ("-", "-", "-", "-", "-", [], [], [])


def test_render_detail_shows_a_message_when_the_decision_read_fails():
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=None, decision_status=ReadStatus.ERROR)
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    (
        symbol, action, status, confidence, updated,
        evidence_rows, governance_rows, approval_rows,
    ) = ui._render_detail("dec-001")

    assert symbol == "Unable to load this decision."
    assert action == "-"
    assert status == "-"
    assert confidence == "-"
    assert updated == "-"
    assert evidence_rows == []
    assert governance_rows == []
    assert approval_rows == []


def test_render_detail_shows_a_message_when_evidence_read_fails_but_decision_still_renders():
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, evidence=(), evidence_status=ReadStatus.ERROR,
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    (
        symbol, action, status, confidence, updated,
        evidence_rows, governance_rows, approval_rows,
    ) = ui._render_detail("dec-001")

    assert symbol == "AAPL"
    assert evidence_rows == [["Evidence is temporarily unavailable.", "-", "-"]]
    assert governance_rows == []
    assert approval_rows == []


def test_render_detail_shows_a_message_when_governance_read_fails():
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, governance=(), governance_status=ReadStatus.ERROR,
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_rest, evidence_rows, governance_rows, approval_rows = ui._render_detail("dec-001")

    assert governance_rows == [["Governance information is temporarily unavailable.", "-", "-"]]
    assert evidence_rows == []
    assert approval_rows == []


def test_render_detail_shows_a_message_when_approvals_read_fails():
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, approvals=(), approvals_status=ReadStatus.ERROR,
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_rest, evidence_rows, governance_rows, approval_rows = ui._render_detail("dec-001")

    assert approval_rows == [["Approval information is temporarily unavailable.", "-", "-"]]
    assert evidence_rows == []
    assert governance_rows == []


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

    (
        symbol, action, status, confidence, updated,
        evidence_rows, governance_rows, approval_rows,
    ) = ui._on_row_select(_make_select_event(row))

    assert symbol == "NVDA"
    assert action == "SELL"
    assert status == "Approval Recorded"
    assert confidence == "91%"
    assert evidence_rows == []
    assert governance_rows == []
    assert approval_rows == []


def test_row_select_handles_deselection_without_crashing():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    result = ui._on_row_select(_make_select_event(["dec-001"], selected=False))

    assert result == ("-", "-", "-", "-", "-", [], [], [])
    assert controller.load_decision_detail_calls == []


def test_row_select_handles_missing_row_value_without_crashing():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, [])

    result = ui._on_row_select(_make_select_event(None))

    assert result == ("-", "-", "-", "-", "-", [], [], [])
    assert controller.load_decision_detail_calls == []


def test_render_detail_renders_a_single_evidence_row():
    view = _make_view()
    entry = _make_entry(evidence_type="NEWS_SENTIMENT", source="newsapi")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_rows, _governance_rows, _approval_rows = ui._render_detail("dec-001")

    assert evidence_rows == [["NEWS_SENTIMENT", "newsapi", "2026-08-08 09:05 UTC"]]


def test_render_detail_renders_multiple_evidence_rows_in_order():
    view = _make_view()
    entry_a = _make_entry(evidence_type="NEWS_SENTIMENT", source="newsapi")
    entry_b = _make_entry(
        evidence_type="PRICE_ACTION", source="alpaca",
        attached_at=datetime.datetime(2026, 8, 8, 9, 10, 0),
    )
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, evidence=(entry_a, entry_b))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_rows, _governance_rows, _approval_rows = ui._render_detail("dec-001")

    assert evidence_rows == [
        ["NEWS_SENTIMENT", "newsapi", "2026-08-08 09:05 UTC"],
        ["PRICE_ACTION", "alpaca", "2026-08-08 09:10 UTC"],
    ]


def test_render_detail_renders_an_empty_evidence_table_for_a_decision_with_no_evidence():
    view = _make_view()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=()))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_rows, _governance_rows, _approval_rows = ui._render_detail("dec-001")

    assert evidence_rows == []


def test_render_detail_renders_a_single_governance_row():
    view = _make_view()
    entry = _make_governance_entry(policy_id="pol-max-pos", enabled=True)
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, governance=(entry,))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_rows, governance_rows, _approval_rows = ui._render_detail("dec-001")

    assert governance_rows == [["pol-max-pos", "Yes", "2026-08-08 09:06 UTC"]]


def test_render_detail_renders_a_disabled_policy_as_no():
    view = _make_view()
    entry = _make_governance_entry(enabled=False)
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, governance=(entry,))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_rows, governance_rows, _approval_rows = ui._render_detail("dec-001")

    assert governance_rows == [["pol-001", "No", "2026-08-08 09:06 UTC"]]


def test_render_detail_renders_multiple_governance_rows_in_order():
    view = _make_view()
    entry_a = _make_governance_entry(policy_id="pol-001")
    entry_b = _make_governance_entry(
        policy_id="pol-002", evaluated_at=datetime.datetime(2026, 8, 8, 9, 8, 0),
    )
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, governance=(entry_a, entry_b))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_rows, governance_rows, _approval_rows = ui._render_detail("dec-001")

    assert governance_rows == [
        ["pol-001", "Yes", "2026-08-08 09:06 UTC"],
        ["pol-002", "Yes", "2026-08-08 09:08 UTC"],
    ]


def test_render_detail_renders_an_empty_governance_table_for_a_decision_with_no_governance():
    view = _make_view()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, governance=()))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_rows, governance_rows, _approval_rows = ui._render_detail("dec-001")

    assert governance_rows == []


def test_render_detail_renders_a_single_approval_row():
    view = _make_view()
    entry = _make_approval_entry(status=ApprovalStatus.APPROVED, approved_by="risk_officer")
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, approvals=(entry,))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_rows, _governance_rows, approval_rows = ui._render_detail("dec-001")

    assert approval_rows == [["Approved", "risk_officer", "2026-08-08 09:07 UTC"]]


def test_render_detail_renders_a_rejected_approval():
    view = _make_view()
    entry = _make_approval_entry(status=ApprovalStatus.REJECTED)
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, approvals=(entry,))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_rows, _governance_rows, approval_rows = ui._render_detail("dec-001")

    assert approval_rows == [["Rejected", "risk_officer", "2026-08-08 09:07 UTC"]]


def test_render_detail_renders_an_empty_approval_table_for_a_decision_with_no_approvals():
    view = _make_view()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, approvals=()))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_rows, _governance_rows, approval_rows = ui._render_detail("dec-001")

    assert approval_rows == []


def test_row_select_renders_governance_and_approval_for_the_selected_decision():
    view = _make_view(decision_id="dec-003", symbol="NVDA")
    governance_entry = _make_governance_entry()
    approval_entry = _make_approval_entry()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, governance=(governance_entry,), approvals=(approval_entry,),
        )
    )
    ui = DecisionCenterUI(controller, ["dec-003"])
    row = ["dec-003", "NVDA", "SELL", "Approval Recorded", "91%"]

    *_, _evidence_rows, governance_rows, approval_rows = ui._on_row_select(
        _make_select_event(row)
    )

    assert governance_rows == [["pol-001", "Yes", "2026-08-08 09:06 UTC"]]
    assert approval_rows == [["Approved", "risk_officer", "2026-08-08 09:07 UTC"]]


def test_render_detail_renders_governance_and_approval_from_manual_lookup():
    view = _make_view(decision_id="dec-002")
    governance_entry = _make_governance_entry()
    approval_entry = _make_approval_entry()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, governance=(governance_entry,), approvals=(approval_entry,),
        )
    )
    ui = DecisionCenterUI(controller, ["dec-002"])

    *_, _evidence_rows, governance_rows, approval_rows = ui._render_detail("dec-002")

    assert governance_rows == [["pol-001", "Yes", "2026-08-08 09:06 UTC"]]
    assert approval_rows == [["Approved", "risk_officer", "2026-08-08 09:07 UTC"]]
