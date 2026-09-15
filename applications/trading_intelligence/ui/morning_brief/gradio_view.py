"""Gradio shell for Morning Brief -- screen shell only.

Self-contained: does not import ui/decision_center/, ui/portfolio_intelligence/,
or ui/risk_intelligence/ (no cross-package import of any kind). No
controller, no service, no sentinel_engine/bot/dashboard import, and no
MorningBriefQuery of any kind (see screen.py's and mock_data.py's module
docstrings for why). Wired into bootstrap.py as the 4th Trading
Intelligence tab.

Data is fetched at render time, not build time: the UI takes a
`screen_provider` callable (bootstrap.py's `_build_morning_brief_screen`,
which assembles a MorningBriefScreen from LegacyCapitalSource,
LegacyRegimeSource, LegacyCandidateScreeningSource and AlpacaNewsSource)
and re-invokes it on every `demo.load()` and every Refresh click, so a
long-running Space shows data as of page load rather than app start.
Freshness is shown at two levels: page-level, a "Rendered at {timestamp}"
line (the UI render clock, advances on every Refresh) and an "Operational
data snapshot: {timestamp}" line (when the ADR-055 trades.db snapshot was
fetched for this Space process -- fixed across Refresh, since Refresh
re-reads the same file and never re-downloads the database); and
per-section, an "as of {timestamp}" line under each available section
carrying that section's own data timestamp (its source row's timestamp
for the trades.db-backed sections, the live fetch instant for Overnight
Holdings News). The Refresh button reuses ui/decision_center/gradio_view.py's and
ui/portfolio_intelligence/gradio_view.py's disable -> render -> enable
double-submit guard. When neither `screen` nor `screen_provider` is
supplied the provider is `build_mock_screen` -- this package's own fixed
all-unavailable screen (not fabricated numbers; see mock_data.py's
docstring), never illustrative content.

Unlike ui/portfolio_intelligence/gradio_view.py and
ui/risk_intelligence/gradio_view.py, this screen renders no "Illustrative
Data" disclosure banner -- there is no illustrative data here to disclose,
real or otherwise: a section either shows its own real, adapter-sourced
available_summary (see bootstrap.py's _build_morning_brief_screen()) or
its own honest, fixed unavailable message, per docs/products/AARA_TRADING_
INTELLIGENCE_UI_SPECIFICATION.md Section 2's "Required information" for
Morning Brief and Section 7's "evidence over emotion" UX principle: mark
unbuilt functionality as unavailable rather than invent content to fill
it. This unit does not touch theme.py; the "As of" line reuses the
existing `.mb-subtitle` treatment.

AARA shell consistency pass: renders the same AARA logo header + inter-
screen nav Decision Center/Portfolio Intelligence/Risk Intelligence show,
via `ui/shell.py` (a sibling of all four screen packages, not owned by any
one of them).
"""
import html
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import gradio as gr
import pandas as pd

from applications.trading_intelligence.ui.integration_health_view import (
    CSS as _INTEGRATION_HEALTH_CSS,
    render_unavailable,
)
from applications.trading_intelligence.ui.morning_brief.mock_data import build_mock_screen
from applications.trading_intelligence.ui.morning_brief.screen import (
    PORTFOLIO_SNAPSHOT_TITLE,
    MorningBriefScreen,
    MorningBriefSection,
    PortfolioHistoryPoint,
)
from applications.trading_intelligence.ui.morning_brief.theme import CSS
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html

_PAGE_HEADER_HTML = (
    '<div class="mb-page-header">'
    "<h2>Morning Brief</h2>"
    '<div class="mb-subtitle">Single-glance daily summary before market open</div>'
    "</div>"
)

# The UI render clock -- advances every Refresh.
_RENDERED_AT_PREFIX = "Rendered at "

# Freshness of the ADR-055 trades.db operational snapshot for this Space
# process -- deliberately worded so it is never read as a realtime
# database, and annotated to make the once-per-process caching explicit.
_SNAPSHOT_PREFIX = "Operational data snapshot: "
_SNAPSHOT_REFRESH_NOTE = " (fetched once per Space start; not re-downloaded on Refresh)"
_SNAPSHOT_UNAVAILABLE = _SNAPSHOT_PREFIX + "unavailable"

