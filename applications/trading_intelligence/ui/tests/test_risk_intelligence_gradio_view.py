import pathlib

import gradio as gr

from applications.trading_intelligence.ui.risk_intelligence.gradio_view import (
    _AS_OF_PREFIX,
    _LIVE_ANNOUNCER_ELEM_ID,
    _LIVE_REGION_SETUP_JS,
    _OBSERVED_CLASSIFICATION_HTML,
    _SIZING_UNAVAILABLE_HTML,
    _TRIGGER_REASON_UNAVAILABLE_HTML,
    _UNAVAILABLE_MESSAGE_HTML,
    _format_as_of_html,
    RiskIntelligenceUI,
)
from applications.trading_intelligence.ui.risk_intelligence.screen import (
    RiskHistoryEntry,
    RiskScreen,
    RiskSnapshot,
)
from applications.trading_intelligence.ui.risk_intelligence.theme import CSS
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html


def _make_snapshot(**overrides):
    defaults = dict(
        state="NORMAL",
        trigger_reason="Portfolio drawdown -3.1% -- within normal range.",
        recommended_sizing_pct=100.0,
        actual_sizing_pct=100.0,
        as_of="2026-08-18 14:00 UTC",
    )
    defaults.update(overrides)
    return RiskSnapshot(**defaults)


_TEST_HISTORY = (
    RiskHistoryEntry(
        timestamp="2026-08-18 14:00 UTC", state="NORMAL",
        trigger_reason="Portfolio drawdown -3.1% -- within normal range.",
        recommended_sizing_pct=100.0, actual_sizing_pct=100.0,
    ),
    RiskHistoryEntry(
        timestamp="2026-08-17 09:15 UTC", state="WARNING",
        trigger_reason="Portfolio drawdown -11.4% -- approaching daily loss limit.",
        recommended_sizing_pct=75.0, actual_sizing_pct=70.0,
    ),
)


def _make_available_screen(**overrides):
    """An explicitly-injected, available RiskScreen for the formatter/
    rendering tests -- this path is unchanged by the illustrative-data
    removal (only the production *default* became unavailable)."""
    defaults = dict(current=_make_snapshot(), history=_TEST_HISTORY)
    defaults.update(overrides)
    return RiskScreen(**defaults)


def test_ui_defaults_to_an_unavailable_screen():
    ui = RiskIntelligenceUI()

    assert ui._screen.is_available is False
    assert ui._screen.current is None


def test_build_returns_a_gradio_blocks_instance():
    ui = RiskIntelligenceUI()

    demo = ui.build()

    assert isinstance(demo, gr.Blocks)


def test_default_build_renders_the_unavailable_message_and_no_fabricated_content():
    """Production default: no real risk source, so the view must render a
    single UNAVAILABLE message and never a fabricated state badge, history
    table, evaluation card, sizing metric, timestamp, or an "Illustrative
    Data" disclosure. The stable component tree still contains a hidden
    history Dataframe (toggled via `visible=` in _render), so assert it is
    not visible rather than absent."""
    ui = RiskIntelligenceUI()

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    combined = "\n".join(value for value in html_values if value)
    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]

    assert _UNAVAILABLE_MESSAGE_HTML in html_values
    assert "Risk Intelligence data is currently unavailable." in combined
    assert all(df.visible is False for df in dataframes)
    assert "Illustrative Data" not in combined
    for fabricated in ("state-normal", "state-warning", "state-defensive", "ri-state-badge"):
        assert fabricated not in combined
    assert "ri-current-state" not in combined
    assert "ri-sizing-metrics" not in combined
    assert '<details class="ri-history-detail-card">' not in combined
    assert "Recommended Sizing" not in combined


def test_default_build_still_renders_shell_header_nav_page_header_and_announcer():
    ui = RiskIntelligenceUI()

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    combined = "\n".join(html_values)
    assert SHELL_IDENTITY_HTML in html_values
    assert build_shell_nav_html("Risk Intelligence") in html_values
    assert '<h2 class="aara-eyebrow">Risk Intelligence</h2>' in combined
    live_blocks = [
        block for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and getattr(block, "elem_id", None) == _LIVE_ANNOUNCER_ELEM_ID
    ]
    assert len(live_blocks) == 1


