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
import html

import gradio as gr

from applications.trading_intelligence.projections.approval_entry import ApprovalEntry, ApprovalStatus
from applications.trading_intelligence.projections.audit_entry import AuditEntry
from applications.trading_intelligence.projections.decision_view import DecisionState, DecisionView
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.ui.decision_center.gradio_view import (
    _ACCESSIBLE_NAME_SETUP_JS,
    _APPROVAL_ERROR_MESSAGE,
    _AUDIT_ERROR_MESSAGE,
    _DECISION_NOT_FOUND_MESSAGE,
    _DECISION_READ_ERROR_MESSAGE,
    _EVIDENCE_ERROR_MESSAGE,
    _GOVERNANCE_ERROR_MESSAGE,
    _JOURNEY_TARGET_FOCUS_SETUP_JS,
    _LIVE_ANNOUNCER_ELEM_ID,
    _NO_PRODUCER_DISCLOSURE_BODY,
    _NO_PRODUCER_DISCLOSURE_HTML,
    _NO_PRODUCER_DISCLOSURE_TITLE,
    _RISK_CONTEXT_BODY,
    _RISK_CONTEXT_HTML,
    _RISK_CONTEXT_TITLE,
    _RISK_REFERENCE_CLARIFICATION_HTML,
    _RISK_REFERENCE_NAV_LINK_CLASS,
    _RISK_REFERENCE_NAV_LINK_HTML,
    _RISK_REFERENCE_NAV_LINK_JS,
    _RISK_REFERENCE_NAV_LINK_LABEL,
    _SCOPE_NOTE_BODY,
    _SCOPE_NOTE_HTML,
    _SELECT_DECISION_HTML,
    _SELECT_DECISION_MESSAGE,
    _SELECTION_ARIA_SYNC_JS,
    _SHELL_NAV_HTML,
    _TIMESTAMP_DISCLOSURE_BODY,
    _TIMESTAMP_DISCLOSURE_HTML,
    _TIMESTAMP_DISCLOSURE_TITLE,
    _WHY_EVIDENCE_CLARIFICATION,
    _WHY_EVIDENCE_ERROR_HTML,
    _WHY_EVIDENCE_ERROR_TITLE,
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
from applications.trading_intelligence.ui.decision_center.theme import CSS


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


def test_disable_refresh_button_returns_a_not_interactive_update():
    result = DecisionCenterUI._disable_refresh_button()

    assert result == {"interactive": False, "__type__": "update"}


def test_enable_refresh_button_returns_an_interactive_update():
    result = DecisionCenterUI._enable_refresh_button()

    assert result == {"interactive": True, "__type__": "update"}


def test_refresh_button_click_chain_disables_then_renders_then_reenables():
    """MVP Loading States slice: double-submit guard. Proves the actual
    click().then().then() wiring in build() -- not just that the two helper
    methods above exist in isolation, which a regression leaving them
    defined but un-wired would still pass. Refresh's own render step must
    still be _render_screen itself, unchanged in fn/inputs/outputs -- only
    wrapped by the disable/enable steps."""
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    refresh_button = next(
        block for block in demo.blocks.values()
        if isinstance(block, gr.Button) and "aara-refresh-button" in (block.elem_classes or [])
    )
    refresh_button_id = next(
        block_id for block_id, block in demo.blocks.items() if block is refresh_button
    )
    disable_dep = next(
        dep for dep in demo.config["dependencies"]
        if demo.fns[dep["id"]].fn is DecisionCenterUI._disable_refresh_button
    )
    enable_dep = next(
        dep for dep in demo.config["dependencies"]
        if demo.fns[dep["id"]].fn is DecisionCenterUI._enable_refresh_button
    )
    render_dep = next(
        dep for dep in demo.config["dependencies"]
        if dep.get("trigger_after") == disable_dep["id"]
    )

    assert disable_dep["targets"] == [(refresh_button_id, "click")]
    assert refresh_button_id in disable_dep["outputs"]
    assert demo.fns[render_dep["id"]].fn == ui._render_screen
    assert enable_dep["trigger_after"] == render_dep["id"]
    assert refresh_button_id in enable_dep["outputs"]


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

    # Verdict is the backslash-escaped dash, not a bare "-" -- see
    # test_list_rows_render_the_missing_value_dash_when_no_verdict_recorded's
    # own docstring for why (P3 manual-QA fix, CF-04).
    assert list_rows == [[
        "dec-001", "AAPL",
        '<span class="aara-list-action-badge action-buy">BUY</span>',
        "Approval Recorded", "91%", "2026-08-08 04:00 CDT", "\\-",
    ]]
    assert list_empty_html == ""
    assert "AAPL" in header
    assert "BUY" in header
    assert "dec-001" not in header
    assert "Approval" in lifecycle
    assert conviction == "91%"
    assert updated == "2026-08-08 04:00 CDT"
    assert status == "Approval Recorded"
    assert why_html == _WHY_RATIONALE_HTML
    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'
    assert governance_html == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )
    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'
    assert audit_html == '<div class="aara-empty-message">No audit events recorded.</div>'


def test_render_screen_formats_list_row_timestamp_in_cst_during_winter():
    """DST-aware in gradio_view.py's own list-row rendering path too, not
    just screen.py's timestamp_display -- winter (January) is CST (UTC-6),
    proving the conversion isn't a fixed CDT offset."""
    view = _make_view(updated_at=datetime.datetime(2026, 1, 8, 15, 40, 0))
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[view]),
        detail_area=DecisionDetailArea(decision=view),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-001"])

    list_rows = ui._render_screen()[0]

    assert list_rows[0][5] == "2026-01-08 09:40 CST"


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
    assert why_html == _SELECT_DECISION_HTML
    assert evidence_html == _SELECT_DECISION_HTML
    assert governance_html == _SELECT_DECISION_HTML
    assert approval_html == _SELECT_DECISION_HTML
    assert audit_html == _SELECT_DECISION_HTML


def test_select_decision_message_is_the_exact_fixed_text():
    """MVP Loading States slice: _empty_detail()'s why/evidence/governance/
    approval/audit slots must show an explicit, decision-independent
    'select a decision' cue instead of rendering as literal blank space --
    reuses the same aara-empty-message class every other 'this section has
    no records' case in this file already uses (no new CSS class)."""
    assert _SELECT_DECISION_MESSAGE == "Select a decision to view details"
    assert _SELECT_DECISION_HTML == (
        f'<div class="aara-empty-message">{_SELECT_DECISION_MESSAGE}</div>'
    )


def test_missing_and_error_detail_states_are_unaffected_by_the_select_message():
    """Scope guard: the MVP Loading States slice only touches _empty_detail()
    (nothing selected yet) -- _missing_decision_detail() (a real lookup
    miss) and _decision_error_detail() (a read failure) must keep rendering
    their own distinct header message and blank sub-sections, unchanged."""
    controller = _FakeController(detail_area=DecisionDetailArea(decision=None))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, why_html, evidence_html, governance_html, approval_html, audit_html = ui._render_detail(
        "missing-decision"
    )

    assert _SELECT_DECISION_MESSAGE not in why_html
    assert why_html == "" == evidence_html == governance_html == approval_html == audit_html


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


def test_render_detail_header_omits_raw_evidence_and_risk_reference():
    """UI hardening pass: evidence_reference/risk_reference are opaque
    internal DecisionContract pointers -- their raw values must never
    appear in the normal user-facing header. The plumbing still passes
    them through (a future admin/debug surface may use them), but the
    rendered header shows neither value nor the old "raw, unresolved"
    labels."""
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, evidence_reference="evidence-001", risk_reference="risk-001",
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    header = ui._render_detail("dec-001")[0]

    assert "evidence-001" not in header
    assert "risk-001" not in header
    assert "Evidence Reference" not in header
    assert "Risk Reference" not in header
    assert "unresolved" not in header.lower()


