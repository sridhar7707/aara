"""Gradio shell for Portfolio Intelligence.

Self-contained: does not import ui/decision_center/ (no gradio_view.py,
theme.py, screen.py, or mock_data.py cross-import). Renders whatever
PortfolioScreen it is given. The production path (bootstrap.py's
_build_portfolio_intelligence_ui) assembles the screen from
adapters.legacy_capital_source.LegacyCapitalSource,
adapters.legacy_position_source.LegacyPositionSource, and
adapters.live_price_source.LivePriceSource; any section whose real source
is unavailable renders an explicit unavailable state -- this module never
imports mock_data.py and the default (no `screen` supplied) is an
all-unavailable PortfolioScreen(), never a fabricated one. No controller,
no service, no sentinel_engine/bot import. Wired into main.py/bootstrap.py
as the 2nd Trading Intelligence tab.

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
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

import gradio as gr

from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    AlpacaAccountSnapshot,
    AlpacaOrder,
    AlpacaPosition,
    CapitalSummary,
    PortfolioHolding,
    PortfolioScreen,
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
    f'<div class="pi-disclosure-title">{html.escape(_UNAVAILABLE_DATA_TITLE)}</div>'
    f'<div class="pi-disclosure-body">{html.escape(_UNAVAILABLE_DATA_BODY)}</div>'
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
    f'<div class="pi-disclosure-title">{html.escape(_PARTIAL_DATA_TITLE)}</div>'
    f'<div class="pi-disclosure-body">{html.escape(_PARTIAL_DATA_BODY)}</div>'
    "</div>"
)

# Per-section unavailable notes (rendered in place of the Capital Summary
# metrics / Allocation bar / Holdings table when their real source is not
# available). Styled with .pi-unavailable -- the same look the Alpaca
# sections' own unavailable state already uses.
_CAPITAL_UNAVAILABLE_MESSAGE = (
    "Capital Summary is not available -- the managed capital pool could "
    "not be read in this environment."
)
_HOLDINGS_UNAVAILABLE_MESSAGE = (
    "Holdings are not available -- open-position data or live prices "
    "could not be read in this environment."
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
    f'<div class="pi-disclosure-title">{html.escape(_REAL_DATA_TITLE)}</div>'
    f'<div class="pi-disclosure-body">{html.escape(_REAL_DATA_BODY)}</div>'
    "</div>"
)

_PAGE_HEADER_HTML = (
    '<div class="pi-page-header">'
    "<h2>Portfolio Intelligence</h2>"
    '<div class="pi-subtitle">Holdings, capital allocation, and current exposure</div>'
    "</div>"
)


class PortfolioIntelligenceUI:
    def __init__(self, screen: PortfolioScreen = None):
        """The default screen (no `screen` supplied) is an explicit
        all-unavailable `PortfolioScreen()` -- never a mock/illustrative
        screen. `_capital_is_real` / `_holdings_is_real` are derived
        solely from the screen's own availability (`capital_is_available`
        / `holdings_is_available`), so the disclosure banner can never
        contradict what the sections actually render."""
        self._screen = screen if screen is not None else PortfolioScreen()
        self._capital_is_real = self._screen.capital_is_available
        self._holdings_is_real = self._screen.holdings_is_available

    def build(self) -> gr.Blocks:
        with gr.Blocks(
            title="AARA Trading Intelligence — Portfolio Intelligence", css=CSS,
        ) as demo:
            gr.HTML(SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(build_shell_nav_html("Portfolio Intelligence"), elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML)
            gr.HTML(self._format_disclosure_html())

            gr.HTML('<div class="pi-section-label">Capital Summary</div>')
            if self._screen.capital_is_available:
                gr.HTML(self._format_capital_summary_html(self._screen.capital))
            else:
                gr.HTML(self._format_unavailable_html(_CAPITAL_UNAVAILABLE_MESSAGE))

            gr.HTML('<div class="pi-section-label">Capital Allocation</div>')
            if self._screen.capital_is_available:
                gr.HTML(self._format_allocation_html(self._screen.capital))
            else:
                gr.HTML(self._format_unavailable_html(_CAPITAL_UNAVAILABLE_MESSAGE))

            gr.HTML('<div class="pi-section-label">Holdings</div>')
            if not self._screen.holdings_is_available:
                gr.HTML(self._format_unavailable_html(_HOLDINGS_UNAVAILABLE_MESSAGE))
            elif self._screen.is_empty:
                gr.HTML(self._format_empty_message_html(self._screen))
            else:
                gr.Dataframe(
                    headers=_HOLDINGS_HEADERS,
                    value=self._format_holdings_rows(self._screen.holdings),
                    datatype=["str", "str", "str", "str", "str"],
                    interactive=False,
                    label="Holdings",
                    show_label=False,
                    elem_classes=["pi-holdings-table"],
                    **{_DATAFRAME_HEIGHT_KWARG: 320},
                )

            gr.HTML(
                f'<div class="pi-section-label">Alpaca Paper Account '
                f'<span class="pi-alpaca-badge">{html.escape(_ALPACA_PAPER_BADGE_TEXT)}</span></div>'
            )
            if not self._screen.alpaca_is_available:
                gr.HTML(f'<div class="pi-alpaca-unavailable">{html.escape(_ALPACA_UNAVAILABLE_MESSAGE)}</div>')
            else:
                gr.HTML(self._format_alpaca_account_html(self._screen.alpaca_account))
                if len(self._screen.alpaca_positions) == 0:
                    gr.HTML(
                        f'<div class="pi-empty-message">'
                        f'{html.escape(self._screen.alpaca_empty_state_message)}</div>'
                    )
                else:
                    gr.Dataframe(
                        headers=_ALPACA_POSITIONS_HEADERS,
                        value=self._format_alpaca_positions_rows(self._screen.alpaca_positions),
                        datatype=["str"] * len(_ALPACA_POSITIONS_HEADERS),
                        interactive=False,
                        label="Alpaca Paper Positions",
                        show_label=False,
                        elem_classes=["pi-alpaca-positions-table"],
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
            if not self._screen.alpaca_orders_available:
                gr.HTML(
                    f'<div class="pi-alpaca-unavailable">'
                    f'{html.escape(_ALPACA_ORDERS_UNAVAILABLE_MESSAGE)}</div>'
                )
            elif self._screen.alpaca_orders.is_empty:
                gr.HTML(
                    f'<div class="pi-empty-message">'
                    f'{html.escape(self._screen.alpaca_orders_empty_state_message)}</div>'
                )
            else:
                if self._screen.alpaca_orders.truncated:
                    gr.HTML(
                        f'<div class="pi-alpaca-orders-truncation">'
                        f'{html.escape(_ALPACA_ORDERS_TRUNCATION_NOTE)}</div>'
                    )
                gr.Dataframe(
                    headers=_ALPACA_ORDERS_HEADERS,
                    value=self._format_alpaca_orders_rows(self._screen.alpaca_orders.orders),
                    datatype=["str"] * len(_ALPACA_ORDERS_HEADERS),
                    interactive=False,
                    label="Alpaca Paper Recent Orders",
                    show_label=False,
                    elem_classes=["pi-alpaca-orders-table"],
                    **{_DATAFRAME_HEIGHT_KWARG: 320},
                )

        return demo

    def _format_disclosure_html(self) -> str:
        if self._capital_is_real and self._holdings_is_real:
            return _REAL_DATA_HTML
        if self._capital_is_real:
            return _PARTIAL_DATA_HTML
        return _UNAVAILABLE_DATA_HTML

    @staticmethod
    def _format_unavailable_html(message: str) -> str:
        return f'<div class="pi-unavailable">{html.escape(message)}</div>'

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
        metrics_html = "".join(
            '<div class="pi-metric">'
            f'<span class="pi-metric-label">{html.escape(label)}</span>'
            f'<span class="pi-metric-value">${value:,.2f}</span>'
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
    def _format_empty_message_html(screen: PortfolioScreen) -> str:
        return f'<div class="pi-empty-message">{html.escape(screen.empty_state_message)}</div>'

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
            f'<span class="pi-metric-label">{html.escape(label)}</span>'
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
