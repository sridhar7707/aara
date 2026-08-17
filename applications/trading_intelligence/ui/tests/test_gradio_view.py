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
from applications.trading_intelligence.projections.audit_entry import AuditEntry
from applications.trading_intelligence.projections.decision_view import DecisionState, DecisionView
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.ui.decision_center.gradio_view import (
    _NAV_COMING_SOON_BADGE_HTML,
    _NAV_COMING_SOON_LABEL,
    _RISK_CONTEXT_BODY,
    _RISK_CONTEXT_HTML,
    _RISK_CONTEXT_TITLE,
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
        evidence_id="ev-001",
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
        approval_id="apr-001",
        status=ApprovalStatus.APPROVED,
        approved_by="risk_officer",
        approved_at=datetime.datetime(2026, 8, 8, 9, 7, 0),
    )
    defaults.update(overrides)
    return ApprovalEntry(**defaults)


def _make_audit_entry(**overrides):
    defaults = dict(
        event_id="evt-001",
        event_type="DECISION_CREATED",
        created_at=datetime.datetime(2026, 8, 8, 9, 0, 0),
        payload={"decision_id": "dec-001", "symbol": "AAPL", "action": "BUY"},
    )
    defaults.update(overrides)
    return AuditEntry(**defaults)


class _FakeController:
    def __init__(self, screen=None, detail_area=None):
        self._screen = screen
        self._detail_area = detail_area
        self.load_screen_calls = []
        self.load_decision_detail_calls = []
        self.load_decisions_calls = []

    def load_screen(self, decision_ids, selected_id=None):
        self.load_screen_calls.append((decision_ids, selected_id))
        return self._screen

    def load_decision_detail(self, decision_id):
        self.load_decision_detail_calls.append(decision_id)
        return self._detail_area

    def load_decisions(self, decision_ids):
        """_render_screen()'s own _newest_decision_id() calls this to
        resolve the initial (no-selection-yet) detail pane -- returns the
        same list_area already set on self._screen, matching what
        load_screen() would build from decisions had this fake actually
        composed one, per the existing load_screen()/_screen pattern above."""
        self.load_decisions_calls.append(decision_ids)
        return self._screen.list_area if self._screen is not None else DecisionListArea(decisions=[])


def _assert_index_order(html, *substrings):
    positions = [html.index(s) for s in substrings]
    assert positions == sorted(positions), f"expected order {substrings} in {html!r}"


def test_decision_center_ui_can_be_constructed():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    assert isinstance(demo, gr.Blocks)


def test_render_screen_calls_controller_with_known_decision_ids():
    """decision_ids (the composition root's known-ids list) is always
    forwarded as load_screen()'s first argument unchanged. The second
    argument is no longer None here: with no explicit selection yet,
    _render_screen resolves it to the newest decision's id first (see
    test_render_screen_resolves_no_selection_to_the_newest_decision below)
    -- with a single seeded view, that's trivially "dec-001"."""
    view = _make_view()
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[view]),
        detail_area=DecisionDetailArea(decision=view),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-001", "dec-002"])

    ui._render_screen()

    assert controller.load_screen_calls == [(["dec-001", "dec-002"], "dec-001")]


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
        list_rows, list_empty_html, header, lifecycle, conviction, updated, status, why_html,
        evidence_html, governance_html, approval_html, audit_html,
    ) = ui._render_screen()

    assert list_rows == [[
        "dec-001", "AAPL",
        '<span class="aara-list-action-badge action-buy">BUY</span>',
        "Approval Recorded", "91%", "2026-08-08 09:00 UTC", "-",
    ]]
    assert list_empty_html == ""
    assert "AAPL" in header
    assert "BUY" in header
    assert "dec-001" not in header
    assert "Approval" in lifecycle
    assert conviction == "91%"
    assert updated == "2026-08-08 09:00 UTC"
    assert status == "Approval Recorded"
    assert why_html == _WHY_RATIONALE_HTML
    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'
    assert governance_html == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )
    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'
    assert audit_html == '<div class="aara-empty-message">No audit events recorded.</div>'


