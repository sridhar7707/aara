import gradio as gr

from applications.trading_intelligence.ui.risk_intelligence.gradio_view import (
    _ILLUSTRATIVE_DATA_BODY,
    _ILLUSTRATIVE_DATA_HTML,
    _ILLUSTRATIVE_DATA_TITLE,
    RiskIntelligenceUI,
)
from applications.trading_intelligence.ui.risk_intelligence.screen import (
    RiskHistoryEntry,
    RiskScreen,
    RiskSnapshot,
)


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


def test_ui_can_be_constructed_with_default_mock_screen():
    ui = RiskIntelligenceUI()

    assert not ui._screen.is_empty


def test_build_returns_a_gradio_blocks_instance():
    ui = RiskIntelligenceUI()

    demo = ui.build()

    assert isinstance(demo, gr.Blocks)


def test_illustrative_data_disclosure_is_the_exact_fixed_text():
    assert _ILLUSTRATIVE_DATA_TITLE == "Illustrative Data"
    assert _ILLUSTRATIVE_DATA_HTML == (
        '<div class="ri-disclosure">'
        f'<div class="ri-disclosure-title">{_ILLUSTRATIVE_DATA_TITLE}</div>'
        f'<div class="ri-disclosure-body">{_ILLUSTRATIVE_DATA_BODY}</div>'
        "</div>"
    )


def test_illustrative_data_disclosure_block_is_present_in_the_built_layout():
    ui = RiskIntelligenceUI()

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert _ILLUSTRATIVE_DATA_HTML in html_values


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
    assert dataframes == []
    assert any("No risk evaluations recorded yet." in value for value in html_values)


def test_build_renders_a_dataframe_when_history_exists():
    ui = RiskIntelligenceUI()

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    assert len(dataframes) == 1
    assert "ri-history-table" in dataframes[0].elem_classes
