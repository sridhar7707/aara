"""Browser end-to-end content coverage for Morning Brief, Portfolio
Intelligence, Risk Intelligence, Performance & Learning, and Settings.

Sprint 1 Phase 4: before this file, real-browser (Playwright) coverage
existed only for tab navigation (``test_navigation_e2e.py``, static
page-header markers only, never wired to real screen data) and for
Decision Center's evidence cards (``test_decision_center_evidence_e2e.py``).
The other five screens' own real rendering -- the actual data-mapping /
visibility logic each screen's ``gradio_view.py`` runs on ``demo.load()`` --
had no browser-level proof it produces real DOM text, only unit-level
proof via ``block.value``/``block.visible`` on the Python return value
(``test_*_gradio_view.py``). This file closes that gap the same way the
two existing e2e files closed theirs: build each screen's real UI class
directly with a hand-seeded, real dataclass screen (the exact same
``XxxScreen`` shape ``bootstrap.py`` itself produces from real data -- not
a fabricated bootstrap/database layer), launch it as a real local Gradio
server, and assert the actual rendered DOM contains the expected content
after ``demo.load()`` populates it.

Deterministic and offline: every fixture screen below is hand-built from
each package's own real dataclasses (``PortfolioScreen``, ``RiskScreen``,
``MorningBriefScreen``, ``PerformanceLearningScreen``) -- no trades.db, no
HuggingFace snapshot, no live market data, no bootstrap of the full
six-screen app. Settings has no wired data source at all in production
(see ``ui/settings/mock_data.py``), so its test uses the exact same
default ``SettingsUI()`` bootstrap.py itself constructs.

Each test also asserts at least one honest empty/unavailable state
alongside the populated content, so a screen never appears to silently
drop its own "no data" messaging when other sections are real.

No fabricated timestamps, prices, portfolio values, or outcomes: every
figure asserted below is a value this file itself put into the seed
screen, echoed back, not a number invented to make an assertion pass.

Isolation / opt-out, identical to the other two e2e files:
  * Skipped (not failed) if ``playwright.sync_api`` cannot be imported, or
    if the Playwright driver / Chromium binary is not installed.

Run just this file:
    python -m pytest applications/trading_intelligence/ui/tests/test_content_screens_e2e.py -q
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

_sync_api = pytest.importorskip("playwright.sync_api")

from applications.platform.integrations import IntegrationHealth  # noqa: E402
from applications.trading_intelligence.ui.morning_brief.gradio_view import (  # noqa: E402
    MorningBriefUI,
)
from applications.trading_intelligence.ui.morning_brief.mock_data import (  # noqa: E402
    build_mock_screen as build_morning_brief_mock_screen,
)
from applications.trading_intelligence.ui.morning_brief.screen import (  # noqa: E402
    PortfolioHistoryPoint as MorningBriefPortfolioHistoryPoint,
)
from applications.trading_intelligence.ui.performance_learning.gradio_view import (  # noqa: E402
    PerformanceLearningUI,
)
from applications.trading_intelligence.ui.performance_learning.mock_data import (  # noqa: E402
    build_mock_screen as build_performance_learning_mock_screen,
)
from applications.trading_intelligence.ui.performance_learning.screen import (  # noqa: E402
    ATTRIBUTION_BREAKDOWN_TITLE,
    OutcomeHistoryRow,
)
from applications.trading_intelligence.ui.portfolio_intelligence.gradio_view import (  # noqa: E402
    PortfolioIntelligenceUI,
    _ALPACA_UNAVAILABLE_MESSAGE,
)
from applications.trading_intelligence.ui.portfolio_intelligence.screen import (  # noqa: E402
    AlpacaAccountSnapshot,
    CapitalSummary,
    PortfolioHistoryPoint,
    PortfolioHolding,
    PortfolioScreen,
    ReconciliationRow,
    ReconciliationStatus,
)
from applications.trading_intelligence.ui.risk_intelligence.gradio_view import (  # noqa: E402
    RiskIntelligenceUI,
)
from applications.trading_intelligence.ui.risk_intelligence.screen import (  # noqa: E402
    CURRENT_RISK_PARAMETERS,
    ConcentrationHolding,
    DrawdownPoint,
    RiskScreen,
    RiskSnapshot,
)
from applications.trading_intelligence.ui.settings.gradio_view import (  # noqa: E402
    SettingsUI,
)
from applications.trading_intelligence.ui.settings.mock_data import (  # noqa: E402
    build_mock_screen as build_settings_mock_screen,
)

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

_TIMEOUT_MS = 20_000
_PROVIDER = "e2e_seed"
_HEALTHY = IntegrationHealth.healthy(_PROVIDER)


@pytest.fixture(scope="module")
def browser():
    try:
        playwright = _sync_api.sync_playwright().start()
    except Exception as exc:  # noqa: BLE001 - Playwright/node driver bundle missing
        pytest.skip(f"Playwright runtime not available: {exc}")
    try:
        try:
            chromium = playwright.chromium.launch(headless=True)
        except _sync_api.Error as exc:  # Chromium binary not installed on this host
            pytest.skip(f"Chromium not available for Playwright: {exc}")
        try:
            yield chromium
        finally:
            chromium.close()
    finally:
        playwright.stop()


@contextmanager
def _launched_app(ui):
    """Launches any of the five screens' real UI object (already
    constructed with a seeded ``screen=``) as a real local Gradio server
    and yields its URL."""
    demo = ui.build()
    demo.launch(
        prevent_thread_lock=True, quiet=True, show_error=True, show_api=False,
        server_name="127.0.0.1", inbrowser=False,
    )
    try:
        yield demo.local_url
    finally:
        demo.close()


def _page_with_text(browser, url, expect_text):
    """Opens `url` and polls real DOM text (never a timer) until
    `expect_text` is actually visible -- the same synchronization
    ``test_decision_center_evidence_e2e.py`` uses to wait for
    ``demo.load()`` to have populated a screen's dynamic content."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=_TIMEOUT_MS)
    page.wait_for_function(
        """(needle) => document.body.innerText.includes(needle)""",
        arg=expect_text,
        timeout=_TIMEOUT_MS,
    )
    return context, page


