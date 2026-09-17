"""Gradio shell for Portfolio Intelligence.

Self-contained: does not import ui/decision_center/ (no gradio_view.py,
theme.py, screen.py, or mock_data.py cross-import). Data is fetched at
render time, not build time: the UI takes a `screen_provider` callable
(bootstrap.py's `_build_portfolio_intelligence_screen`, which assembles a
PortfolioScreen from adapters.legacy_capital_source.LegacyCapitalSource,
adapters.legacy_position_source.LegacyPositionSource,
adapters.live_price_source.LivePriceSource and the three read-only Alpaca
paper adapters) and re-invokes it on every `demo.load()` and every
Refresh click, so a long-running Space shows data as of page load rather
than app start. Freshness is shown at two levels, matching
ui/morning_brief/gradio_view.py: a page-level "Rendered at {timestamp}"
line (the render clock, advances on every Refresh) and an "Operational
data snapshot: {timestamp}" line (when the ADR-055 trades.db snapshot
behind Capital Summary / Allocation / Holdings' open positions was fetched
for this Space process -- fixed across Refresh, since Refresh re-reads the
same file; Holdings' prices are the one part fetched live each Refresh).
The Refresh button reuses ui/decision_center/gradio_view.py's disable ->
render -> enable double-submit guard. Any section whose real source is
unavailable renders an explicit unavailable state -- this module never
imports mock_data.py and the default provider (no `screen` /
`screen_provider` supplied) is `PortfolioScreen` itself, the
all-unavailable state, never a fabricated one. No controller, no service,
no sentinel_engine/bot import. Wired into main.py/bootstrap.py as the 2nd
Trading Intelligence tab.

Alpaca Paper Account section (2026-08-27 unit): a separate, always
distinctly-labeled "ALPACA PAPER" block rendered below Holdings, sourced
from adapters.alpaca_paper_source.AlpacaPaperSource -- Alpaca's own
broker-side paper account, not the bot's internal capital_pools/
position_state bookkeeping Capital Summary/Holdings reflect. The two are
never merged: this section has its own independent available/unavailable
state (screen.alpaca_is_available), never influenced by the Capital
Summary/Holdings availability, and is never counted toward the "Real
Data"/partial/unavailable disclosure above, which describes Capital
Summary/Allocation/Holdings only.

AARA shell consistency pass: renders the same AARA logo header + inter-screen
nav Decision Center shows, via `ui/shell.py` (a sibling of all three screen
packages, not `ui/decision_center/` -- see that module's own docstring for
why this doesn't violate this package's self-containment). No new CSS is
added here; `.aara-shell-header`/`.aara-shell-nav`/`.nav-item` and the tokens
they use are Decision Center's theme.py rules, already merged into the
composed app's single stylesheet by `bootstrap.py`.
"""
import html
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import gradio as gr
import pandas as pd

from applications.trading_intelligence.ui.integration_health_view import (
    CSS as _INTEGRATION_HEALTH_CSS,
    render_unavailable,
)
from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    AlpacaAccountSnapshot,
    AlpacaOrder,
    AlpacaPosition,
    CapitalSummary,
    PortfolioDrawdownPoint,
    PortfolioHistoryPoint,
    PortfolioHolding,
    PortfolioScreen,
    ReconciliationRow,
    ReconciliationStatus,
)
from applications.trading_intelligence.ui.portfolio_intelligence.theme import CSS
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html

# gr.Dataframe's row-height-budget kwarg is named `height` on gradio 4.44.1
# but was renamed `max_height` by gradio 5.x -- same compat shim as
# ui/decision_center/gradio_view.py's own _DATAFRAME_HEIGHT_KWARG, kept as
# a separate literal here rather than imported, per this package's
# no-coupling-to-decision_center scope.
_gr_major = int(gr.__version__.split(".")[0])
_DATAFRAME_HEIGHT_KWARG = "height" if _gr_major < 5 else "max_height"

_HOLDINGS_HEADERS = ["Symbol", "Quantity", "Price", "Market Value", "Weight %"]

_ALPACA_POSITIONS_HEADERS = [
    "Symbol", "Quantity", "Avg Entry", "Current Price", "Market Value",
    "Unrealized P/L", "Unrealized P/L %", "Side",
]

# Unmistakable environment identifier (Phase 4 safety requirement) --
# always rendered verbatim wherever Alpaca-sourced data appears, so Paper
# data can never be mistaken for live brokerage data. This section only
# ever reads Alpaca's Paper endpoint (see adapters/alpaca_paper_source.py's
# own hard-coded paper=True) -- this label is a UI-visibility guarantee on
# top of that, not the safety mechanism itself.
_ALPACA_PAPER_BADGE_TEXT = "ALPACA PAPER"

_ALPACA_UNAVAILABLE_MESSAGE = (
    "Alpaca Paper account data is not available -- credentials or "
    "network access are not configured for this environment."
)

# ALPACA PAPER -- RECENT ORDERS (2026-08-27 unit). A separate, additive
# section rendered below the Alpaca Paper Account block, sourced from
# adapters/alpaca_paper_orders_source.py -- a read-only observation of
# Alpaca's own broker-side order history. Its own independent
# available/unavailable state (screen.alpaca_orders_available), never
# coupled to screen.alpaca_is_available or the Capital Summary/Holdings
# availability, and never counted toward the disclosure above.
_ALPACA_ORDERS_HEADERS = [
    "Submitted", "Symbol", "Side", "Type", "Quantity", "Filled Qty",
    "Limit Price", "Status", "Working", "Filled At",
]

_ALPACA_ORDERS_UNAVAILABLE_MESSAGE = (
    "Alpaca Paper recent orders are not available -- credentials or "
    "network access are not configured for this environment."
)

# Shown unconditionally under the Recent Orders heading, in every state
# (unavailable / empty / populated). This section is a broker-side
# observation of the paper account only -- there is no decision->order
# linkage anywhere in this product, so it must never read as connected to
# Decision Center.
_ALPACA_ORDERS_SCOPE_CAPTION = (
    "Broker-side observation of the paper account. Not linked to Decision Center."
)

# Also shown unconditionally under the Recent Orders heading. Every column
# below (side, status, quantity, filled quantity, fill time) is Alpaca's
# own value rendered unchanged (see adapters/alpaca_paper_orders_source.py),
# so a broker state that looks contradictory at a glance -- most commonly a
# "canceled" order that still carries a partial fill quantity and fill time
# because it filled partly before the remainder was canceled -- is a
# faithful display of the broker record, not a UI error.
_ALPACA_ORDERS_STATUS_NOTE = (
    "Status, side and quantities are shown exactly as the broker reports them; "
    "a canceled order may still show a partial fill quantity and time."
)

# Shown only when an underlying API call hit its defensive per-call cap
# (screen.alpaca_orders.truncated) -- makes the truncation explicit rather
# than silently showing a clipped list.
_ALPACA_ORDERS_TRUNCATION_NOTE = (
    "Showing the 50 most recent open orders and the 50 most recent orders "
    "from the last 14 days."
)

# Broker-verbatim order status is always displayed unchanged; this marker
# is shown in a separate "Working" column for orders still live at the
# broker, never by altering the status string itself.
_ALPACA_ORDERS_WORKING_MARKER = "WORKING"

# Portfolio Intelligence must not import ui/decision_center/, so its
# format_display_timestamp() is duplicated here as a local primitive
# (same "duplicate the primitive, never cross-import" convention as
# _DATAFRAME_HEIGHT_KWARG above). Alpaca's Order timestamps are tz-aware
# UTC; Decision Center's own helper assumes naive-UTC, so this variant
# normalises either case before converting to America/Chicago for display,
# DST-aware via zoneinfo, matching Decision Center's "%Y-%m-%d %H:%M %Z"
# format for visual consistency.
_ORDERS_DISPLAY_TIMEZONE = ZoneInfo("America/Chicago")


