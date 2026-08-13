"""Tests for applications.trading_intelligence.ui.decision_center.gradio_view.

Uses a fake DecisionCenterController -- no real query service/adapter/
sentinel_engine wiring -- since this file only tests Gradio-facing
rendering/mapping, not the controller itself (already tested in
test_decision_center_controller.py).

Evidence/Governance/Approval and the decision header/lifecycle track are
HTML fragments (see gradio_view.py's Visual Pass rewrite) -- these tests
assert on the presence and order of key text content within them rather
than matching a byte-exact HTML string, since exact markup is an
implementation detail, not the contract.
"""
import datetime

import gradio as gr

from applications.trading_intelligence.projections.approval_entry import ApprovalEntry, ApprovalStatus
from applications.trading_intelligence.projections.decision_view import DecisionState, DecisionView
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.ui.decision_center.gradio_view import (
    _NAV_COMING_SOON_BADGE_HTML,
    _NAV_COMING_SOON_LABEL,
    _SHELL_NAV_HTML,
    _WHY_RATIONALE_BODY,
    _WHY_RATIONALE_HTML,
    _WHY_RATIONALE_TITLE,
    DecisionCenterUI,
)
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


def _assert_index_order(html, *substrings):
    positions = [html.index(s) for s in substrings]
    assert positions == sorted(positions), f"expected order {substrings} in {html!r}"


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


def test_render_screen_forwards_an_explicit_selected_id_to_the_controller():
    """The Refresh button passes its selected_decision_id gr.State value as
    _render_screen's selected_id argument -- this asserts that argument
    reaches DecisionCenterController.load_screen() unchanged, exactly the
    same forwarding DecisionCenterController itself already has full
    coverage for (test_decision_center_controller.py's
    test_load_screen_selects_explicit_decision_when_given)."""
    view = _make_view()
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[view]),
        detail_area=DecisionDetailArea(decision=view),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-001", "dec-002"])

    ui._render_screen("dec-002")

    assert controller.load_screen_calls == [(["dec-001", "dec-002"], "dec-002")]


def test_refresh_after_row_select_preserves_the_selected_decision():
    """Simulates the real Refresh wiring end to end: _on_row_select's
    returned decision_id is exactly what the selected_decision_id gr.State
    holds and what Refresh's click handler then passes back into
    _render_screen -- closing the gap where Refresh used to always reset
    the detail panel to the first decision in the list."""
    selected_view = _make_view(decision_id="dec-002", symbol="MSFT")
    detail_area = DecisionDetailArea(decision=selected_view)
    controller = _FakeController(detail_area=detail_area)
    ui = DecisionCenterUI(controller, ["dec-001", "dec-002"])
    row = ["dec-002", "MSFT", "HOLD", "Decision Created", "82%"]

    select_result = ui._on_row_select(_make_select_event(row))
    selected_decision_id = select_result[0]

    controller._screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[selected_view]), detail_area=detail_area,
    )
    ui._render_screen(selected_decision_id)

    assert selected_decision_id == "dec-002"
    assert controller.load_screen_calls == [(["dec-001", "dec-002"], "dec-002")]


def test_render_screen_maps_list_rows_and_detail_fields():
    view = _make_view(status=DecisionState.APPROVAL_RECORDED, confidence=0.91)
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[view]),
        detail_area=DecisionDetailArea(decision=view),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-001"])

    (
        list_rows, list_empty_html, header, lifecycle, conviction, updated, status,
        evidence_html, governance_html, approval_html,
    ) = ui._render_screen()

    assert list_rows == [[
        "dec-001", "AAPL",
        '<span class="aara-list-action-badge action-buy">BUY</span>',
        "Approval Recorded", "91%", "2026-08-08 09:00 UTC",
    ]]
    assert list_empty_html == ""
    assert "AAPL" in header
    assert "BUY" in header
    assert "dec-001" not in header
    assert "Approval" in lifecycle
    assert conviction == "91%"
    assert updated == "2026-08-08 09:00 UTC"
    assert status == "Approval Recorded"
    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'
    assert governance_html == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )
    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'