def test_render_detail_header_clarifies_risk_is_not_resolved_when_risk_reference_present():
    """UI hardening pass: the raw risk_reference value is no longer shown,
    but when a decision carries one the header still emits the
    opaque-pointer clarification so the accompanying Risk Intelligence
    navigation cannot be read as resolved risk analysis (Risk Intelligence
    is not implemented for this workspace). Asserts wording only, not
    exact markup."""
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, evidence_reference="evidence-001", risk_reference="risk-001",
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    header = ui._render_detail("dec-001")[0]

    assert "risk-001" not in header
    assert "opaque pointer" in header.lower()
    assert "not currently implemented" in header.lower()


def test_render_detail_header_omits_risk_clarification_when_no_risk_reference():
    """The clarification note and Risk Intelligence nav link are tied to
    risk_reference existing -- an Evidence-only decision must not carry any
    Risk wording in its header."""
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, evidence_reference="evidence-001", risk_reference=None,
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    header = ui._render_detail("dec-001")[0]

    assert "aara-decision-header" in header
    assert "opaque pointer" not in header.lower()
    assert "Risk" not in header


def test_render_detail_header_omits_reference_fields_when_none_are_present():
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, evidence_reference=None, risk_reference=None)
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    header = ui._render_detail("dec-001")[0]

    assert "Evidence Reference" not in header
    assert "Risk Reference" not in header
    assert "opaque pointer" not in header.lower()


def test_risk_reference_clarification_html_is_unchanged():
    """DC-01 regression lock: the existing opaque-pointer disclosure must
    remain byte-for-byte unchanged by the new navigation link added
    alongside it -- this pins the exact prior value so any future edit to
    this constant fails a test instead of silently drifting."""
    assert _RISK_REFERENCE_CLARIFICATION_HTML == (
        '<div class="aara-disclosure-message">'
        '<div class="aara-disclosure-body">'
        "This is an opaque pointer, not resolved risk analysis -- Risk "
        "Intelligence is not currently implemented for this workspace."
        "</div></div>"
    )


def test_render_detail_header_includes_risk_intelligence_nav_link_when_risk_reference_present():
    """DC-01: a navigational element to Risk Intelligence appears alongside
    the existing opaque-pointer clarification, only when risk_reference is
    present -- structure only (element exists, correct class/role/label);
    actual cross-tab click behavior is not verifiable at this level (see
    module docstring) and must be confirmed live."""
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, evidence_reference="evidence-001", risk_reference="risk-001",
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    header = ui._render_detail("dec-001")[0]

    assert _RISK_REFERENCE_CLARIFICATION_HTML in header
    assert _RISK_REFERENCE_NAV_LINK_HTML in header
    assert f'class="{_RISK_REFERENCE_NAV_LINK_CLASS}"' in header
    assert 'role="button"' in header
    assert 'tabindex="0"' in header
    assert _RISK_REFERENCE_NAV_LINK_LABEL in header
    # The clarification must precede the nav link, not replace it.
    assert header.index(_RISK_REFERENCE_CLARIFICATION_HTML) < header.index(
        _RISK_REFERENCE_NAV_LINK_HTML
    )


def test_render_detail_header_omits_risk_intelligence_nav_link_when_no_risk_reference():
    """The nav link is tied to risk_reference existing, identically to the
    existing clarification note it accompanies -- an Evidence-only decision
    must not carry either."""
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view, evidence_reference="evidence-001", risk_reference=None,
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    header = ui._render_detail("dec-001")[0]

    assert _RISK_REFERENCE_NAV_LINK_CLASS not in header
    assert _RISK_REFERENCE_NAV_LINK_LABEL not in header


def test_risk_reference_nav_link_script_is_present_in_built_layout():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    assert _RISK_REFERENCE_NAV_LINK_JS in demo.head


def test_risk_reference_nav_link_script_targets_the_documented_dom_contract():
    """DC-01: the bridge must forward to the real outer "Risk Intelligence"
    tab button via the same findRealTab()/click() pattern bootstrap.py's
    _INNER_NAV_LINK_JS already uses, scoped only to this one element's own
    class -- never broadening bootstrap.py's six-item, shell-nav-scoped
    bridge. Asserted here as a contract check so a future edit can't
    silently drop the selector or target label without failing a test."""
    assert _RISK_REFERENCE_NAV_LINK_CLASS in _RISK_REFERENCE_NAV_LINK_JS
    assert 'querySelectorAll(\'button[role="tab"]\')' in _RISK_REFERENCE_NAV_LINK_JS
    assert '"Risk Intelligence"' in _RISK_REFERENCE_NAV_LINK_JS
    assert "tabButton.click()" in _RISK_REFERENCE_NAV_LINK_JS
    # Must never reference or extend the six-screen shell-nav bridge.
    assert "aara-shell-nav-list" not in _RISK_REFERENCE_NAV_LINK_JS
    assert "EXPECTED_NAV_LISTS" not in _RISK_REFERENCE_NAV_LINK_JS


def test_render_detail_header_never_leaks_raw_reference_values_even_hostile_ones():
    """UI hardening pass: raw evidence_reference/risk_reference values are
    not rendered at all, so a hostile pointer string can appear neither
    verbatim nor as an escaped fragment in the header. The static Risk
    clarification + nav link (no value interpolation) still render because
    risk_reference is present."""
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view,
            evidence_reference="<script>alert(1)</script>",
            risk_reference="<script>alert(2)</script>",
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    header = ui._render_detail("dec-001")[0]

    assert "<script>" not in header
    assert "&lt;script&gt;" not in header
    assert "alert(1)" not in header
    assert "alert(2)" not in header
    assert "opaque pointer" in header.lower()


def test_render_detail_returns_blank_state_for_blank_decision_id():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    result = ui._render_detail("")

    assert result == (
        "", "-", "-", "-", "-",
        _SELECT_DECISION_HTML, _SELECT_DECISION_HTML, _SELECT_DECISION_HTML,
        _SELECT_DECISION_HTML, _SELECT_DECISION_HTML,
    )
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
    """P2 Why/Rationale error-wording fix: an evidence read failure must
    render distinctly from a genuinely evidence-free decision -- both used
    to collapse to the same "Rationale not captured / thesis has not yet
    been recorded" wording (_WHY_RATIONALE_HTML), which misstates a
    transient read failure as a permanent absence of data. why_html must
    now be _WHY_EVIDENCE_ERROR_HTML, reusing the exact same
    _EVIDENCE_ERROR_MESSAGE text the Evidence section itself already shows
    for this identical failure."""
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
    assert why_html == _WHY_EVIDENCE_ERROR_HTML
    assert why_html != _WHY_RATIONALE_HTML
    assert _WHY_EVIDENCE_ERROR_TITLE in why_html
    assert _EVIDENCE_ERROR_MESSAGE in why_html
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

    assert result == (
        None, "", "-", "-", "-", "-",
        _SELECT_DECISION_HTML, _SELECT_DECISION_HTML, _SELECT_DECISION_HTML,
        _SELECT_DECISION_HTML, _SELECT_DECISION_HTML,
    )
    assert controller.load_decision_detail_calls == []


def test_row_select_handles_missing_row_value_without_crashing():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, [])

    result = ui._on_row_select(_make_select_event(None))

    assert result == (
        None, "", "-", "-", "-", "-",
        _SELECT_DECISION_HTML, _SELECT_DECISION_HTML, _SELECT_DECISION_HTML,
        _SELECT_DECISION_HTML, _SELECT_DECISION_HTML,
    )
    assert controller.load_decision_detail_calls == []