def test_render_screen_handles_empty_decision_list():
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[]),
        detail_area=DecisionDetailArea(decision=None),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, [])

    (
        list_rows, list_empty_html, header, lifecycle, conviction, updated, status, why_html,
        evidence_html, governance_html, approval_html, audit_html,
    ) = ui._render_screen()

    assert list_rows == []
    assert list_empty_html == '<div class="aara-empty-message">No decisions recorded yet.</div>'
    assert header == ""
    assert lifecycle == "-"
    assert conviction == "-"
    assert updated == "-"
    assert status == "-"
    assert why_html == ""
    assert evidence_html == ""
    assert governance_html == ""
    assert approval_html == ""
    assert audit_html == ""


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
        header, lifecycle, conviction, updated, status, why_html,
        evidence_html, governance_html, approval_html, audit_html,
    ) = ui._render_detail("dec-001")

    assert "NVDA" in header
    assert "SELL" in header
    assert "Evidence" in lifecycle
    assert conviction == "74%"
    assert status == "Evidence Attached"
    assert why_html == _WHY_RATIONALE_HTML
    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'
    assert governance_html == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )
    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'
    assert audit_html == '<div class="aara-empty-message">No audit events recorded.</div>'


def test_render_detail_returns_blank_state_for_blank_decision_id():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    result = ui._render_detail("")

    assert result == ("", "-", "-", "-", "-", "", "", "", "", "")
    assert controller.load_decision_detail_calls == []


def test_render_detail_shows_not_found_message_for_a_missing_decision():
    controller = _FakeController(detail_area=DecisionDetailArea(decision=None))
    ui = DecisionCenterUI(controller, ["dec-001"])

    header, lifecycle, conviction, updated, status, why, evidence, governance, approval, audit = (
        ui._render_detail("missing-decision")
    )

    assert "No decision found for this ID." in header
    assert lifecycle == "-"
    assert conviction == "-"
    assert updated == "-"
    assert status == "-"
    assert why == ""
    assert evidence == ""
    assert governance == ""
    assert approval == ""
    assert audit == ""


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
        header, lifecycle, conviction, updated, status, why_html,
        evidence_html, governance_html, approval_html, audit_html,
    ) = ui._render_detail("dec-001")

    assert "Unable to load this decision." in header
    assert lifecycle == "-"
    assert conviction == "-"
    assert updated == "-"
    assert status == "-"
    assert why_html == ""
    assert evidence_html == ""
    assert governance_html == ""
    assert approval_html == ""
    assert audit_html == ""


def test_render_detail_shows_a_message_when_evidence_read_fails_but_decision_still_renders():
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, evidence=(), evidence_status=ReadStatus.ERROR,
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    (
        header, lifecycle, conviction, updated, status, why_html,
        evidence_html, governance_html, approval_html, audit_html,
    ) = ui._render_detail("dec-001")

    assert "AAPL" in header
    assert why_html == _WHY_RATIONALE_HTML
    assert "Evidence is temporarily unavailable." in evidence_html
    assert 'class="aara-error-message"' in evidence_html
    assert governance_html == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )
    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'
    assert audit_html == '<div class="aara-empty-message">No audit events recorded.</div>'


def test_render_detail_shows_a_message_when_governance_read_fails():
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, governance=(), governance_status=ReadStatus.ERROR,
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_rest, evidence_html, governance_html, approval_html, audit_html = ui._render_detail(
        "dec-001"
    )

    assert "Governance information is temporarily unavailable." in governance_html
    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'
    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'
    assert audit_html == '<div class="aara-empty-message">No audit events recorded.</div>'


def test_render_detail_shows_a_message_when_approvals_read_fails():
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, approvals=(), approvals_status=ReadStatus.ERROR,
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_rest, evidence_html, governance_html, approval_html, audit_html = ui._render_detail(
        "dec-001"
    )

    assert "Approval information is temporarily unavailable." in approval_html
    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'
    assert governance_html == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )
    assert audit_html == '<div class="aara-empty-message">No audit events recorded.</div>'


def test_render_detail_shows_a_message_when_audit_trail_read_fails():
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, audit_trail=(), audit_trail_status=ReadStatus.ERROR,
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_rest, evidence_html, governance_html, approval_html, audit_html = ui._render_detail(
        "dec-001"
    )

    assert "Audit trail is temporarily unavailable." in audit_html
    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'
    assert governance_html == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )
    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'


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
        decision_id, header, lifecycle, conviction, updated, status, why_html,
        evidence_html, governance_html, approval_html, audit_html,
    ) = ui._on_row_select(_make_select_event(row))

    assert decision_id == "dec-003"
    assert "NVDA" in header
    assert "SELL" in header
    assert "Approval" in lifecycle
    assert conviction == "91%"
    assert status == "Approval Recorded"
    assert why_html == _WHY_RATIONALE_HTML
    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'
    assert governance_html == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )
    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'
    assert audit_html == '<div class="aara-empty-message">No audit events recorded.</div>'