def test_render_screen_handles_empty_decision_list():
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[]),
        detail_area=DecisionDetailArea(decision=None),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, [])

    (
        list_rows, list_empty_html, header, lifecycle, conviction, updated, status,
        evidence_html, governance_html, approval_html,
    ) = ui._render_screen()

    assert list_rows == []
    assert list_empty_html == '<div class="aara-empty-message">No decisions recorded yet.</div>'
    assert header == ""
    assert lifecycle == "-"
    assert conviction == "-"
    assert updated == "-"
    assert status == "-"
    assert evidence_html == ""
    assert governance_html == ""
    assert approval_html == ""


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
        header, lifecycle, conviction, updated, status,
        evidence_html, governance_html, approval_html,
    ) = ui._render_detail("dec-001")

    assert "NVDA" in header
    assert "SELL" in header
    assert "Evidence" in lifecycle
    assert conviction == "74%"
    assert status == "Evidence Attached"
    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'
    assert governance_html == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )
    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'


def test_render_detail_returns_blank_state_for_blank_decision_id():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    result = ui._render_detail("")

    assert result == ("", "-", "-", "-", "-", "", "", "")
    assert controller.load_decision_detail_calls == []


def test_render_detail_shows_not_found_message_for_a_missing_decision():
    controller = _FakeController(detail_area=DecisionDetailArea(decision=None))
    ui = DecisionCenterUI(controller, ["dec-001"])

    header, lifecycle, conviction, updated, status, evidence, governance, approval = (
        ui._render_detail("missing-decision")
    )

    assert "No decision found for this ID." in header
    assert lifecycle == "-"
    assert conviction == "-"
    assert updated == "-"
    assert status == "-"
    assert evidence == ""
    assert governance == ""
    assert approval == ""


def test_missing_decision_and_blank_selection_render_different_headers():
    """A real lookup miss must be distinguishable from nothing being
    selected -- EMPTY (blank textbox) != NOT FOUND (searched and missed)."""
    controller = _FakeController(detail_area=DecisionDetailArea(decision=None))
    ui = DecisionCenterUI(controller, ["dec-001"])

    blank_header = ui._render_detail("")[0]
    missing_header = ui._render_detail("does-not-exist")[0]

    assert blank_header == ""
    assert "No decision found for this ID." in missing_header
    assert blank_header != missing_header


def test_render_detail_shows_a_message_when_the_decision_read_fails():
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=None, decision_status=ReadStatus.ERROR)
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    (
        header, lifecycle, conviction, updated, status,
        evidence_html, governance_html, approval_html,
    ) = ui._render_detail("dec-001")

    assert "Unable to load this decision." in header
    assert lifecycle == "-"
    assert conviction == "-"
    assert updated == "-"
    assert status == "-"
    assert evidence_html == ""
    assert governance_html == ""
    assert approval_html == ""


def test_render_detail_shows_a_message_when_evidence_read_fails_but_decision_still_renders():
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, evidence=(), evidence_status=ReadStatus.ERROR,
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    (
        header, lifecycle, conviction, updated, status,
        evidence_html, governance_html, approval_html,
    ) = ui._render_detail("dec-001")

    assert "AAPL" in header
    assert "Evidence is temporarily unavailable." in evidence_html
    assert 'class="aara-error-message"' in evidence_html
    assert governance_html == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )
    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'


def test_render_detail_shows_a_message_when_governance_read_fails():
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, governance=(), governance_status=ReadStatus.ERROR,
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_rest, evidence_html, governance_html, approval_html = ui._render_detail("dec-001")

    assert "Governance information is temporarily unavailable." in governance_html
    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'
    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'


def test_render_detail_shows_a_message_when_approvals_read_fails():
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, approvals=(), approvals_status=ReadStatus.ERROR,
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_rest, evidence_html, governance_html, approval_html = ui._render_detail("dec-001")

    assert "Approval information is temporarily unavailable." in approval_html
    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'
    assert governance_html == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )


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
        decision_id, header, lifecycle, conviction, updated, status,
        evidence_html, governance_html, approval_html,
    ) = ui._on_row_select(_make_select_event(row))

    assert decision_id == "dec-003"
    assert "NVDA" in header
    assert "SELL" in header
    assert "Approval" in lifecycle
    assert conviction == "91%"
    assert status == "Approval Recorded"
    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'
    assert governance_html == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )
    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'