def test_render_detail_renders_a_single_evidence_card():
    view = _make_view()
    entry = _make_entry(evidence_type="NEWS_SENTIMENT", source="newsapi")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail("dec-001")

    assert "NEWS_SENTIMENT" in evidence_html
    assert "newsapi" in evidence_html
    assert "2026-08-08 04:05 CDT" in evidence_html
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
    assert "2026-08-08 04:06 CDT" in governance_html


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
    assert "2026-08-08 04:07 CDT" in approval_html
    assert "Approved By" in approval_html
    assert "Approved At" in approval_html


def test_render_detail_renders_a_rejected_approval():
    view = _make_view()
    entry = _make_approval_entry(status=ApprovalStatus.REJECTED)
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, approvals=(entry,))
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, _governance_html, approval_html, _audit_html = ui._render_detail("dec-001")

    assert "Rejected" in approval_html


def test_rejected_approval_card_uses_recorded_wording_not_approved_wording():
    """P3 visual-polish fix (Finding 2): a REJECTED entry previously still
    showed the field labels 'Approved By'/'Approved At' right next to its
    own REJECTED pill -- self-contradictory wording, live-verified on
    dec-seed-005/TSLA. ApprovalEntry.approved_by/approved_at themselves are
    unchanged (still the same two real fields, regardless of verdict) --
    only the REJECTED card's display labels become 'Recorded By'/
    'Recorded At'; the APPROVED case (see the two tests above) keeps the
    original 'Approved By'/'Approved At' wording unchanged."""
    view = _make_view()
    entry = _make_approval_entry(status=ApprovalStatus.REJECTED, approved_by="risk_officer")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, approvals=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    *_, _evidence_html, _governance_html, approval_html, _audit_html = ui._render_detail("dec-001")

    assert "Recorded By" in approval_html
    assert "Recorded At" in approval_html
    assert "risk_officer" in approval_html
    assert "Approved By" not in approval_html
    assert "Approved At" not in approval_html


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
    assert "2026-08-08 04:07 CDT" in approval_html


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
    assert "2026-08-08 04:00 CDT" in audit_html
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
    fabricated "Pending" badge (ApprovalStatus has no PENDING member).

    P3 manual-QA fix (CF-04): asserts the backslash-escaped form, not a
    bare "-". This exact assertion previously passed against a bare "-"
    while the live-rendered cell was actually an invisible empty markdown
    bullet (<ul><li></li></ul>) -- the Verdict column renders via
    datatype="markdown" (_LIST_DATATYPES), and CommonMark treats a
    line-leading "-" as an empty unordered-list item, not literal text.
    Checking the raw Python string alone missed this; a live browser check
    (P3 manual-QA pass) is what actually caught it. This test now locks in
    the escaped value specifically so a future edit can't silently drop
    the backslash and reintroduce the same invisible-dash regression."""
    view = _make_view()
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[view]),
        detail_area=DecisionDetailArea(decision=view),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-001"])

    list_rows = ui._render_screen()[0]

    assert list_rows[0][6] == "\\-"


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
        '<div class="aara-disclosure-body">1 NEWS_SENTIMENT signal from newsapi. '
        f"{html.escape(_WHY_EVIDENCE_CLARIFICATION)}</div>"
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
    assert html.escape(_WHY_EVIDENCE_CLARIFICATION) in why_html


def test_why_summary_clarification_is_not_shown_for_the_zero_evidence_fallback():
    """P2 trust clarification pass: the clarification is appended only to
    the real-evidence sentence -- _WHY_RATIONALE_HTML's zero-evidence
    fallback ("Rationale not captured") already makes no thesis/causal
    claim, so there is nothing for it to clarify."""
    view = _make_view()
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=()))
    ui = DecisionCenterUI(controller, ["dec-001"])

    why_html = ui._render_detail("dec-001")[5]

    assert _WHY_EVIDENCE_CLARIFICATION not in why_html
    assert why_html == _WHY_RATIONALE_HTML


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
    # UI hardening pass: the internal event_id is never rendered.
    assert "evt-001" not in audit_html
    assert "AAPL" in audit_html
    assert "BUY" in audit_html


def test_audit_card_has_no_disclosure_when_payload_has_no_authorized_keys():
    """UI hardening pass: with event_id no longer seeded into the audit
    disclosure, an event whose payload carries only non-authorized keys
    (e.g. just decision_id) must render no <details> block at all, not an
    empty one."""
    view = _make_view()
    entry = _make_audit_entry(
        event_id="evt-002", event_type="DECISION_CREATED",
        payload={"decision_id": "dec-001"},
    )
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, audit_trail=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    audit_html = ui._render_detail("dec-001")[9]

    assert "aara-payload-disclosure" not in audit_html
    assert "evt-002" not in audit_html
    assert "dec-001" not in audit_html


def test_audit_payload_disclosure_escapes_html_in_values():
    view = _make_view()
    entry = _make_audit_entry(
        payload={"decision_id": "dec-001", "action": "<img src=x onerror=alert(1)>"},
    )
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, audit_trail=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    audit_html = ui._render_detail("dec-001")[9]

    assert "<img" not in audit_html
    assert "&lt;img" in audit_html


def test_audit_payload_disclosure_excludes_decision_id_but_keeps_authorized_fields():
    """P0 fix (accessibility/completeness audit): decision_id must never
    appear in rendered UI, matching the same rule already enforced on the
    decision header (test_decision_header_escapes_symbol_and_never_exposes_
    the_raw_decision_id) -- but every real Event.payload
    (DecisionService.create_decision(), etc.) includes decision_id, and the
    old _format_audit_detail_html rendered every payload key unfiltered, so
    it leaked here. Proves: the raw value is absent, the literal key is
    absent, and already-authorized fields (symbol, action) still render."""
    view = _make_view()
    entry = _make_audit_entry(
        payload={"decision_id": "dec-001", "symbol": "AAPL", "action": "BUY"},
    )
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, audit_trail=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-001"])

    audit_html = ui._render_detail("dec-001")[9]

    assert "dec-001" not in audit_html
    assert "decision_id" not in audit_html
    assert "AAPL" in audit_html
    assert "BUY" in audit_html


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


def test_why_evidence_error_html_is_the_exact_fixed_title_and_reused_evidence_error_body():
    """P2 Why/Rationale error-wording fix: the evidence-read-error variant
    of the Why panel is a distinct, fixed constant -- not the zero-evidence
    _WHY_RATIONALE_HTML -- whose body is _EVIDENCE_ERROR_MESSAGE verbatim
    (the exact same sentence the Evidence section itself already shows for
    this failure), not new copy invented for this panel."""
    assert _WHY_EVIDENCE_ERROR_TITLE == "Rationale unavailable"
    assert _WHY_EVIDENCE_ERROR_HTML == (
        '<div class="aara-disclosure-message">'
        '<div class="aara-disclosure-title">Rationale unavailable</div>'
        f'<div class="aara-disclosure-body">{_EVIDENCE_ERROR_MESSAGE}</div>'
        "</div>"
    )
    assert _WHY_EVIDENCE_ERROR_HTML != _WHY_RATIONALE_HTML


def test_why_evidence_error_html_is_present_in_the_built_layout_on_an_evidence_read_failure():
    """Same real-render-path guarantee as
    test_why_rationale_block_is_present_in_the_built_layout above, for the
    evidence-read-error branch specifically."""
    view = _make_view()
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, evidence=(), evidence_status=ReadStatus.ERROR)
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    why_html = ui._render_detail("dec-001")[5]

    assert why_html == _WHY_EVIDENCE_ERROR_HTML
    assert why_html != _WHY_RATIONALE_HTML


def test_why_summary_html_distinguishes_zero_evidence_from_evidence_read_error():
    """Direct regression guard for the P2 Why/Rationale error-wording fix:
    two DecisionDetailArea inputs that both carry an empty evidence tuple
    (previously indistinguishable to _why_summary_sentence) must render
    different why_html depending on evidence_status alone."""
    view = _make_view()
    zero_evidence = DecisionDetailArea(decision=view, evidence=(), evidence_status=ReadStatus.OK)
    evidence_error = DecisionDetailArea(decision=view, evidence=(), evidence_status=ReadStatus.ERROR)

    assert DecisionCenterUI._format_why_summary_html(zero_evidence) == _WHY_RATIONALE_HTML
    assert DecisionCenterUI._format_why_summary_html(evidence_error) == _WHY_EVIDENCE_ERROR_HTML


def test_evidence_summary_heading_is_present_in_the_built_layout():
    """P2 Why/Rationale heading-clarity fix: "Why?" (which reads as a
    promise of a causal explanation this panel has never provided) is
    replaced with "Evidence Summary" -- states the section's real scope
    directly in the heading, same short sibling-parallel style as the
    Evidence/Governance & Policy/Approval headings around it."""
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    combined = "".join(_built_markup_blocks(ui))

    assert '<h3 class="aara-eyebrow">Evidence Summary</h3>' in combined
    assert '<h3 class="aara-eyebrow">Why?</h3>' not in combined
    assert ">Why?<" not in combined


def test_shell_nav_has_exactly_one_active_item_and_no_muted_items():
    """Both Portfolio Intelligence and Risk Intelligence have shipped as
    real screens (wired via gr.TabbedInterface in bootstrap.py) -- neither
    nav item is muted or badged any longer; only Decision Center stays
    marked active."""
    assert _SHELL_NAV_HTML.count('class="nav-item active"') == 1
    assert _SHELL_NAV_HTML.count('class="nav-item muted"') == 0
    assert "aara-nav-badge" not in _SHELL_NAV_HTML
    assert "Decision Center" in _SHELL_NAV_HTML
    assert "Portfolio Intelligence" in _SHELL_NAV_HTML
    assert "Risk Intelligence" in _SHELL_NAV_HTML


def test_shell_nav_portfolio_and_risk_intelligence_are_no_longer_coming_soon():
    """Portfolio Intelligence (ui/portfolio_intelligence/) and Risk
    Intelligence (ui/risk_intelligence/) both shipped, wired via
    gr.TabbedInterface in bootstrap.py -- neither nav item may claim
    otherwise."""
    assert (
        '<span class="nav-item" role="tab" aria-selected="false">'
        "Portfolio Intelligence</span>"
    ) in _SHELL_NAV_HTML
    assert (
        '<span class="nav-item" role="tab" aria-selected="false">'
        "Risk Intelligence</span>"
    ) in _SHELL_NAV_HTML
    assert "Coming Soon" not in _SHELL_NAV_HTML


def test_shell_nav_is_an_aria_tablist_with_correct_selected_state():
    """Duplicate-navigation audit: this nav becomes the app's single
    accessible tablist once the outer gr.TabbedInterface tabs are hidden
    (bootstrap.py's _TABBED_LAYOUT_CSS) -- it must carry the same
    role="tablist"/"tab"/aria-selected pattern the outer tabs already had.

    Counts raised from 3/2 to 6/5 after a live Playwright audit found this
    literal had drifted stale (still 3 items) once Morning Brief,
    Performance & Learning, and Settings were added to the six-screen app;
    fixed to match build_shell_nav_html("Decision Center")'s current
    six-label output (see ui/tests/test_shell.py's parity test)."""
    assert 'role="tablist"' in _SHELL_NAV_HTML
    assert _SHELL_NAV_HTML.count('role="tab"') == 6
    assert _SHELL_NAV_HTML.count('aria-selected="true"') == 1
    assert _SHELL_NAV_HTML.count('aria-selected="false"') == 5
    assert (
        '<span class="nav-item active" role="tab" aria-selected="true">'
        "Decision Center</span>"
    ) in _SHELL_NAV_HTML


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


def _built_markup_blocks(ui: DecisionCenterUI):
    """gr.HTML and gr.Markdown blocks both render literal markup in this
    module's built layout (see build()'s page header vs. section-label
    calls) -- collect both kinds' static values so heading-hierarchy
    assertions can see the whole rendered page, not just the gr.HTML
    subset the other _built_layout tests check."""
    demo = ui.build()
    return [
        block.value for block in demo.blocks.values()
        if isinstance(block, (gr.HTML, gr.Markdown))
        and isinstance(getattr(block, "value", None), str)
    ]


def test_decision_center_page_has_exactly_one_page_level_h1():
    """P2 #1 (Decision Center UI audit): the page needs exactly one
    semantic <h1> identifying it as Decision Center -- _PAGE_HEADER_HTML
    is the only page-title block in the built layout, so it must be the
    sole <h1> anywhere on the page."""
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    combined = "".join(_built_markup_blocks(ui))

    assert combined.count("<h1") == 1
    assert '<h1 class="aara-eyebrow">Decision Center</h1>' in combined


def test_decision_center_major_section_headings_remain_h2():
    """Promoting the page title to <h1> must not shift the "Decisions"
    (list column toolbar) or "Decision Intelligence" (detail column group
    label) headings -- they stay <h2>, logically below the new <h1>."""
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    combined = "".join(_built_markup_blocks(ui))

    assert '<h2 class="aara-eyebrow">Decisions</h2>' in combined
    assert '<h2 class="aara-eyebrow">Decision Intelligence</h2>' in combined


def test_decision_center_title_is_not_duplicated_as_a_lower_level_heading():
    """The promoted <h1> must be the only heading carrying the "Decision
    Center" page title -- no leftover <h2>/<h3> copy of it anywhere in the
    built layout (the nav tab's plain <span> at the same text is not a
    heading and is unaffected -- see _SHELL_NAV_HTML)."""
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    combined = "".join(_built_markup_blocks(ui))

    assert combined.count("Decision Center</h1>") == 1
    assert "Decision Center</h2>" not in combined
    assert "Decision Center</h3>" not in combined


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


def test_no_illustrative_data_disclosure_is_defined_or_rendered():
    """Phase 1 zero-illustrative-data: the "Illustrative Data" disclosure
    constants must not exist in the view module, and the composed layout
    must contain no such text. Decision Center now renders only real
    decisions (or its EMPTY state) with no data-authenticity disclaimer."""
    import applications.trading_intelligence.ui.decision_center.gradio_view as view_module

    for removed in ("_ILLUSTRATIVE_DATA_HTML", "_ILLUSTRATIVE_DATA_TITLE", "_ILLUSTRATIVE_DATA_BODY"):
        assert not hasattr(view_module, removed)

    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])
    demo = ui.build()
    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert not any("Illustrative Data" in value for value in html_values)