def test_row_select_handles_deselection_without_crashing():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    result = ui._on_row_select(_make_select_event(["dec-001"], selected=False))

    assert result == (None, "", "-", "-", "-", "-", "", "", "", "", "")
    assert controller.load_decision_detail_calls == []


def test_row_select_handles_missing_row_value_without_crashing():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, [])

    result = ui._on_row_select(_make_select_event(None))

    assert result == (None, "", "-", "-", "-", "-", "", "", "", "", "")
    assert controller.load_decision_detail_calls == []


def test_render_detail_renders_a_single_evidence_card():
    view = _make_view()
    entry = _make_entry(evidence_type="NEWS_SENTIMENT", source="newsapi")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

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

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

    _assert_index_order(evidence_html, "NEWS_SENTIMENT", "PRICE_ACTION")


def test_render_detail_renders_an_empty_evidence_message_for_a_decision_with_no_evidence():
    view = _make_view()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=()))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'


def test_evidence_detail_disclosure_renders_all_five_authorized_fields():
    """ADR-037: shap_drivers, is_degraded, val_loss, raw_score, headlines."""
    view = _make_view()
    entry = _make_entry(data={"metadata": {
        "shap_drivers": [{"feature": "rsi", "shap_value": 0.12}],
        "is_degraded": True,
        "val_loss": 0.61,
        "raw_score": 0.42,
        "headlines": ["Stock surges on earnings beat"],
    }})
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

    assert '<details class="aara-payload-disclosure">' in evidence_html
    assert "rsi" in evidence_html
    assert "0.12" in evidence_html
    assert "Yes" in evidence_html
    assert "0.61" in evidence_html
    assert "0.42" in evidence_html
    assert "Stock surges on earnings beat" in evidence_html


def test_evidence_detail_disclosure_renders_multiple_headlines_individually():
    view = _make_view()
    entry = _make_entry(data={"metadata": {
        "headlines": ["First headline", "Second headline"],
    }})
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

    assert "First headline" in evidence_html
    assert "Second headline" in evidence_html
    assert "['First headline', 'Second headline']" not in evidence_html


def test_evidence_detail_disclosure_renders_empty_headlines_as_explicit_na():
    view = _make_view()
    entry = _make_entry(data={"metadata": {"headlines": []}})
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

    assert "N/A" in evidence_html
    assert "[]" not in evidence_html


def test_evidence_detail_disclosure_renders_val_loss_none_as_explicit_na():
    view = _make_view()
    entry = _make_entry(data={"metadata": {"val_loss": None}})
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

    assert "N/A" in evidence_html
    assert "None" not in evidence_html


def test_evidence_detail_disclosure_escapes_html_in_headlines():
    view = _make_view()
    entry = _make_entry(data={"metadata": {
        "headlines": ["<img src=x onerror=alert(1)>"],
    }})
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

    assert "<img" not in evidence_html
    assert "&lt;img" in evidence_html


def test_evidence_detail_disclosure_does_not_render_unknown_metadata_keys():
    view = _make_view()
    entry = _make_entry(data={"metadata": {
        "raw_score": 0.5,
        "some_future_key": "should not appear",
    }})
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

    assert "should not appear" not in evidence_html
    assert "some_future_key" not in evidence_html


def test_evidence_card_does_not_render_signal_or_confidence():
    """ADR-037 §2.3: signal/confidence are per-model informational values,
    not the decision -- must never appear in the Evidence card at all."""
    view = _make_view()
    entry = _make_entry(data={
        "signal": "BUY",
        "confidence": 0.913,
        "metadata": {"raw_score": 0.5},
    })
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

    assert "0.913" not in evidence_html
    assert "BUY" not in evidence_html


def test_evidence_card_renders_no_detail_disclosure_when_metadata_is_empty():
    """No metadata keys present -- the header fields render exactly as
    before ADR-037, with no expandable disclosure appended."""
    view = _make_view()
    entry = _make_entry()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

    assert '<details class="aara-payload-disclosure">' not in evidence_html


def test_render_detail_renders_a_single_governance_card():
    view = _make_view()
    entry = _make_governance_entry(policy_id="pol-max-pos", enabled=True)
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, governance=(entry,))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

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

    *_, _evidence_html, governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

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

    *_, _evidence_html, governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

    _assert_index_order(governance_html, "pol-001", "pol-002")