def test_row_select_handles_deselection_without_crashing():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    result = ui._on_row_select(_make_select_event(["dec-001"], selected=False))

    assert result == (None, "", "-", "-", "-", "-", "", "", "")
    assert controller.load_decision_detail_calls == []


def test_row_select_handles_missing_row_value_without_crashing():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, [])

    result = ui._on_row_select(_make_select_event(None))

    assert result == (None, "", "-", "-", "-", "-", "", "", "")
    assert controller.load_decision_detail_calls == []


def test_render_detail_renders_a_single_evidence_card():
    view = _make_view()
    entry = _make_entry(evidence_type="NEWS_SENTIMENT", source="newsapi")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html = ui._render_detail("dec-001")

    assert "NEWS_SENTIMENT" in evidence_html
    assert "newsapi" in evidence_html
    assert "2026-08-08 09:05 UTC" in evidence_html
    assert 'class="aara-record-card"' in evidence_html


def test_render_detail_renders_multiple_evidence_cards_in_order():
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

    *_, evidence_html, _governance_html, _approval_html = ui._render_detail("dec-001")

    _assert_index_order(evidence_html, "NEWS_SENTIMENT", "PRICE_ACTION")


def test_render_detail_renders_an_empty_evidence_message_for_a_decision_with_no_evidence():
    view = _make_view()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=()))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html = ui._render_detail("dec-001")

    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'


def test_render_detail_renders_a_single_governance_card():
    view = _make_view()
    entry = _make_governance_entry(policy_id="pol-max-pos", enabled=True)
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, governance=(entry,))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, governance_html, _approval_html = ui._render_detail("dec-001")

    assert "pol-max-pos" in governance_html
    assert "Yes" in governance_html
    assert "2026-08-08 09:06 UTC" in governance_html


def test_render_detail_renders_a_disabled_policy_as_no():
    view = _make_view()
    entry = _make_governance_entry(enabled=False)
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, governance=(entry,))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, governance_html, _approval_html = ui._render_detail("dec-001")

    assert "pol-001" in governance_html
    assert "No" in governance_html


def test_render_detail_renders_multiple_governance_cards_in_order():
    view = _make_view()
    entry_a = _make_governance_entry(policy_id="pol-001")
    entry_b = _make_governance_entry(
        policy_id="pol-002", evaluated_at=datetime.datetime(2026, 8, 8, 9, 8, 0),
    )
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, governance=(entry_a, entry_b))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, governance_html, _approval_html = ui._render_detail("dec-001")

    _assert_index_order(governance_html, "pol-001", "pol-002")


def test_render_detail_renders_an_empty_governance_message_for_a_decision_with_no_governance():
    view = _make_view()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, governance=()))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, governance_html, _approval_html = ui._render_detail("dec-001")

    assert governance_html == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )


def test_render_detail_renders_a_single_approval_card():
    view = _make_view()
    entry = _make_approval_entry(status=ApprovalStatus.APPROVED, approved_by="risk_officer")
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, approvals=(entry,))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, _governance_html, approval_html = ui._render_detail("dec-001")

    assert "Approved" in approval_html
    assert "risk_officer" in approval_html
    assert "2026-08-08 09:07 UTC" in approval_html


def test_render_detail_renders_a_rejected_approval():
    view = _make_view()
    entry = _make_approval_entry(status=ApprovalStatus.REJECTED)
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, approvals=(entry,))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, _governance_html, approval_html = ui._render_detail("dec-001")

    assert "Rejected" in approval_html