def _format_order_timestamp(moment: Optional[datetime]) -> str:
    if not isinstance(moment, datetime):
        return ""
    aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)
    return aware.astimezone(_ORDERS_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")


# Internal vs Alpaca PAPER reconciliation: a factual, descriptive
# comparison of the SAME two already-loaded sources this screen already
# shows separately above (Holdings / Alpaca Paper Positions) -- no new
# read, no new adapter. Never labels a difference a risk, error, unhealthy
# state, trading opportunity, or execution failure; QUANTITY_DIFFERENCE
# only ever reports the recorded numeric difference.
_RECONCILIATION_HEADERS = [
    "Symbol", "Status", "Internal Qty", "Alpaca PAPER Qty", "Qty Difference",
    "Internal Market Value", "Alpaca PAPER Market Value",
]

_RECONCILIATION_STATUS_LABELS = {
    ReconciliationStatus.MATCHED: "MATCHED",
    ReconciliationStatus.INTERNAL_ONLY: "INTERNAL ONLY",
    ReconciliationStatus.BROKER_ONLY: "BROKER ONLY",
    ReconciliationStatus.QUANTITY_DIFFERENCE: "QUANTITY DIFFERENCE",
}

_RECONCILIATION_SCOPE_CAPTION = (
    "Compares the Internal Portfolio (managed capital-pool bookkeeping, "
    "above) against the Alpaca PAPER account (also above) by symbol and "
    "quantity. A factual comparison only -- it does not judge either "
    "source, and a difference is not evidence of an error, a risk, or a "
    "trading opportunity."
)

_RECONCILIATION_INTERNAL_UNAVAILABLE_MESSAGE = (
    "Reconciliation is not available -- the Internal Portfolio (Holdings) "
    "could not be read in this environment."
)
_RECONCILIATION_ALPACA_UNAVAILABLE_MESSAGE = (
    "Reconciliation is not available -- the Alpaca PAPER account/positions "
    "could not be read in this environment."
)

# Shown when the managed capital pool could not be read in this
# environment (LegacyCapitalSource returned None). The production UI never
# substitutes fabricated/illustrative figures -- every affected section
# renders its explicit unavailable state and this page-level banner says
# so plainly.
_UNAVAILABLE_DATA_TITLE = "Data Unavailable"
_UNAVAILABLE_DATA_BODY = (
    "Portfolio data is not available in this environment -- the managed "
    "capital pool could not be read. No capital or holdings figures are "
    "shown."
)
_UNAVAILABLE_DATA_HTML = (
    '<div class="pi-disclosure">'
    f'<div class="pi-disclosure-title aara-disclosure-title">{html.escape(_UNAVAILABLE_DATA_TITLE)}</div>'
    f'<div class="pi-disclosure-body aara-disclosure-body">{html.escape(_UNAVAILABLE_DATA_BODY)}</div>'
    "</div>"
)

# Used only when a real Capital Summary/Allocation was supplied but real
# Holdings could not be (open-position source or live-price source
# unavailable). Capital Summary and Allocation are real managed-capital-
# pool figures at that point; Holdings renders its own unavailable state,
# never a fabricated table.
_PARTIAL_DATA_TITLE = "Partial Data"
_PARTIAL_DATA_BODY = (
    "Capital Summary and Allocation reflect the real managed capital "
    "pool. Holdings data is currently unavailable."
)
_PARTIAL_DATA_HTML = (
    '<div class="pi-disclosure">'
    f'<div class="pi-disclosure-title aara-disclosure-title">{html.escape(_PARTIAL_DATA_TITLE)}</div>'
    f'<div class="pi-disclosure-body aara-disclosure-body">{html.escape(_PARTIAL_DATA_BODY)}</div>'
    "</div>"
)

# Per-section unavailable notes (rendered in place of the Capital Summary
# metrics / Allocation bar / Holdings table when their real source is not
# available). ADR-061 A4: passed as the `fallback_message` to the shared
# render_unavailable(), which names the specific reason from the section's
# IntegrationHealth when one was recorded and otherwise shows this text.
_CAPITAL_UNAVAILABLE_MESSAGE = (
    "Capital Summary is not available -- the managed capital pool could "
    "not be read in this environment."
)
_HOLDINGS_UNAVAILABLE_MESSAGE = (
    "Holdings are not available -- open-position data or live prices "
    "could not be read in this environment."
)

# Portfolio Value Over Time (real portfolio_snapshots equity/value curve).
# A read-only observation of the bot's own trades.db history, entirely
# separate from Capital Summary/Holdings' point-in-time figures above.
# Visual Dashboard Phase A: the chart itself still plots portfolio_value at
# each recorded instant, nothing else, and the timeframe selector below is
# a pure client-side-triggered filter over that SAME already-fetched
# history (no new read, no interpolation, no fabricated point). The one
# addition is the summary line -- current/starting value and their plain
# absolute/percentage difference over the SELECTED window, simple
# subtraction/division over two already-real points. No compounding,
# annualizing, risk-adjusted, or benchmark-relative metric (return series,
# drawdown, Sharpe, alpha, beta, CAGR, ROI, attribution) is ever computed
# here or rendered anywhere near it -- those remain explicitly out of
# Phase A's scope.
_PORTFOLIO_HISTORY_UNAVAILABLE_MESSAGE = (
    "Portfolio value history is not available -- the managed portfolio "
    "snapshot history could not be read in this environment."
)
_PORTFOLIO_HISTORY_EMPTY_MESSAGE = "No portfolio history is recorded yet."
_PORTFOLIO_HISTORY_NO_DATA_FOR_TIMEFRAME_MESSAGE = (
    "No portfolio history is available for the selected timeframe."
)

# Ordered left-to-right in the UI; "ALL" (the full, unfiltered history --
# today's pre-Phase-A behavior) is the default so a page load / Refresh
# with no explicit timeframe interaction renders identically to before
# this feature existed.
_TIMEFRAME_CHOICES = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "ALL"]
_DEFAULT_TIMEFRAME = "ALL"

# Calendar-day windows for the fixed-length timeframes -- same "cutoff =
# now - timedelta(days=N)" convention ui/morning_brief/'s own 30-day
# portfolio-history window already established (bootstrap.py's
# _recent_morning_brief_portfolio_history). "YTD" and "ALL" are handled
# separately (see _filter_history_by_timeframe): YTD's cutoff is January 1
# of `now`'s own year, not a fixed day count; ALL applies no cutoff at all.
_TIMEFRAME_WINDOW_DAYS = {
    "1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365,
}

# Visual Dashboard Phase B: drawdown chart, visually complementing the
# Portfolio Value Over Time chart above -- reuses the SAME already-fetched
# portfolio_history and the SAME timeframe_selector (no second control, no
# second fetch). See _compute_portfolio_drawdown_history for the running-
# peak algorithm (mirrors bootstrap.py's own _compute_drawdown_history --
# Risk Intelligence's drawdown chart -- as a pattern, not a cross-package
# import; this package stays self-contained). Never implies prediction,
# causality, or future risk -- a backward-looking observation only.
_DRAWDOWN_UNAVAILABLE_MESSAGE = (
    "Portfolio drawdown is not available -- the managed portfolio "
    "snapshot history could not be read in this environment."
)
_DRAWDOWN_EMPTY_MESSAGE = "No portfolio history is recorded yet."
_DRAWDOWN_NO_DATA_FOR_TIMEFRAME_MESSAGE = (
    "No portfolio history is available for the selected timeframe."
)
_DRAWDOWN_DISCLAIMER = (
    "Historical drawdown, measured from the running peak of the portfolio "
    "value shown above, over the same timeframe selected above. A "
    "backward-looking observation only -- it does not predict, imply, or "
    "measure future risk."
)

# Used only when both Capital Summary/Allocation AND Holdings were
# supplied from real sources (screen.capital_is_available and
# screen.holdings_is_available both True). Holdings' current price/market
# value are fetched live (see adapters/live_price_source.py); the
# disclosure says so rather than implying a static, always-fresh figure.
_REAL_DATA_TITLE = "Real Data"
_REAL_DATA_BODY = (
    "Capital Summary, Allocation, and Holdings reflect the real managed "
    "capital pool and current open positions. Prices are fetched live "
    "from a market data provider and may be briefly delayed."
)
_REAL_DATA_HTML = (
    '<div class="pi-disclosure">'
    f'<div class="pi-disclosure-title aara-disclosure-title">{html.escape(_REAL_DATA_TITLE)}</div>'
    f'<div class="pi-disclosure-body aara-disclosure-body">{html.escape(_REAL_DATA_BODY)}</div>'
    "</div>"
)

_PAGE_HEADER_HTML = (
    '<div class="pi-page-header">'
    '<h2 class="aara-page-title">Portfolio Intelligence</h2>'
    '<div class="pi-subtitle">Holdings, capital allocation, and current exposure</div>'
    "</div>"
)

