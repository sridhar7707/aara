"""Gradio shell for Risk Intelligence -- real data or an explicit
UNAVAILABLE state; never fabricated/illustrative risk figures.

Self-contained: does not import ui/decision_center/ or
ui/portfolio_intelligence/ (no cross-package import of any kind), and does
not import mock_data.py. Renders whatever RiskScreen it is given; the
production default (no `screen` / `screen_provider` supplied) is an
unavailable RiskScreen() (current is None), which renders a single
UNAVAILABLE message and no fabricated state badge, history table,
evaluation cards, or sizing metrics. No controller, no service, no
sentinel_engine/bot import. Wired into bootstrap.py as the 4th Trading
Intelligence tab.

Data is fetched at render time, not build time: the UI takes a
`screen_provider` callable (bootstrap.py's `_build_risk_intelligence_screen`,
which reads the operational `risk_state` table via
adapters.legacy_risk_state_source.LegacyRiskStateSource) and re-invokes it
on every `demo.load()` and every Refresh click, so a long-running Space
shows data as of page load rather than app start. Freshness is shown at
two levels, matching ui/portfolio_intelligence/gradio_view.py and
ui/morning_brief/gradio_view.py: a "Rendered at {timestamp}" line (the UI
render clock, advances on every Refresh) and an "Operational data
snapshot: {timestamp}" line (when the ADR-055 trades.db snapshot behind
`risk_state` was fetched for this Space process -- fixed across Refresh,
since Refresh re-reads the same file and never re-downloads the database).
The `risk_state` row's own `updated_at` is still shown inline beside the
state badge as "as of {timestamp}" -- that is the data's own timestamp,
distinct from both lines above. The Refresh button
reuses ui/decision_center/gradio_view.py's disable -> render -> enable
double-submit guard.

Observed, not enforced: when a current risk state is shown it is the risk
governor's most recently *observed* classification, read from the
operational `risk_state` table. The screen states this explicitly and
never implies the system enforced the state or blocked execution.
`trigger_reason` and recommended/actual sizing are not persisted in
`risk_state` (they live only in the hash-chained `risk_evaluation_events`
ledger table, which this screen does not read), so when they are None the
view says so plainly rather than fabricating them, and no sizing gap is
computed. History is never fabricated -- with no history source wired it
stays empty and the "Risk evaluation history is not recorded in this data
source." message is shown.

Keyboard focus/activation uses native HTML controls only, no custom JS:
the trigger-reason disclosure and each evaluation-history card are real
<details>/<summary> elements (natively Tab-focusable, Enter/Space-
togglable, with a visible :focus-visible ring -- see theme.py's
Accessibility parity pass), and the history table is a gr.Dataframe
(Gradio's own native keyboard-navigable table).

Accessibility parity pass: one small, self-contained JS bridge
(_LIVE_REGION_SETUP_JS below) sets aria-live/aria-atomic/role on a
screen-reader-only live-region element, since gr.HTML exposes no aria_*
constructor kwarg -- the same reasoning and bounded-polling technique
already shipped and tested in ui/decision_center/gradio_view.py's own
live-region setup, reused here as a pattern (not imported).

AARA shell consistency pass: renders the same AARA logo header + inter-screen
nav Decision Center shows, via `ui/shell.py` (a sibling of all screen
packages, not `ui/decision_center/` or `ui/portfolio_intelligence/` -- see
that module's own docstring for why this doesn't violate this package's
self-containment). No new CSS is added here.
"""
import html
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import gradio as gr

from applications.trading_intelligence.ui.integration_health_view import (
    CSS as _INTEGRATION_HEALTH_CSS,
    render_unavailable,
)
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

# B3 Tier 1 (additive): the shared design-system status-badge modifier
# wired ALONGSIDE the local state-* class. `state-normal` is intentionally
# NOT mapped -- the shared neutral modifier's foreground (#5D5D5D) differs
# from .ri-state-badge.state-normal's (#666666) and needs separate
# sign-off (Tier 2). The local .ri-state-badge / state-* rules stay
# authoritative for a standalone RiskIntelligenceUI().build() (which loads
# no DESIGN_SYSTEM_CSS).
_SHARED_STATE_BADGE_MODIFIERS = {
    "state-warning": "aara-status-badge--warning",
    "state-defensive": "aara-status-badge--defensive",
}