def test_approval_card_does_not_render_the_fabricated_authorization_recorded_label():
    """V4: 'Authorization Recorded' was V3 presentation copy with no
    ApprovalEntry field behind it -- only real entry data (the status
    verdict, approved_by, approved_at) may appear on the card."""
    view = _make_view()
    entry = _make_approval_entry(status=ApprovalStatus.APPROVED, approved_by="risk_officer")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, approvals=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, _governance_html, approval_html = ui._render_detail("dec-001")

    assert "Authorization Recorded" not in approval_html
    assert "Approved" in approval_html
    assert "risk_officer" in approval_html
    assert "2026-08-08 09:07 UTC" in approval_html


def test_render_detail_renders_an_empty_approval_message_for_a_decision_with_no_approvals():
    view = _make_view()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, approvals=()))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, _governance_html, approval_html = ui._render_detail("dec-001")

    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'


def test_evidence_governance_approval_record_lists_carry_distinct_section_variant_classes():
    """Detail Panel Polish pass: each section's non-empty record list gets
    its own aara-record-list--{section} wrapper class so theme.py can give
    each a distinct subtle surface -- Evidence/Governance/Approval must
    each carry their own variant and never another section's."""
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view,
            evidence=(_make_entry(),),
            governance=(_make_governance_entry(),),
            approvals=(_make_approval_entry(),),
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, governance_html, approval_html = ui._render_detail("dec-001")

    assert "aara-record-list--evidence" in evidence_html
    assert "aara-record-list--governance" not in evidence_html
    assert "aara-record-list--approval" not in evidence_html

    assert "aara-record-list--governance" in governance_html
    assert "aara-record-list--evidence" not in governance_html
    assert "aara-record-list--approval" not in governance_html

    assert "aara-record-list--approval" in approval_html
    assert "aara-record-list--evidence" not in approval_html
    assert "aara-record-list--governance" not in approval_html


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

    *_, _evidence_html, governance_html, approval_html = ui._on_row_select(
        _make_select_event(row)
    )

    assert "pol-001" in governance_html
    assert "Approved" in approval_html
    assert "risk_officer" in approval_html


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

    *_, _evidence_html, governance_html, approval_html = ui._render_detail("dec-002")

    assert "pol-001" in governance_html
    assert "Approved" in approval_html
    assert "risk_officer" in approval_html


def test_lifecycle_track_marks_all_four_stages_for_approval_recorded():
    view = _make_view(status=DecisionState.APPROVAL_RECORDED)
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view))
    ui = DecisionCenterUI(controller, ["dec-001"])

    lifecycle = ui._render_detail("dec-001")[1]

    for label in ("Created", "Evidence", "Governance", "Approval"):
        assert label in lifecycle
    assert lifecycle.count('class="stage complete"') == 3
    assert lifecycle.count('class="stage active"') == 1


def test_lifecycle_track_reflects_decision_created_as_the_first_stage():
    view = _make_view(status=DecisionState.DECISION_CREATED)
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view))
    ui = DecisionCenterUI(controller, ["dec-001"])

    lifecycle = ui._render_detail("dec-001")[1]

    assert 'class="stage active"><span class="dot"></span><span class="label">Created</span>' \
        in lifecycle


def test_decision_header_escapes_symbol_and_never_exposes_the_raw_decision_id():
    """The header shows only symbol + action ('NVDA · SELL'); decision_id is
    an internal identifier (used for row selection, controller/service
    lookups, and audit correlation) and must never appear in user-facing
    HTML, regardless of its content -- see AI-approved UX correction,
    2026-08-10."""
    view = _make_view(symbol="<script>alert(1)</script>", decision_id="dec-should-not-render")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view))
    ui = DecisionCenterUI(controller, ["dec-001"])

    header = ui._render_detail("dec-001")[0]

    assert "<script>" not in header
    assert "&lt;script&gt;" in header
    assert "dec-should-not-render" not in header


def test_evidence_card_escapes_html_in_entry_values():
    view = _make_view()
    entry = _make_entry(evidence_type="<img src=x onerror=alert(1)>", source="newsapi")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html = ui._render_detail("dec-001")

    assert "<img" not in evidence_html
    assert "&lt;img" in evidence_html