def test_timestamp_disclosure_clarifies_last_updated_may_be_governance_evaluation_time():
    """P1 UI-only timestamp fix: GovernanceService.evaluate_policy() stamps
    real evaluation-time (unlike every other lifecycle step, which uses a
    caller-supplied/seed timestamp) -- out of scope to change without
    touching sentinel_engine. Since "Last Updated" can therefore be that
    real evaluation time rather than illustrative demo-timeline data, the
    Decisions list must disclose that explicitly."""
    assert _TIMESTAMP_DISCLOSURE_TITLE == "About Last Updated"
    assert "governance evaluation time" in _TIMESTAMP_DISCLOSURE_BODY
    assert "latest governance workflow event" in _TIMESTAMP_DISCLOSURE_BODY
    assert _TIMESTAMP_DISCLOSURE_HTML == (
        '<div class="aara-disclosure-message">'
        '<div class="aara-disclosure-title">About Last Updated</div>'
        f'<div class="aara-disclosure-body">{html.escape(_TIMESTAMP_DISCLOSURE_BODY)}</div>'
        "</div>"
    )


def test_timestamp_disclosure_block_is_present_in_the_built_layout():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert _TIMESTAMP_DISCLOSURE_HTML in html_values


def test_scope_note_states_decision_center_is_not_order_or_execution_state():
    """UI hardening pass: a static, decision-independent note making explicit
    that Decision Center is an intelligence/governance view only and carries
    no order-submission / execution / settlement state."""
    assert "intelligence and governance only" in _SCOPE_NOTE_BODY
    assert "does not represent order submission, execution, or settlement" in _SCOPE_NOTE_BODY