# Rendered in place of every current-state / history / sizing element when
# no real risk source is available (RiskScreen.is_available is False -- the
# production default when the operational `risk_state` table cannot be
# read). ADR-061 A4: routed through the shared render_unavailable() so the
# specific reason (NOT_CONFIGURED / AUTH_FAILED / RATE_LIMITED / UNAVAILABLE
# / API_ERROR) carried on RiskScreen.state_health is named, falling back to
# this fixed sentence when no health was recorded. No fabricated state
# badge, history table, evaluation card, or sizing metric is emitted
# alongside it.

_PAGE_HEADER_HTML = (
    '<div class="ri-page-header">'
    '<h2 class="aara-eyebrow">Risk Intelligence</h2>'
    '<div class="ri-subtitle">Current risk-governor state and position sizing</div>'
    "</div>"
)

_HISTORY_DETAIL_SECTION_LABEL_HTML = '<div class="ri-section-label">Evaluation Details</div>'
_CURRENT_STATE_SECTION_LABEL_HTML = '<div class="ri-section-label">Current State</div>'
_HISTORY_SECTION_LABEL_HTML = '<div class="ri-section-label">Recent Risk Evaluations</div>'

# Shown alongside a current state, reusing theme.py's existing .ri-disclosure
# treatment. Makes explicit that the state is an OBSERVED governor
# classification read from the operational risk_state table -- not proof
# the system enforced a risk state or blocked any execution.
_OBSERVED_CLASSIFICATION_HTML = (
    '<div class="ri-disclosure">'
    '<div class="ri-disclosure-title aara-disclosure-title">Observed governor classification</div>'
    '<div class="ri-disclosure-body aara-disclosure-body">'
    "This risk state is read from the operational risk_state table and reflects "
    "the risk governor's most recently observed classification. It is not a "
    "confirmation that the system enforced this state or blocked any execution."
    "</div>"
    "</div>"
)

_TRIGGER_REASON_UNAVAILABLE_HTML = (
    '<div class="ri-empty-message aara-empty">'
    "Trigger reason is not recorded in this data source."
    "</div>"
)
_SIZING_UNAVAILABLE_HTML = (
    '<div class="ri-empty-message aara-empty">'
    "Sizing information (recommended vs. actual) is not recorded in this data source."
    "</div>"
)

# The UI render clock -- advances every Refresh. Deliberately "Rendered
# at" and not "As of": it is when this render ran, never a claim about the
# risk data's freshness. Matches ui/portfolio_intelligence/gradio_view.py
# and ui/morning_brief/gradio_view.py so all three snapshot-backed screens
# read the same way.
_RENDERED_AT_PREFIX = "Rendered at "

# Freshness of the ADR-055 trades.db operational snapshot for this Space
# process -- the source behind the `risk_state` read. ADR-055 pulls the
# snapshot once per process and Refresh only re-reads the same file, so
# this line is fixed across Refresh and only advances on a Space restart;
# the note makes that explicit so a refreshed page is never mistaken for a
# re-fetched one. Same wording as ui/portfolio_intelligence/gradio_view.py.
_SNAPSHOT_PREFIX = "Operational data snapshot: "
_SNAPSHOT_REFRESH_NOTE = " (fetched once per Space start; not re-downloaded on Refresh)"
_SNAPSHOT_UNAVAILABLE = _SNAPSHOT_PREFIX + "unavailable"

# Local primitive, not a cross-package import (same "duplicate the
# primitive" convention ui/portfolio_intelligence/ and ui/morning_brief/
# use for their own timestamp display): America/Chicago, DST-aware via
# zoneinfo, "%Y-%m-%d %H:%M %Z" -- the wall-clock convention every other
# Trading Intelligence timestamp uses.
_DISPLAY_TIMEZONE = ZoneInfo("America/Chicago")