def test_announce_current_state_reports_unavailable_by_default():
    ui = RiskIntelligenceUI()

    announcement = ui._announce_current_state()

    assert announcement == (
        "Risk Intelligence loaded. Risk Intelligence data is currently unavailable."
    )


def test_shell_header_and_nav_are_present_in_the_built_layout():
    """AARA shell consistency pass: Risk Intelligence now renders the same
    shell header/nav Decision Center does, reused via ui/shell.py -- see
    that module's docstring for why it isn't imported from
    ui/decision_center/ or ui/portfolio_intelligence/ directly."""
    ui = RiskIntelligenceUI()

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert SHELL_IDENTITY_HTML in html_values
    assert build_shell_nav_html("Risk Intelligence") in html_values


def test_shell_header_and_nav_blocks_carry_the_expected_elem_classes():
    ui = RiskIntelligenceUI()

    demo = ui.build()

    html_blocks = [block for block in demo.blocks.values() if isinstance(block, gr.HTML)]
    assert any("aara-shell-header" in (block.elem_classes or []) for block in html_blocks)
    assert any("aara-shell-nav" in (block.elem_classes or []) for block in html_blocks)


def test_state_badge_html_reflects_every_state():
    for state, css_class in (
        ("NORMAL", "state-normal"), ("WARNING", "state-warning"), ("DEFENSIVE", "state-defensive"),
    ):
        badge_html = RiskIntelligenceUI._format_state_badge_html(state)

        assert css_class in badge_html
        assert state in badge_html


def test_current_state_html_includes_badge_trigger_reason_and_sizing():
    snapshot = _make_snapshot(
        state="WARNING",
        trigger_reason="Portfolio drawdown -11.4% -- approaching daily loss limit.",
        recommended_sizing_pct=75.0,
        actual_sizing_pct=70.0,
        as_of="2026-08-17 09:15 UTC",
    )

    current_html = RiskIntelligenceUI._format_current_state_html(snapshot)

    assert "state-warning" in current_html
    assert "WARNING" in current_html
    assert "2026-08-17 09:15 UTC" in current_html
    assert "<summary>Trigger Reason</summary>" in current_html
    assert "Portfolio drawdown -11.4%" in current_html
    assert "75%" in current_html
    assert "70%" in current_html
    assert "+5%" in current_html


def test_current_state_html_uses_native_details_disclosure_for_keyboard_access():
    """<details>/<summary> is natively Tab-focusable and Enter/Space-
    togglable -- no custom JS bridge needed, matching this package's own
    self-contained, no-custom-JS scope."""
    snapshot = _make_snapshot()

    current_html = RiskIntelligenceUI._format_current_state_html(snapshot)

    assert "<details" in current_html
    assert "<summary>" in current_html


def test_format_history_rows_maps_every_field():
    entry = RiskHistoryEntry(
        timestamp="2026-08-18 14:00 UTC", state="NORMAL",
        trigger_reason="Portfolio drawdown -3.1% -- within normal range.",
        recommended_sizing_pct=100.0, actual_sizing_pct=100.0,
    )

    rows = RiskIntelligenceUI._format_history_rows((entry,))

    assert rows == [[
        "2026-08-18 14:00 UTC", "NORMAL",
        "Portfolio drawdown -3.1% -- within normal range.", "100%", "100%",
    ]]


def test_format_history_rows_handles_multiple_entries_in_order():
    entry_a = RiskHistoryEntry(
        timestamp="2026-08-18 14:00 UTC", state="NORMAL", trigger_reason="a",
        recommended_sizing_pct=100.0, actual_sizing_pct=100.0,
    )
    entry_b = RiskHistoryEntry(
        timestamp="2026-08-17 09:15 UTC", state="WARNING", trigger_reason="b",
        recommended_sizing_pct=75.0, actual_sizing_pct=70.0,
    )

    rows = RiskIntelligenceUI._format_history_rows((entry_a, entry_b))

    assert [row[1] for row in rows] == ["NORMAL", "WARNING"]


def test_empty_message_html_renders_the_screens_own_message():
    screen = RiskScreen(current=_make_snapshot())

    empty_html = RiskIntelligenceUI._format_empty_message_html(screen)

    assert 'class="ri-empty-message"' in empty_html
    assert "No risk evaluations recorded yet." in empty_html


