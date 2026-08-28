"""Gradio shell for Risk Intelligence -- real data or an explicit
UNAVAILABLE state; never fabricated/illustrative risk figures.

Self-contained: does not import ui/decision_center/ or
ui/portfolio_intelligence/ (no cross-package import of any kind), and does
not import mock_data.py. Renders whatever RiskScreen it is given; the
production default (no `screen` supplied) is an unavailable RiskScreen()
(current is None), which renders a single UNAVAILABLE message and no
fabricated state badge, history table, evaluation cards, or sizing
metrics. No controller, no service, no sentinel_engine/bot import. Wired
into main.py/bootstrap.py as the 3rd Trading Intelligence tab.

Keyboard focus/activation uses native HTML controls only, no custom JS:
the trigger-reason disclosure and each evaluation-history card are real
<details>/<summary> elements (natively Tab-focusable, Enter/Space-
togglable, now with a visible :focus-visible ring -- see theme.py's
Accessibility parity pass), and the history table is a gr.Dataframe
(Gradio's own native keyboard-navigable table, same mechanism
ui/portfolio_intelligence/gradio_view.py's holdings table already relies
on).

Accessibility parity pass: one small, self-contained JS bridge
(_LIVE_REGION_SETUP_JS below) sets aria-live/aria-atomic/role on a
screen-reader-only live-region element, since gr.HTML exposes no aria_*
constructor kwarg -- the same reasoning and bounded-polling technique
already shipped and tested in ui/decision_center/gradio_view.py's own
live-region setup, reused here as a pattern (not imported).

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

# Rendered in place of every current-state / history / sizing element when
# no governed real risk source is available (RiskScreen.is_available is
# False -- the production default). Reuses the .ri-empty-message treatment
# this screen's own theme.py already defines; no fabricated state badge,
# history table, evaluation card, or sizing metric is emitted alongside it.
_UNAVAILABLE_MESSAGE_HTML = (
    '<div class="ri-empty-message">'
    f'{html.escape("Risk Intelligence data is currently unavailable.")}'
    "</div>"
)

_PAGE_HEADER_HTML = (
    '<div class="ri-page-header">'
    '<h2 class="aara-eyebrow">Risk Intelligence</h2>'
    '<div class="ri-subtitle">Current risk-governor state and position sizing</div>'
    "</div>"
)

_HISTORY_DETAIL_SECTION_LABEL_HTML = '<div class="ri-section-label">Evaluation Details</div>'

# Accessibility parity pass: screen-reader-only live-region announcer,
# following the same pattern already shipped and tested in
# ui/decision_center/gradio_view.py (see that file's own "P1 accessibility
# slice" comments for the full Svelte-source-verified reasoning: gr.HTML's
# stable outer root element is the only place aria-live/aria-atomic/role
# can be set, since Gradio 4.44.1 exposes no aria_* constructor kwarg).
# Reused as a PATTERN here, not imported -- this package stays
# self-contained (no import of ui/decision_center/).
#
# elem_id is package-prefixed ("ri-" not "aara-") because bootstrap.py's
# TabbedInterface composes every screen's Blocks into one document at
# once, not lazily per-tab -- reusing Decision Center's own
# "aara-live-announcer" id here would collide (two elements sharing one
# id; document.getElementById only ever finds the first).
_LIVE_ANNOUNCER_ELEM_ID = "ri-live-announcer"
_LIVE_REGION_SETUP_JS = f"""
<script>
(function () {{
  var attempts = 0;
  var maxAttempts = 100;
  var intervalId = setInterval(function () {{
    attempts += 1;
    var el = document.getElementById("{_LIVE_ANNOUNCER_ELEM_ID}");
    if (el) {{
      el.setAttribute("aria-live", "polite");
      el.setAttribute("aria-atomic", "true");
      el.setAttribute("role", "status");
      clearInterval(intervalId);
      return;
    }}
    if (attempts >= maxAttempts) {{
      clearInterval(intervalId);
    }}
  }}, 50);
}})();
</script>
"""


class RiskIntelligenceUI:
    def __init__(self, screen: RiskScreen = None):
        """The default screen (no `screen` supplied) is an unavailable
        RiskScreen() -- current is None -- never a mock/illustrative
        screen. When the screen is unavailable the view renders only a
        single UNAVAILABLE message; the current-state, history, and
        evaluation-detail sections are omitted entirely."""
        self._screen = screen if screen is not None else RiskScreen()

    def build(self) -> gr.Blocks:
        with gr.Blocks(
            title="AARA Trading Intelligence — Risk Intelligence", css=CSS,
            head=_LIVE_REGION_SETUP_JS,
        ) as demo:
            gr.HTML(SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(build_shell_nav_html("Risk Intelligence"), elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML)

            # Accessibility parity pass: visually hidden, screen-reader-only
            # live region -- see _LIVE_REGION_SETUP_JS above for how
            # aria-live/aria-atomic/role get attached to this element's
            # stable host, and _announce_current_state below for what
            # populates it. Empty initial value; never rendered with
            # visible content of its own. Rendered regardless of
            # availability so the announcer is always present.
            live_announcer = gr.HTML(
                value="", elem_id=_LIVE_ANNOUNCER_ELEM_ID, elem_classes=["ri-sr-only"],
            )

            if not self._screen.is_available:
                gr.HTML(_UNAVAILABLE_MESSAGE_HTML)
            else:
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
                    gr.HTML(_HISTORY_DETAIL_SECTION_LABEL_HTML)
                    gr.HTML(self._format_history_detail_list_html(self._screen.history))

            # Accessibility parity pass: this screen has no refresh button or
            # selection interactivity (see this module's own docstring) --
            # everything is already rendered synchronously above from
            # self._screen -- so demo.load() is the only available trigger,
            # matching ui/decision_center/gradio_view.py's own
            # demo.load(fn=self._announce_screen, ...) pattern.
            demo.load(fn=self._announce_current_state, inputs=None, outputs=[live_announcer])

        return demo

    def _announce_current_state(self) -> str:
        """Accessibility parity pass: populates live_announcer on page
        load. When no real risk source is available, announces the same
        UNAVAILABLE fact the visible message states. Otherwise describes
        the current risk state exactly as _format_current_state_html
        renders it, from the same RiskScreen data -- never implies the
        state is live."""
        if not self._screen.is_available:
            return f"Risk Intelligence loaded. {self._screen.unavailable_message}"
        return f"Risk Intelligence loaded. Current risk state: {self._screen.current.state}."

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
    def _format_history_detail_html(entry: RiskHistoryEntry) -> str:
        """One expandable, fully-readable record for a single history
        entry -- native <details>/<summary>, no JS, matching
        _format_current_state_html's own trigger-reason disclosure
        pattern. Renders exactly the five fields RiskHistoryEntry already
        carries (state, trigger_reason, recommended_sizing_pct,
        actual_sizing_pct, timestamp) plus the sizing gap, computed the
        same way RiskSnapshot.sizing_gap_pct already defines it
        (recommended minus actual) -- a presentation-only computation, not
        a new domain field, since RiskHistoryEntry itself carries no such
        property. Exists because the Dataframe's own trigger_reason cell
        has no line-wrapping rule (theme.py's .ri-history-table styles
        only font/alignment) and can clip a full sentence -- this is the
        one place on the page where every history entry's complete text
        is guaranteed readable."""
        badge_html = RiskIntelligenceUI._format_state_badge_html(entry.state)
        gap = entry.recommended_sizing_pct - entry.actual_sizing_pct
        gap_class = "ri-gap-nonzero" if abs(gap) > 0.01 else ""
        rows = [
            ("Trigger Reason", entry.trigger_reason),
            ("Recommended Sizing", f"{entry.recommended_sizing_pct:.0f}%"),
            ("Actual Sizing", f"{entry.actual_sizing_pct:.0f}%"),
            ("Gap", f"{gap:+.0f}%"),
        ]
        field_html = "".join(
            '<div class="ri-record-field">'
            f'<span class="record-label">{html.escape(label)}</span>'
            f'<span class="record-value {gap_class if label == "Gap" else ""}">'
            f'{html.escape(value)}</span>'
            "</div>"
            for label, value in rows
        )
        return (
            '<details class="ri-history-detail-card">'
            "<summary>"
            f"{badge_html}"
            f'<span class="ri-history-detail-timestamp">{html.escape(entry.timestamp)}</span>'
            "</summary>"
            f'<div class="ri-record-card-fields">{field_html}</div>'
            "</details>"
        )

    @staticmethod
    def _format_history_detail_list_html(history: Tuple[RiskHistoryEntry, ...]) -> str:
        cards = "".join(
            RiskIntelligenceUI._format_history_detail_html(entry) for entry in history
        )
        return f'<div class="ri-history-detail-list">{cards}</div>'

    @staticmethod
    def _format_empty_message_html(screen: RiskScreen) -> str:
        return f'<div class="ri-empty-message">{html.escape(screen.empty_state_message)}</div>'