def test_scope_note_block_is_present_in_the_built_layout():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert _SCOPE_NOTE_HTML in html_values


# --- P0-1: data-source transparency disclosure on the Decisions area -----


def test_no_producer_disclosure_wording_communicates_the_three_points():
    """Static, decision-independent note. Wave 1: the deployed Decision
    Center reads the trading bot's own execution history (the trades.db
    snapshot), so this states that truthfully -- historical decision-time
    evidence, not a live order-control surface, and not a Sentinel decision
    producer. Wording only, no store/read-model change."""
    assert _NO_PRODUCER_DISCLOSURE_TITLE == "About this view"
    # 1. sourced from the trading bot's execution history / trades snapshot
    assert "trading bot's execution history" in _NO_PRODUCER_DISCLOSURE_BODY
    assert "trades database snapshot" in _NO_PRODUCER_DISCLOSURE_BODY
    # 2. scope distinction: decision-time evidence, not live order control
    assert "historical decision-time evidence" in _NO_PRODUCER_DISCLOSURE_BODY
    assert "not a live order-control surface" in _NO_PRODUCER_DISCLOSURE_BODY
    # 3. an empty list is scoped to this view; not a claim about platform history
    assert "empty list means" in _NO_PRODUCER_DISCLOSURE_BODY
    assert (
        "does not mean the platform has no decision history"
        in _NO_PRODUCER_DISCLOSURE_BODY
    )
    # must not claim Sentinel produced these decisions
    lowered = _NO_PRODUCER_DISCLOSURE_BODY.lower()
    assert "sentinel" not in lowered
    # no internal names / table names / ADR numbers exposed
    for leaked in ("inmemory", "repository", "trust_ledger", "decision_events", "adr-", "adr "):
        assert leaked not in lowered
    assert _NO_PRODUCER_DISCLOSURE_HTML == (
        '<div class="aara-disclosure-message">'
        f'<div class="aara-disclosure-title">{html.escape(_NO_PRODUCER_DISCLOSURE_TITLE)}</div>'
        f'<div class="aara-disclosure-body">{html.escape(_NO_PRODUCER_DISCLOSURE_BODY)}</div>'
        "</div>"
    )


def test_no_producer_disclosure_block_is_present_in_the_built_layout():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert _NO_PRODUCER_DISCLOSURE_HTML in html_values


def test_no_producer_disclosure_is_static_not_part_of_render_outputs():
    """It is set as a fixed gr.HTML value at build() time (like
    _SCOPE_NOTE_HTML), never returned by _render_screen()/_render_detail()
    and never in _DetailValues, so no callback can change it."""
    view = _make_view()
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[view]),
        detail_area=DecisionDetailArea(decision=view),
    )
    controller = _FakeController(
        screen=screen, detail_area=DecisionDetailArea(decision=view)
    )
    ui = DecisionCenterUI(controller, ["dec-001"])

    screen_values = ui._render_screen()
    detail_values = ui._render_detail("dec-001")

    for produced in (*screen_values, *detail_values):
        assert produced != _NO_PRODUCER_DISCLOSURE_HTML
        if isinstance(produced, str):
            assert _NO_PRODUCER_DISCLOSURE_TITLE not in produced
            assert "trading bot's execution history" not in produced


def test_render_screen_return_shape_is_unchanged_by_the_disclosure():
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[]),
        detail_area=DecisionDetailArea(decision=None),
    )
    ui = DecisionCenterUI(_FakeController(screen=screen), [])

    assert len(ui._render_screen()) == 12  # list_rows, list_empty_html + _DetailValues (10)


def test_render_detail_return_shape_is_unchanged_by_the_disclosure():
    view = _make_view()
    ui = DecisionCenterUI(
        _FakeController(detail_area=DecisionDetailArea(decision=view)), ["dec-001"]
    )

    assert len(ui._render_detail("dec-001")) == 10  # _DetailValues


def test_existing_zero_decision_wording_intact_alongside_the_disclosure():
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[]),
        detail_area=DecisionDetailArea(decision=None),
    )
    ui = DecisionCenterUI(_FakeController(screen=screen), [])

    (list_rows, list_empty_html, *_rest) = ui._render_screen()
    assert list_rows == []
    assert list_empty_html == '<div class="aara-empty-message">No decisions recorded yet.</div>'
    assert ui._announce_screen() == "Decision Center updated. Showing 0 decisions."


def test_gradio_view_module_imports_no_bot_dashboard_or_ledger():
    import ast
    import inspect

    import applications.trading_intelligence.ui.decision_center.gradio_view as module

    tree = ast.parse(inspect.getsource(module))
    forbidden = ("bot", "dashboard", "ledger", "database", "scheduler")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.split(".")[0] in forbidden, alias.name
                assert "trust_ledger" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            assert root not in forbidden, node.module
            assert "trust_ledger" not in (node.module or "")


def test_announce_screen_wording_for_zero_decisions():
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[]), detail_area=DecisionDetailArea(decision=None),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, [])

    assert ui._announce_screen() == "Decision Center updated. Showing 0 decisions."


def test_announce_screen_wording_for_one_decision_is_singular():
    view = _make_view()
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[view]), detail_area=DecisionDetailArea(decision=view),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-001"])

    assert ui._announce_screen() == "Decision Center updated. Showing 1 decision."


def test_announce_screen_wording_for_multiple_decisions_is_plural():
    views = [_make_view(decision_id="dec-001"), _make_view(decision_id="dec-002")]
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=views), detail_area=DecisionDetailArea(decision=None),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-001", "dec-002"])

    assert ui._announce_screen() == "Decision Center updated. Showing 2 decisions."


def test_announce_screen_ignores_its_selected_id_argument():
    """refresh_button.click() wires this fn with inputs=[selected_decision_id]
    (see build()) -- confirms passing a value there doesn't change the
    wording, since the announcement only reports a count."""
    views = [_make_view(decision_id="dec-001"), _make_view(decision_id="dec-002")]
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=views), detail_area=DecisionDetailArea(decision=None),
    )
    controller = _FakeController(screen=screen)
    ui = DecisionCenterUI(controller, ["dec-001", "dec-002"])

    assert ui._announce_screen("dec-002") == "Decision Center updated. Showing 2 decisions."


def test_announce_row_select_wording_includes_the_rationale_for_a_single_evidence_entry():
    view = _make_view(decision_id="dec-002", symbol="MSFT")
    entry = _make_entry(evidence_type="NEWS_SENTIMENT", source="newsapi")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-002"])
    row = ["dec-002", "MSFT", "HOLD", "Decision Created", "82%"]

    result = ui._announce_row_select(_make_select_event(row))

    assert result == (
        "Decision selected: MSFT. 1 NEWS_SENTIMENT signal from newsapi. "
        f"{_WHY_EVIDENCE_CLARIFICATION}"
    )


