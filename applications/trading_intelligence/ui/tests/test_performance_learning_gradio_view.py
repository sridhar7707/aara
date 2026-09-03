import gradio as gr

from applications.trading_intelligence.ui.performance_learning.gradio_view import (
    PerformanceLearningUI,
)
from applications.trading_intelligence.ui.performance_learning.mock_data import build_mock_screen
from applications.trading_intelligence.ui.performance_learning.screen import (
    ATTRIBUTION_BREAKDOWN_TITLE,
    MODEL_CONFIDENCE_CALIBRATION_TITLE,
    OUTCOME_HISTORY_TITLE,
)
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html


def _html_values(demo):
    return [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]


def test_ui_can_be_constructed_with_default_mock_screen():
    ui = PerformanceLearningUI()

    assert ui._screen == build_mock_screen()


def test_build_returns_a_gradio_blocks_instance():
    ui = PerformanceLearningUI()

    demo = ui.build()

    assert isinstance(demo, gr.Blocks)


def test_shell_header_and_nav_are_present_in_the_built_layout():
    ui = PerformanceLearningUI()

    demo = ui.build()

    html_values = _html_values(demo)
    assert SHELL_IDENTITY_HTML in html_values
    assert build_shell_nav_html("Performance & Learning") in html_values


def test_shell_header_and_nav_blocks_carry_the_expected_elem_classes():
    ui = PerformanceLearningUI()

    demo = ui.build()

    html_blocks = [block for block in demo.blocks.values() if isinstance(block, gr.HTML)]
    assert any("aara-shell-header" in (block.elem_classes or []) for block in html_blocks)
    assert any("aara-shell-nav" in (block.elem_classes or []) for block in html_blocks)


def test_all_three_frozen_section_titles_render():
    ui = PerformanceLearningUI()

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert OUTCOME_HISTORY_TITLE in combined
    assert ATTRIBUTION_BREAKDOWN_TITLE in combined
    assert MODEL_CONFIDENCE_CALIBRATION_TITLE in combined


def test_all_three_sections_render_their_own_unavailable_message():
    screen = build_mock_screen()
    ui = PerformanceLearningUI(screen=screen)

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    for section in screen.sections:
        assert section.unavailable_message in combined


def test_outcome_history_dataframe_is_present_but_hidden_when_unavailable():
    """Wave 2B: the Outcome History table is part of the stable component
    tree (like Risk Intelligence's history Dataframe), created once and
    hidden until a HEALTHY read with decisions exists. The no-provider
    default screen is unavailable, so the table must be present and
    `visible is False`."""
    ui = PerformanceLearningUI()

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    assert len(dataframes) == 1
    assert dataframes[0].visible is False
    assert "pl-outcome-table" in (dataframes[0].elem_classes or [])


def test_no_illustrative_data_disclosure_is_rendered():
    """Portfolio/Risk Intelligence show an "Illustrative Data" banner for
    their own fabricated numbers -- Performance & Learning must not, since
    it fabricates nothing (no fake numerical metrics or fake outcomes)."""
    ui = PerformanceLearningUI()

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert "Illustrative Data" not in combined
