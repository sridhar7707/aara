"""Browser end-to-end coverage for Decision Center's Sprint 7 "Evidence
Since Decision" evidence cards: news-cache-diff, recommendation-change, and
earnings-proximity.

Why this file exists: ``test_gradio_view.py`` already has thorough unit
coverage calling ``DecisionCenterUI._format_news_cache_diff_html()`` and
``._render_detail()`` directly, and ``tests/check_ui.py`` (Playwright against
``dashboard/app.py``) asserts a *different*, unrelated "Decision Center"
section that belongs to the legacy TradeGenius dashboard, not this product
-- extending that file would not exercise Sprint 7's evidence cards at all.
This file closes that gap the same way ``test_navigation_e2e.py`` closes the
equivalent gap for tab navigation: build the real ``DecisionCenterUI`` with a
fake controller (the same duck-typed fixture ``test_gradio_view.py`` already
uses), launch it as a real Gradio server, and assert the actual rendered DOM
-- not just the Python return value -- contains each evidence category's
content after ``demo.load()`` populates it.

Deterministic and offline: the fake controller returns fixed, hand-built
evidence objects -- no trades.db, no HuggingFace snapshot, no live market
data, no bootstrap of the full six-screen app.

Isolation / opt-out, identical to test_navigation_e2e.py:
  * Skipped (not failed) if ``playwright.sync_api`` cannot be imported, or if
    the Playwright driver / Chromium binary is not installed.

Run just this file:
    python -m pytest applications/trading_intelligence/ui/tests/test_decision_center_evidence_e2e.py -q
"""
from __future__ import annotations

import datetime
import os
from contextlib import contextmanager

import pytest

_sync_api = pytest.importorskip("playwright.sync_api")

from applications.trading_intelligence.adapters.legacy_earnings_source import (  # noqa: E402
    EarningsSnapshot,
)
from applications.trading_intelligence.projections.decision_view import (  # noqa: E402
    DecisionState,
    DecisionView,
)
from applications.trading_intelligence.services.news_cache_snapshot_diff import (  # noqa: E402
    NewsCacheSnapshotDiff,
)
from applications.trading_intelligence.services.recommendation_diff import (  # noqa: E402
    RecommendationDiff,
)
from applications.trading_intelligence.ui.decision_center.gradio_view import (  # noqa: E402
    DecisionCenterUI,
)
from applications.trading_intelligence.ui.decision_center.screen import (  # noqa: E402
    DecisionCenterScreen,
    DecisionDetailArea,
    DecisionListArea,
)

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

_TIMEOUT_MS = 20_000
_DECISION_ID = "dec-e2e-001"


def _make_view() -> DecisionView:
    return DecisionView(
        decision_id=_DECISION_ID,
        symbol="AAPL",
        action="BUY",
        status=DecisionState.DECISION_CREATED,
        confidence=0.82,
        updated_at=datetime.datetime(2026, 8, 8, 9, 0, 0),
    )


class _FakeController:
    """Minimal duck-typed stand-in for DecisionCenterController -- the same
    fixture shape ``test_gradio_view.py``'s ``_FakeController`` uses, kept
    local so this file has no dependency on that test module."""

    def __init__(self, screen, detail_area):
        self._screen = screen
        self._detail_area = detail_area

    def load_screen(self, decision_ids, selected_id=None):
        return self._screen

    def load_decision_detail(self, decision_id):
        return self._detail_area

    def load_decisions(self, decision_ids):
        return self._screen.list_area


@contextmanager
def _launched_app(detail_area: DecisionDetailArea):
    """Builds DecisionCenterUI over a single seeded decision with the given
    evidence, launches it as a real local Gradio server, and yields its URL."""
    view = _make_view()
    screen = DecisionCenterScreen(
        list_area=DecisionListArea(decisions=[view]), detail_area=detail_area,
    )
    controller = _FakeController(screen=screen, detail_area=detail_area)
    ui = DecisionCenterUI(controller, [_DECISION_ID])
    demo = ui.build()
    demo.launch(
        prevent_thread_lock=True, quiet=True, show_error=True, show_api=False,
        server_name="127.0.0.1", inbrowser=False,
    )
    try:
        yield demo.local_url
    finally:
        demo.close()


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