def test_build_renders_empty_message_instead_of_a_table_when_no_history():
    empty_screen = RiskScreen(current=_make_snapshot())
    ui = RiskIntelligenceUI(screen=empty_screen)

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert all(df.visible is False for df in dataframes)
    assert any("No risk evaluations recorded yet." in value for value in html_values)


def test_build_renders_a_dataframe_when_history_exists():
    ui = RiskIntelligenceUI(screen=_make_available_screen())

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    assert len(dataframes) == 1
    assert "ri-history-table" in dataframes[0].elem_classes


def test_history_detail_html_uses_native_details_disclosure_for_keyboard_access():
    entry = RiskHistoryEntry(
        timestamp="2026-08-18 14:00 UTC", state="NORMAL",
        trigger_reason="Portfolio drawdown -3.1% -- within normal range.",
        recommended_sizing_pct=100.0, actual_sizing_pct=100.0,
    )

    detail_html = RiskIntelligenceUI._format_history_detail_html(entry)

    assert "<details" in detail_html
    assert "<summary>" in detail_html


def test_history_detail_html_includes_full_untruncated_trigger_reason():
    long_reason = (
        "Portfolio drawdown -16.8% -- CRO approval required for new positions."
    )
    entry = RiskHistoryEntry(
        timestamp="2026-08-16 16:45 UTC", state="DEFENSIVE",
        trigger_reason=long_reason,
        recommended_sizing_pct=50.0, actual_sizing_pct=45.0,
    )

    detail_html = RiskIntelligenceUI._format_history_detail_html(entry)

    assert long_reason in detail_html


def test_history_detail_html_includes_state_sizing_gap_and_timestamp():
    entry = RiskHistoryEntry(
        timestamp="2026-08-17 09:15 UTC", state="WARNING",
        trigger_reason="Portfolio drawdown -11.4% -- approaching daily loss limit.",
        recommended_sizing_pct=75.0, actual_sizing_pct=70.0,
    )

    detail_html = RiskIntelligenceUI._format_history_detail_html(entry)

    assert "state-warning" in detail_html
    assert "WARNING" in detail_html
    assert "2026-08-17 09:15 UTC" in detail_html
    assert "75%" in detail_html
    assert "70%" in detail_html
    assert "+5%" in detail_html


def test_history_detail_list_html_produces_one_card_per_entry():
    entry_a = RiskHistoryEntry(
        timestamp="2026-08-18 14:00 UTC", state="NORMAL", trigger_reason="a",
        recommended_sizing_pct=100.0, actual_sizing_pct=100.0,
    )
    entry_b = RiskHistoryEntry(
        timestamp="2026-08-17 09:15 UTC", state="WARNING", trigger_reason="b",
        recommended_sizing_pct=75.0, actual_sizing_pct=70.0,
    )

    list_html = RiskIntelligenceUI._format_history_detail_list_html((entry_a, entry_b))

    assert list_html.count('<details class="ri-history-detail-card">') == 2


def test_build_renders_a_detail_card_per_history_entry_when_history_exists():
    ui = RiskIntelligenceUI(screen=_make_available_screen())

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    combined = "\n".join(html_values)
    assert combined.count('<details class="ri-history-detail-card">') == len(ui._screen.history)


def test_build_renders_no_detail_cards_when_history_is_empty():
    empty_screen = RiskScreen(current=_make_snapshot())
    ui = RiskIntelligenceUI(screen=empty_screen)

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    combined = "\n".join(html_values)
    assert '<details class="ri-history-detail-card">' not in combined


def test_page_header_title_carries_the_aara_eyebrow_class():
    ui = RiskIntelligenceUI()

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    combined = "\n".join(html_values)
    assert '<h2 class="aara-eyebrow">Risk Intelligence</h2>' in combined


def test_gradio_view_module_defines_no_illustrative_data_disclosure():
    """Guardrail: the illustrative-data disclosure constants and their
    "Illustrative Data" text must not exist in the production view
    module."""
    import applications.trading_intelligence.ui.risk_intelligence.gradio_view as view_module

    for removed in ("_ILLUSTRATIVE_DATA_HTML", "_ILLUSTRATIVE_DATA_TITLE", "_ILLUSTRATIVE_DATA_BODY"):
        assert not hasattr(view_module, removed)
    source = pathlib.Path(view_module.__file__).read_text(encoding="utf-8")
    assert "Illustrative Data" not in source
    assert "build_mock_screen" not in source
    import_lines = [
        line for line in source.splitlines()
        if line.strip().startswith(("import ", "from ")) and "mock_data" in line
    ]
    assert import_lines == []