def test_announce_row_select_wording_includes_the_rationale_for_multiple_evidence_entries():
    view = _make_view(decision_id="dec-002", symbol="MSFT")
    entry_a = _make_entry(evidence_type="NEWS_SENTIMENT", source="newsapi")
    entry_b = _make_entry(evidence_id="ev-002", evidence_type="PRICE_ACTION", source="alpaca")
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, evidence=(entry_a, entry_b))
    )
    ui = DecisionCenterUI(controller, ["dec-002"])
    row = ["dec-002", "MSFT", "HOLD", "Decision Created", "82%"]

    result = ui._announce_row_select(_make_select_event(row))

    assert result == (
        "Decision selected: MSFT. 2 signals: NEWS_SENTIMENT from newsapi; "
        f"PRICE_ACTION from alpaca. {_WHY_EVIDENCE_CLARIFICATION}"
    )


def test_announce_row_select_wording_falls_back_to_the_placeholder_for_zero_evidence():
    view = _make_view(decision_id="dec-001", symbol="AAPL")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=()))
    ui = DecisionCenterUI(controller, ["dec-001"])
    row = ["dec-001", "AAPL", "BUY", "Decision Created", "71%"]

    result = ui._announce_row_select(_make_select_event(row))

    assert result == (
        "Decision selected: AAPL. Rationale not captured. "
        "The decision thesis has not yet been recorded."
    )


def test_announce_row_select_wording_is_error_specific_on_a_read_error():
    """P2 Loading States accessibility pass: a read error must be
    announced distinctly from a normal selection, reusing the exact same
    _DECISION_READ_ERROR_MESSAGE the visible header already shows for this
    case (_decision_error_header_html) -- not the old ambiguous bare
    "Decision selected: {symbol}." wording, which read identically to a
    successful selection to a screen-reader user."""
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=None, decision_status=ReadStatus.ERROR)
    )
    ui = DecisionCenterUI(controller, ["dec-001"])
    row = ["dec-001", "AAPL", "BUY", "Decision Created", "71%"]

    result = ui._announce_row_select(_make_select_event(row))

    assert result == f"Decision selected: AAPL. {_DECISION_READ_ERROR_MESSAGE}"


def test_announce_row_select_wording_is_not_found_specific_when_the_decision_is_missing():
    """P2 Loading States accessibility pass: a genuine not-found result
    (decision_status is OK but no decision was returned) must be announced
    with _DECISION_NOT_FOUND_MESSAGE, reusing the exact text the visible
    header already shows (_missing_decision_header_html) -- distinct from
    both a successful selection and a read error."""
    controller = _FakeController(detail_area=DecisionDetailArea(decision=None))
    ui = DecisionCenterUI(controller, ["dec-001"])
    row = ["dec-001", "AAPL", "BUY", "Decision Created", "71%"]

    result = ui._announce_row_select(_make_select_event(row))

    assert result == f"Decision selected: AAPL. {_DECISION_NOT_FOUND_MESSAGE}"


def test_announce_row_select_wording_includes_the_evidence_error_message():
    """P1 accessibility audit fix: a successfully-loaded decision whose
    Evidence read failed must have that failure spoken, reusing the exact
    same _EVIDENCE_ERROR_MESSAGE the visible Evidence section already shows
    (_format_evidence_html) -- not silently omitted, which previously left
    screen-reader users with no signal that a section failed to load.

    P2 Why/Rationale error-wording fix: the announcement previously said
    "Rationale not captured. The decision thesis has not yet been
    recorded." immediately before this same _EVIDENCE_ERROR_MESSAGE --
    self-contradictory wording (a permanent "not yet recorded" claim right
    next to a "temporarily unavailable" one for the same read failure).
    Now uses the short _WHY_EVIDENCE_ERROR_TITLE ("Rationale unavailable.")
    instead, with _EVIDENCE_ERROR_MESSAGE supplying the one and only
    detailed explanation, matching the visible panel's own
    title/body split (_WHY_EVIDENCE_ERROR_HTML)."""
    view = _make_view(decision_id="dec-002", symbol="MSFT")
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, evidence_status=ReadStatus.ERROR)
    )
    ui = DecisionCenterUI(controller, ["dec-002"])
    row = ["dec-002", "MSFT", "HOLD", "Decision Created", "82%"]

    result = ui._announce_row_select(_make_select_event(row))

    assert result == (
        f"Decision selected: MSFT. {_WHY_EVIDENCE_ERROR_TITLE}. "
        f"{_EVIDENCE_ERROR_MESSAGE}"
    )
    assert "The decision thesis has not yet been recorded." not in result


def test_announce_row_select_wording_includes_the_governance_error_message():
    view = _make_view(decision_id="dec-001", symbol="AAPL")
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, governance_status=ReadStatus.ERROR)
    )
    ui = DecisionCenterUI(controller, ["dec-001"])
    row = ["dec-001", "AAPL", "BUY", "Decision Created", "71%"]

    result = ui._announce_row_select(_make_select_event(row))

    assert result == (
        "Decision selected: AAPL. Rationale not captured. "
        "The decision thesis has not yet been recorded. "
        f"{_GOVERNANCE_ERROR_MESSAGE}"
    )


def test_announce_row_select_wording_includes_the_approval_error_message():
    view = _make_view(decision_id="dec-001", symbol="AAPL")
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, approvals_status=ReadStatus.ERROR)
    )
    ui = DecisionCenterUI(controller, ["dec-001"])
    row = ["dec-001", "AAPL", "BUY", "Decision Created", "71%"]

    result = ui._announce_row_select(_make_select_event(row))

    assert result == (
        "Decision selected: AAPL. Rationale not captured. "
        "The decision thesis has not yet been recorded. "
        f"{_APPROVAL_ERROR_MESSAGE}"
    )


def test_announce_row_select_wording_includes_the_audit_trail_error_message():
    view = _make_view(decision_id="dec-001", symbol="AAPL")
    controller = _FakeController(
        detail_area=DecisionDetailArea(decision=view, audit_trail_status=ReadStatus.ERROR)
    )
    ui = DecisionCenterUI(controller, ["dec-001"])
    row = ["dec-001", "AAPL", "BUY", "Decision Created", "71%"]

    result = ui._announce_row_select(_make_select_event(row))

    assert result == (
        "Decision selected: AAPL. Rationale not captured. "
        "The decision thesis has not yet been recorded. "
        f"{_AUDIT_ERROR_MESSAGE}"
    )


def test_announce_row_select_wording_includes_every_failed_section_error_in_a_fixed_order():
    """Multiple simultaneous section failures are announced together, in a
    fixed Evidence -> Governance -> Approval -> Audit Trail order matching
    the detail panel's own top-to-bottom section order -- not just the
    first one encountered."""
    view = _make_view(decision_id="dec-001", symbol="AAPL")
    controller = _FakeController(
        detail_area=DecisionDetailArea(
            decision=view,
            evidence_status=ReadStatus.ERROR,
            governance_status=ReadStatus.ERROR,
            approvals_status=ReadStatus.ERROR,
            audit_trail_status=ReadStatus.ERROR,
        )
    )
    ui = DecisionCenterUI(controller, ["dec-001"])
    row = ["dec-001", "AAPL", "BUY", "Decision Created", "71%"]

    result = ui._announce_row_select(_make_select_event(row))

    # P2 Why/Rationale error-wording fix: evidence_status ERROR here means
    # the rationale summary itself is the short _WHY_EVIDENCE_ERROR_TITLE,
    # not the old "not yet recorded" wording -- _EVIDENCE_ERROR_MESSAGE
    # still appears exactly once, as the first section error, not repeated.
    assert result == (
        f"Decision selected: AAPL. {_WHY_EVIDENCE_ERROR_TITLE}. "
        f"{_EVIDENCE_ERROR_MESSAGE} {_GOVERNANCE_ERROR_MESSAGE} "
        f"{_APPROVAL_ERROR_MESSAGE} {_AUDIT_ERROR_MESSAGE}"
    )