def test_render_detail_renders_an_empty_governance_message_for_a_decision_with_no_governance():
    view = _make_view()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, governance=()))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

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

    *_, _evidence_html, _governance_html, approval_html, _audit_html = ui._render_detail("dec-001")

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

    *_, _evidence_html, _governance_html, approval_html, _audit_html = ui._render_detail("dec-001")

    assert "Rejected" in approval_html


def test_approval_card_does_not_render_the_fabricated_authorization_recorded_label():
    """V4: 'Authorization Recorded' was V3 presentation copy with no
    ApprovalEntry field behind it -- only real entry data (the status
    verdict, approved_by, approved_at) may appear on the card."""
    view = _make_view()
    entry = _make_approval_entry(status=ApprovalStatus.APPROVED, approved_by="risk_officer")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, approvals=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, _governance_html, approval_html, _audit_html = ui._render_detail("dec-001")

    assert "Authorization Recorded" not in approval_html
    assert "Approved" in approval_html
    assert "risk_officer" in approval_html
    assert "2026-08-08 09:07 UTC" in approval_html


def test_render_detail_renders_an_empty_approval_message_for_a_decision_with_no_approvals():
    view = _make_view()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, approvals=()))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, _governance_html, approval_html, _audit_html = ui._render_detail("dec-001")

    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'


def test_render_detail_renders_a_single_audit_card():
    view = _make_view()
    entry = _make_audit_entry(event_type="DECISION_CREATED")
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, audit_trail=(entry,))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, audit_html = ui._render_detail("dec-001")

    assert "Decision Created" in audit_html
    assert "2026-08-08 09:00 UTC" in audit_html
    assert 'class="aara-record-card"' in audit_html


def test_render_detail_renders_multiple_audit_cards_in_chronological_order():
    """Requirement: audit trail rendering must preserve the ordering already
    established by DecisionQuery.get_decision_timeline() -- the UI must not
    reorder AuditEntry values it is given."""
    view = _make_view()
    entry_a = _make_audit_entry(
        event_type="DECISION_CREATED", created_at=datetime.datetime(2026, 8, 8, 9, 0, 0),
    )
    entry_b = _make_audit_entry(
        event_type="EVIDENCE_ATTACHED", created_at=datetime.datetime(2026, 8, 8, 9, 5, 0),
    )
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, audit_trail=(entry_a, entry_b))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, audit_html = ui._render_detail("dec-001")

    _assert_index_order(audit_html, "Decision Created", "Evidence Attached")


def test_render_detail_renders_an_empty_audit_message_for_a_decision_with_no_events():
    view = _make_view()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, audit_trail=()))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, audit_html = ui._render_detail("dec-001")

    assert audit_html == '<div class="aara-empty-message">No audit events recorded.</div>'


def test_audit_card_escapes_html_in_entry_values():
    """event_type is title-cased for display (Requirement 3: reuse the
    existing card pattern), so this only asserts on the escaping itself
    -- not an exact-case substring -- to stay independent of that
    formatting detail."""
    view = _make_view()
    entry = _make_audit_entry(event_type="<img src=x onerror=alert(1)>")
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, audit_trail=(entry,))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, audit_html = ui._render_detail("dec-001")

    assert "<img" not in audit_html.lower()
    assert "&lt;" in audit_html.lower()


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
            audit_trail=(_make_audit_entry(),),
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, governance_html, approval_html, audit_html = ui._render_detail("dec-001")

    assert "aara-record-list--evidence" in evidence_html
    assert "aara-record-list--governance" not in evidence_html
    assert "aara-record-list--approval" not in evidence_html

    assert "aara-record-list--governance" in governance_html
    assert "aara-record-list--evidence" not in governance_html
    assert "aara-record-list--approval" not in governance_html

    assert "aara-record-list--approval" in approval_html
    assert "aara-record-list--evidence" not in approval_html
    assert "aara-record-list--governance" not in approval_html

    assert "aara-record-list--audit" in audit_html
    assert "aara-record-list--evidence" not in audit_html
    assert "aara-record-list--governance" not in audit_html
    assert "aara-record-list--approval" not in audit_html


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

    *_, _evidence_html, governance_html, approval_html, _audit_html = ui._on_row_select(
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

    *_, _evidence_html, governance_html, approval_html, _audit_html = ui._render_detail("dec-002")

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

    assert (
        'class="stage active"><span class="dot"></span>'
        '<a class="label" href="#decision-created-section">Created</a>'
    ) in lifecycle


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

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

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


def test_list_rows_render_an_approved_verdict_badge():
    view = _make_view(approval_status=ApprovalStatus.APPROVED)
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[view]),
        detail_area=DecisionDetailArea(decision=view),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-001"])

    list_rows = ui._render_screen()[0]

    assert list_rows[0][6] == '<span class="aara-list-verdict-badge verdict-approved">Approved</span>'