def _format_rendered_at_html(moment: datetime) -> str:
    """Render-clock stamp for the whole screen -- when this render ran, not
    a claim about the risk data's freshness. Reuses the existing
    `.ri-page-header .ri-subtitle` treatment (muted secondary text,
    already defined in this package's theme.py) rather than introducing a
    new styled class."""
    stamp = moment.astimezone(_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")
    return (
        '<div class="ri-page-header">'
        f'<div class="ri-subtitle">{html.escape(_RENDERED_AT_PREFIX + stamp)}</div>'
        "</div>"
    )


def _format_snapshot_line_html(moment: Optional[datetime]) -> str:
    """Freshness of the trades.db operational snapshot (ADR-055) for the
    current Space process, shown as a line separate from the render clock
    so a stale snapshot is never mistaken for realtime data. Fixed across
    Refresh clicks (Refresh re-reads the same file); only advances on a
    Space restart. `None` (no snapshot obtained -- deployed Space today,
    local dev, tests) renders an honest "unavailable", never a fabricated
    timestamp. Mirrors ui/portfolio_intelligence/gradio_view.py."""
    if moment is None:
        return (
            '<div class="ri-page-header">'
            f'<div class="ri-subtitle">{html.escape(_SNAPSHOT_UNAVAILABLE)}</div>'
            "</div>"
        )
    stamp = moment.astimezone(_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")
    return (
        '<div class="ri-page-header">'
        '<div class="ri-subtitle">'
        f"{html.escape(_SNAPSHOT_PREFIX + stamp + _SNAPSHOT_REFRESH_NOTE)}"
        "</div>"
        "</div>"
    )


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


def _html_update(state: Tuple[str, bool]) -> Dict[str, Any]:
    value, visible = state
    return gr.update(value=value, visible=visible)


def _table_update(state: Tuple[List[List[str]], bool]) -> Dict[str, Any]:
    rows, visible = state
    return gr.update(value=rows, visible=visible)


class RiskIntelligenceUI:
    def __init__(
        self,
        screen: Optional[RiskScreen] = None,
        *,
        screen_provider: Optional[Callable[[], RiskScreen]] = None,
        snapshot_fetched_at_provider: Optional[
            Callable[[], Optional[datetime]]
        ] = None,
    ):
        """Render-time data model. `screen_provider` (bootstrap.py's
        `_build_risk_intelligence_screen`) is re-invoked on every
        `demo.load()` and every Refresh click, so a long-running Space
        shows data as of page load, not app start. A fixed `screen`
        (tests) is wrapped in a constant provider. When neither is
        supplied the provider is `RiskScreen` itself -- the explicit
        unavailable state (current is None), never a mock/illustrative
        screen.

        `snapshot_fetched_at_provider` (bootstrap.py's `_snapshot_fetched_at`
        bound to the runtime snapshot path) returns when the ADR-055
        trades.db snapshot -- the source behind the `risk_state` read --
        was fetched for this process, or `None` if none was. It is
        re-called on every render but reads the same file, so its value is
        stable across Refresh; that stability is the point. Default: a
        provider returning `None` (pure shell / tests). Mirrors
        ui/portfolio_intelligence/gradio_view.py and
        ui/morning_brief/gradio_view.py.

        The provider is also called once here so `self._screen` describes
        the build-time snapshot. `build()` renders from that snapshot and
        wires `demo.load()` to refresh it immediately on page load."""
        if screen_provider is not None:
            self._screen_provider = screen_provider
        elif screen is not None:
            self._screen_provider = lambda: screen
        else:
            self._screen_provider = RiskScreen
        self._screen = self._screen_provider()
        self._snapshot_fetched_at_provider = snapshot_fetched_at_provider or (
            lambda: None
        )

    def build(self) -> gr.Blocks:
        initial = self._screen
        with gr.Blocks(
            title="AARA Trading Intelligence — Risk Intelligence",
            css=CSS + _INTEGRATION_HEALTH_CSS,
            head=_LIVE_REGION_SETUP_JS,
        ) as demo:
            gr.HTML(SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(build_shell_nav_html("Risk Intelligence"), elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML)
            refresh_button = gr.Button(
                "↻ Refresh", size="sm", scale=0, elem_classes=["aara-refresh-button"],
            )
            rendered_at_output = gr.HTML(_format_rendered_at_html(self._now()))
            snapshot_output = gr.HTML(
                _format_snapshot_line_html(self._snapshot_fetched_at_provider())
            )

            # Accessibility parity pass: visually hidden, screen-reader-only
            # live region -- see _LIVE_REGION_SETUP_JS above for how
            # aria-live/aria-atomic/role get attached to this element's
            # stable host, and _announcement_for below for what populates
            # it. Empty initial value; never rendered with visible content
            # of its own. Rendered regardless of availability so the
            # announcer is always present.
            live_announcer = gr.HTML(
                value="", elem_id=_LIVE_ANNOUNCER_ELEM_ID, elem_classes=["ri-sr-only"],
            )

            # Stable component tree: every section below is created once,
            # unconditionally, and toggled via `visible=` in _render() --
            # the same pattern ui/portfolio_intelligence/gradio_view.py
            # uses so demo.load()/Refresh can update it without rebuilding.
            unavailable_value, unavailable_visible = self._unavailable_state(initial)
            unavailable_output = gr.HTML(unavailable_value, visible=unavailable_visible)

            observed_value, observed_visible = self._observed_note_state(initial)
            observed_output = gr.HTML(observed_value, visible=observed_visible)

            current_label_value, current_label_visible = self._current_label_state(initial)
            current_state_label = gr.HTML(current_label_value, visible=current_label_visible)
            current_value, current_visible = self._current_state_output_state(initial)
            current_state_output = gr.HTML(current_value, visible=current_visible)

            history_label_value, history_label_visible = self._history_label_state(initial)
            history_label = gr.HTML(history_label_value, visible=history_label_visible)

            history_empty_value, history_empty_visible = self._history_empty_state(initial)
            history_empty_output = gr.HTML(history_empty_value, visible=history_empty_visible)

            history_rows, history_table_visible = self._history_table_state(initial)
            history_table = gr.Dataframe(
                headers=_HISTORY_HEADERS,
                value=history_rows,
                datatype=["str", "str", "str", "str", "str"],
                interactive=False,
                label="Recent Risk Evaluations",
                show_label=False,
                elem_classes=["ri-history-table"],
                visible=history_table_visible,
                **{_DATAFRAME_HEIGHT_KWARG: 320},
            )

            detail_label_value, detail_label_visible = self._history_detail_label_state(initial)
            history_detail_label = gr.HTML(detail_label_value, visible=detail_label_visible)
            detail_value, detail_visible = self._history_detail_output_state(initial)
            history_detail_output = gr.HTML(detail_value, visible=detail_visible)

            outputs = [
                rendered_at_output, snapshot_output, live_announcer,
                unavailable_output, observed_output,
                current_state_label, current_state_output,
                history_label, history_empty_output, history_table,
                history_detail_label, history_detail_output,
            ]

            # Same disable -> render -> enable double-submit guard chain as
            # ui/decision_center/ and ui/portfolio_intelligence/: a second
            # click while a render is in flight cannot dispatch a second
            # concurrent fetch. _render is wired identically to demo.load()
            # (same fn, same inputs=None, same outputs) -- only wrapped in
            # the .then() chain here.
            refresh_button.click(
                fn=self._disable_refresh_button, inputs=None, outputs=[refresh_button],
            ).then(
                fn=self._render, inputs=None, outputs=outputs,
            ).then(
                fn=self._enable_refresh_button, inputs=None, outputs=[refresh_button],
            )
            demo.load(fn=self._render, inputs=None, outputs=outputs)

        return demo

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _disable_refresh_button() -> Dict[str, Any]:
        """First link in the Refresh double-submit guard chain (see
        build()) -- disables the button the instant it is clicked, before
        _render runs. Mirrors ui/decision_center/ and
        ui/portfolio_intelligence/."""
        return gr.update(interactive=False)

    @staticmethod
    def _enable_refresh_button() -> Dict[str, Any]:
        """Last link in the Refresh double-submit guard chain (see
        build()) -- re-enables the button once _render has returned,
        success or not."""
        return gr.update(interactive=True)

    def _render(self) -> Tuple[Dict[str, Any], ...]:
        """Re-fetch through the provider and return one Gradio update per
        dynamic output, in build()'s `outputs` order. Called by
        demo.load() on page load and by the Refresh chain. A provider that
        now returns an unavailable RiskScreen() collapses every section
        back to the single explicit UNAVAILABLE message -- there is no
        mock/illustrative fallback anywhere in this path."""
        screen = self._screen_provider()
        return (
            gr.update(value=_format_rendered_at_html(self._now())),
            gr.update(
                value=_format_snapshot_line_html(self._snapshot_fetched_at_provider())
            ),
            gr.update(value=self._announcement_for(screen)),
            _html_update(self._unavailable_state(screen)),
            _html_update(self._observed_note_state(screen)),
            _html_update(self._current_label_state(screen)),
            _html_update(self._current_state_output_state(screen)),
            _html_update(self._history_label_state(screen)),
            _html_update(self._history_empty_state(screen)),
            _table_update(self._history_table_state(screen)),
            _html_update(self._history_detail_label_state(screen)),
            _html_update(self._history_detail_output_state(screen)),
        )

    # --- per-section state (value, visible), shared by build() and _render() ---

    @staticmethod
    def _unavailable_state(screen: RiskScreen) -> Tuple[str, bool]:
        return (
            render_unavailable(
                screen.state_health, fallback_message=screen.unavailable_message
            ),
            not screen.is_available,
        )

    @staticmethod
    def _observed_note_state(screen: RiskScreen) -> Tuple[str, bool]:
        # Constant value, visibility toggled -- mirrors _unavailable_state
        # so the disclosure element is always present in the tree and only
        # shown alongside a real current state.
        return (_OBSERVED_CLASSIFICATION_HTML, screen.is_available)

    @staticmethod
    def _current_label_state(screen: RiskScreen) -> Tuple[str, bool]:
        return (_CURRENT_STATE_SECTION_LABEL_HTML, screen.is_available)

    def _current_state_output_state(self, screen: RiskScreen) -> Tuple[str, bool]:
        if screen.is_available:
            return (self._format_current_state_html(screen.current), True)
        return ("", False)

    @staticmethod
    def _history_label_state(screen: RiskScreen) -> Tuple[str, bool]:
        return (_HISTORY_SECTION_LABEL_HTML, screen.is_available)

    def _history_empty_state(self, screen: RiskScreen) -> Tuple[str, bool]:
        if screen.is_available and screen.is_empty:
            return (self._format_empty_message_html(screen), True)
        return ("", False)

    def _history_table_state(self, screen: RiskScreen) -> Tuple[List[List[str]], bool]:
        if screen.is_available and not screen.is_empty:
            return (self._format_history_rows(screen.history), True)
        return ([], False)

    @staticmethod
    def _history_detail_label_state(screen: RiskScreen) -> Tuple[str, bool]:
        return (_HISTORY_DETAIL_SECTION_LABEL_HTML, screen.is_available and not screen.is_empty)

    def _history_detail_output_state(self, screen: RiskScreen) -> Tuple[str, bool]:
        if screen.is_available and not screen.is_empty:
            return (self._format_history_detail_list_html(screen.history), True)
        return ("", False)

    def _announce_current_state(self) -> str:
        """Accessibility parity pass: announcement for the build-time
        snapshot. Kept for direct unit-testing; _render() computes the
        same string from the freshly-fetched screen via _announcement_for."""
        return self._announcement_for(self._screen)

    @staticmethod
    def _announcement_for(screen: RiskScreen) -> str:
        """When no real risk source is available, announces the same
        UNAVAILABLE fact the visible message states. Otherwise describes
        the current risk state exactly as _format_current_state_html
        renders it, from the same RiskScreen data -- never implies the
        state is live."""
        if not screen.is_available:
            return f"Risk Intelligence loaded. {screen.unavailable_message}"
        return f"Risk Intelligence loaded. Current risk state: {screen.current.state}."

    @staticmethod
    def _format_state_badge_html(state: str) -> str:
        css_class = _STATE_BADGE_CLASSES.get(state, "state-normal")
        classes = ["ri-state-badge", "aara-status-badge", css_class]
        shared_modifier = _SHARED_STATE_BADGE_MODIFIERS.get(css_class)
        if shared_modifier:
            classes.append(shared_modifier)
        return f'<span class="{" ".join(classes)}">{html.escape(state)}</span>'

    @staticmethod
    def _format_current_state_html(current: RiskSnapshot) -> str:
        badge_html = RiskIntelligenceUI._format_state_badge_html(current.state)

        if current.trigger_reason is not None:
            trigger_html = (
                '<details class="ri-trigger-reason">'
                "<summary>Trigger Reason</summary>"
                f'<div class="ri-trigger-body">{html.escape(current.trigger_reason)}</div>'
                "</details>"
            )
        else:
            trigger_html = _TRIGGER_REASON_UNAVAILABLE_HTML

        if current.recommended_sizing_pct is not None and current.actual_sizing_pct is not None:
            gap = current.sizing_gap_pct
            gap_class = "ri-gap-nonzero" if abs(gap) > 0.01 else ""
            metrics_html = (
                '<div class="ri-sizing-metrics">'
                '<div class="ri-metric">'
                '<span class="ri-metric-label aara-metric-label">Recommended Sizing</span>'
                f'<span class="ri-metric-value">{current.recommended_sizing_pct:.0f}%</span>'
                "</div>"
                '<div class="ri-metric">'
                '<span class="ri-metric-label aara-metric-label">Actual Sizing</span>'
                f'<span class="ri-metric-value">{current.actual_sizing_pct:.0f}%</span>'
                "</div>"
                '<div class="ri-metric">'
                '<span class="ri-metric-label aara-metric-label">Gap</span>'
                f'<span class="ri-metric-value {gap_class}">{gap:+.0f}%</span>'
                "</div>"
                "</div>"
            )
        else:
            metrics_html = _SIZING_UNAVAILABLE_HTML

        return (
            '<div class="ri-current-state">'
            f'{badge_html}'
            f'<span style="margin-left:8px;color:var(--ri-color-text-secondary);'
            f'font-size:12px;">as of {html.escape(current.as_of)}</span>'
            f'{trigger_html}'
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
        return f'<div class="ri-empty-message aara-empty">{html.escape(screen.empty_state_message)}</div>'
