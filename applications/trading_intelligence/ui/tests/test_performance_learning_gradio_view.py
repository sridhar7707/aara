import gradio as gr

from applications.platform.integrations import IntegrationHealth
from applications.trading_intelligence.projections.calibration_band import CalibrationBand
from applications.trading_intelligence.ui.performance_learning.gradio_view import (
    PerformanceLearningUI,
)
from applications.trading_intelligence.ui.performance_learning.mock_data import (
    build_calibration_preview_screen,
    build_mock_screen,
)
from applications.trading_intelligence.ui.performance_learning.screen import (
    ATTRIBUTION_BREAKDOWN_TITLE,
    CALIBRATION_CONTENT_HEADING,
    CALIBRATION_MIN_OUTCOMES,
    MODEL_CONFIDENCE_CALIBRATION_TITLE,
    OUTCOME_HISTORY_TITLE,
    PerformanceLearningScreen,
    PerformanceLearningSection,
)
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html


def _html_values(demo):
    return [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]


def _visible_html(demo):
    return "\n".join(
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML)
        and isinstance(getattr(block, "value", None), str)
        and block.visible
    )


_CAL_PROVIDER = "trades_db_outcomes"


def _calibration_screen(bands, *, health=None):
    base = build_mock_screen()
    return PerformanceLearningScreen(
        outcome_history=base.outcome_history,
        attribution_breakdown=base.attribution_breakdown,
        model_confidence_calibration=base.model_confidence_calibration,
        calibration_health=health or IntegrationHealth.healthy(_CAL_PROVIDER),
        calibration_bands=tuple(bands),
    )


def _band(label, wins, losses):
    return CalibrationBand(label=label, wins=wins, losses=losses)


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


# --- Sprint 4 #1: Model Confidence Calibration render ---------------------


def test_calibration_section_still_uses_the_frozen_ia_label():
    demo = PerformanceLearningUI().build()

    assert MODEL_CONFIDENCE_CALIBRATION_TITLE in "\n".join(_html_values(demo))


def test_calibration_unavailable_by_default_shows_section_message_hides_table():
    demo = PerformanceLearningUI().build()

    visible = _visible_html(demo)
    assert build_mock_screen().model_confidence_calibration.unavailable_message in visible
    assert CALIBRATION_CONTENT_HEADING not in visible


def test_calibration_renders_historical_outcome_heading_when_enough_data():
    demo = PerformanceLearningUI(screen=build_calibration_preview_screen()).build()

    visible = _visible_html(demo)
    assert CALIBRATION_CONTENT_HEADING in visible
    assert "predictive accuracy" not in visible.lower()
    assert "probability calibration" not in visible.lower()
    assert "guaranteed" not in visible.lower()
    assert "certainty" not in visible.lower()


def test_calibration_table_lists_every_band_with_counts_and_win_rate():
    demo = PerformanceLearningUI(screen=build_calibration_preview_screen()).build()

    visible = _visible_html(demo)
    for label in ("0.50-0.55", "0.55-0.60", "0.60-0.65", "0.65-1.00"):
        assert label in visible
    # 0.60-0.65 preview band is 9 wins / 6 losses -> 60%
    assert "60%" in visible
    # the empty 0.55-0.60 band shows a zero count and no fabricated rate
    assert ">0<" in visible


def test_calibration_small_n_shows_notice_not_table():
    screen = _calibration_screen([_band("0.60-0.65", 2, 1)])
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    assert str(CALIBRATION_MIN_OUTCOMES) in visible
    assert "Only 3 closed BUY outcomes" in visible
    assert CALIBRATION_CONTENT_HEADING not in visible


def test_calibration_empty_state_message_when_healthy_with_no_qualifying_outcomes():
    screen = _calibration_screen([_band("0.60-0.65", 0, 0)])
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    assert "No closed BUY decisions with a recorded ensemble score" in visible
    assert CALIBRATION_CONTENT_HEADING not in visible


def test_calibration_non_healthy_read_uses_shared_unavailable_phrase():
    screen = _calibration_screen(
        [_band("0.60-0.65", 5, 5)],
        health=IntegrationHealth.unavailable(_CAL_PROVIDER, detail="no snapshot"),
    )
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    assert "Data unavailable" in visible
    assert CALIBRATION_CONTENT_HEADING not in visible


def test_calibration_table_html_escapes_interpolated_values():
    html = PerformanceLearningUI._format_calibration_table_html(
        _calibration_screen([_band("<script>", 1, 0)] + [_band("x", 0, 0)] * 3)
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