def test_list_rows_render_a_rejected_verdict_badge():
    view = _make_view(approval_status=ApprovalStatus.REJECTED)
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[view]),
        detail_area=DecisionDetailArea(decision=view),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-001"])

    list_rows = ui._render_screen()[0]

    assert list_rows[0][6] == '<span class="aara-list-verdict-badge verdict-rejected">Rejected</span>'


def test_list_rows_render_the_missing_value_dash_when_no_verdict_recorded():
    """approval_status defaults to None (_make_view does not set it) --
    the Verdict column must show the plain missing-value dash, never a
    fabricated "Pending" badge (ApprovalStatus has no PENDING member)."""
    view = _make_view()
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[view]),
        detail_area=DecisionDetailArea(decision=view),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-001"])

    list_rows = ui._render_screen()[0]

    assert list_rows[0][6] == "-"


def test_list_rows_render_newest_decision_first():
    """DecisionListArea carries no ordering guarantee -- list_rows must sort
    by DecisionView.updated_at descending regardless of the order decisions
    arrive in, so investors see the most recent decision at the top without
    scrolling/scanning for it."""
    oldest = _make_view(
        decision_id="dec-oldest", updated_at=datetime.datetime(2026, 8, 8, 8, 0, 0),
    )
    newest = _make_view(
        decision_id="dec-newest", updated_at=datetime.datetime(2026, 8, 8, 10, 0, 0),
    )
    middle = _make_view(
        decision_id="dec-middle", updated_at=datetime.datetime(2026, 8, 8, 9, 0, 0),
    )
    screen = DecisionCenterScreen(
        # Deliberately out of order (not already newest-first) -- proves
        # the sort, not an incidental pass-through of input order.
        list_area=DecisionListArea(decisions=[oldest, newest, middle]),
        detail_area=DecisionDetailArea(decision=oldest),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-oldest", "dec-newest", "dec-middle"])

    list_rows = ui._render_screen()[0]

    assert [row[0] for row in list_rows] == ["dec-newest", "dec-middle", "dec-oldest"]


def test_render_screen_resolves_no_selection_to_the_newest_decision():
    """Regression test for the Candidate-1 follow-up: the table sorts
    newest-first (_format_list_rows), but controller.load_screen()'s own
    "no selection yet" default picks list_area.decisions[0] in original,
    unsorted order -- without _newest_decision_id(), the initial detail
    pane could show a different decision than the table's own top row.

    Proves, in one place:
    1. The table is newest-first.
    2. With no explicit selection, the resolved selection sent to the
       controller is that same newest decision -- not whatever happened to
       be list_area.decisions[0] (here, deliberately the oldest).
    3. An explicit selection of a different, older decision still reaches
       the controller unchanged -- not silently overridden back to
       "newest"."""
    oldest = _make_view(
        decision_id="dec-oldest", symbol="AAPL",
        updated_at=datetime.datetime(2026, 8, 8, 8, 0, 0),
    )
    newest = _make_view(
        decision_id="dec-newest", symbol="TSLA",
        updated_at=datetime.datetime(2026, 8, 8, 10, 0, 0),
    )
    # decisions[0] is deliberately the oldest, and detail_area is
    # deliberately set to that same oldest decision -- reproducing exactly
    # the inconsistency this fix closes, so the assertions below fail if
    # the fix regresses back to trusting decisions[0] as-is.
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[oldest, newest]),
        detail_area=DecisionDetailArea(decision=oldest),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-oldest", "dec-newest"])

    list_rows = ui._render_screen()[0]

    # 1. Table is newest-first.
    assert [row[0] for row in list_rows] == ["dec-newest", "dec-oldest"]
    # 2. No explicit selection was given, yet load_screen() was called with
    # the newest decision's id, not None and not "dec-oldest".
    assert controller.load_screen_calls == [(["dec-oldest", "dec-newest"], "dec-newest")]

    # 3. An explicit selection of the *older* decision still reaches the
    # controller unchanged -- proves this fix only fills in the missing
    # case, it never overrides a real user selection.
    controller.load_screen_calls.clear()
    ui._render_screen("dec-oldest")

    assert controller.load_screen_calls == [(["dec-oldest", "dec-newest"], "dec-oldest")]