# Shown once, directly under the Capital Summary heading, in every state.
# Capital Summary / Allocation are the bot's own internal managed
# capital-pool ledger (trades.db capital_pools) -- a deliberately separate
# system of record from the "Alpaca Paper Account" block further down,
# which is the broker's marked-to-market view. The two are tracked
# independently and are expected to differ; this line says so plainly so
# neither is read as authoritative over the other. Same always-on caption
# pattern as _ALPACA_ORDERS_SCOPE_CAPTION.
_CAPITAL_SOURCE_CAPTION = (
    "Internal managed capital-pool ledger. Tracked separately from the Alpaca "
    "Paper Account below -- the two are different systems and may not match."
)
_CAPITAL_SOURCE_CAPTION_HTML = (
    f'<div class="pi-source-caption">{html.escape(_CAPITAL_SOURCE_CAPTION)}</div>'
)


# The UI render clock -- advances every Refresh. Deliberately "Rendered
# at" and not "As of": it is when this render ran, never a claim about any
# section's data freshness. Matches ui/morning_brief/gradio_view.py's
# _RENDERED_AT_PREFIX so the two trades.db-snapshot-backed screens read the
# same way.
_RENDERED_AT_PREFIX = "Rendered at "

# Freshness of the ADR-055 trades.db operational snapshot for this Space
# process -- the source behind Capital Summary, Allocation and Holdings'
# open positions. ADR-055 pulls the snapshot once per process and Refresh
# only re-reads the same file, so this line is fixed across Refresh and
# only advances on a Space restart; the note makes that explicit so a
# refreshed page is never mistaken for a re-fetched one. Holdings' prices
# are the one part fetched live per Refresh (see the "Real Data"
# disclosure, adapters/live_price_source.py). Same wording as
# ui/morning_brief/gradio_view.py.
_SNAPSHOT_PREFIX = "Operational data snapshot: "
_SNAPSHOT_REFRESH_NOTE = " (fetched once per Space start; not re-downloaded on Refresh)"
_SNAPSHOT_UNAVAILABLE = _SNAPSHOT_PREFIX + "unavailable"


