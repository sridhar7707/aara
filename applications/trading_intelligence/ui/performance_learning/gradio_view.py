"""Gradio shell for Performance & Learning -- screen shell only.

Self-contained: does not import ui/decision_center/, ui/portfolio_intelligence/,
ui/risk_intelligence/, ui/morning_brief/, or ui/settings/ (no cross-package
import of any kind). Renders mock_data.py's PerformanceLearningScreen
only -- no controller, no service, no sentinel_engine/bot/dashboard
import, and no outcome/attribution/calibration contract of any kind (see
screen.py's and mock_data.py's module docstrings for why). Wired into
bootstrap.py as the 5th Trading Intelligence tab (Performance & Learning
precedes Settings in the frozen six-screen order).

Like ui/morning_brief/gradio_view.py and ui/settings/gradio_view.py, and
unlike ui/portfolio_intelligence/gradio_view.py and
ui/risk_intelligence/gradio_view.py, this screen renders no "Illustrative
Data" disclosure banner -- there is no illustrative data here to disclose,
and inventing any could be read as real trading performance. Every area
instead shows its own honest, fixed unavailable message, per
docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md Section 2's
"Required information" for Performance & Learning and Section 7's
"evidence over emotion" UX principle: mark unbuilt functionality as
unavailable rather than invent content to fill it.

AARA shell consistency pass: renders the same AARA logo header + inter-
screen nav Decision Center/Portfolio Intelligence/Risk Intelligence/
Morning Brief/Settings show, via `ui/shell.py` (a sibling of all six
screen packages, not owned by any one of them).
"""
import html

import gradio as gr

from applications.trading_intelligence.ui.performance_learning.mock_data import build_mock_screen
from applications.trading_intelligence.ui.performance_learning.screen import (
    PerformanceLearningScreen,
    PerformanceLearningSection,
)
from applications.trading_intelligence.ui.performance_learning.theme import CSS
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html

_PAGE_HEADER_HTML = (
    '<div class="pl-page-header">'
    "<h2>Performance & Learning</h2>"
    '<div class="pl-subtitle">Outcome history, attribution, and model confidence calibration</div>'
    "</div>"
)


class PerformanceLearningUI:
    def __init__(self, screen: PerformanceLearningScreen = None):
        self._screen = screen if screen is not None else build_mock_screen()

    def build(self) -> gr.Blocks:
        with gr.Blocks(
            title="AARA Trading Intelligence — Performance & Learning", css=CSS,
        ) as demo:
            gr.HTML(SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(build_shell_nav_html("Performance & Learning"), elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML)

            for section in self._screen.sections:
                gr.HTML(self._format_section_label_html(section))
                gr.HTML(self._format_unavailable_message_html(section))

        return demo

    @staticmethod
    def _format_section_label_html(section: PerformanceLearningSection) -> str:
        return f'<div class="pl-section-label">{html.escape(section.title)}</div>'

    @staticmethod
    def _format_unavailable_message_html(section: PerformanceLearningSection) -> str:
        return (
            '<div class="pl-unavailable-message">'
            f'{html.escape(section.unavailable_message)}'
            "</div>"
        )
