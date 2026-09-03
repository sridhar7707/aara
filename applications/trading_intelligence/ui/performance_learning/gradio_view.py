"""Gradio shell for Performance & Learning.

Self-contained: no import of any sibling screen package, no
sentinel_engine/bot/dashboard import, no service call. Renders whatever
`PerformanceLearningScreen` it is given. The production screen is built by
bootstrap.py's `_build_performance_learning_screen`, which maps the
verified Wave 2A decision-outcome lineage
(`DecisionOutcomeQueryService`) into this package's own
`OutcomeHistoryRow` shape -- this view never touches Wave 2A directly and
never re-derives a pairing.

Three states for the Outcome History area, mirroring
ui/risk_intelligence/gradio_view.py's stable-tree pattern (every element
created once, visibility toggled):

  1. non-HEALTHY read  -> an unavailable message. `outcome_health is None`
     (standalone / no-provider build) renders this section's own fixed
     message verbatim; a real non-HEALTHY `IntegrationHealth` renders the
     shared ADR-061 "Data unavailable -- <reason>" phrase.
  2. HEALTHY, zero BUY decisions -> an honest empty-state message.
  3. HEALTHY, decisions present -> a factual summary line + a
     `gr.Dataframe` of one row per `DecisionOutcome`.

Attribution Breakdown and Model Confidence Calibration remain unavailable
in every state -- Wave 2A produces no attribution or calibration data and
none is fabricated here.

No Refresh button and no `demo.load()` in this slice: the screen is
rendered once at build time from the screen the provider returns.

Renders no "Illustrative Data" banner -- every value shown is real,
sourced verbatim from Wave 2A; nothing is illustrative.
"""
import html
from typing import Callable, List, Optional

import gradio as gr

from applications.trading_intelligence.ui.integration_health_view import (
    CSS as _INTEGRATION_HEALTH_CSS,
    render_unavailable,
)
from applications.trading_intelligence.ui.performance_learning.mock_data import build_mock_screen
from applications.trading_intelligence.ui.performance_learning.screen import (
    OutcomeHistoryRow,
    PerformanceLearningScreen,
    PerformanceLearningSection,
)
from applications.trading_intelligence.ui.performance_learning.theme import CSS
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html

# gr.Dataframe's row-height-budget kwarg is `height` on gradio 4.x and
# `max_height` on gradio 5.x -- same compat shim the other table screens
# keep as a local literal (no cross-package import).
_gr_major = int(gr.__version__.split(".")[0])
_DATAFRAME_HEIGHT_KWARG = "height" if _gr_major < 5 else "max_height"

_OUTCOME_HEADERS = [
    "Decision", "Entry date", "Status", "Exit date", "Holding days",
    "Realized P&L $", "Realized P&L %", "Exit basis", "Pairing method",
    "Pairing confidence", "Direction",
]

_PAGE_HEADER_HTML = (
    '<div class="pl-page-header">'
    "<h2>Performance & Learning</h2>"
    '<div class="pl-subtitle">Outcome history, attribution, and model confidence calibration</div>'
    "</div>"
)


def _outcome_row_cells(row: OutcomeHistoryRow) -> List[str]:
    return [
        row.decision, row.entry_date, row.status, row.exit_date, row.holding_days,
        row.realized_pnl_usd, row.realized_pnl_pct, row.exit_basis,
        row.pairing_method, row.pairing_confidence, row.direction,
    ]


class PerformanceLearningUI:
    def __init__(
        self,
        screen: Optional[PerformanceLearningScreen] = None,
        *,
        screen_provider: Optional[Callable[[], PerformanceLearningScreen]] = None,
    ):
        """`screen_provider` (bootstrap.py's `_build_performance_learning_screen`)
        is invoked once here to obtain the screen this build renders. A
        fixed `screen` (tests) is wrapped in a constant provider. With
        neither supplied the provider is `build_mock_screen` -- the
        standalone honest-unavailable shell, never fabricated outcomes."""
        if screen_provider is not None:
            self._screen_provider = screen_provider
        elif screen is not None:
            self._screen_provider = lambda: screen
        else:
            self._screen_provider = build_mock_screen
        self._screen = self._screen_provider()

    def build(self) -> gr.Blocks:
        screen = self._screen
        with gr.Blocks(
            title="AARA Trading Intelligence — Performance & Learning",
            css=CSS + _INTEGRATION_HEALTH_CSS,
        ) as demo:
            gr.HTML(SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(build_shell_nav_html("Performance & Learning"), elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML)

            # --- Outcome History (Wave 2B: real, or an honest state) ---
            gr.HTML(self._format_section_label_html(screen.outcome_history))

            populated = screen.outcome_history_available and not screen.outcome_history_is_empty

            gr.HTML(
                self._format_summary_html(screen.summary),
                visible=populated and screen.summary is not None,
            )
            gr.HTML(
                self._format_outcome_unavailable_html(screen),
                visible=not screen.outcome_history_available,
            )
            gr.HTML(
                self._format_outcome_empty_html(screen),
                visible=screen.outcome_history_available and screen.outcome_history_is_empty,
            )
            gr.Dataframe(
                headers=_OUTCOME_HEADERS,
                value=[_outcome_row_cells(row) for row in screen.outcome_rows],
                datatype=["str"] * len(_OUTCOME_HEADERS),
                interactive=False,
                label="Outcome History",
                show_label=False,
                elem_classes=["pl-outcome-table"],
                visible=populated,
                **{_DATAFRAME_HEIGHT_KWARG: 360},
            )

            # --- Attribution Breakdown / Model Confidence Calibration ---
            # unchanged: no wired source, fixed honest unavailable message
            for section in (
                screen.attribution_breakdown,
                screen.model_confidence_calibration,
            ):
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

    @staticmethod
    def _format_outcome_unavailable_html(screen: PerformanceLearningScreen) -> str:
        """`outcome_health is None` (standalone / no provider) -> this
        section's own fixed message, byte-identical to the pre-Wave-2B
        render. A real non-HEALTHY health -> the shared ADR-061
        "Data unavailable -- <reason>" phrase (reason from status only;
        never the provider name or detail)."""
        if screen.outcome_health is None:
            return PerformanceLearningUI._format_unavailable_message_html(
                screen.outcome_history
            )
        return render_unavailable(
            screen.outcome_health,
            fallback_message=screen.outcome_history.unavailable_message,
        )

    @staticmethod
    def _format_outcome_empty_html(screen: PerformanceLearningScreen) -> str:
        return (
            '<div class="pl-unavailable-message">'
            f'{html.escape(screen.outcome_history_empty_message)}'
            "</div>"
        )

    @staticmethod
    def _format_summary_html(summary: Optional[str]) -> str:
        if not summary:
            return ""
        return f'<div class="pl-summary">{html.escape(summary)}</div>'