def _format_rendered_at_html(moment: datetime) -> str:
    """Render-clock stamp for the whole screen -- when this render ran, not
    a claim about any data's freshness. America/Chicago in the same
    "%Y-%m-%d %H:%M %Z" format the order timestamps already use (see
    `_format_order_timestamp`), so the two never disagree on wall-clock
    convention. Reuses the existing `.pi-subtitle` treatment (muted
    secondary text, already defined in this package's theme.py and used by
    `_PAGE_HEADER_HTML`) rather than introducing a new styled class."""
    stamp = moment.astimezone(_ORDERS_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")
    return f'<div class="pi-subtitle">{html.escape(_RENDERED_AT_PREFIX + stamp)}</div>'


def _format_snapshot_line_html(moment: Optional[datetime]) -> str:
    """Freshness of the trades.db operational snapshot (ADR-055) for the
    current Space process, shown as a line separate from the render clock
    so a stale snapshot is never mistaken for realtime data. Fixed across
    Refresh clicks (Refresh re-reads the same file); only advances on a
    Space restart. `None` (no snapshot obtained -- deployed Space today,
    local dev, tests) renders an honest "unavailable", never a fabricated
    timestamp. Mirrors ui/morning_brief/gradio_view.py."""
    if moment is None:
        return f'<div class="pi-subtitle">{html.escape(_SNAPSHOT_UNAVAILABLE)}</div>'
    stamp = moment.astimezone(_ORDERS_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")
    return (
        '<div class="pi-subtitle">'
        f"{html.escape(_SNAPSHOT_PREFIX + stamp + _SNAPSHOT_REFRESH_NOTE)}"
        "</div>"
    )


def _html_update(state: Tuple[str, bool]) -> Dict[str, Any]:
    value, visible = state
    return gr.update(value=value, visible=visible)


def _table_update(state: Tuple[List[List[str]], bool]) -> Dict[str, Any]:
    rows, visible = state
    return gr.update(value=rows, visible=visible)


def _chart_update(state: Tuple[pd.DataFrame, bool]) -> Dict[str, Any]:
    dataframe, visible = state
    return gr.update(value=dataframe, visible=visible)


class PortfolioIntelligenceUI:
    def __init__(
        self,
        screen: Optional[PortfolioScreen] = None,
        *,
        screen_provider: Optional[Callable[[], PortfolioScreen]] = None,
        snapshot_fetched_at_provider: Optional[
            Callable[[], Optional[datetime]]
        ] = None,
    ):
        """Render-time data model. `screen_provider` (bootstrap.py's
        `_build_portfolio_intelligence_screen`) is re-invoked on every
        `demo.load()` and every Refresh click, so a long-running Space
        shows data as of page load, not app start. A fixed `screen`
        (tests) is wrapped in a constant provider. When neither is
        supplied the provider is `PortfolioScreen` itself -- the explicit
        all-unavailable state, never a mock/illustrative screen.

        `snapshot_fetched_at_provider` (bootstrap.py's `_snapshot_fetched_at`
        bound to the runtime snapshot path) returns when the ADR-055
        trades.db snapshot -- the source behind Capital Summary, Allocation
        and Holdings' open positions -- was fetched for this process, or
        `None` if none was. It is re-called on every render but reads the
        same file, so its value is stable across Refresh; that stability is
        the point. Default: a provider returning `None` (pure shell /
        tests). Mirrors ui/morning_brief/gradio_view.py.

        The provider is also called once here so `self._screen` /
        `self._capital_is_real` / `self._holdings_is_real` describe the
        build-time snapshot -- the same values bootstrap.py computed
        eagerly before this slice. `build()` renders from that snapshot and
        wires `demo.load()` to refresh it immediately on page load.
        `_capital_is_real` / `_holdings_is_real` are derived solely from
        the screen's own availability, so the disclosure banner can never
        contradict what the sections render."""
        if screen_provider is not None:
            self._screen_provider = screen_provider
        elif screen is not None:
            self._screen_provider = lambda: screen
        else:
            self._screen_provider = PortfolioScreen
        self._screen = self._screen_provider()
        self._snapshot_fetched_at_provider = snapshot_fetched_at_provider or (
            lambda: None
        )
        self._capital_is_real = self._screen.capital_is_available
        self._holdings_is_real = self._screen.holdings_is_available

    def build(self) -> gr.Blocks:
        initial = self._screen
        with gr.Blocks(
            title="AARA Trading Intelligence — Portfolio Intelligence",
            css=CSS + _INTEGRATION_HEALTH_CSS,
        ) as demo:
            gr.HTML(SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(build_shell_nav_html("Portfolio Intelligence"), elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML)
            refresh_button = gr.Button(
                "↻ Refresh", size="sm", scale=0, elem_classes=["aara-refresh-button"],
            )
            rendered_at_output = gr.HTML(_format_rendered_at_html(self._now()))
            snapshot_output = gr.HTML(
                _format_snapshot_line_html(self._snapshot_fetched_at_provider())
            )

            disclosure_output = gr.HTML(self._format_disclosure_html(initial))

            gr.HTML('<div class="pi-section-label">Capital Summary</div>')
            gr.HTML(_CAPITAL_SOURCE_CAPTION_HTML)
            capital_summary_output = gr.HTML(self._capital_summary_state(initial)[0])

            gr.HTML('<div class="pi-section-label">Capital Allocation</div>')
            allocation_output = gr.HTML(self._allocation_state(initial)[0])

            gr.HTML('<div class="pi-section-label">Holdings</div>')
            holdings_message_value, holdings_message_visible = self._holdings_message_state(initial)
            holdings_message_output = gr.HTML(
                holdings_message_value, visible=holdings_message_visible,
            )
            holdings_rows, holdings_visible = self._holdings_table_state(initial)
            holdings_table = gr.Dataframe(
                headers=_HOLDINGS_HEADERS,
                value=holdings_rows,
                datatype=["str", "str", "str", "str", "str"],
                interactive=False,
                label="Holdings",
                show_label=False,
                elem_classes=["pi-holdings-table"],
                visible=holdings_visible,
                **{_DATAFRAME_HEIGHT_KWARG: 320},
            )

            gr.HTML('<div class="pi-section-label">Allocation by Holding</div>')
            holding_allocation_output = gr.HTML(self._holding_allocation_state(initial)[0])

            gr.HTML('<div class="pi-section-label">Portfolio Value Over Time</div>')
            # Holds the CURRENT render's already-fetched (history, health)
            # pair so the timeframe selector below can re-filter it without
            # a second fetch -- refreshed by _render() on every demo.load()/
            # Refresh, read (never written) by _on_timeframe_change().
            history_state = gr.State(
                value=(initial.portfolio_history, initial.portfolio_history_health)
            )
            timeframe_selector = gr.Radio(
                choices=_TIMEFRAME_CHOICES,
                value=_DEFAULT_TIMEFRAME,
                label="Timeframe",
                elem_classes=["pi-timeframe-selector"],
            )
            (
                history_message_value, history_message_visible,
                history_dataframe, history_visible, summary_value,
            ) = self._history_render_state(
                initial.portfolio_history, initial.portfolio_history_health, _DEFAULT_TIMEFRAME,
            )
            portfolio_summary_output = gr.HTML(summary_value)
            portfolio_history_message_output = gr.HTML(
                history_message_value, visible=history_message_visible,
            )
            portfolio_history_chart = gr.LinePlot(
                value=history_dataframe,
                x="as_of",
                y="portfolio_value",
                x_title="Date",
                y_title="Portfolio Value ($)",
                visible=history_visible,
                elem_classes=["pi-portfolio-history-chart"],
            )

            # Drawdown: visually complements the value chart directly above
            # it, sharing the SAME timeframe_selector -- no second control.
            gr.HTML('<div class="pi-section-label">Drawdown</div>')
            gr.HTML(f'<div class="pi-source-caption">{html.escape(_DRAWDOWN_DISCLAIMER)}</div>')
            (
                drawdown_message_value, drawdown_message_visible,
                drawdown_dataframe, drawdown_visible, drawdown_summary_value,
            ) = self._drawdown_render_state(
                initial.portfolio_history, initial.portfolio_history_health, _DEFAULT_TIMEFRAME,
            )
            drawdown_summary_output = gr.HTML(drawdown_summary_value)
            drawdown_message_output = gr.HTML(
                drawdown_message_value, visible=drawdown_message_visible,
            )
            drawdown_chart = gr.LinePlot(
                value=drawdown_dataframe,
                x="as_of",
                y="drawdown_pct",
                x_title="Date",
                y_title="Drawdown (%)",
                visible=drawdown_visible,
                elem_classes=["pi-portfolio-drawdown-chart"],
            )

            gr.HTML(
                f'<div class="pi-section-label">Alpaca Paper Account '
                f'<span class="pi-alpaca-badge">{html.escape(_ALPACA_PAPER_BADGE_TEXT)}</span></div>'
            )
            alpaca_account_output = gr.HTML(self._alpaca_account_state(initial)[0])
            positions_message_value, positions_message_visible = (
                self._alpaca_positions_message_state(initial)
            )
            alpaca_positions_message_output = gr.HTML(
                positions_message_value, visible=positions_message_visible,
            )
            positions_rows, positions_visible = self._alpaca_positions_table_state(initial)
            alpaca_positions_table = gr.Dataframe(
                headers=_ALPACA_POSITIONS_HEADERS,
                value=positions_rows,
                datatype=["str"] * len(_ALPACA_POSITIONS_HEADERS),
                interactive=False,
                label="Alpaca Paper Positions",
                show_label=False,
                elem_classes=["pi-alpaca-positions-table"],
                visible=positions_visible,
                **{_DATAFRAME_HEIGHT_KWARG: 320},
            )

            gr.HTML(
                '<div class="pi-section-label">Internal Portfolio vs '
                f'<span class="pi-alpaca-badge">{html.escape(_ALPACA_PAPER_BADGE_TEXT)}</span> '
                "Reconciliation</div>"
            )
            gr.HTML(
                f'<div class="pi-source-caption">'
                f'{html.escape(_RECONCILIATION_SCOPE_CAPTION)}</div>'
            )
            reconciliation_summary_value, reconciliation_summary_visible = (
                self._reconciliation_summary_state(initial)
            )
            reconciliation_summary_output = gr.HTML(
                reconciliation_summary_value, visible=reconciliation_summary_visible,
            )
            reconciliation_message_value, reconciliation_message_visible = (
                self._reconciliation_message_state(initial)
            )
            reconciliation_message_output = gr.HTML(
                reconciliation_message_value, visible=reconciliation_message_visible,
            )
            reconciliation_rows, reconciliation_visible = (
                self._reconciliation_table_state(initial)
            )
            reconciliation_table = gr.Dataframe(
                headers=_RECONCILIATION_HEADERS,
                value=reconciliation_rows,
                datatype=["str"] * len(_RECONCILIATION_HEADERS),
                interactive=False,
                label="Internal vs Alpaca PAPER Reconciliation",
                show_label=False,
                elem_classes=["pi-reconciliation-table"],
                visible=reconciliation_visible,
                **{_DATAFRAME_HEIGHT_KWARG: 320},
            )

            gr.HTML(
                f'<div class="pi-section-label">Alpaca Paper &mdash; Recent Orders '
                f'<span class="pi-alpaca-badge">{html.escape(_ALPACA_PAPER_BADGE_TEXT)}</span></div>'
            )
            gr.HTML(
                f'<div class="pi-alpaca-orders-caption">'
                f'{html.escape(_ALPACA_ORDERS_SCOPE_CAPTION)}</div>'
            )
            gr.HTML(
                f'<div class="pi-alpaca-orders-caption">'
                f'{html.escape(_ALPACA_ORDERS_STATUS_NOTE)}</div>'
            )
            truncation_value, truncation_visible = self._alpaca_orders_truncation_state(initial)
            alpaca_orders_truncation_output = gr.HTML(
                truncation_value, visible=truncation_visible,
            )
            orders_message_value, orders_message_visible = (
                self._alpaca_orders_message_state(initial)
            )
            alpaca_orders_message_output = gr.HTML(
                orders_message_value, visible=orders_message_visible,
            )
            orders_rows, orders_visible = self._alpaca_orders_table_state(initial)
            alpaca_orders_table = gr.Dataframe(
                headers=_ALPACA_ORDERS_HEADERS,
                value=orders_rows,
                datatype=["str"] * len(_ALPACA_ORDERS_HEADERS),
                interactive=False,
                label="Alpaca Paper Recent Orders",
                show_label=False,
                elem_classes=["pi-alpaca-orders-table"],
                visible=orders_visible,
                **{_DATAFRAME_HEIGHT_KWARG: 320},
            )

            outputs = [
                rendered_at_output, snapshot_output,
                disclosure_output, capital_summary_output, allocation_output,
                holdings_message_output, holdings_table,
                portfolio_history_message_output, portfolio_history_chart,
                alpaca_account_output, alpaca_positions_message_output, alpaca_positions_table,
                alpaca_orders_truncation_output, alpaca_orders_message_output,
                alpaca_orders_table,
                # Internal vs Alpaca PAPER reconciliation -- appended at the
                # end, never inserted/reordered, so every existing index
                # above (used by _render()'s own tuple and by tests that
                # unpack it positionally) stays stable.
                reconciliation_summary_output, reconciliation_message_output,
                reconciliation_table,
                # Visual Dashboard Phase A: same append-only discipline --
                # the summary line and the (history, health) State both go
                # at the very end.
                portfolio_summary_output, history_state,
                # Visual Dashboard Phase B: same append-only discipline --
                # allocation-by-holding (screen-driven, no timeframe
                # involvement) and the drawdown chart's own three outputs.
                holding_allocation_output,
                drawdown_summary_output, drawdown_message_output, drawdown_chart,
            ]

            # Same disable -> render -> enable double-submit guard chain as
            # ui/decision_center/gradio_view.py's Refresh: a second click
            # while a render is in flight cannot dispatch a second
            # concurrent fetch. _render is wired identically to demo.load()
            # (same fn, same outputs) -- only wrapped in the .then() chain
            # here. `timeframe_selector` is now an INPUT (not an output) of
            # _render(), so a Refresh re-renders the CURRENTLY selected
            # timeframe rather than silently resetting it back to ALL; the
            # selector's own value is left untouched by every output list
            # above, so Gradio preserves whatever the user last picked
            # across the click.
            refresh_button.click(
                fn=self._disable_refresh_button, inputs=None, outputs=[refresh_button],
            ).then(
                fn=self._render, inputs=[timeframe_selector], outputs=outputs,
            ).then(
                fn=self._enable_refresh_button, inputs=None, outputs=[refresh_button],
            )
            demo.load(fn=self._render, inputs=[timeframe_selector], outputs=outputs)

            # Timeframe change: pure re-filter of the (history, health) pair
            # history_state already holds from the last render/Refresh --
            # no new fetch, no screen_provider call. Only the six
            # timeframe-dependent outputs (value chart's three, drawdown
            # chart's three) are touched; every other section (Capital
            # Summary, Holdings, allocation-by-holding, Alpaca,
            # reconciliation, ...) is untouched by this event. Both charts
            # share this ONE selector -- there is no second timeframe
            # control for drawdown.
            timeframe_selector.change(
                fn=self._on_timeframe_change,
                inputs=[timeframe_selector, history_state],
                outputs=[
                    portfolio_history_message_output, portfolio_history_chart,
                    portfolio_summary_output,
                    drawdown_message_output, drawdown_chart, drawdown_summary_output,
                ],
            )

        return demo

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _disable_refresh_button() -> Dict[str, Any]:
        """First link in the Refresh double-submit guard chain (see
        build()) -- disables the button the instant it is clicked, before
        _render runs. Mirrors ui/decision_center/gradio_view.py."""
        return gr.update(interactive=False)

    @staticmethod
    def _enable_refresh_button() -> Dict[str, Any]:
        """Last link in the Refresh double-submit guard chain (see
        build()) -- re-enables the button once _render has returned,
        success or not."""
        return gr.update(interactive=True)

    def _render(self, timeframe: str = _DEFAULT_TIMEFRAME) -> Tuple[Dict[str, Any], ...]:
        """Re-fetch through the provider and return one Gradio update per
        dynamic output, in build()'s `outputs` order. Called by
        demo.load() on page load and by the Refresh chain -- `timeframe`
        is the Timeframe selector's own current value (an INPUT now, not
        an output of this function), defaulting to ALL only for direct
        callers that don't pass one (e.g. existing tests, which therefore
        see byte-identical full-history behavior to before this feature
        existed). An unchanged provider result yields an unchanged screen;
        a provider that now returns an all-unavailable PortfolioScreen
        collapses every section back to its own explicit unavailable
        state -- there is no mock fallback anywhere in this path."""
        screen = self._screen_provider()
        (
            history_message_value, history_message_visible,
            history_dataframe, history_visible, summary_value,
        ) = self._history_render_state(
            screen.portfolio_history, screen.portfolio_history_health, timeframe,
        )
        (
            drawdown_message_value, drawdown_message_visible,
            drawdown_dataframe, drawdown_visible, drawdown_summary_value,
        ) = self._drawdown_render_state(
            screen.portfolio_history, screen.portfolio_history_health, timeframe,
        )
        return (
            gr.update(value=_format_rendered_at_html(self._now())),
            gr.update(
                value=_format_snapshot_line_html(self._snapshot_fetched_at_provider())
            ),
            gr.update(value=self._format_disclosure_html(screen)),
            gr.update(value=self._capital_summary_state(screen)[0]),
            gr.update(value=self._allocation_state(screen)[0]),
            _html_update(self._holdings_message_state(screen)),
            _table_update(self._holdings_table_state(screen)),
            gr.update(value=history_message_value, visible=history_message_visible),
            gr.update(value=history_dataframe, visible=history_visible),
            gr.update(value=self._alpaca_account_state(screen)[0]),
            _html_update(self._alpaca_positions_message_state(screen)),
            _table_update(self._alpaca_positions_table_state(screen)),
            _html_update(self._alpaca_orders_truncation_state(screen)),
            _html_update(self._alpaca_orders_message_state(screen)),
            _table_update(self._alpaca_orders_table_state(screen)),
            _html_update(self._reconciliation_summary_state(screen)),
            _html_update(self._reconciliation_message_state(screen)),
            _table_update(self._reconciliation_table_state(screen)),
            gr.update(value=summary_value),
            gr.update(value=(screen.portfolio_history, screen.portfolio_history_health)),
            gr.update(value=self._holding_allocation_state(screen)[0]),
            gr.update(value=drawdown_summary_value),
            gr.update(value=drawdown_message_value, visible=drawdown_message_visible),
            gr.update(value=drawdown_dataframe, visible=drawdown_visible),
        )

    def _on_timeframe_change(
        self,
        timeframe: str,
        history_and_health: Tuple[
            Optional[Tuple[PortfolioHistoryPoint, ...]], Optional[Any],
        ],
    ) -> Tuple[
        Dict[str, Any], Dict[str, Any], Dict[str, Any],
        Dict[str, Any], Dict[str, Any], Dict[str, Any],
    ]:
        """Pure re-filter of the (history, health) pair history_state
        already holds from the last render/Refresh -- no screen_provider
        call, no new read. Returns updates for exactly the six
        timeframe-dependent outputs, in the order build() wires them:
        value-chart message, chart, summary, then drawdown message, chart,
        summary. Both charts share this ONE timeframe -- there is no
        second selector, and both are re-filtered from the SAME
        history_state pair."""
        history, health = history_and_health
        (
            message_value, message_visible,
            chart_dataframe, chart_visible, summary_value,
        ) = self._history_render_state(history, health, timeframe)
        (
            drawdown_message_value, drawdown_message_visible,
            drawdown_dataframe, drawdown_visible, drawdown_summary_value,
        ) = self._drawdown_render_state(history, health, timeframe)
        return (
            gr.update(value=message_value, visible=message_visible),
            gr.update(value=chart_dataframe, visible=chart_visible),
            gr.update(value=summary_value),
            gr.update(value=drawdown_message_value, visible=drawdown_message_visible),
            gr.update(value=drawdown_dataframe, visible=drawdown_visible),
            gr.update(value=drawdown_summary_value),
        )

    # --- per-section state (value, visible), shared by build() and _render() ---

    def _capital_summary_state(self, screen: PortfolioScreen) -> Tuple[str, bool]:
        if screen.capital_is_available:
            return (self._format_capital_summary_html(screen.capital), True)
        return (
            render_unavailable(
                screen.capital_health, fallback_message=_CAPITAL_UNAVAILABLE_MESSAGE
            ),
            True,
        )

    def _allocation_state(self, screen: PortfolioScreen) -> Tuple[str, bool]:
        if screen.capital_is_available:
            return (self._format_allocation_html(screen.capital), True)
        return (
            render_unavailable(
                screen.capital_health, fallback_message=_CAPITAL_UNAVAILABLE_MESSAGE
            ),
            True,
        )

    def _holdings_message_state(self, screen: PortfolioScreen) -> Tuple[str, bool]:
        if not screen.holdings_is_available:
            return (
                render_unavailable(
                    screen.holdings_health,
                    fallback_message=_HOLDINGS_UNAVAILABLE_MESSAGE,
                ),
                True,
            )
        if screen.is_empty:
            return (self._format_empty_message_html(screen), True)
        return ("", False)

    def _holdings_table_state(self, screen: PortfolioScreen) -> Tuple[List[List[str]], bool]:
        if screen.holdings_is_available and not screen.is_empty:
            return (self._format_holdings_rows(screen.holdings), True)
        return ([], False)

    def _holding_allocation_state(self, screen: PortfolioScreen) -> Tuple[str, bool]:
        """Visual Dashboard Phase B: same availability/empty gating as
        Holdings itself (screen.holdings_is_available / screen.is_empty) --
        this is a visual companion to that same table, sourced from the
        SAME already-fetched holdings, never a second read. Always
        visible=True (the content itself switches between unavailable/
        empty/populated), matching Capital Allocation's own simpler
        single-output shape above rather than Holdings' message+table
        pair, since this renders as one HTML block, not a hideable table."""
        if not screen.holdings_is_available:
            return (
                render_unavailable(
                    screen.holdings_health, fallback_message=_HOLDINGS_UNAVAILABLE_MESSAGE,
                ),
                True,
            )
        if screen.is_empty:
            return (self._format_empty_message_html(screen), True)
        return (self._format_holding_allocation_html(screen.holdings), True)

    def _portfolio_history_message_state(
        self, screen: PortfolioScreen, timeframe: str = _DEFAULT_TIMEFRAME,
    ) -> Tuple[str, bool]:
        message_value, message_visible, _, _, _ = self._history_render_state(
            screen.portfolio_history, screen.portfolio_history_health, timeframe,
        )
        return (message_value, message_visible)

    def _portfolio_history_chart_state(
        self, screen: PortfolioScreen, timeframe: str = _DEFAULT_TIMEFRAME,
    ) -> Tuple[pd.DataFrame, bool]:
        _, _, chart_dataframe, chart_visible, _ = self._history_render_state(
            screen.portfolio_history, screen.portfolio_history_health, timeframe,
        )
        return (chart_dataframe, chart_visible)

    def _portfolio_summary_state(
        self, screen: PortfolioScreen, timeframe: str = _DEFAULT_TIMEFRAME,
    ) -> str:
        _, _, _, _, summary_value = self._history_render_state(
            screen.portfolio_history, screen.portfolio_history_health, timeframe,
        )
        return summary_value

    def _history_render_state(
        self,
        history: Optional[Tuple[PortfolioHistoryPoint, ...]],
        health: Optional[Any],
        timeframe: str,
    ) -> Tuple[str, bool, pd.DataFrame, bool, str]:
        """Single source of truth for Portfolio Value Over Time's three
        timeframe-dependent outputs (message, chart, summary) -- returns
        (message_value, message_visible, chart_dataframe, chart_visible,
        summary_html). Shared by the screen-driven render path
        (build()/_render(), via the three thin wrappers above) and the
        State-driven, no-refetch timeframe-only path (_on_timeframe_change()),
        so the empty/unavailable/insufficient-for-timeframe/populated
        decision is made in exactly one place.

        Four states: `history is None` -> unavailable (the managed
        snapshot history itself could not be read); an empty tuple -> the
        screen's own honest "no history recorded" message (real source,
        zero rows, ever); a real, non-empty history that has NO points
        within the selected timeframe's window -> a distinct, equally
        honest "no data for this timeframe" message (never silently
        reused from the zero-rows-total case, which would misstate why
        nothing is shown); otherwise the real filtered points populate
        both the chart and the summary."""
        empty_chart = self._format_portfolio_history_dataframe(())
        if history is None:
            return (
                render_unavailable(
                    health, fallback_message=_PORTFOLIO_HISTORY_UNAVAILABLE_MESSAGE,
                ),
                True, empty_chart, False, "",
            )
        if len(history) == 0:
            return (
                f'<div class="pi-empty-message aara-empty">'
                f'{html.escape(_PORTFOLIO_HISTORY_EMPTY_MESSAGE)}</div>',
                True, empty_chart, False, "",
            )
        filtered = self._filter_history_by_timeframe(history, timeframe, self._now())
        if not filtered:
            return (
                f'<div class="pi-empty-message aara-empty">'
                f'{html.escape(_PORTFOLIO_HISTORY_NO_DATA_FOR_TIMEFRAME_MESSAGE)}</div>',
                True, empty_chart, False, "",
            )
        return (
            "", False,
            self._format_portfolio_history_dataframe(filtered), True,
            self._format_portfolio_summary_html(self._compute_portfolio_summary(filtered)),
        )

    @staticmethod
    def _filter_history_by_timeframe(
        points: Tuple[PortfolioHistoryPoint, ...], timeframe: str, now: datetime,
    ) -> Tuple[PortfolioHistoryPoint, ...]:
        """Pure filter over already-fetched real portfolio_history points
        -- no new read, no interpolation, no fabricated point. "ALL" (and
        any unrecognized value, defensively) returns every point
        unchanged. Points already arrive in ascending as_of order (the
        adapter's own `ORDER BY timestamp ASC`); that order is preserved.
        A point whose as_of cannot be parsed is dropped rather than
        guessed into or out of the window -- same "unparseable -> drop,
        never invent" discipline Morning Brief's own windowing uses."""
        if timeframe == "ALL":
            return points
        if timeframe == "YTD":
            cutoff = datetime(now.year, 1, 1, tzinfo=timezone.utc)
        else:
            window_days = _TIMEFRAME_WINDOW_DAYS.get(timeframe)
            if window_days is None:
                return points
            cutoff = now - timedelta(days=window_days)
        filtered = []
        for point in points:
            try:
                parsed = datetime.fromisoformat(point.as_of)
            except (TypeError, ValueError):
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed >= cutoff:
                filtered.append(point)
        return tuple(filtered)

    @staticmethod
    def _compute_portfolio_summary(
        points: Tuple[PortfolioHistoryPoint, ...],
    ) -> Optional[Dict[str, Optional[float]]]:
        """Only ever computed from real, already-filtered points -- plain
        subtraction/division, never a compounding, annualizing, risk-
        adjusted, or benchmark-relative metric. `current` is the most
        recent point's own portfolio_value; `starting` is the EARLIEST
        point within the selected window (not the all-time starting
        value, which is a different, un-requested figure). `percentage_
        change` is None (never a fabricated +/-inf) when the starting
        value is exactly zero."""
        if not points:
            return None
        current = points[-1].portfolio_value
        starting = points[0].portfolio_value
        absolute_change = current - starting
        percentage_change = (
            (absolute_change / starting) * 100.0 if starting != 0 else None
        )
        return {
            "current": current,
            "starting": starting,
            "absolute_change": absolute_change,
            "percentage_change": percentage_change,
        }

    @staticmethod
    def _format_signed_money(value: float) -> str:
        sign = "-" if value < 0 else "+"
        return f"{sign}${abs(value):,.2f}"

    @staticmethod
    def _format_signed_pct(value: float) -> str:
        sign = "-" if value < 0 else "+"
        return f"{sign}{abs(value):.2f}%"

    @staticmethod
    def _format_portfolio_summary_html(summary: Optional[Dict[str, Optional[float]]]) -> str:
        """Reuses the exact .pi-capital-summary/.pi-metric/.pi-metric-label/
        .pi-metric-value markup Capital Summary and the Alpaca Paper
        Account block already use -- no new metric styling introduced.
        `""` (hidden) when there is nothing to summarize yet. Percentage
        Change is omitted entirely (never shown as 0% or blank) when the
        starting value was zero and no rate is mathematically defined."""
        if not summary:
            return ""
        fields = [
            ("Current Value", f"${summary['current']:,.2f}"),
            ("Starting Value", f"${summary['starting']:,.2f}"),
            ("Change", PortfolioIntelligenceUI._format_signed_money(summary["absolute_change"])),
        ]
        if summary["percentage_change"] is not None:
            fields.append(
                ("% Change", PortfolioIntelligenceUI._format_signed_pct(summary["percentage_change"]))
            )
        metrics_html = "".join(
            '<div class="pi-metric">'
            f'<span class="pi-metric-label aara-metric-label">{html.escape(label)}</span>'
            f'<span class="pi-metric-value">{html.escape(value)}</span>'
            "</div>"
            for label, value in fields
        )
        return f'<div class="pi-capital-summary">{metrics_html}</div>'

    # --- Visual Dashboard Phase B: drawdown ------------------------------

    def _drawdown_render_state(
        self,
        history: Optional[Tuple[PortfolioHistoryPoint, ...]],
        health: Optional[Any],
        timeframe: str,
    ) -> Tuple[str, bool, pd.DataFrame, bool, str]:
        """Single source of truth for the drawdown chart's three
        timeframe-dependent outputs (message, chart, summary) -- mirrors
        _history_render_state's own four-state shape exactly (unavailable
        / empty / no-data-for-timeframe / populated), reusing the SAME
        already-fetched `history` the value chart uses (no second read).
        The running peak is always computed over the FULL history BEFORE
        any timeframe filtering (see _compute_portfolio_drawdown_history),
        so a shorter window (e.g. "1M") shows real drawdown from the TRUE
        all-time peak, never a peak invented from the window's own first
        point."""
        empty_chart = self._format_portfolio_drawdown_dataframe(())
        if history is None:
            return (
                render_unavailable(health, fallback_message=_DRAWDOWN_UNAVAILABLE_MESSAGE),
                True, empty_chart, False, "",
            )
        if len(history) == 0:
            return (
                f'<div class="pi-empty-message aara-empty">'
                f'{html.escape(_DRAWDOWN_EMPTY_MESSAGE)}</div>',
                True, empty_chart, False, "",
            )
        full_drawdown = self._compute_portfolio_drawdown_history(history)
        # _filter_history_by_timeframe only ever reads `.as_of` off each
        # point -- reused here as-is (duck-typed) over PortfolioDrawdownPoint
        # rather than duplicated, exactly like Phase A's own value chart.
        filtered = self._filter_history_by_timeframe(full_drawdown, timeframe, self._now())
        if not filtered:
            return (
                f'<div class="pi-empty-message aara-empty">'
                f'{html.escape(_DRAWDOWN_NO_DATA_FOR_TIMEFRAME_MESSAGE)}</div>',
                True, empty_chart, False, "",
            )
        return (
            "", False,
            self._format_portfolio_drawdown_dataframe(filtered), True,
            self._format_drawdown_summary_html(self._compute_drawdown_summary(filtered)),
        )

    @staticmethod
    def _compute_portfolio_drawdown_history(
        points: Tuple[PortfolioHistoryPoint, ...],
    ) -> Tuple[PortfolioDrawdownPoint, ...]:
        """Same running-peak algorithm as bootstrap.py's own
        _compute_drawdown_history() (Risk Intelligence's drawdown chart) --
        reused here as a pattern, not by cross-package import (this
        package stays self-contained), with the sign convention this
        feature's own spec calls for: drawdown_pct = (value - peak) / peak
        * 100 -- 0.0 at a new peak, negative while underwater, never
        positive. A non-positive running peak (should not occur for a real
        portfolio_snapshots row, but handled defensively) yields
        drawdown_pct=0.0 rather than a division error or a fabricated
        value. Always computed over the FULL, unfiltered `points` passed
        in -- the running peak is the TRUE all-time peak up to each point,
        never reset by a display window (see _drawdown_render_state, which
        filters the ALREADY-computed points by timeframe afterward)."""
        history = []
        peak: Optional[float] = None
        for point in points:
            value = point.portfolio_value
            if peak is None or value > peak:
                peak = value
            drawdown_pct = 0.0 if not peak or peak <= 0 else (value - peak) / peak * 100.0
            history.append(
                PortfolioDrawdownPoint(
                    as_of=point.as_of, portfolio_value=value, drawdown_pct=drawdown_pct,
                )
            )
        return tuple(history)

    @staticmethod
    def _compute_drawdown_summary(
        points: Tuple[PortfolioDrawdownPoint, ...],
    ) -> Optional[Dict[str, float]]:
        """Only ever computed from real, already-filtered drawdown points.
        `current_drawdown_pct` is the most recent point's own drawdown;
        `max_drawdown_pct` is the single most negative value within the
        selected window (the deepest real observed drawdown in that
        range) -- plain min(), never an estimate or a claim about the
        future."""
        if not points:
            return None
        return {
            "current_drawdown_pct": points[-1].drawdown_pct,
            "max_drawdown_pct": min(p.drawdown_pct for p in points),
        }

    @staticmethod
    def _format_drawdown_summary_html(summary: Optional[Dict[str, float]]) -> str:
        """Reuses the exact .pi-capital-summary/.pi-metric markup every
        other summary card on this screen already uses -- no new metric
        styling introduced. `""` (hidden) when there is nothing to
        summarize yet."""
        if not summary:
            return ""
        fields = [
            ("Current Drawdown", f"{summary['current_drawdown_pct']:.2f}%"),
            ("Max Drawdown", f"{summary['max_drawdown_pct']:.2f}%"),
        ]
        metrics_html = "".join(
            '<div class="pi-metric">'
            f'<span class="pi-metric-label aara-metric-label">{html.escape(label)}</span>'
            f'<span class="pi-metric-value">{html.escape(value)}</span>'
            "</div>"
            for label, value in fields
        )
        return f'<div class="pi-capital-summary">{metrics_html}</div>'

    @staticmethod
    def _format_portfolio_drawdown_dataframe(
        points: Tuple[PortfolioDrawdownPoint, ...],
    ) -> pd.DataFrame:
        """Two real columns only -- each point's own as_of instant and its
        own drawdown_pct (already computed above from real portfolio_
        history rows -- never recomputed or altered here)."""
        return pd.DataFrame(
            {
                "as_of": [pd.Timestamp(point.as_of) for point in points],
                "drawdown_pct": [point.drawdown_pct for point in points],
            }
        )

    def _alpaca_account_state(self, screen: PortfolioScreen) -> Tuple[str, bool]:
        if screen.alpaca_is_available:
            return (self._format_alpaca_account_html(screen.alpaca_account), True)
        return (
            render_unavailable(
                screen.alpaca_health, fallback_message=_ALPACA_UNAVAILABLE_MESSAGE
            ),
            True,
        )

    def _alpaca_positions_message_state(self, screen: PortfolioScreen) -> Tuple[str, bool]:
        if screen.alpaca_is_available and len(screen.alpaca_positions) == 0:
            return (
                f'<div class="pi-empty-message aara-empty">'
                f'{html.escape(screen.alpaca_empty_state_message)}</div>',
                True,
            )
        return ("", False)

    def _alpaca_positions_table_state(
        self, screen: PortfolioScreen,
    ) -> Tuple[List[List[str]], bool]:
        if screen.alpaca_is_available and len(screen.alpaca_positions) > 0:
            return (self._format_alpaca_positions_rows(screen.alpaca_positions), True)
        return ([], False)

    def _alpaca_orders_truncation_state(self, screen: PortfolioScreen) -> Tuple[str, bool]:
        if (
            screen.alpaca_orders_available
            and not screen.alpaca_orders.is_empty
            and screen.alpaca_orders.truncated
        ):
            return (
                f'<div class="pi-alpaca-orders-truncation">'
                f'{html.escape(_ALPACA_ORDERS_TRUNCATION_NOTE)}</div>',
                True,
            )
        return ("", False)

    def _alpaca_orders_message_state(self, screen: PortfolioScreen) -> Tuple[str, bool]:
        if not screen.alpaca_orders_available:
            return (
                render_unavailable(
                    screen.alpaca_orders_health,
                    fallback_message=_ALPACA_ORDERS_UNAVAILABLE_MESSAGE,
                ),
                True,
            )
        if screen.alpaca_orders.is_empty:
            return (
                f'<div class="pi-empty-message aara-empty">'
                f'{html.escape(screen.alpaca_orders_empty_state_message)}</div>',
                True,
            )
        return ("", False)

    def _alpaca_orders_table_state(
        self, screen: PortfolioScreen,
    ) -> Tuple[List[List[str]], bool]:
        if screen.alpaca_orders_available and not screen.alpaca_orders.is_empty:
            return (self._format_alpaca_orders_rows(screen.alpaca_orders.orders), True)
        return ([], False)

    # --- Internal vs Alpaca PAPER reconciliation --------------------------
    #
    # Independent of Capital Summary / Portfolio History availability --
    # gated only on the two sources it actually compares: Holdings
    # (screen.holdings_is_available) and the Alpaca Paper account/positions
    # read (screen.alpaca_is_available). Never infers a match when either
    # is unavailable.

    def _reconciliation_message_state(self, screen: PortfolioScreen) -> Tuple[str, bool]:
        if not screen.holdings_is_available:
            return (
                render_unavailable(
                    screen.holdings_health,
                    fallback_message=_RECONCILIATION_INTERNAL_UNAVAILABLE_MESSAGE,
                ),
                True,
            )
        if not screen.alpaca_is_available:
            return (
                render_unavailable(
                    screen.alpaca_health,
                    fallback_message=_RECONCILIATION_ALPACA_UNAVAILABLE_MESSAGE,
                ),
                True,
            )
        if screen.reconciliation_is_empty:
            return (
                f'<div class="pi-empty-message aara-empty">'
                f'{html.escape(screen.reconciliation_empty_state_message)}</div>',
                True,
            )
        return ("", False)

    def _reconciliation_table_state(
        self, screen: PortfolioScreen,
    ) -> Tuple[List[List[str]], bool]:
        if screen.reconciliation_is_available and not screen.reconciliation_is_empty:
            return (self._format_reconciliation_rows(screen.reconciliation), True)
        return ([], False)

    def _reconciliation_summary_state(self, screen: PortfolioScreen) -> Tuple[str, bool]:
        if screen.reconciliation_is_available and not screen.reconciliation_is_empty:
            return (self._format_reconciliation_summary_html(screen.reconciliation), True)
        return ("", False)

    @staticmethod
    def _format_reconciliation_rows(rows: Tuple[ReconciliationRow, ...]) -> List[List[str]]:
        def _qty(value: Optional[float]) -> str:
            return f"{value:g}" if value is not None else ""

        def _money(value: Optional[float]) -> str:
            return f"${value:,.2f}" if value is not None else ""

        return [
            [
                row.symbol,
                _RECONCILIATION_STATUS_LABELS.get(row.status, row.status.name),
                _qty(row.internal_quantity),
                _qty(row.alpaca_quantity),
                _qty(row.quantity_difference),
                _money(row.internal_market_value),
                _money(row.alpaca_market_value),
            ]
            for row in rows
        ]

    @staticmethod
    def _format_reconciliation_summary_html(rows: Tuple[ReconciliationRow, ...]) -> str:
        """Concise counts only -- no percentage, ratio, or judgment. Every
        row belongs to exactly one status, so the four counts always sum
        to len(rows)."""
        counts = Counter(row.status for row in rows)
        parts = [
            f"{counts.get(ReconciliationStatus.MATCHED, 0)} matched",
            f"{counts.get(ReconciliationStatus.QUANTITY_DIFFERENCE, 0)} quantity difference",
            f"{counts.get(ReconciliationStatus.INTERNAL_ONLY, 0)} internal only",
            f"{counts.get(ReconciliationStatus.BROKER_ONLY, 0)} broker only",
        ]
        return (
            '<div class="pi-reconciliation-summary">'
            f'{html.escape(" · ".join(parts))}</div>'
        )

    @staticmethod
    def _format_disclosure_html(screen: PortfolioScreen) -> str:
        if screen.capital_is_available and screen.holdings_is_available:
            return _REAL_DATA_HTML
        if screen.capital_is_available:
            return _PARTIAL_DATA_HTML
        return _UNAVAILABLE_DATA_HTML

    # Impeccable critique finding #5: of these seven capital metrics, only
    # "Realized Profit" is a signed P&L figure that can meaningfully be
    # negative in this domain (Allocated/Available Cash/Invested/Reserve/
    # Tradeable Cash/Total Value are not) -- so it is the one label this
    # set's negative-value modifier below is keyed to.
    _NEGATIVE_ELIGIBLE_CAPITAL_METRIC = "Realized Profit"

    @staticmethod
    def _format_capital_summary_html(capital: CapitalSummary) -> str:
        fields = [
            ("Allocated", capital.allocated_amount),
            ("Available Cash", capital.available_cash),
            ("Invested", capital.invested_amount),
            ("Reserve", capital.reserve),
            ("Tradeable Cash", capital.tradeable_cash),
            ("Total Value", capital.total_value),
            ("Realized Profit", capital.realized_profit),
        ]

        def _value_class(label: str, value: float) -> str:
            is_negative = (
                label == PortfolioIntelligenceUI._NEGATIVE_ELIGIBLE_CAPITAL_METRIC
                and value < 0
            )
            return "pi-metric-value" + (" pi-metric-value--negative" if is_negative else "")

        metrics_html = "".join(
            '<div class="pi-metric">'
            f'<span class="pi-metric-label aara-metric-label">{html.escape(label)}</span>'
            f'<span class="{_value_class(label, value)}">${value:,.2f}</span>'
            "</div>"
            for label, value in fields
        )
        return f'<div class="pi-capital-summary">{metrics_html}</div>'

    @staticmethod
    def _format_allocation_html(capital: CapitalSummary) -> str:
        invested_pct = capital.invested_weight_pct
        cash_pct = capital.cash_weight_pct
        return (
            '<div class="pi-allocation-bar">'
            f'<div class="invested" style="width:{invested_pct:.1f}%;"></div>'
            f'<div class="cash" style="width:{cash_pct:.1f}%;"></div>'
            "</div>"
            '<div class="pi-allocation-legend">'
            f'<span class="invested"><span class="swatch"></span>Invested {invested_pct:.1f}%</span>'
            f'<span class="cash"><span class="swatch"></span>Cash {cash_pct:.1f}%</span>'
            "</div>"
        )

    @staticmethod
    def _format_holdings_rows(holdings: Tuple[PortfolioHolding, ...]) -> List[List[str]]:
        return [
            [
                holding.symbol,
                f"{holding.quantity:g}",
                f"${holding.price:,.2f}",
                f"${holding.market_value:,.2f}",
                f"{holding.weight_pct:.1f}%",
            ]
            for holding in holdings
        ]

    @staticmethod
    def _format_holding_allocation_html(holdings: Tuple[PortfolioHolding, ...]) -> str:
        """Visual Dashboard Phase B: one bar per holding -- symbol +
        allocation percentage. weight_pct is already the authoritative,
        live-priced figure PortfolioHolding carries (see bootstrap.py's
        _build_portfolio_holdings, which computes it as this holding's
        share of total holdings market value) -- reused verbatim here,
        never recomputed, never a new valuation. Deterministic order:
        weight_pct descending (the most useful reading order for "what am
        I most exposed to"), ties broken alphabetically by symbol so the
        same inputs always render the same order. One decimal place only
        -- matches the Holdings table's own Weight % column -- avoids
        implying false precision."""
        ordered = sorted(holdings, key=lambda h: (-h.weight_pct, h.symbol))
        rows = "".join(
            '<div class="pi-holding-allocation-row">'
            f'<span class="pi-holding-allocation-symbol">{html.escape(holding.symbol)}</span>'
            '<div class="pi-holding-allocation-bar">'
            f'<div class="fill" style="width:{max(0.0, min(100.0, holding.weight_pct)):.1f}%"></div>'
            "</div>"
            f'<span class="pi-holding-allocation-pct">{holding.weight_pct:.1f}%</span>'
            "</div>"
            for holding in ordered
        )
        return f'<div class="pi-holding-allocation-list">{rows}</div>'

    @staticmethod
    def _format_empty_message_html(screen: PortfolioScreen) -> str:
        return f'<div class="pi-empty-message aara-empty">{html.escape(screen.empty_state_message)}</div>'

    @staticmethod
    def _format_portfolio_history_dataframe(
        points: Tuple[PortfolioHistoryPoint, ...],
    ) -> pd.DataFrame:
        """Two real columns only -- each point's own as_of instant and its
        own portfolio_value, verbatim from portfolio_snapshots. No derived
        column (return, drawdown, or any other computed metric) is ever
        added here."""
        return pd.DataFrame(
            {
                "as_of": [pd.Timestamp(point.as_of) for point in points],
                "portfolio_value": [point.portfolio_value for point in points],
            }
        )

    @staticmethod
    def _format_alpaca_account_html(account: AlpacaAccountSnapshot) -> str:
        fields = [
            ("Equity", account.equity),
            ("Cash", account.cash),
            ("Buying Power", account.buying_power),
            ("Portfolio Value", account.portfolio_value),
        ]
        metrics_html = "".join(
            '<div class="pi-metric">'
            f'<span class="pi-metric-label aara-metric-label">{html.escape(label)}</span>'
            f'<span class="pi-metric-value">${value:,.2f}</span>'
            "</div>"
            for label, value in fields
        )
        return f'<div class="pi-capital-summary">{metrics_html}</div>'

    @staticmethod
    def _format_alpaca_positions_rows(positions: Tuple[AlpacaPosition, ...]) -> List[List[str]]:
        return [
            [
                position.symbol,
                f"{position.quantity:g}",
                f"${position.avg_entry_price:,.2f}",
                f"${position.current_price:,.2f}",
                f"${position.market_value:,.2f}",
                f"${position.unrealized_pl:,.2f}",
                f"{position.unrealized_plpc * 100:.2f}%",
                position.side,
            ]
            for position in positions
        ]

    @staticmethod
    def _format_alpaca_orders_rows(orders: Tuple[AlpacaOrder, ...]) -> List[List[str]]:
        """side/status are rendered exactly as the broker returned them.
        The working/pending flag is surfaced in its own column, never by
        rewriting the status string. order_id is intentionally not
        rendered -- it is an internal dedupe/sort key, not a decision
        identifier."""
        return [
            [
                _format_order_timestamp(order.submitted_at),
                order.symbol,
                order.side,
                order.order_type,
                order.quantity,
                order.filled_quantity,
                order.limit_price,
                order.status,
                _ALPACA_ORDERS_WORKING_MARKER if order.is_working else "",
                _format_order_timestamp(order.filled_at),
            ]
            for order in orders
        ]