def test_announce_row_select_wording_has_no_section_errors_when_all_sections_succeed():
    """Regression guard: a fully successful selection's wording must stay
    byte-identical to the pre-existing behavior (plus the P2 trust
    clarification appended to the rationale sentence itself) -- no trailing
    space, no empty section-error text appended."""
    view = _make_view(decision_id="dec-002", symbol="MSFT")
    entry = _make_entry(evidence_type="NEWS_SENTIMENT", source="newsapi")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=(entry,)))
    ui = DecisionCenterUI(controller, ["dec-002"])
    row = ["dec-002", "MSFT", "HOLD", "Decision Created", "82%"]

    result = ui._announce_row_select(_make_select_event(row))

    assert result == (
        "Decision selected: MSFT. 1 NEWS_SENTIMENT signal from newsapi. "
        f"{_WHY_EVIDENCE_CLARIFICATION}"
    )


def test_announce_row_select_is_empty_on_deselection():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    result = ui._announce_row_select(_make_select_event(["dec-001"], selected=False))

    assert result == ""
    assert controller.load_decision_detail_calls == []


def test_announce_row_select_is_empty_on_missing_row_value():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    result = ui._announce_row_select(_make_select_event(None))

    assert result == ""
    assert controller.load_decision_detail_calls == []


def test_announce_row_select_calls_the_controller_for_the_selected_decision():
    """P2 accessibility pass: unlike P1's original wording, the
    rationale-inclusive announcement needs the decision's evidence, so
    this now makes one load_decision_detail() call per selection --
    mirroring _announce_screen's own already-accepted duplicate-fetch
    precedent (re-fetching via load_decisions()) rather than threading
    _on_row_select's own render through to this independent listener."""
    view = _make_view(decision_id="dec-002", symbol="MSFT")
    controller = _FakeController(detail_area=DecisionDetailArea(decision=view, evidence=()))
    ui = DecisionCenterUI(controller, ["dec-002"])
    row = ["dec-002", "MSFT", "HOLD", "Decision Created", "82%"]

    ui._announce_row_select(_make_select_event(row))

    assert controller.load_decision_detail_calls == ["dec-002"]


def test_live_announcer_block_is_present_in_the_built_layout_with_empty_initial_value():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    live_announcer_blocks = [
        block for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and getattr(block, "elem_id", None) == _LIVE_ANNOUNCER_ELEM_ID
    ]
    assert len(live_announcer_blocks) == 1
    assert live_announcer_blocks[0].value == ""
    assert "aara-sr-only" in live_announcer_blocks[0].elem_classes


def test_selection_aria_sync_script_is_present_in_built_layout():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    assert _SELECTION_ARIA_SYNC_JS in demo.head


def test_selection_aria_sync_script_targets_the_documented_dom_contract():
    """Same DOM contract V3.1's keyboard bridge already depends on
    (.aara-decisions-table anchor; a real data row is tr[slot="tbody"];
    Gradio's own click handler marks the selected cell with a td.focus
    class) -- asserted here as a contract check so a future edit that
    silently breaks it fails a test instead of failing only in the
    browser."""
    assert "aara-decisions-table" in _SELECTION_ARIA_SYNC_JS
    assert 'tr[slot="tbody"]' in _SELECTION_ARIA_SYNC_JS
    assert "td.focus" in _SELECTION_ARIA_SYNC_JS


def test_selection_aria_sync_script_discovers_the_table_containing_real_rows():
    """Regression check: .aara-decisions-table contains two <table>
    elements -- Gradio's own hidden column-width-measurement table (zero
    tr[slot="tbody"] rows) and the real, interactive, virtualized table --
    in unspecified DOM order. A live-verified defect found the script
    using a single document.querySelector(".aara-decisions-table table"),
    which silently bound to whichever table happened to render first
    (the empty one), so aria-selected was never applied to any real row.
    The fix enumerates every matching table via querySelectorAll and picks
    the one containing a real tr[slot="tbody"] row -- asserted here as a
    source-level contract so a future edit can't silently reintroduce the
    single-match .querySelector(".aara-decisions-table table") call."""
    assert "document.querySelector(\".aara-decisions-table table\")" not in _SELECTION_ARIA_SYNC_JS
    assert "querySelectorAll(\".aara-decisions-table table\")" in _SELECTION_ARIA_SYNC_JS
    assert 'querySelector(\'tr[slot="tbody"]\')' in _SELECTION_ARIA_SYNC_JS
    assert "aria-selected" in _SELECTION_ARIA_SYNC_JS


def test_accessible_name_setup_script_is_present_in_built_layout():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    assert _ACCESSIBLE_NAME_SETUP_JS in demo.head


def test_accessible_name_setup_script_targets_the_documented_dom_contract():
    """P1 accessibility fix: gr.Dataframe's label="Decisions" only reaches
    a <caption> inside the child <table> elements, never the interactive
    role="grid" div a screen reader actually names (see gradio_view.py's
    own docstring on _ACCESSIBLE_NAME_SETUP_JS for the verified DOM
    contract). Asserted here as a contract check so a future edit can't
    silently drop the selector or the aria-label value without failing a
    test instead of only failing in the browser."""
    assert '.aara-decisions-table [role="grid"]' in _ACCESSIBLE_NAME_SETUP_JS
    assert 'setAttribute("aria-label", "Decisions")' in _ACCESSIBLE_NAME_SETUP_JS


def test_journey_target_focus_setup_script_is_present_in_built_layout():
    controller = _FakeController()
    ui = DecisionCenterUI(controller, ["dec-001"])

    demo = ui.build()

    assert _JOURNEY_TARGET_FOCUS_SETUP_JS in demo.head


def test_journey_target_focus_setup_script_targets_the_documented_dom_contract():
    """P2 #6 fix: the Decision Journey's four anchor links jump to plain,
    non-focusable gr.HTML(elem_id=...) divs, so a keyboard/screen-reader
    user activating one gets no focus change and no announcement -- only
    the (imperceptible to them) visual scroll (see gradio_view.py's own
    docstring on _JOURNEY_TARGET_FOCUS_SETUP_JS for the full contract).
    Asserted here as a contract check so a future edit can't silently drop
    one of the four target ids or the tabindex="-1" attribute without
    failing a test instead of only failing in the browser."""
    assert "decision-created-section" in _JOURNEY_TARGET_FOCUS_SETUP_JS
    assert "evidence-section" in _JOURNEY_TARGET_FOCUS_SETUP_JS
    assert "governance-section" in _JOURNEY_TARGET_FOCUS_SETUP_JS
    assert "approval-section" in _JOURNEY_TARGET_FOCUS_SETUP_JS
    assert 'setAttribute("tabindex", "-1")' in _JOURNEY_TARGET_FOCUS_SETUP_JS


