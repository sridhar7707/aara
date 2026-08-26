import gradio as gr

from applications.trading_intelligence.ui.settings.gradio_view import SettingsUI
from applications.trading_intelligence.ui.settings.mock_data import build_mock_screen
from applications.trading_intelligence.ui.settings.screen import (
    NOTIFICATION_PREFERENCES_TITLE,
    THRESHOLDS_TITLE,
    USER_SETTINGS_TITLE,
)
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html


def _html_values(demo):
    return [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]


def test_ui_can_be_constructed_with_default_mock_screen():
    ui = SettingsUI()

    assert ui._screen == build_mock_screen()


def test_build_returns_a_gradio_blocks_instance():
    ui = SettingsUI()

    demo = ui.build()

    assert isinstance(demo, gr.Blocks)


def test_shell_header_and_nav_are_present_in_the_built_layout():
    ui = SettingsUI()

    demo = ui.build()

    html_values = _html_values(demo)
    assert SHELL_IDENTITY_HTML in html_values
    assert build_shell_nav_html("Settings") in html_values


def test_shell_header_and_nav_blocks_carry_the_expected_elem_classes():
    ui = SettingsUI()

    demo = ui.build()

    html_blocks = [block for block in demo.blocks.values() if isinstance(block, gr.HTML)]
    assert any("aara-shell-header" in (block.elem_classes or []) for block in html_blocks)
    assert any("aara-shell-nav" in (block.elem_classes or []) for block in html_blocks)


def test_all_three_frozen_area_titles_render():
    ui = SettingsUI()

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert USER_SETTINGS_TITLE in combined
    assert THRESHOLDS_TITLE in combined
    assert NOTIFICATION_PREFERENCES_TITLE in combined


def test_all_three_areas_render_their_own_unavailable_message():
    screen = build_mock_screen()
    ui = SettingsUI(screen=screen)

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    for area in screen.areas:
        assert area.unavailable_message in combined


def test_no_gradio_dataframe_is_rendered():
    """Unlike Portfolio/Risk Intelligence (which render a gr.Dataframe once
    holdings/history exist), Settings has no populated-data branch at all --
    there must never be a table to render."""
    ui = SettingsUI()

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    assert dataframes == []


def test_no_illustrative_data_disclosure_is_rendered():
    """Portfolio/Risk Intelligence show an "Illustrative Data" banner for
    their own fabricated numbers -- Settings must not, since it fabricates
    nothing (rule 6: no mock values that could be mistaken for real user
    settings)."""
    ui = SettingsUI()

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert "Illustrative Data" not in combined


def test_thresholds_still_renders_only_its_unavailable_message_no_control():
    screen = build_mock_screen()
    ui = SettingsUI(screen=screen)

    demo = ui.build()

    radios = [block for block in demo.blocks.values() if isinstance(block, gr.Radio)]
    radio_labels = {radio.label for radio in radios}
    assert "Display Theme" in radio_labels
    assert "Show In-App Notifications" in radio_labels
    # Thresholds has no preference_fields, so it contributes no gr.Radio.
    assert len(radios) == 2


def test_user_settings_and_notification_preferences_render_their_allow_listed_control():
    screen = build_mock_screen()
    ui = SettingsUI(screen=screen)

    demo = ui.build()

    radios = {radio.label: radio for radio in demo.blocks.values() if isinstance(radio, gr.Radio)}
    assert radios["Display Theme"].choices == [("Light", "Light"), ("Dark", "Dark")]
    assert radios["Display Theme"].value == "Light"
    assert radios["Show In-App Notifications"].choices == [("On", "On"), ("Off", "Off")]
    assert radios["Show In-App Notifications"].value == "On"


def test_available_areas_render_a_session_only_notice_not_an_unavailable_message_div():
    ui = SettingsUI()

    demo = ui.build()

    html_blocks = [block for block in demo.blocks.values() if isinstance(block, gr.HTML)]
    session_only_html = [
        block.value for block in html_blocks
        if isinstance(block.value, str) and "st-session-only-notice" in block.value
    ]
    assert len(session_only_html) == 2
    combined = "\n".join(session_only_html)
    assert "not saved" in combined.lower()


def test_no_save_or_submit_control_is_rendered():
    """These preferences are UI-local for the current session only -- there
    must be no Button implying a save/submit action, and no persistence
    call of any kind wired to the Radio controls."""
    ui = SettingsUI()

    demo = ui.build()

    buttons = [block for block in demo.blocks.values() if isinstance(block, gr.Button)]
    assert buttons == []