# --- Accessibility & Keyboard Interaction Parity pass -----------------


def test_theme_defines_a_focus_visible_rule_for_both_summary_disclosures():
    """Local, RI-scoped :focus-visible rule (not a page-wide
    `.gradio-container summary:focus-visible` selector -- see theme.py's
    own comment on why a page-wide rule would leak onto Decision
    Center's own elements), using an existing RI token rather than a
    new color.

    Regression lock (defect found in manual verification): the outline
    declaration must carry !important, or it is silently inert in the
    composed app -- bootstrap.py merges every screen's CSS into one
    stylesheet, and Decision Center's own `.gradio-container
    summary:focus-visible` rule already ships with !important, which
    always wins over a non-!important declaration regardless of
    selector specificity or source order."""
    assert ".ri-trigger-reason summary:focus-visible" in CSS
    assert ".ri-history-detail-card summary:focus-visible" in CSS
    assert "outline: 2px solid var(--ri-color-navy) !important;" in CSS


def test_theme_defines_a_local_sr_only_utility_class():
    """Local copy of the visually-hidden-but-accessible technique
    (not decision_center's .aara-sr-only), backing the live-region
    announcer element."""
    assert ".ri-sr-only {" in CSS
    assert "clip: rect(0, 0, 0, 0);" in CSS


def test_live_announcer_elem_id_does_not_collide_with_decision_center():
    """bootstrap.py composes every screen's Blocks into one document at
    once -- a shared elem_id would mean document.getElementById only
    ever finds one of the two elements."""
    assert _LIVE_ANNOUNCER_ELEM_ID == "ri-live-announcer"
    assert _LIVE_ANNOUNCER_ELEM_ID != "aara-live-announcer"


def test_build_wires_the_live_region_setup_script_into_blocks_head():
    ui = RiskIntelligenceUI()

    demo = ui.build()

    assert _LIVE_REGION_SETUP_JS in demo.head
    assert _LIVE_ANNOUNCER_ELEM_ID in demo.head


def test_build_renders_a_live_announcer_html_block_with_expected_hooks():
    ui = RiskIntelligenceUI()

    demo = ui.build()

    live_blocks = [
        block for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and getattr(block, "elem_id", None) == _LIVE_ANNOUNCER_ELEM_ID
    ]
    assert len(live_blocks) == 1
    assert "ri-sr-only" in (live_blocks[0].elem_classes or [])
    assert live_blocks[0].value == ""


def test_announce_current_state_describes_the_screens_actual_state():
    snapshot = _make_snapshot(state="WARNING")
    ui = RiskIntelligenceUI(screen=RiskScreen(current=snapshot))

    announcement = ui._announce_current_state()

    assert announcement == "Risk Intelligence loaded. Current risk state: WARNING."


def test_announce_current_state_reflects_every_state():
    for state in ("NORMAL", "WARNING", "DEFENSIVE"):
        ui = RiskIntelligenceUI(screen=RiskScreen(current=_make_snapshot(state=state)))

        announcement = ui._announce_current_state()

        assert state in announcement


def test_announce_current_state_does_not_claim_the_data_is_live():
    ui = RiskIntelligenceUI()

    announcement = ui._announce_current_state()

    for forbidden in ("live", "real-time", "real time"):
        assert forbidden not in announcement.lower()


# --- Slice B: render-time refresh pattern + optional-field rendering -------


class _CountingProvider:
    """A screen_provider that records how many times it was invoked."""

    def __init__(self, screen):
        self._screen = screen
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self._screen


def _partial_snapshot(**overrides):
    """A RiskSnapshot with only the two fields the operational risk_state
    table can supply -- state + as_of -- everything else left None."""
    defaults = dict(state="NORMAL", as_of="2026-08-20 10:03 CDT")
    defaults.update(overrides)
    return RiskSnapshot(**defaults)


def _bound_render_functions(demo, ui):
    return [
        bf for bf in demo.fns.values()
        if getattr(bf.fn, "__func__", None) is RiskIntelligenceUI._render
        and getattr(bf.fn, "__self__", None) is ui
    ]