# Per-section data-freshness lead-in -- rendered under a section's own
# available_summary, so "as of" refers to that section's data, never the
# page-level render clock (which uses `_RENDERED_AT_PREFIX`).
_SECTION_AS_OF_PREFIX = "as of "

# Always-on data-source caption for the Portfolio Snapshot section only.
# That section reads trades.db's `portfolio_snapshots` (the freshest
# per-cycle operational portfolio value, marked to market) -- deliberately
# NOT the internal managed capital-pool ledger that backs Portfolio
# Intelligence's Capital Summary. The two systems of record are tracked
# independently and are expected to differ; this line says so plainly so
# the Morning Brief figure is never read as the same number Portfolio
# Intelligence shows. Same always-on caption pattern (and "-- the two are
# different systems and may not match" phrasing) as
# ui/portfolio_intelligence/gradio_view.py's own _CAPITAL_SOURCE_CAPTION,
# with wording truthful for this section's actual source. Reuses the
# existing `.mb-subtitle` treatment; no theme.py change.
_PORTFOLIO_SNAPSHOT_SOURCE_CAPTION = (
    "Latest per-cycle operational portfolio snapshot, marked to market. "
    "Tracked separately from Portfolio Intelligence's managed capital-pool "
    "ledger -- the two are different systems and may not match."
)
_PORTFOLIO_SNAPSHOT_SOURCE_CAPTION_HTML = (
    f'<div class="mb-subtitle">{html.escape(_PORTFOLIO_SNAPSHOT_SOURCE_CAPTION)}</div>'
)

# Sprint 1: recent-window portfolio value trend, alongside the Portfolio
# Snapshot section's existing point-in-time summary. Same
# unavailable/empty-vs-populated convention as every other integration
# section on this screen -- no fabricated chart data.
_PORTFOLIO_HISTORY_UNAVAILABLE_MESSAGE = (
    "Portfolio value trend is not available -- the managed portfolio "
    "snapshot history could not be read in this environment."
)
_PORTFOLIO_HISTORY_EMPTY_MESSAGE = "No portfolio history is recorded yet."
_PORTFOLIO_HISTORY_SECTION_LABEL_HTML = (
    '<div class="mb-section-label">Portfolio Value Trend</div>'
)

# Decision Activity & Risk State Context sprint: two small, always-present
# facts near Portfolio Snapshot -- reusing the SAME DecisionOutcomeQueryService
# lineage Decision Center/Performance & Learning already exercise, and the
# SAME LegacyRiskStateSource read Risk Intelligence's own Current State
# already uses (both invoked a second, independent time by bootstrap.py's
# _build_morning_brief_screen -- no new adapter). Purely descriptive: never
# a recommendation, a trading opportunity, an enforcement claim, a causal
# claim, or advice.
_DECISION_ACTIVITY_UNAVAILABLE_MESSAGE = (
    "Decision activity is not available -- the trades snapshot could not "
    "be read in this environment."
)
_RISK_STATE_UNAVAILABLE_MESSAGE = (
    "Current risk state is not available -- the operational risk state "
    "could not be read in this environment."
)

# Local primitive, not a cross-package import (same "duplicate the
# primitive" convention ui/portfolio_intelligence/gradio_view.py uses for
# its own order-timestamp display): America/Chicago, DST-aware via
# zoneinfo, "%Y-%m-%d %H:%M %Z" -- the same wall-clock convention every
# other Trading Intelligence timestamp uses.
_DISPLAY_TIMEZONE = ZoneInfo("America/Chicago")