# --- Morning Brief ---------------------------------------------------------


def test_morning_brief_renders_real_portfolio_snapshot_and_honest_unavailable_sections(
    browser,
):
    """A real Portfolio Snapshot summary renders verbatim, while the three
    still-unwired sections keep their own real, honest unavailable
    messages -- proving populated and unavailable states coexist correctly
    in the real DOM, not just in the Python return value."""
    base = build_morning_brief_mock_screen()
    seeded_summary = "Total value $125,430.50 ($42,100.00 cash, $83,330.50 invested)."
    screen = replace(
        base,
        portfolio_snapshot=replace(
            base.portfolio_snapshot,
            available_summary=seeded_summary,
            health=_HEALTHY,
            as_of="2026-09-01 09:00 CDT",
        ),
        portfolio_history=(
            MorningBriefPortfolioHistoryPoint(as_of="2026-08-25T00:00:00+00:00", portfolio_value=120000.0),
            MorningBriefPortfolioHistoryPoint(as_of="2026-09-01T00:00:00+00:00", portfolio_value=125430.50),
        ),
        portfolio_history_health=_HEALTHY,
    )
    ui = MorningBriefUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(browser, url, seeded_summary)
        try:
            visible_text = page.inner_text("body")
            assert seeded_summary in visible_text
            assert "2026-09-01 09:00 CDT" in visible_text
            # the three still-unwired sections keep their own real,
            # honest unavailable messages -- never silently dropped
            # alongside the populated Portfolio Snapshot section.
            assert base.market_mood_regime.unavailable_message in visible_text
            assert base.candidate_screening_summary.unavailable_message in visible_text
            assert base.overnight_holdings_news.unavailable_message in visible_text
        finally:
            context.close()


def test_morning_brief_portfolio_history_honest_empty_state(browser):
    """A HEALTHY read with zero rows in the recent window renders the
    honest 'no portfolio history' message, never a fabricated/empty chart
    presented as if it were data."""
    base = build_morning_brief_mock_screen()
    screen = replace(base, portfolio_history=(), portfolio_history_health=_HEALTHY)
    ui = MorningBriefUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(browser, url, "No portfolio history is recorded yet.")
        try:
            assert "No portfolio history is recorded yet." in page.inner_text("body")
        finally:
            context.close()