def test_action_badge_reflects_buy_sell_and_hold():
    for action, css_class in (("BUY", "action-buy"), ("SELL", "action-sell"), ("HOLD", "action-hold")):
        view = _make_view(action=action)
        controller = _FakeController(detail_area=DecisionDetailArea(decision=view))
        ui = DecisionCenterUI(controller, ["dec-001"])

        header = ui._render_detail("dec-001")[0]

        assert css_class in header
        assert action in header


def test_list_rows_render_the_action_column_as_a_badge_for_each_action():
    """The Decisions gr.Dataframe renders its Action column through
    datatype="markdown" (V3) -- list_rows must carry the same restrained
    badge markup as the hero, not a plain string, for every BUY/SELL/HOLD
    value, and it must not disturb column 0 (decision_id), which
    _on_row_select depends on via evt.row_value[0]."""
    for action, css_class in (("BUY", "action-buy"), ("SELL", "action-sell"), ("HOLD", "action-hold")):
        view = _make_view(action=action)
        screen = DecisionCenterScreen(
            list_area=DecisionListArea(decisions=[view]),
            detail_area=DecisionDetailArea(decision=view),
        )
        controller = _FakeController(screen=screen)
        ui = DecisionCenterUI(controller, ["dec-001"])

        list_rows = ui._render_screen()[0]

        assert list_rows[0][0] == "dec-001"
        assert list_rows[0][2] == f'<span class="aara-list-action-badge {css_class}">{action}</span>'


def test_why_rationale_is_the_exact_fixed_placeholder_text():
    """The Why?/Rationale section is a static, decision-independent
    two-line empty state -- no LLM call, no inferred copy, no
    backend/domain contract. Render exactly this title and body,
    verbatim, for every decision."""
    assert _WHY_RATIONALE_TITLE == "Rationale not captured"
    assert _WHY_RATIONALE_BODY == "The decision thesis has not yet been recorded."
    assert _WHY_RATIONALE_HTML == (
        '<div class="aara-disclosure-message">'
        '<div class="aara-disclosure-title">Rationale not captured</div>'
        '<div class="aara-disclosure-body">'
        "The decision thesis has not yet been recorded.</div>"
        "</div>"
    )


def test_why_rationale_block_is_present_in_the_built_layout():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert _WHY_RATIONALE_HTML in html_values


def test_nav_coming_soon_badge_is_the_exact_fixed_label():
    """The two muted nav items (Portfolio Intelligence, Risk Intelligence)
    each carry a fixed 'Coming Soon' badge -- no per-decision or
    per-session variation, matching _WHY_RATIONALE_HTML's own
    fixed-text-lock rationale."""
    assert _NAV_COMING_SOON_LABEL == "Coming Soon"
    assert _NAV_COMING_SOON_BADGE_HTML == '<span class="aara-nav-badge">Coming Soon</span>'


def test_shell_nav_has_exactly_one_active_item_and_two_muted_coming_soon_items():
    assert _SHELL_NAV_HTML.count('class="nav-item active"') == 1
    assert _SHELL_NAV_HTML.count('class="nav-item muted"') == 2
    assert _SHELL_NAV_HTML.count(_NAV_COMING_SOON_BADGE_HTML) == 2
    assert "Decision Center" in _SHELL_NAV_HTML
    assert "Portfolio Intelligence" in _SHELL_NAV_HTML
    assert "Risk Intelligence" in _SHELL_NAV_HTML


def test_shell_nav_muted_items_remain_non_interactive():
    """Coming Soon must never imply clickability -- no link, button,
    tabindex, or click/href attribute anywhere in the nav markup; every
    item stays a plain, non-focusable <span>, unchanged in kind by this
    pass."""
    assert "<a " not in _SHELL_NAV_HTML
    assert "<button" not in _SHELL_NAV_HTML
    assert "href=" not in _SHELL_NAV_HTML
    assert "tabindex" not in _SHELL_NAV_HTML
    assert "onclick" not in _SHELL_NAV_HTML


def test_shell_nav_block_is_present_in_the_built_layout():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert _SHELL_NAV_HTML in html_values
