"""Gradio shell for Morning Brief -- screen shell only.

Self-contained: does not import ui/decision_center/, ui/portfolio_intelligence/,
or ui/risk_intelligence/ (no cross-package import of any kind). Renders
mock_data.py's MorningBriefScreen only -- no controller, no service, no
sentinel_engine/bot/dashboard import, and no MorningBriefQuery of any kind
(see screen.py's and mock_data.py's module docstrings for why). Wired into
bootstrap.py as the 4th Trading Intelligence tab.

Unlike ui/portfolio_intelligence/gradio_view.py and
ui/risk_intelligence/gradio_view.py, this screen renders no "Illustrative
Data" disclosure banner -- there is no illustrative data here to disclose.
Every section instead shows its own honest, fixed unavailable message, per
docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md Section 2's
"Required information" for Morning Brief and Section 7's "evidence over
emotion" UX principle: mark unbuilt functionality as unavailable rather
than invent content to fill it.

AARA shell consistency pass: renders the same AARA logo header + inter-
screen nav Decision Center/Portfolio Intelligence/Risk Intelligence show,
via `ui/shell.py` (a sibling of all four screen packages, not owned by any
one of them).
"""
import html

import gradio as gr

from applications.trading_intelligence.ui.morning_brief.mock_data import build_mock_screen
from applications.trading_intelligence.ui.morning_brief.screen import (
    MorningBriefScreen,
    MorningBriefSection,
)
from applications.trading_intelligence.ui.morning_brief.theme import CSS
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html

_PAGE_HEADER_HTML = (
    '<div class="mb-page-header">'
    "<h2>Morning Brief</h2>"
    '<div class="mb-subtitle">Single-glance daily summary before market open</div>'
    "</div>"
)


class MorningBriefUI:
    def __init__(self, screen: MorningBriefScreen = None):
        self._screen = screen if screen is not None else build_mock_screen()

    def build(self) -> gr.Blocks:
        with gr.Blocks(
            title="AARA Trading Intelligence — Morning Brief", css=CSS,
        ) as demo:
            gr.HTML(SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(build_shell_nav_html("Morning Brief"), elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML)

            for section in self._screen.sections:
                gr.HTML(self._format_section_label_html(section))
                gr.HTML(self._format_unavailable_message_html(section))

        return demo

    @staticmethod
    def _format_section_label_html(section: MorningBriefSection) -> str:
        return f'<div class="mb-section-label">{html.escape(section.title)}</div>'

    @staticmethod
    def _format_unavailable_message_html(section: MorningBriefSection) -> str:
        return (
            '<div class="mb-unavailable-message">'
            f'{html.escape(section.unavailable_message)}'
            "</div>"
        )