def test_why_summary_renders_a_real_sentence_for_a_single_evidence_entry():
    view = _make_view()
    entry = _make_entry(evidence_type="NEWS_SENTIMENT", source="newsapi")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    why_html = ui._render_detail("dec-001")[5]

    assert why_html == (
        '<div class="aara-disclosure-message">'
        '<div class="aara-disclosure-body">1 NEWS_SENTIMENT signal from newsapi.</div>'
        "</div>"
    )


def test_why_summary_renders_multiple_evidence_entries():
    view = _make_view()
    entry_a = _make_entry(evidence_type="NEWS_SENTIMENT", source="newsapi")
    entry_b = _make_entry(evidence_id="ev-002", evidence_type="PRICE_ACTION", source="alpaca")
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, evidence=(entry_a, entry_b))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    why_html = ui._render_detail("dec-001")[5]

    assert "2 signals" in why_html
    assert "NEWS_SENTIMENT from newsapi" in why_html
    assert "PRICE_ACTION from alpaca" in why_html


def test_why_summary_falls_back_to_the_static_placeholder_for_zero_evidence():
    view = _make_view()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=()))
    ui = DecisionCenterUI(controller, ["dec-001"])

    why_html = ui._render_detail("dec-001")[5]

    assert why_html == _WHY_RATIONALE_HTML


def test_why_summary_escapes_html_in_evidence_values():
    view = _make_view()
    entry = _make_entry(evidence_type="<img src=x onerror=alert(1)>", source="newsapi")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    why_html = ui._render_detail("dec-001")[5]

    assert "<img" not in why_html
    assert "&lt;img" in why_html


def test_audit_card_renders_an_expandable_payload_disclosure():
    view = _make_view()
    entry = _make_audit_entry(
        event_id="evt-001", event_type="DECISION_CREATED",
        payload={"decision_id": "dec-001", "symbol": "AAPL", "action": "BUY"},
    )
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, audit_trail=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    audit_html = ui._render_detail("dec-001")[9]

    assert '<details class="aara-payload-disclosure">' in audit_html
    assert "<summary>Details</summary>" in audit_html
    assert "evt-001" in audit_html
    assert "AAPL" in audit_html
    assert "BUY" in audit_html


def test_audit_payload_disclosure_escapes_html_in_values():
    view = _make_view()
    entry = _make_audit_entry(
        payload={"decision_id": "dec-001", "note": "<img src=x onerror=alert(1)>"},
    )
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, audit_trail=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    audit_html = ui._render_detail("dec-001")[9]

    assert "<img" not in audit_html
    assert "&lt;img" in audit_html


def test_lifecycle_track_links_each_stage_to_its_existing_detail_section():
    view = _make_view(status=DecisionState.APPROVAL_RECORDED)
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view))
    ui = DecisionCenterUI(controller, ["dec-001"])

    lifecycle = ui._render_detail("dec-001")[1]

    assert 'href="#decision-created-section"' in lifecycle
    assert 'href="#evidence-section"' in lifecycle
    assert 'href="#governance-section"' in lifecycle
    assert 'href="#approval-section"' in lifecycle


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
    """Why? is no longer a permanently-static block wired into the layout
    at build() time (see Decision Detail Depth pass) -- this now proves the
    same guarantee (the disclosure text is genuinely reachable) through the
    real render path: a decision with no evidence still renders the exact
    fixed placeholder, unchanged."""
    view = _make_view()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=()))
    ui = DecisionCenterUI(controller, ["dec-001"])

    why_html = ui._render_detail("dec-001")[5]

    assert why_html == _WHY_RATIONALE_HTML


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


def test_risk_context_is_the_exact_fixed_placeholder_text():
    """Slice 1 (UI-completion audit): the Risk section is a static,
    decision-independent disclosure -- no RiskEvaluation/RiskEntry contract
    or reader exists anywhere in this codebase. Render exactly this title
    and body, verbatim, for every decision."""
    assert _RISK_CONTEXT_TITLE == "Risk context not yet available"
    assert _RISK_CONTEXT_BODY == (
        "Position-level risk analysis has not yet been implemented for this workspace."
    )
    assert _RISK_CONTEXT_HTML == (
        '<div class="aara-disclosure-message">'
        '<div class="aara-disclosure-title">Risk context not yet available</div>'
        '<div class="aara-disclosure-body">'
        "Position-level risk analysis has not yet been implemented for this workspace.</div>"
        "</div>"
    )


def test_risk_context_block_is_present_in_the_built_layout():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert _RISK_CONTEXT_HTML in html_values
