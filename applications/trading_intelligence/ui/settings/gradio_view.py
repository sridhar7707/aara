"""Gradio shell for Settings -- screen shell only.

Self-contained: does not import ui/decision_center/, ui/portfolio_intelligence/,
ui/risk_intelligence/, or ui/morning_brief/ (no cross-package import of any
kind). Renders mock_data.py's SettingsScreen only -- no controller, no
service, no sentinel_engine/bot/dashboard import, and no persistence/
configuration contract of any kind (see screen.py's and mock_data.py's
module docstrings for why). Wired into bootstrap.py as the 5th Trading
Intelligence tab.

Like ui/morning_brief/gradio_view.py, and unlike
ui/portfolio_intelligence/gradio_view.py and
ui/risk_intelligence/gradio_view.py, this screen renders no "Illustrative
Data" disclosure banner -- there is no illustrative data here to disclose,
and inventing any could be mistaken for real user settings. An area with
no preference_fields (Thresholds, always) shows its own honest, fixed
unavailable message, per docs/products/AARA_TRADING_INTELLIGENCE_UI_
SPECIFICATION.md Section 2's "Required information" for Settings and
Section 7's "evidence over emotion" UX principle: mark unbuilt
functionality as unavailable rather than invent content to fill it. An
area with preference_fields (User Settings, Notification Preferences)
instead renders its allow-listed controls -- non-interactive, since
nothing consumes their value -- plus a disclosure that they are not
currently configurable and cannot be saved. See screen.py's module
docstring.

AARA shell consistency pass: renders the same AARA logo header + inter-
screen nav Decision Center/Portfolio Intelligence/Risk Intelligence/
Morning Brief show, via `ui/shell.py` (a sibling of all five screen
packages, not owned by any one of them).
"""
import html

import gradio as gr

from applications.trading_intelligence.ui.settings.mock_data import build_mock_screen
from applications.trading_intelligence.ui.settings.screen import SettingsArea, SettingsScreen
from applications.trading_intelligence.ui.settings.theme import CSS
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html

_PAGE_HEADER_HTML = (
    '<div class="st-page-header">'
    "<h2>Settings</h2>"
    '<div class="st-subtitle">User settings, thresholds, and notification preferences</div>'
    "</div>"
)


class SettingsUI:
    def __init__(self, screen: SettingsScreen = None):
        self._screen = screen if screen is not None else build_mock_screen()

    def build(self) -> gr.Blocks:
        with gr.Blocks(
            title="AARA Trading Intelligence — Settings", css=CSS,
        ) as demo:
            gr.HTML(SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(build_shell_nav_html("Settings"), elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML)

            for area in self._screen.areas:
                gr.HTML(self._format_section_label_html(area))
                if area.is_available:
                    gr.HTML(self._format_session_only_notice_html(area))
                    for pref_field in area.preference_fields:
                        # V3 fix: no .change() handler is wired and nothing
                        # consumes this value, so the control is rendered
                        # non-interactive -- a truthful "not configurable
                        # yet" state rather than a control that silently
                        # does nothing. The session-only notice above says
                        # so in words.
                        gr.Radio(
                            choices=list(pref_field.options),
                            value=pref_field.default,
                            label=pref_field.label,
                            interactive=False,
                            elem_classes=["st-preference-control"],
                        )
                else:
                    gr.HTML(self._format_unavailable_message_html(area))

        return demo

    @staticmethod
    def _format_section_label_html(area: SettingsArea) -> str:
        return f'<div class="st-section-label">{html.escape(area.title)}</div>'

    @staticmethod
    def _format_unavailable_message_html(area: SettingsArea) -> str:
        return (
            '<div class="st-unavailable-message">'
            f'{html.escape(area.unavailable_message)}'
            "</div>"
        )

    @staticmethod
    def _format_session_only_notice_html(area: SettingsArea) -> str:
        return (
            '<div class="st-session-only-notice">'
            f'{html.escape(area.unavailable_message)}'
            "</div>"
        )
