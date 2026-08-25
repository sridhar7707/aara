import gradio as gr

from applications.trading_intelligence.ui.morning_brief.gradio_view import MorningBriefUI
from applications.trading_intelligence.ui.morning_brief.mock_data import build_mock_screen
from applications.trading_intelligence.ui.morning_brief.screen import (
    CANDIDATE_SCREENING_SUMMARY_TITLE,
    MARKET_MOOD_REGIME_TITLE,
    OVERNIGHT_HOLDINGS_NEWS_TITLE,
    PORTFOLIO_SNAPSHOT_TITLE,
)
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html


def _html_values(demo):
    return [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]


def test_ui_can_be_constructed_with_default_mock_screen():
    ui = MorningBriefUI()

    assert ui._screen == build_mock_screen()


def test_build_returns_a_gradio_blocks_instance():
    ui = MorningBriefUI()

    demo = ui.build()

    assert isinstance(demo, gr.Blocks)


def test_shell_header_and_nav_are_present_in_the_built_layout():
    ui = MorningBriefUI()

    demo = ui.build()

    html_values = _html_values(demo)
    assert SHELL_IDENTITY_HTML in html_values
    assert build_shell_nav_html("Morning Brief") in html_values


def test_shell_header_and_nav_blocks_carry_the_expected_elem_classes():
    ui = MorningBriefUI()

    demo = ui.build()

    html_blocks = [block for block in demo.blocks.values() if isinstance(block, gr.HTML)]
    assert any("aara-shell-header" in (block.elem_classes or []) for block in html_blocks)
    assert any("aara-shell-nav" in (block.elem_classes or []) for block in html_blocks)


def test_all_four_frozen_section_titles_render():
    ui = MorningBriefUI()

    demo = ui.build()

    html_values = _html_values(demo)
    combined = "\n".join(html_values)
    assert PORTFOLIO_SNAPSHOT_TITLE in combined
    assert MARKET_MOOD_REGIME_TITLE in combined
    assert CANDIDATE_SCREENING_SUMMARY_TITLE in combined
    assert OVERNIGHT_HOLDINGS_NEWS_TITLE in combined


def test_all_four_sections_render_their_own_unavailable_message():
    screen = build_mock_screen()
    ui = MorningBriefUI(screen=screen)

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    for section in screen.sections:
        assert section.unavailable_message in combined


def test_no_gradio_dataframe_is_rendered():
    """Unlike Portfolio/Risk Intelligence (which render a gr.Dataframe once
    holdings/history exist), Morning Brief has no populated-data branch at
    all -- there must never be a table to render."""
    ui = MorningBriefUI()

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    assert dataframes == []


def test_no_illustrative_data_disclosure_is_rendered():
    """Portfolio/Risk Intelligence show an "Illustrative Data" banner for
    their own fabricated numbers -- Morning Brief must not, since it
    fabricates nothing."""
    ui = MorningBriefUI()

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert "Illustrative Data" not in combined