def _format_rendered_at_html(moment: datetime) -> str:
    """Render-clock stamp for the whole screen -- when this render ran, not
    a claim about any data's freshness. Reuses the existing `.mb-subtitle`
    treatment (muted secondary text, already defined in this package's
    theme.py and used by `_PAGE_HEADER_HTML`) rather than introducing a new
    styled class."""
    stamp = moment.astimezone(_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")
    return f'<div class="mb-subtitle">{html.escape(_RENDERED_AT_PREFIX + stamp)}</div>'


def _format_snapshot_line_html(moment: Optional[datetime]) -> str:
    """Freshness of the trades.db operational snapshot (ADR-055) for the
    current Space process, shown as a line separate from the render clock
    so a stale snapshot is never mistaken for realtime data. ADR-055 pulls
    the snapshot once per process and Refresh re-reads the same file, so
    this line is fixed across Refresh clicks and only advances when the
    Space process restarts. `None` (no snapshot obtained) renders an honest
    "unavailable" -- never a fabricated timestamp."""
    if moment is None:
        return f'<div class="mb-subtitle">{html.escape(_SNAPSHOT_UNAVAILABLE)}</div>'
    stamp = moment.astimezone(_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")
    return (
        '<div class="mb-subtitle">'
        f"{html.escape(_SNAPSHOT_PREFIX + stamp + _SNAPSHOT_REFRESH_NOTE)}"
        "</div>"
    )


class MorningBriefUI:
    def __init__(
        self,
        screen: Optional[MorningBriefScreen] = None,
        *,
        screen_provider: Optional[Callable[[], MorningBriefScreen]] = None,
        snapshot_fetched_at_provider: Optional[
            Callable[[], Optional[datetime]]
        ] = None,
    ):
        """Render-time data model. `screen_provider` (bootstrap.py's
        `_build_morning_brief_screen`) is re-invoked on every `demo.load()`
        and every Refresh click, so a long-running Space shows data as of
        page load, not app start. A fixed `screen` (tests) is wrapped in a
        constant provider. When neither is supplied the provider is
        `build_mock_screen` -- this package's own fixed all-unavailable
        screen, never a fabricated one.

        `snapshot_fetched_at_provider` (bootstrap.py's `_snapshot_fetched_at`
        bound to the runtime snapshot path) returns when the ADR-055
        trades.db snapshot was fetched for this process, or `None` if none
        was. It is re-called on every render but reads the same file, so
        its value is stable across Refresh -- that stability is the point.
        Default: a provider returning `None` (pure shell / tests).

        The screen provider is also called once here so `self._screen`
        describes the build-time snapshot -- the same value bootstrap.py
        computed eagerly before this slice. `build()` renders from that
        snapshot and wires `demo.load()` to refresh it immediately on page
        load."""
        if screen_provider is not None:
            self._screen_provider = screen_provider
        elif screen is not None:
            self._screen_provider = lambda: screen
        else:
            self._screen_provider = build_mock_screen
        self._screen = self._screen_provider()
        self._snapshot_fetched_at_provider = snapshot_fetched_at_provider or (
            lambda: None
        )

    def build(self) -> gr.Blocks:
        initial = self._screen
        with gr.Blocks(
            title="AARA Trading Intelligence — Morning Brief",
            css=CSS + _INTEGRATION_HEALTH_CSS,
        ) as demo:
            gr.HTML(SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(build_shell_nav_html("Morning Brief"), elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML)
            refresh_button = gr.Button(
                "↻ Refresh", size="sm", scale=0, elem_classes=["aara-refresh-button"],
            )
            rendered_at_output = gr.HTML(_format_rendered_at_html(self._now()))
            snapshot_output = gr.HTML(
                _format_snapshot_line_html(self._snapshot_fetched_at_provider())
            )

            section_bodies = []
            for section in initial.sections:
                gr.HTML(self._format_section_label_html(section))
                if section.title == PORTFOLIO_SNAPSHOT_TITLE:
                    # Static disclosure, shown in every state (available or
                    # unavailable). Not a dynamic output -- not added to
                    # `outputs`, so _render()/_OUTPUT_COUNT are unchanged.
                    gr.HTML(_PORTFOLIO_SNAPSHOT_SOURCE_CAPTION_HTML)
                section_bodies.append(gr.HTML(self._section_body_html(section)))

            # Decision Activity & Risk State Context sprint: two small,
            # independently-gated facts near Portfolio Snapshot, above the
            # Portfolio Value Trend chart. Always present (never hidden
            # outright) -- content switches between the honest unavailable
            # message and the real summary, matching the Concentration
            # section's own always-visible-with-switching-content pattern
            # (ui/risk_intelligence/gradio_view.py).
            decision_activity_output = gr.HTML(
                self._decision_activity_state(initial)[0],
                elem_classes=["mb-decision-activity-output"],
            )
            risk_state_output = gr.HTML(
                self._current_risk_state_state(initial)[0],
                elem_classes=["mb-risk-state-output"],
            )

            gr.HTML(_PORTFOLIO_HISTORY_SECTION_LABEL_HTML)
            history_message_value, history_message_visible = (
                self._portfolio_history_message_state(initial)
            )
            portfolio_history_message_output = gr.HTML(
                history_message_value, visible=history_message_visible,
            )
            history_dataframe, history_visible = self._portfolio_history_chart_state(initial)
            portfolio_history_chart = gr.LinePlot(
                value=history_dataframe,
                x="as_of",
                y="portfolio_value",
                x_title="Date",
                y_title="Portfolio Value ($)",
                visible=history_visible,
                elem_classes=["mb-portfolio-history-chart"],
            )
            portfolio_history_caption_output = gr.HTML(
                self._portfolio_history_caption_html(initial)
            )

            outputs = [
                rendered_at_output, snapshot_output, *section_bodies,
                portfolio_history_message_output, portfolio_history_chart,
                portfolio_history_caption_output,
                decision_activity_output, risk_state_output,
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
        dynamic output, in build()'s `outputs` order (the render-clock line
        first, then the operational-snapshot-freshness line, then one body
        per section in MorningBriefScreen.sections order). Called by
        demo.load() on page load and by the Refresh chain. The render clock
        advances every call; the snapshot line is re-read but stays fixed
        (Refresh does not re-download the database). A provider that now
        returns an all-unavailable screen collapses every section back to
        its own explicit unavailable message -- there is no
        mock/illustrative fallback anywhere in this path."""
        screen = self._screen_provider()
        history_message_value, history_message_visible = (
            self._portfolio_history_message_state(screen)
        )
        history_dataframe, history_visible = self._portfolio_history_chart_state(screen)
        return (
            gr.update(value=_format_rendered_at_html(self._now())),
            gr.update(
                value=_format_snapshot_line_html(self._snapshot_fetched_at_provider())
            ),
            *(
                gr.update(value=self._section_body_html(section))
                for section in screen.sections
            ),
            gr.update(value=history_message_value, visible=history_message_visible),
            gr.update(value=history_dataframe, visible=history_visible),
            gr.update(value=self._portfolio_history_caption_html(screen)),
            gr.update(value=self._decision_activity_state(screen)[0]),
            gr.update(value=self._current_risk_state_state(screen)[0]),
        )

    @staticmethod
    def _section_body_html(section: MorningBriefSection) -> str:
        if section.is_available:
            return MorningBriefUI._format_available_summary_html(section)
        return MorningBriefUI._format_unavailable_message_html(section)

    @staticmethod
    def _format_section_label_html(section: MorningBriefSection) -> str:
        return f'<div class="mb-section-label">{html.escape(section.title)}</div>'

    @staticmethod
    def _format_unavailable_message_html(section: MorningBriefSection) -> str:
        # ADR-061 A4: route the unavailable body through the shared
        # renderer so a section backed by a real adapter names its
        # specific failure reason (bootstrap.py records section.health on
        # every path); a section with no adapter health (section.health is
        # None) falls back to its own fixed unavailable_message unchanged.
        return render_unavailable(
            section.health, fallback_message=section.unavailable_message
        )

    @staticmethod
    def _format_available_summary_html(section: MorningBriefSection) -> str:
        body = (
            '<div class="mb-available-summary">'
            f"{html.escape(section.available_summary)}"
            "</div>"
        )
        if section.as_of:
            # A per-section freshness line: the timestamp of the data this
            # section is showing (its source row / live fetch instant),
            # separate from the page-level "Rendered at" clock.
            body += (
                '<div class="mb-subtitle">'
                f"{html.escape(_SECTION_AS_OF_PREFIX + section.as_of)}"
                "</div>"
            )
        return body

    # --- Sprint 1: Portfolio Value Trend --------------------------------
    #
    # Same duplicated-primitive convention as everything else in this
    # self-contained package: shaped identically to
    # ui/portfolio_intelligence/gradio_view.py's own portfolio-history
    # chart helpers, but not imported from it.

    @staticmethod
    def _portfolio_history_message_state(screen: MorningBriefScreen) -> Tuple[str, bool]:
        if not screen.portfolio_history_is_available:
            return (
                render_unavailable(
                    screen.portfolio_history_health,
                    fallback_message=_PORTFOLIO_HISTORY_UNAVAILABLE_MESSAGE,
                ),
                True,
            )
        if screen.portfolio_history_is_empty:
            return (
                f'<div class="mb-unavailable-message">'
                f'{html.escape(_PORTFOLIO_HISTORY_EMPTY_MESSAGE)}</div>',
                True,
            )
        return ("", False)

    @staticmethod
    def _portfolio_history_chart_state(
        screen: MorningBriefScreen,
    ) -> Tuple[pd.DataFrame, bool]:
        if screen.portfolio_history_is_available and not screen.portfolio_history_is_empty:
            return (
                MorningBriefUI._format_portfolio_history_dataframe(screen.portfolio_history),
                True,
            )
        return (MorningBriefUI._format_portfolio_history_dataframe(()), False)

    @staticmethod
    def _format_portfolio_history_dataframe(
        points: Tuple[PortfolioHistoryPoint, ...],
    ) -> pd.DataFrame:
        """Two real columns only -- each point's own as_of instant and its
        own portfolio_value, verbatim from portfolio_snapshots (already
        windowed to a recent range by bootstrap.py). No derived column
        (return, drawdown, or any other computed metric) is ever added
        here, matching Portfolio Intelligence's own chart's scope guard."""
        return pd.DataFrame(
            {
                "as_of": [pd.Timestamp(point.as_of) for point in points],
                "portfolio_value": [point.portfolio_value for point in points],
            }
        )

    @staticmethod
    def _portfolio_history_caption_html(screen: MorningBriefScreen) -> str:
        """Honest freshness line for the trend chart -- the most recent
        point's own real timestamp, using the exact same "as of" wording
        every other section on this screen already uses. Empty when there
        is nothing to caption; the message state above already explains
        the unavailable/empty cases."""
        if not screen.portfolio_history_is_available or screen.portfolio_history_is_empty:
            return ""
        most_recent_as_of = screen.portfolio_history[-1].as_of
        return (
            '<div class="mb-subtitle">'
            f"{html.escape(_SECTION_AS_OF_PREFIX + most_recent_as_of)}"
            "</div>"
        )

    # --- Decision Activity & Risk State Context sprint --------------------
    #
    # Each independent of the other and of every section above -- one being
    # unavailable must never hide or alter the other's real content.

    @staticmethod
    def _decision_activity_state(screen: MorningBriefScreen) -> Tuple[str, bool]:
        """Always present (visible=True) -- content switches between the
        honest unavailable message (routed through the shared
        render_unavailable() so a real adapter failure names its specific
        reason) and the real, ready-to-render summary bootstrap.py already
        formatted. Never fabricates a count."""
        if not screen.decision_activity_is_available:
            return (
                render_unavailable(
                    screen.decision_activity_health,
                    fallback_message=_DECISION_ACTIVITY_UNAVAILABLE_MESSAGE,
                ),
                True,
            )
        return (
            f'<div class="mb-available-summary">'
            f'{html.escape(screen.decision_activity_summary)}</div>',
            True,
        )

    @staticmethod
    def _current_risk_state_state(screen: MorningBriefScreen) -> Tuple[str, bool]:
        """Same always-present, switching-content pattern as
        _decision_activity_state above."""
        if not screen.current_risk_state_is_available:
            return (
                render_unavailable(
                    screen.current_risk_state_health,
                    fallback_message=_RISK_STATE_UNAVAILABLE_MESSAGE,
                ),
                True,
            )
        return (
            f'<div class="mb-available-summary">'
            f'{html.escape(screen.current_risk_state_summary)}</div>',
            True,
        )