# --- Portfolio Intelligence -------------------------------------------------


def test_portfolio_intelligence_renders_real_capital_and_holdings_and_honest_alpaca_unavailable(
    browser,
):
    """Real Capital Summary figures and a real Holdings row render
    verbatim, while the separate, still-unwired Alpaca Paper section keeps
    its own real, honest unavailable message."""
    screen = PortfolioScreen(
        capital=CapitalSummary(
            allocated_amount=100_000.0, available_cash=42_000.0,
            invested_amount=58_000.0, reserve=5_000.0, realized_profit=1_200.0,
        ),
        holdings=(
            PortfolioHolding(
                symbol="AAPL", quantity=10.0, price=190.25,
                market_value=1_902.50, weight_pct=100.0,
            ),
        ),
        capital_health=_HEALTHY,
        holdings_health=_HEALTHY,
    )
    ui = PortfolioIntelligenceUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(browser, url, "AAPL")
        try:
            visible_text = page.inner_text("body")
            assert "AAPL" in visible_text
            assert "1,902.50" in visible_text or "1902.50" in visible_text
            # Alpaca Paper is a separate, independently-gated section --
            # its own real, honest unavailable message must still show.
            assert _ALPACA_UNAVAILABLE_MESSAGE in visible_text
        finally:
            context.close()


def test_portfolio_intelligence_holdings_honest_empty_state(browser):
    """Real holdings source connected but zero open positions -> the
    screen's own honest empty message, never a fabricated row."""
    screen = PortfolioScreen(
        capital=CapitalSummary(
            allocated_amount=50_000.0, available_cash=50_000.0,
            invested_amount=0.0, reserve=0.0, realized_profit=0.0,
        ),
        holdings=(),
        capital_health=_HEALTHY,
        holdings_health=_HEALTHY,
    )
    ui = PortfolioIntelligenceUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(browser, url, "No holdings recorded yet.")
        try:
            assert "No holdings recorded yet." in page.inner_text("body")
        finally:
            context.close()


def test_portfolio_intelligence_renders_the_reconciliation_section_with_real_seeded_rows(
    browser,
):
    """Internal vs Alpaca PAPER reconciliation: a MATCHED and a QUANTITY
    DIFFERENCE row, plus the summary counts, render in a real browser from
    seeded data. `.pi-section-label` is rendered visually all-caps via CSS
    text-transform (see theme.py) -- the section title is asserted
    case-insensitively, same as test_decision_center_evidence_e2e.py's own
    fix for the identical CSS pattern; row/summary values carry no such
    transform and are asserted with their real case."""
    screen = PortfolioScreen(
        capital=CapitalSummary(
            allocated_amount=100_000.0, available_cash=42_000.0,
            invested_amount=58_000.0, reserve=5_000.0, realized_profit=1_200.0,
        ),
        holdings=(
            PortfolioHolding(
                symbol="AAPL", quantity=10.0, price=190.25,
                market_value=1_902.50, weight_pct=100.0,
            ),
        ),
        capital_health=_HEALTHY,
        holdings_health=_HEALTHY,
        alpaca_account=AlpacaAccountSnapshot(
            equity=100_000.0, cash=50_000.0, buying_power=100_000.0,
            portfolio_value=100_000.0,
        ),
        alpaca_positions=(),
        alpaca_health=_HEALTHY,
        reconciliation=(
            ReconciliationRow(
                symbol="AAPL", status=ReconciliationStatus.MATCHED,
                internal_quantity=10.0, alpaca_quantity=10.0, quantity_difference=0.0,
            ),
            ReconciliationRow(
                symbol="MSFT", status=ReconciliationStatus.QUANTITY_DIFFERENCE,
                internal_quantity=4.0, alpaca_quantity=6.0, quantity_difference=-2.0,
            ),
        ),
    )
    ui = PortfolioIntelligenceUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(browser, url, "QUANTITY DIFFERENCE")
        try:
            visible_text = page.inner_text("body")
            assert "internal portfolio" in visible_text.lower()
            assert "reconciliation" in visible_text.lower()
            assert "MATCHED" in visible_text
            assert "QUANTITY DIFFERENCE" in visible_text
            assert "1 matched" in visible_text
            assert "1 quantity difference" in visible_text
        finally:
            context.close()