def _page_with_evidence(browser, url, expect_text):
    """Opens `url`, waits for demo.load() to have populated the "Evidence
    Since Decision" section, expands every native ``<details>`` disclosure
    in it (production markup renders each evidence fact collapsed behind a
    "Details" toggle -- see gradio_view.py's ``_news_cache_evidence_html`` /
    ``_format_recommendation_diff_html`` / ``_format_earnings_html``, all
    three of which wrap their content in
    ``<details class="aara-payload-disclosure">``), then polls real DOM
    text (never a timer) until `expect_text` is actually visible."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=_TIMEOUT_MS)
    page.wait_for_selector("details.aara-payload-disclosure", timeout=_TIMEOUT_MS)
    for summary in page.locator("details.aara-payload-disclosure summary").all():
        summary.click()
    page.wait_for_function(
        """(needle) => document.body.innerText.includes(needle)""",
        arg=expect_text,
        timeout=_TIMEOUT_MS,
    )
    return context, page


def test_news_cache_diff_evidence_renders_in_the_real_browser(browser):
    """A. News-cache-diff / Evidence Since Decision."""
    diff = NewsCacheSnapshotDiff(
        symbol="AAPL",
        before_fetch_date="2026-09-01", after_fetch_date="2026-09-05",
        before_cached_at="2026-09-01 10:00:00", after_cached_at="2026-09-05 10:00:00",
        before_headline_count=1, after_headline_count=2,
        added_headlines=("New headline about AAPL",), removed_headlines=("Old headline",),
        is_identical=False, same_headlines_reordered=False,
    )
    detail_area = DecisionDetailArea(decision=_make_view(), news_cache_diff=diff)
    with _launched_app(detail_area) as url:
        context, page = _page_with_evidence(browser, url, "New headline about AAPL")
        try:
            _sync_api.expect(page.get_by_text("Evidence Since Decision")).to_be_visible(
                timeout=_TIMEOUT_MS
            )
            visible_text = page.inner_text("body")
            assert "New headline about AAPL" in visible_text
            assert "Old headline" in visible_text
        finally:
            context.close()


def test_recommendation_change_evidence_renders_in_the_real_browser(browser):
    """B. Recommendation-change evidence."""
    rec_diff = RecommendationDiff(
        symbol="AAPL",
        before_prediction_date="2026-09-01", after_prediction_date="2026-09-05",
        before_recommendation="BUY", after_recommendation="WAIT",
        before_confidence=0.61, after_confidence=0.58,
        is_unchanged=False,
    )
    detail_area = DecisionDetailArea(decision=_make_view(), recommendation_diff=rec_diff)
    with _launched_app(detail_area) as url:
        # The label text is rendered all-caps via CSS text-transform (see
        # theme.py's .record-label rule) -- wait/assert case-insensitively
        # on the label, matching what a real user visually sees; the value
        # spans ("BUY"/"WAIT") are not transformed and keep their case.
        context, page = _page_with_evidence(browser, url, "RECOMMENDATION NOW")
        try:
            visible_text = page.inner_text("body")
            assert "recommendation then" in visible_text.lower()
            assert "recommendation now" in visible_text.lower()
            assert "WAIT" in visible_text
        finally:
            context.close()


def test_earnings_proximity_evidence_renders_in_the_real_browser(browser):
    """C. Earnings-proximity evidence."""
    snapshot = EarningsSnapshot(
        symbol="AAPL", near_earnings=True, cached_at="2026-09-01T16:41:57+00:00",
    )
    detail_area = DecisionDetailArea(decision=_make_view(), earnings_snapshot=snapshot)
    with _launched_app(detail_area) as url:
        context, page = _page_with_evidence(browser, url, "Near earnings")
        try:
            assert "Near earnings" in page.inner_text("body")
        finally:
            context.close()


def test_all_three_evidence_categories_render_together_in_the_real_browser(browser):
    """Regression guard for the production shape: all three facts are
    concatenated into the SAME "Evidence Since Decision" HTML output, so a
    change that clobbers one while adding another must be caught here, not
    only in the three isolated tests above."""
    diff = NewsCacheSnapshotDiff(
        symbol="AAPL",
        before_fetch_date="2026-09-01", after_fetch_date="2026-09-05",
        before_cached_at="2026-09-01 10:00:00", after_cached_at="2026-09-05 10:00:00",
        before_headline_count=1, after_headline_count=2,
        added_headlines=("New headline about AAPL",), removed_headlines=(),
        is_identical=False, same_headlines_reordered=False,
    )
    rec_diff = RecommendationDiff(
        symbol="AAPL",
        before_prediction_date="2026-09-01", after_prediction_date="2026-09-05",
        before_recommendation="BUY", after_recommendation="WAIT",
        before_confidence=0.61, after_confidence=0.58,
        is_unchanged=False,
    )
    snapshot = EarningsSnapshot(
        symbol="AAPL", near_earnings=True, cached_at="2026-09-01T16:41:57+00:00",
    )
    detail_area = DecisionDetailArea(
        decision=_make_view(),
        news_cache_diff=diff, recommendation_diff=rec_diff, earnings_snapshot=snapshot,
    )
    with _launched_app(detail_area) as url:
        context, page = _page_with_evidence(browser, url, "Near earnings")
        try:
            visible_text = page.inner_text("body")
            assert "New headline about AAPL" in visible_text
            assert "recommendation now" in visible_text.lower() and "WAIT" in visible_text
            assert "Near earnings" in visible_text
        finally:
            context.close()
