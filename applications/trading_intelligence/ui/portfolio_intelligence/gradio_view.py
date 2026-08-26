"""Gradio shell for Portfolio Intelligence -- illustrative MVP.

Self-contained: does not import ui/decision_center/ (no gradio_view.py,
theme.py, screen.py, or mock_data.py cross-import). Renders mock_data.py's
PortfolioScreen only -- no controller, no service, no sentinel_engine/bot
import. Wired into main.py/bootstrap.py as the 2nd Trading Intelligence tab.

AARA shell consistency pass: renders the same AARA logo header + inter-screen
nav Decision Center shows, via `ui/shell.py` (a sibling of all three screen
packages, not `ui/decision_center/` -- see that module's own docstring for
why this doesn't violate this package's self-containment). No new CSS is
added here; `.aara-shell-header`/`.aara-shell-nav`/`.nav-item` and the tokens
they use are Decision Center's theme.py rules, already merged into the
composed app's single stylesheet by `bootstrap.py`.
"""
import html
from typing import List, Tuple

import gradio as gr

from applications.trading_intelligence.ui.portfolio_intelligence.mock_data import build_mock_screen
from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
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

_ILLUSTRATIVE_DATA_TITLE = "Illustrative Data"
_ILLUSTRATIVE_DATA_BODY = (
    "The holdings and capital figures shown here are illustrative and are "
    "not real trading activity or a real account balance."
)
_ILLUSTRATIVE_DATA_HTML = (
    '<div class="pi-disclosure">'
    f'<div class="pi-disclosure-title">{html.escape(_ILLUSTRATIVE_DATA_TITLE)}</div>'
    f'<div class="pi-disclosure-body">{html.escape(_ILLUSTRATIVE_DATA_BODY)}</div>'
    "</div>"
)

# Used only when a real Capital Summary/Allocation was supplied (see
# PortfolioIntelligenceUI's capital_is_real param) -- the plain
# _ILLUSTRATIVE_DATA_HTML above would then be false: Capital Summary and
# Allocation are real managed-capital-pool figures at that point, only
# Holdings remains illustrative. Same title (still accurate -- part of the
# page is still illustrative), corrected body only.
_PARTIAL_ILLUSTRATIVE_DATA_BODY = (
    "Capital Summary and Allocation reflect the real managed capital "
    "pool. Holdings shown below is illustrative and is not real trading "
    "activity."
)
_PARTIAL_ILLUSTRATIVE_DATA_HTML = (
    '<div class="pi-disclosure">'
    f'<div class="pi-disclosure-title">{html.escape(_ILLUSTRATIVE_DATA_TITLE)}</div>'
    f'<div class="pi-disclosure-body">{html.escape(_PARTIAL_ILLUSTRATIVE_DATA_BODY)}</div>'
    "</div>"
)

_PAGE_HEADER_HTML = (
    '<div class="pi-page-header">'
    "<h2>Portfolio Intelligence</h2>"
    '<div class="pi-subtitle">Holdings, capital allocation, and current exposure</div>'
    "</div>"
)


class PortfolioIntelligenceUI:
    def __init__(self, screen: PortfolioScreen = None, capital_is_real: bool = False):
        """capital_is_real: True only when `screen.capital` was supplied
        from a real source (see bootstrap.py's use of
        adapters.legacy_capital_source.LegacyCapitalSource) -- controls
        only the disclosure wording below; Holdings' own rendering is
        completely unaffected and always illustrative in this unit."""
        self._screen = screen if screen is not None else build_mock_screen()
        self._capital_is_real = capital_is_real

    def build(self) -> gr.Blocks:
        with gr.Blocks(
            title="AARA Trading Intelligence — Portfolio Intelligence", css=CSS,
        ) as demo:
            gr.HTML(SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(build_shell_nav_html("Portfolio Intelligence"), elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML)
            gr.HTML(self._format_disclosure_html())

            gr.HTML('<div class="pi-section-label">Capital Summary</div>')
            gr.HTML(self._format_capital_summary_html(self._screen.capital))

            gr.HTML('<div class="pi-section-label">Capital Allocation</div>')
            gr.HTML(self._format_allocation_html(self._screen.capital))

            gr.HTML('<div class="pi-section-label">Holdings</div>')
            if self._screen.is_empty:
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

        return demo

    def _format_disclosure_html(self) -> str:
        return _PARTIAL_ILLUSTRATIVE_DATA_HTML if self._capital_is_real else _ILLUSTRATIVE_DATA_HTML

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