def test_portfolio_intelligence_reconciliation_honest_unavailable_state(browser):
    """Holdings unavailable -> the reconciliation section shows its own
    honest unavailable message -- never inferring a match when one source
    could not be read -- while the rest of the page keeps rendering."""
    screen = PortfolioScreen(
        capital=CapitalSummary(
            allocated_amount=50_000.0, available_cash=50_000.0,
            invested_amount=0.0, reserve=0.0, realized_profit=0.0,
        ),
        holdings=None,
        capital_health=_HEALTHY,
    )
    ui = PortfolioIntelligenceUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(
            browser, url, "Reconciliation is not available"
        )
        try:
            visible_text = page.inner_text("body")
            assert "Reconciliation is not available" in visible_text
            assert "Internal Portfolio" in visible_text
        finally:
            context.close()


def test_portfolio_intelligence_renders_the_value_chart_summary_and_timeframe_selection(
    browser,
):
    """Visual Dashboard Phase A + B: a real, multi-year seeded history
    (with a real intermediate dip, at 100 days ago, for the drawdown
    chart to show something other than a flat 0%) renders the value
    chart, the drawdown chart, the eight timeframe choices, and real
    ALL-timeframe summaries for both; selecting "1M" then re-filters BOTH
    charts consistently to real, different figures for that shorter
    window (Starting Value for the value chart; Max Drawdown for the
    drawdown chart, since the 100-days-ago dip falls outside a 30-day
    window) -- proving the single shared selector actually changes what's
    shown on both, purely client-triggered (no new fetch).
    Metric LABELS ("Current Value", "Starting Value", "Max Drawdown", ...)
    render visually all-caps via CSS text-transform (see design_system.py's
    shared .aara-metric-label, the same rule Capital Summary already
    uses) -- asserted case-insensitively, same fix already applied
    elsewhere in this file for the identical pattern. Dollar/percentage
    VALUES carry no such transform and are asserted with their real case."""
    now = datetime.now(timezone.utc)
    points = (
        PortfolioHistoryPoint(
            as_of=(now - timedelta(days=730)).isoformat(), portfolio_value=50_000.0,
        ),
        PortfolioHistoryPoint(
            as_of=(now - timedelta(days=180)).isoformat(), portfolio_value=80_000.0,
        ),
        # A real dip below the 80,000 peak-so-far, OUTSIDE the "1M" (30-day)
        # window -- (60,000 - 80,000) / 80,000 * 100 = -25.00%.
        PortfolioHistoryPoint(
            as_of=(now - timedelta(days=100)).isoformat(), portfolio_value=60_000.0,
        ),
        PortfolioHistoryPoint(
            as_of=(now - timedelta(days=20)).isoformat(), portfolio_value=95_000.0,
        ),
        PortfolioHistoryPoint(as_of=now.isoformat(), portfolio_value=100_000.0),
    )
    screen = PortfolioScreen(
        capital=CapitalSummary(
            allocated_amount=100_000.0, available_cash=0.0, invested_amount=100_000.0,
            reserve=0.0, realized_profit=0.0,
        ),
        capital_health=_HEALTHY,
        portfolio_history=points,
        portfolio_history_health=_HEALTHY,
    )
    ui = PortfolioIntelligenceUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(browser, url, "$100,000.00")
        try:
            visible_text = page.inner_text("body")
            assert "portfolio value over time" in visible_text.lower()
            assert "current value" in visible_text.lower()
            assert "starting value" in visible_text.lower()
            assert "drawdown" in visible_text.lower()
            assert "current drawdown" in visible_text.lower()
            assert "max drawdown" in visible_text.lower()
            for choice in ("1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "ALL"):
                assert choice in visible_text
            # Default timeframe is ALL: starting = the earliest real point;
            # max drawdown = the real -25.00% dip at 100 days ago.
            assert "$100,000.00" in visible_text  # current value
            assert "$50,000.00" in visible_text  # starting value (ALL)
            assert "-25.00%" in visible_text  # max drawdown (ALL)

            page.get_by_text("1M", exact=True).click()
            page.wait_for_function(
                """() => document.body.innerText.includes("$95,000.00")""",
                timeout=_TIMEOUT_MS,
            )
            visible_text_after = page.inner_text("body")
            # 1M's own window starts at the 20-days-ago point, not the
            # all-time earliest one -- a real, different, honest figure.
            assert "$95,000.00" in visible_text_after
            assert "$100,000.00" in visible_text_after  # current unchanged
            # The -25% dip (100 days ago) falls OUTSIDE the 1M window, so
            # the drawdown summary consistently updates too -- both charts
            # driven by the SAME one selector, the same state-held history.
            assert "-25.00%" not in visible_text_after
            assert "0.00%" in visible_text_after  # max/current drawdown within 1M
        finally:
            context.close()


def test_portfolio_intelligence_history_honest_unavailable_state_no_summary(browser):
    """Portfolio history unavailable -> its own honest unavailable message,
    and no summary block is fabricated alongside it."""
    screen = PortfolioScreen(
        capital=CapitalSummary(
            allocated_amount=50_000.0, available_cash=50_000.0,
            invested_amount=0.0, reserve=0.0, realized_profit=0.0,
        ),
        capital_health=_HEALTHY,
        portfolio_history=None,
    )
    ui = PortfolioIntelligenceUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(
            browser, url, "Portfolio value history is not available"
        )
        try:
            visible_text = page.inner_text("body")
            assert "Portfolio value history is not available" in visible_text
            assert "Current Value" not in visible_text
        finally:
            context.close()


def test_portfolio_intelligence_renders_allocation_by_holding(browser):
    """Visual Dashboard Phase B: real seeded holdings render as a symbol +
    allocation-percentage visualization, in a real browser, deterministically
    ordered by weight descending. ".pi-section-label" is rendered visually
    all-caps via CSS text-transform (see theme.py) -- asserted case-
    insensitively; the symbol/percentage values carry no such transform."""
    screen = PortfolioScreen(
        capital=CapitalSummary(
            allocated_amount=100_000.0, available_cash=40_000.0, invested_amount=60_000.0,
            reserve=0.0, realized_profit=0.0,
        ),
        capital_health=_HEALTHY,
        holdings=(
            PortfolioHolding(
                symbol="AAPL", quantity=10.0, price=190.25,
                market_value=1_902.50, weight_pct=63.2,
            ),
            PortfolioHolding(
                symbol="MSFT", quantity=2.0, price=555.0,
                market_value=1_110.0, weight_pct=36.8,
            ),
        ),
        holdings_health=_HEALTHY,
    )
    ui = PortfolioIntelligenceUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(browser, url, "63.2%")
        try:
            visible_text = page.inner_text("body")
            assert "allocation by holding" in visible_text.lower()
            assert "AAPL" in visible_text and "63.2%" in visible_text
            assert "MSFT" in visible_text and "36.8%" in visible_text
            # deterministic ordering: higher weight (AAPL) before lower (MSFT).
            assert visible_text.index("AAPL") < visible_text.index("MSFT")
        finally:
            context.close()


def test_portfolio_intelligence_allocation_by_holding_honest_empty_state(browser):
    """Real holdings source connected but zero open positions -> the same
    honest empty message Holdings itself already shows, never a fabricated
    allocation bar."""
    screen = PortfolioScreen(
        capital=CapitalSummary(
            allocated_amount=50_000.0, available_cash=50_000.0,
            invested_amount=0.0, reserve=0.0, realized_profit=0.0,
        ),
        capital_health=_HEALTHY,
        holdings=(),
        holdings_health=_HEALTHY,
    )
    ui = PortfolioIntelligenceUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(browser, url, "No holdings recorded yet.")
        try:
            assert "No holdings recorded yet." in page.inner_text("body")
        finally:
            context.close()


# --- Risk Intelligence ------------------------------------------------------


def test_risk_intelligence_renders_real_current_state_and_drawdown_and_honest_history_message(
    browser,
):
    """A real current risk state renders (with the observed-not-enforced
    disclosure) alongside a real, populated drawdown chart and its
    non-causal disclaimer; the risk-evaluation-history table -- which this
    data source structurally never populates -- keeps its own honest
    'not recorded' message rather than an empty table. Also proves the
    Concentration/Parameters/Drawdown-Context sprint's three additions:
    a real concentration bar list with the largest-holding one-liner, the
    static Risk Parameters card, and the current-drawdown-context line
    near Current State -- all from real seeded data, in the real browser."""
    screen = RiskScreen(
        current=RiskSnapshot(state="WARNING", as_of="2026-09-01 09:00 CDT"),
        state_health=_HEALTHY,
        drawdown_history=(
            DrawdownPoint(as_of="2026-08-25T00:00:00+00:00", portfolio_value=100_000.0, drawdown_pct=0.0),
            DrawdownPoint(as_of="2026-09-01T00:00:00+00:00", portfolio_value=95_000.0, drawdown_pct=5.0),
        ),
        drawdown_history_health=_HEALTHY,
        concentration_holdings=(
            ConcentrationHolding(symbol="AAPL", weight_pct=65.0),
            ConcentrationHolding(symbol="MSFT", weight_pct=35.0),
        ),
        concentration_health=_HEALTHY,
    )
    ui = RiskIntelligenceUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(browser, url, "WARNING")
        try:
            visible_text = page.inner_text("body")
            assert "WARNING" in visible_text
            assert "2026-09-01 09:00 CDT" in visible_text
            assert "Independently observed" in visible_text
            assert "Risk evaluation history is not recorded in this data source." in visible_text
            # Current drawdown context, near Current State.
            assert "Portfolio down 5.0% from peak." in visible_text
            # Concentration: largest-holding one-liner + both symbols.
            assert "Largest single holding: AAPL (65.0%)." in visible_text
            assert "AAPL" in visible_text and "MSFT" in visible_text
            assert "65.0%" in visible_text and "35.0%" in visible_text
            # .ri-section-label is rendered visually all-caps via CSS
            # text-transform -- assert case-insensitively on the label,
            # matching every other screen's own convention in this file.
            assert "concentration" in visible_text.lower()
            # Risk Parameters: static card, all six values present. Labels
            # render visually all-caps via CSS text-transform (.record-label,
            # see theme.py) -- assert case-insensitively on labels, exact
            # case on values, matching this file's own established
            # convention for the same CSS class elsewhere.
            assert "risk parameters" in visible_text.lower()
            lowered_visible_text = visible_text.lower()
            for param in CURRENT_RISK_PARAMETERS:
                assert param.label.lower() in lowered_visible_text
                assert param.value_display in visible_text
        finally:
            context.close()


def test_risk_intelligence_honest_unavailable_state(browser):
    """No real risk source in this environment -> the screen's single
    explicit UNAVAILABLE message for Current State, plus the independent
    honest unavailable message for Concentration -- never a fabricated
    state badge or holding. Risk Parameters is static and still renders
    (it is not gated on any data source)."""
    ui = RiskIntelligenceUI()  # production default: unavailable RiskScreen()
    with _launched_app(ui) as url:
        context, page = _page_with_text(browser, url, "Risk Intelligence data is currently unavailable.")
        try:
            visible_text = page.inner_text("body")
            assert "Risk Intelligence data is currently unavailable." in visible_text
            assert "Concentration is not available" in visible_text
            assert "risk parameters" in visible_text.lower()
            for param in CURRENT_RISK_PARAMETERS:
                assert param.value_display in visible_text
        finally:
            context.close()


# --- Performance & Learning --------------------------------------------------


def test_performance_learning_renders_real_outcome_and_loss_review_and_honest_attribution_unavailable(
    browser,
):
    """A real Outcome History row and the Sprint 1 Phase 3 loss-review
    callout render verbatim, while the still-unwired Attribution Breakdown
    area keeps its own real, honest unavailable message."""
    row = OutcomeHistoryRow(
        decision="AMZN BUY · trade-38", entry_date="2026-07-16 11:50 CDT",
        status="CLOSED", exit_date="2026-09-02 09:33 CDT", holding_days="47",
        realized_pnl_usd="-27.77", realized_pnl_pct="-0.23%", exit_basis="Bot fill",
        pairing_method="WINDOW_SINGLE_BOT_EXIT", pairing_confidence="HIGH",
        direction="LOSS",
    )
    base = build_performance_learning_mock_screen()
    loss_review_summary = (
        "1 of 1 closed BUY decisions realized a loss. "
        "Realized loss range: -0.23% to -0.23%. Holding period: 47 days."
    )
    screen = replace(
        base,
        outcome_rows=(row,),
        outcome_health=_HEALTHY,
        summary="1 BUY decisions — 1 CLOSED · 0 PARTIAL · 0 OPEN · 0 AMBIGUOUS.",
        win_rate_summary="Not enough completed trades yet for a win rate (1 of 30 needed).",
        loss_review_summary=loss_review_summary,
    )
    ui = PerformanceLearningUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(browser, url, "AMZN BUY")
        try:
            visible_text = page.inner_text("body")
            assert "AMZN BUY" in visible_text
            assert "-27.77" in visible_text
            assert loss_review_summary in visible_text
            # .pl-section-label is rendered visually all-caps via CSS
            # text-transform (see theme.py) -- assert case-insensitively on
            # the label, matching what a real user visually sees, same as
            # test_decision_center_evidence_e2e.py's own RECOMMENDATION NOW
            # case-insensitive check.
            assert ATTRIBUTION_BREAKDOWN_TITLE.lower() in visible_text.lower()
            assert base.attribution_breakdown.unavailable_message in visible_text
        finally:
            context.close()


def test_performance_learning_outcome_history_shows_the_decision_center_reference(browser):
    """2. Performance & Learning displays the Decision Center reference for
    a resolvable outcome -- the "Decision ID" column, a clean standalone
    identity (not the existing composite "AMZN BUY · trade-38" text) --
    proven against a real seeded row in a real browser render."""
    row = OutcomeHistoryRow(
        decision="AMZN BUY · trade-38", entry_date="2026-07-16 11:50 CDT",
        status="CLOSED", exit_date="2026-09-02 09:33 CDT", holding_days="47",
        realized_pnl_usd="-27.77", realized_pnl_pct="-0.23%", exit_basis="Bot fill",
        pairing_method="WINDOW_SINGLE_BOT_EXIT", pairing_confidence="HIGH",
        direction="LOSS", decision_reference="trade-38",
    )
    base = build_performance_learning_mock_screen()
    screen = replace(
        base,
        outcome_rows=(row,),
        outcome_health=_HEALTHY,
        summary="1 BUY decisions — 1 CLOSED · 0 PARTIAL · 0 OPEN · 0 AMBIGUOUS.",
    )
    ui = PerformanceLearningUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(browser, url, "trade-38")
        try:
            # The new column header itself -- proves the reference column
            # actually rendered, not merely that "trade-38" already appears
            # as a substring inside the pre-existing "decision" column.
            assert page.locator("th", has_text="Decision ID").count() > 0
            visible_text = page.inner_text("body")
            assert "trade-38" in visible_text
        finally:
            context.close()


def test_performance_learning_honest_empty_outcome_history(browser):
    """A HEALTHY read with zero BUY decisions -> the honest empty message,
    never a fabricated row or a fabricated loss-review sentence."""
    base = build_performance_learning_mock_screen()
    screen = replace(
        base,
        outcome_rows=(),
        outcome_health=_HEALTHY,
        summary="0 BUY decisions — 0 CLOSED · 0 PARTIAL · 0 OPEN · 0 AMBIGUOUS.",
    )
    ui = PerformanceLearningUI(screen=screen)
    with _launched_app(ui) as url:
        context, page = _page_with_text(
            browser, url, "No BUY decisions are present in the current trades snapshot."
        )
        try:
            assert (
                "No BUY decisions are present in the current trades snapshot."
                in page.inner_text("body")
            )
        finally:
            context.close()


# --- Settings ----------------------------------------------------------------


def test_settings_renders_the_real_default_preferences_and_honest_thresholds_unavailable(
    browser,
):
    """Settings has no wired configuration source in production at all --
    ``SettingsUI()`` with no override IS the real content bootstrap.py
    itself renders. Asserts the two real allow-listed preferences and
    Thresholds' own real, honest unavailable message."""
    mock = build_settings_mock_screen()
    ui = SettingsUI()  # production default -- same object bootstrap.py builds
    with _launched_app(ui) as url:
        context, page = _page_with_text(browser, url, "Display Theme")
        try:
            visible_text = page.inner_text("body")
            assert "Display Theme" in visible_text
            assert "Show In-App Notifications" in visible_text
            assert mock.thresholds.unavailable_message in visible_text
        finally:
            context.close()