def test_build_renders_exactly_one_refresh_button_with_the_shared_class():
    demo = RiskIntelligenceUI().build()

    buttons = [
        block for block in demo.blocks.values()
        if isinstance(block, gr.Button) and "aara-refresh-button" in (block.elem_classes or [])
    ]
    assert len(buttons) == 1


def test_disable_refresh_button_returns_a_non_interactive_update():
    update = RiskIntelligenceUI._disable_refresh_button()

    assert update.get("interactive") is False


def test_enable_refresh_button_returns_an_interactive_update():
    update = RiskIntelligenceUI._enable_refresh_button()

    assert update.get("interactive") is True


def test_refresh_button_click_is_wired_disable_then_render_then_enable():
    ui = RiskIntelligenceUI()
    demo = ui.build()

    deps = demo.config["dependencies"]
    disable_dep = next(
        dep for dep in deps
        if demo.fns[dep["id"]].fn is RiskIntelligenceUI._disable_refresh_button
    )
    enable_dep = next(
        dep for dep in deps
        if demo.fns[dep["id"]].fn is RiskIntelligenceUI._enable_refresh_button
    )
    render_dep = next(
        dep for dep in deps if dep.get("trigger_after") == disable_dep["id"]
    )

    assert demo.fns[render_dep["id"]].fn.__func__ is RiskIntelligenceUI._render
    assert enable_dep["trigger_after"] == render_dep["id"]


def test_demo_load_and_the_refresh_chain_both_invoke_render():
    ui = RiskIntelligenceUI()
    demo = ui.build()

    # one _render for demo.load(), one for the Refresh .then() chain
    assert len(_bound_render_functions(demo, ui)) == 2


def test_provider_is_called_once_at_construction_and_again_on_render():
    provider = _CountingProvider(RiskScreen())
    ui = RiskIntelligenceUI(screen_provider=provider)

    assert provider.calls == 1

    ui._render()

    assert provider.calls == 2


def test_provider_is_reinvoked_on_every_render_call():
    provider = _CountingProvider(RiskScreen())
    ui = RiskIntelligenceUI(screen_provider=provider)

    ui._render()
    ui._render()
    ui._render()

    assert provider.calls == 4  # 1 at construction + 3 renders


def test_render_returns_one_update_per_dynamic_output():
    ui = RiskIntelligenceUI(screen=_make_available_screen())

    result = ui._render()

    assert isinstance(result, tuple)
    assert len(result) == 11
    assert all(isinstance(update, dict) for update in result)


def test_render_first_update_is_the_as_of_indicator():
    ui = RiskIntelligenceUI()

    result = ui._render()

    assert _AS_OF_PREFIX in result[0]["value"]


def test_format_as_of_html_uses_the_america_chicago_convention():
    from datetime import datetime, timezone

    moment = datetime(2026, 8, 20, 20, 3, tzinfo=timezone.utc)  # 15:03 CDT

    rendered = _format_as_of_html(moment)

    assert _AS_OF_PREFIX in rendered
    assert "2026-08-20 15:03 CDT" in rendered


def test_build_shows_an_as_of_indicator_component():
    demo = RiskIntelligenceUI().build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert any(_AS_OF_PREFIX in value for value in html_values)


def test_render_collapses_to_the_unavailable_state_when_provider_returns_unavailable():
    provider = _CountingProvider(RiskScreen())
    ui = RiskIntelligenceUI(screen_provider=provider)

    result = ui._render()
    combined = "\n".join(update.get("value") or "" for update in result if isinstance(update.get("value"), str))

    assert "Risk Intelligence data is currently unavailable." in combined
    # unavailable message visible, current-state / history hidden
    unavailable_update = result[2]
    assert unavailable_update.get("visible") is True
    for hidden in result[3:6]:  # observed note, current label, current state
        assert hidden.get("visible") is False


def test_render_never_falls_back_to_mock_or_illustrative_data():
    provider = _CountingProvider(RiskScreen())
    ui = RiskIntelligenceUI(screen_provider=provider)

    result = ui._render()
    combined = "\n".join(update.get("value") or "" for update in result if isinstance(update.get("value"), str))

    for fabricated in (
        "ri-state-badge", "state-normal", "state-warning", "state-defensive",
        "ri-sizing-metrics", "ri-current-state", "ri-history-detail-card",
        "Illustrative Data",
    ):
        assert fabricated not in combined