def test_theme_focus_ring_covers_decision_journey_anchor_links():
    """P2 #2 fix: the Decision Journey's four stage links
    (.aara-lifecycle-track .label -- see _lifecycle_track_html) are plain
    <a href="#..."> anchors, natively focusable without a tabindex
    attribute. theme.py's keyboard-focus-visibility rule previously only
    listed `button:focus-visible` and `[tabindex]:focus-visible`, so these
    links matched neither selector and fell through with no visible focus
    ring, unlike every other focusable element in this app. Asserted as a
    single contiguous rule (not just a same-file substring) so a future
    edit can't silently split `a:focus-visible` into a different
    declaration, or drop it, without failing a test.

    P3 fix: the same rule also now covers `summary:focus-visible`, closing
    the identical gap for the Evidence/Audit Trail payload disclosures'
    native <summary> elements (also natively focusable without tabindex,
    also previously falling through to the browser's raw default outline)."""
    assert (
        ".gradio-container button:focus-visible,\n"
        ".gradio-container [tabindex]:focus-visible,\n"
        ".gradio-container a:focus-visible,\n"
        ".gradio-container summary:focus-visible {\n"
        "  outline: 2px solid var(--color-gold-accent-boundary) !important;\n"
        "  outline-offset: 2px;\n"
        "}"
    ) in CSS


def test_theme_restyles_gradios_own_pending_state_classes():
    """MVP Loading States slice: theme.py must restyle Gradio's own
    pending/processing classes (.eta-bar sweep, .meta-text/.progress-text
    badge -- confirmed real, if svelte-scoped, class names against the
    installed gradio==4.44.1 package's compiled CSS) to the AARA palette,
    rather than leaving Gradio's stock gray/accent-orange defaults
    unstyled.

    P3 dead-CSS cleanup: .generating (the pulsing pending-state border) was
    dropped from this assertion -- live-verified (P2 Loading States pass)
    that it never actually renders in this app, so theme.py's own rule for
    it was removed as dead code; .eta-bar/.meta-text/.progress-text already
    carry the real, working pending signal on their own."""
    for selector in (".eta-bar", ".meta-text", ".progress-text"):
        assert selector in CSS
    assert ".generating {" not in CSS


def test_theme_nav_item_muted_and_badge_rules_are_removed_as_dead_css():
    """P3 dead-CSS cleanup: .nav-item.muted and .aara-nav-badge styled a
    "Coming Soon" treatment for Portfolio/Risk Intelligence nav items that
    no longer exists -- both screens shipped as real tabs, and
    _SHELL_NAV_HTML/build_shell_nav_html() have not emitted either class in
    any live markup for some time (see
    test_shell_nav_has_exactly_one_active_item_and_no_muted_items, which
    already asserts their absence from the rendered nav). This asserts the
    now-unused CSS itself is gone too, not just the markup."""
    assert ".nav-item.muted {" not in CSS
    assert ".aara-nav-badge {" not in CSS


def test_theme_refresh_button_selector_targets_the_button_itself():
    """P3 dead-selector fix: elem_classes=["aara-refresh-button"] lands
    directly on the rendered <button> (gr.Button puts elem_classes on the
    button element itself, not a wrapper) -- confirmed live via
    getComputedStyle. The old ".aara-refresh-button button" descendant
    selector could therefore never match anything and silently left the
    button on Gradio's own default chrome the whole time. This locks in
    both halves of the fix: the corrected selector carries the intended
    styling, and the dead descendant-selector text never reappears."""
    assert (
        ".aara-refresh-button {\n"
        "  flex: none !important;\n"
        "  min-width: 0 !important;\n"
        "  background: transparent !important;\n"
        "  border: 1px solid var(--color-border-subtle) !important;\n"
        "  color: var(--color-text-secondary) !important;\n"
        "  font-size: 12px !important;\n"
        "  font-weight: 600 !important;\n"
        "  box-shadow: none !important;\n"
        "  padding: 4px var(--space-sm) !important;\n"
        "}\n"
        ".aara-refresh-button:hover {\n"
        "  border-color: var(--color-gold-accent-boundary) !important;\n"
        "  color: var(--color-navy-primary) !important;\n"
        "}"
    ) in CSS
    assert ".aara-refresh-button button {" not in CSS
    assert ".aara-refresh-button button:hover {" not in CSS


def test_theme_payload_disclosure_summary_is_styled():
    """P3 fix: the native <summary> in the Evidence/Audit Trail "Details"
    payload disclosure (.aara-payload-disclosure, see
    _format_evidence_detail_html/_format_audit_detail_html) had no CSS rule
    at all -- live-verified (getComputedStyle) it rendered in Gradio's own
    default body color/size (#1F2937/14px, matching none of this app's own
    tokens) with cursor: auto (no click affordance, unlike every other
    interactive element in this file). Reuses existing tokens only --
    --color-text-secondary, matching the surrounding record-field text
    size -- not a new component or a redesign."""
    assert (
        ".aara-payload-disclosure summary {\n"
        "  font-size: 13px;\n"
        "  color: var(--color-text-secondary);\n"
        "  cursor: pointer;\n"
        "}"
    ) in CSS


def test_theme_does_not_introduce_a_custom_spinner_or_skeleton_system():
    """The task is explicit: recolor Gradio's existing pending mechanism,
    do not build a new one. No new aara-* spinner/skeleton component class,
    no @keyframes block, should appear anywhere in this stylesheet --
    checked as class-name/rule substrings, not a bare word search, since
    this file's own comments legitimately discuss "spinner"/"skeleton" as
    the thing deliberately not built."""
    assert "aara-spinner" not in CSS
    assert "aara-skeleton" not in CSS
    assert "@keyframes" not in CSS


def test_theme_decisions_table_uses_fixed_layout_with_all_six_columns_sized():
    """P3 visual-polish fix (Finding 1): live audit found Gradio's own
    content-measured column widths (~747px across 6 visible columns) far
    exceeding the table's actual container (~480-590px at realistic desktop
    widths, narrower on mobile), with the pre-existing overflow-x: hidden
    silently clipping Last Updated/Verdict off-screen entirely -- Verdict
    was completely unreachable, not merely cramped. table-layout: fixed
    plus fixed --cell-width-N percentages (summing to exactly 100%,
    live-verified at both 1440px and 900px) is what makes the table's own
    width, and each column's share of it, authoritative instead of
    content-measured. Asserted here as contract checks so a future edit
    can't silently drop table-layout: fixed, reintroduce a percentage sum
    that doesn't total 100%, or lose the six-column CSS mapping this fix
    depends on (nth-child(1) is Decision ID, hidden -- excluded from this
    count on purpose)."""
    assert "table-layout: fixed !important;" in CSS
    cell_width_percentages = [0, 12, 12, 19, 17, 22, 18]
    for index, percentage in enumerate(cell_width_percentages):
        assert f"--cell-width-{index}: {percentage}% !important;" in CSS
    assert sum(cell_width_percentages) == 100


def test_theme_decisions_table_wraps_only_status_and_last_updated_columns():
    """Companion to the fixed-layout fix above: Symbol/Action/Confidence/
    Verdict hold genuinely short, fixed-vocabulary content (ticker symbols,
    BUY/SELL/HOLD and APPROVED/REJECTED badges, percentages) that must stay
    on one line -- an earlier iteration of this fix instead force-wrapped
    every column, which broke ticker symbols and badges mid-word (e.g.
    "GOOGL" as "GO"/"OGL"). Only Status (nth-child(4)) and Last Updated
    (nth-child(6)) -- the two genuinely long-text columns this fix's
    percentages deliberately don't try to fit on one line -- opt back into
    wrapping. Asserted as a contract check so a future edit can't silently
    re-apply wrapping to the other four columns."""
    assert (
        ".aara-decisions-table table thead th:nth-child(4),\n"
        ".aara-decisions-table table tbody td:nth-child(4),\n"
        ".aara-decisions-table table thead th:nth-child(6),\n"
        ".aara-decisions-table table tbody td:nth-child(6) {\n"
        "  white-space: normal !important;\n"
        "  text-overflow: clip;\n"
        "}"
    ) in CSS
