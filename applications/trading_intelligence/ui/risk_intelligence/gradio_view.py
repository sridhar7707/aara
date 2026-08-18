"""Gradio shell for Risk Intelligence -- illustrative MVP.

Self-contained: does not import ui/decision_center/ or
ui/portfolio_intelligence/ (no cross-package import of any kind). Renders
mock_data.py's RiskScreen only -- no controller, no service, no
sentinel_engine/bot import. Wired into main.py/bootstrap.py as the 3rd
Trading Intelligence tab.

Keyboard accessibility uses native HTML controls only, no custom JS
bridge: the trigger-reason disclosure is a real <details>/<summary>
element (natively Tab-focusable, Enter/Space-togglable), and the history
table is a gr.Dataframe (Gradio's own native keyboard-navigable table,
same mechanism ui/portfolio_intelligence/gradio_view.py's holdings table
already relies on).

AARA shell consistency pass: renders the same AARA logo header + inter-screen
nav Decision Center shows, via `ui/shell.py` (a sibling of all three screen
packages, not `ui/decision_center/` or `ui/portfolio_intelligence/` -- see
that module's own docstring for why this doesn't violate this package's
self-containment). No new CSS is added here; `.aara-shell-header`/
`.aara-shell-nav`/`.nav-item` and the tokens they use are Decision Center's
theme.py rules, already merged into the composed app's single stylesheet by
`bootstrap.py`.
"""
import html
from typing import List, Tuple

import gradio as gr

from applications.trading_intelligence.ui.risk_intelligence.mock_data import build_mock_screen
from applications.trading_intelligence.ui.risk_intelligence.screen import (
    RiskHistoryEntry,
    RiskScreen,
    RiskSnapshot,
)
from applications.trading_intelligence.ui.risk_intelligence.theme import CSS
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html

# gr.Dataframe's row-height-budget kwarg is named `height` on gradio 4.44.1
# but was renamed `max_height` by gradio 5.x -- same compat shim as
# ui/decision_center/gradio_view.py's own _DATAFRAME_HEIGHT_KWARG and
# ui/portfolio_intelligence/gradio_view.py's own copy of it, kept as a
# separate literal here rather than imported, per this package's
# no-coupling scope.
_gr_major = int(gr.__version__.split(".")[0])
_DATAFRAME_HEIGHT_KWARG = "height" if _gr_major < 5 else "max_height"

_HISTORY_HEADERS = ["Timestamp", "State", "Trigger Reason", "Recommended %", "Actual %"]

_STATE_BADGE_CLASSES = {
    "NORMAL": "state-normal",
    "WARNING": "state-warning",
    "DEFENSIVE": "state-defensive",
}

_ILLUSTRATIVE_DATA_TITLE = "Illustrative Data"
_ILLUSTRATIVE_DATA_BODY = (
    "The risk state, trigger reason, and position sizing shown here are "
    "illustrative and are not derived from any real account or governance "
    "decision."
)
_ILLUSTRATIVE_DATA_HTML = (
    '<div class="ri-disclosure">'
    f'<div class="ri-disclosure-title">{html.escape(_ILLUSTRATIVE_DATA_TITLE)}</div>'
    f'<div class="ri-disclosure-body">{html.escape(_ILLUSTRATIVE_DATA_BODY)}</div>'
    "</div>"
)

_PAGE_HEADER_HTML = (
    '<div class="ri-page-header">'
    "<h2>Risk Intelligence</h2>"
    '<div class="ri-subtitle">Current risk-governor state and position sizing</div>'
    "</div>"
)


class RiskIntelligenceUI:
    def __init__(self, screen: RiskScreen = None):
        self._screen = screen if screen is not None else build_mock_screen()

    def build(self) -> gr.Blocks:
        with gr.Blocks(
            title="AARA Trading Intelligence — Risk Intelligence", css=CSS,
        ) as demo:
            gr.HTML(SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(build_shell_nav_html("Risk Intelligence"), elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML)
            gr.HTML(_ILLUSTRATIVE_DATA_HTML)

            gr.HTML('<div class="ri-section-label">Current State</div>')
            gr.HTML(self._format_current_state_html(self._screen.current))

            gr.HTML('<div class="ri-section-label">Recent Risk Evaluations</div>')
            if self._screen.is_empty:
                gr.HTML(self._format_empty_message_html(self._screen))
            else:
                gr.Dataframe(
                    headers=_HISTORY_HEADERS,
                    value=self._format_history_rows(self._screen.history),
                    datatype=["str", "str", "str", "str", "str"],
                    interactive=False,
                    label="Recent Risk Evaluations",
                    show_label=False,
                    elem_classes=["ri-history-table"],
                    **{_DATAFRAME_HEIGHT_KWARG: 320},
                )

        return demo

    @staticmethod
    def _format_state_badge_html(state: str) -> str:
        css_class = _STATE_BADGE_CLASSES.get(state, "state-normal")
        return f'<span class="ri-state-badge {css_class}">{html.escape(state)}</span>'

    @staticmethod
    def _format_current_state_html(current: RiskSnapshot) -> str:
        badge_html = RiskIntelligenceUI._format_state_badge_html(current.state)
        gap = current.sizing_gap_pct
        gap_class = "ri-gap-nonzero" if abs(gap) > 0.01 else ""
        metrics_html = (
            '<div class="ri-sizing-metrics">'
            '<div class="ri-metric">'
            '<span class="ri-metric-label">Recommended Sizing</span>'
            f'<span class="ri-metric-value">{current.recommended_sizing_pct:.0f}%</span>'
            "</div>"
            '<div class="ri-metric">'
            '<span class="ri-metric-label">Actual Sizing</span>'
            f'<span class="ri-metric-value">{current.actual_sizing_pct:.0f}%</span>'
            "</div>"
            '<div class="ri-metric">'
            '<span class="ri-metric-label">Gap</span>'
            f'<span class="ri-metric-value {gap_class}">{gap:+.0f}%</span>'
            "</div>"
            "</div>"
        )
        return (
            '<div class="ri-current-state">'
            f'{badge_html}'
            f'<span style="margin-left:8px;color:var(--ri-color-text-secondary);'
            f'font-size:12px;">as of {html.escape(current.as_of)}</span>'
            '<details class="ri-trigger-reason">'
            "<summary>Trigger Reason</summary>"
            f'<div class="ri-trigger-body">{html.escape(current.trigger_reason)}</div>'
            "</details>"
            f'{metrics_html}'
            "</div>"
        )

    @staticmethod
    def _format_history_rows(history: Tuple[RiskHistoryEntry, ...]) -> List[List[str]]:
        return [
            [
                entry.timestamp,
                entry.state,
                entry.trigger_reason,
                f"{entry.recommended_sizing_pct:.0f}%",
                f"{entry.actual_sizing_pct:.0f}%",
            ]
            for entry in history
        ]

    @staticmethod
    def _format_empty_message_html(screen: RiskScreen) -> str:
        return f'<div class="ri-empty-message">{html.escape(screen.empty_state_message)}</div>'