def test_current_state_html_states_reason_is_not_recorded_when_missing():
    current_html = RiskIntelligenceUI._format_current_state_html(_partial_snapshot())

    assert _TRIGGER_REASON_UNAVAILABLE_HTML in current_html
    assert "not recorded in this data source" in current_html
    assert '<details class="ri-trigger-reason">' not in current_html


def test_current_state_html_states_sizing_is_not_recorded_when_missing():
    current_html = RiskIntelligenceUI._format_current_state_html(_partial_snapshot())

    assert _SIZING_UNAVAILABLE_HTML in current_html
    assert "ri-sizing-metrics" not in current_html
    assert "Recommended Sizing" not in current_html


def test_current_state_html_computes_no_sizing_gap_when_values_missing():
    current_html = RiskIntelligenceUI._format_current_state_html(_partial_snapshot())

    assert "Gap" not in current_html
    assert _partial_snapshot().sizing_gap_pct is None


def test_current_state_html_still_shows_the_real_badge_and_as_of_when_partial():
    current_html = RiskIntelligenceUI._format_current_state_html(
        _partial_snapshot(state="WARNING", as_of="2026-08-20 10:03 CDT")
    )

    assert "state-warning" in current_html
    assert "WARNING" in current_html
    assert "as of 2026-08-20 10:03 CDT" in current_html


def test_partial_snapshot_screen_shows_no_history_table_or_detail_cards():
    ui = RiskIntelligenceUI(screen=RiskScreen(current=_partial_snapshot()))

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    combined = "\n".join(value for value in html_values if value)
    assert all(df.visible is False for df in dataframes)
    assert '<details class="ri-history-detail-card">' not in combined
    assert "No risk evaluations recorded yet." in combined


def test_build_renders_the_observed_governor_classification_disclosure_when_available():
    ui = RiskIntelligenceUI(screen=RiskScreen(current=_partial_snapshot()))

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert _OBSERVED_CLASSIFICATION_HTML in html_values


def test_observed_classification_wording_does_not_imply_enforcement():
    text = _OBSERVED_CLASSIFICATION_HTML.lower()

    assert "observed governor classification" in text
    assert "not a confirmation that the system enforced" in text
    # never a bare positive enforcement claim
    assert "the system enforced this state." not in text


def test_observed_disclosure_is_hidden_in_the_default_unavailable_build():
    demo = RiskIntelligenceUI().build()

    observed_blocks = [
        block for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and block.value == _OBSERVED_CLASSIFICATION_HTML
    ]
    assert len(observed_blocks) == 1
    assert observed_blocks[0].visible is False


def test_existing_current_state_and_history_rendering_is_unaffected():
    """Regression lock: the accessibility pass must not change the
    visible current-state or history-detail markup this unit did not
    touch."""
    snapshot = _make_snapshot(
        state="WARNING",
        trigger_reason="Portfolio drawdown -11.4% -- approaching daily loss limit.",
        recommended_sizing_pct=75.0,
        actual_sizing_pct=70.0,
        as_of="2026-08-17 09:15 UTC",
    )

    current_html = RiskIntelligenceUI._format_current_state_html(snapshot)

    assert current_html == (
        '<div class="ri-current-state">'
        '<span class="ri-state-badge state-warning">WARNING</span>'
        '<span style="margin-left:8px;color:var(--ri-color-text-secondary);'
        'font-size:12px;">as of 2026-08-17 09:15 UTC</span>'
        '<details class="ri-trigger-reason">'
        "<summary>Trigger Reason</summary>"
        '<div class="ri-trigger-body">Portfolio drawdown -11.4% -- '
        "approaching daily loss limit.</div>"
        "</details>"
        '<div class="ri-sizing-metrics">'
        '<div class="ri-metric">'
        '<span class="ri-metric-label">Recommended Sizing</span>'
        '<span class="ri-metric-value">75%</span>'
        "</div>"
        '<div class="ri-metric">'
        '<span class="ri-metric-label">Actual Sizing</span>'
        '<span class="ri-metric-value">70%</span>'
        "</div>"
        '<div class="ri-metric">'
        '<span class="ri-metric-label">Gap</span>'
        '<span class="ri-metric-value ri-gap-nonzero">+5%</span>'
        "</div>"
        "</div>"
        "</div>"
    )
