"""Browser end-to-end coverage for AARA Trading Intelligence navigation.

This is the only test that actually executes ``bootstrap._INNER_NAV_LINK_JS``
in a real DOM. Every other "nav" test in the suite asserts that markup /
script text / CSS strings are *present*; none proves that clicking a visible
``.aara-shell-nav-list .nav-item`` span activates the corresponding
(CSS-hidden) ``gr.TabbedInterface`` tab and swaps the visible screen. Two
documented regressions (stale label list -> screens silently unreachable)
passed the string-level tests and were only caught by manual Playwright
audits; this closes that gap in CI-runnable form.

Mechanism under test (applications/trading_intelligence/bootstrap.py):
  * ``gr.TabbedInterface`` renders six real ``<button role="tab">`` controls,
    hidden by ``_TABBED_LAYOUT_CSS`` (``[role="tablist"]:not(.aara-shell-nav-list)``).
  * Each screen renders its own visible ``<nav class="aara-shell-nav-list">``
    of six inert ``<span class="nav-item">`` items (ui/shell.build_shell_nav_html).
  * ``_INNER_NAV_LINK_JS`` polls until all six nav lists exist, then wires each
    span: click / Enter / Space -> ``findRealTab(label)`` (matches a hidden tab
    button by exact trimmed text) -> ``tabButton.click()``.
The label -> tab join is a pure client-side text match with no server round
trip, so only a real browser can verify it.

Transition safety:
  * ``gr.TabbedInterface``'s Tabs component reactively re-runs its
    "select the currently-selected tab" handler on every child Tab
    re-registration, which Decision Center's ``demo.load()`` produces on
    first render (see bootstrap._TAB_WARNING_SUPPRESSION_JS's comment).
    During such churn two ``.tabitem`` panels can briefly coexist. This
    test never asserts against a "visible=true" heuristic mid-flight: it
    scopes every nav click to the panel that is *known* to be active
    (identified by its marker), and after every navigation it waits, via
    ``_wait_settled_on``, until exactly one panel is shown *and it is the
    expected one* before making any visibility assertion. No sleeps.

Isolation / opt-out:
  * The whole module is skipped if ``playwright.sync_api`` cannot be imported.
  * It is skipped (not failed) if the Playwright driver or Chromium is not
    installed; ``playwright.stop()`` always runs once the driver started.
  * The module-scoped ``app_url`` fixture builds the app *before* any
    function-scoped fixture runs, so conftest.py's function-scoped
    ``neutralize_trades_db_snapshot`` autouse fixture would not yet apply.
    ``app_url`` therefore neutralizes ``bootstrap.fetch_trades_db_snapshot``
    itself for the duration of app construction, so no real HuggingFace
    download can happen during module setup regardless of environment.
  * The screen page-header subtitles used as visibility markers are static
    HTML rendered at ``build()`` time, so this test does not depend on any
    live data source (trades.db / Alpaca / prices / news) being reachable.
  * To exclude it from a broader run:
        python -m pytest applications/trading_intelligence -q \
          --ignore=applications/trading_intelligence/ui/tests/test_navigation_e2e.py

Run just this file:
    python -m pytest applications/trading_intelligence/ui/tests/test_navigation_e2e.py -q
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import pytest

_sync_api = pytest.importorskip("playwright.sync_api")

from applications.trading_intelligence.bootstrap import (  # noqa: E402
    build_trading_intelligence_app,
)

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

# (nav label as it appears in the visible shell nav, unique static
# page-header subtitle that exists in that screen's real source today --
# grep-verified as exactly one occurrence each, in distinct classes:
# mb-subtitle / aara-page-subtitle / pi-subtitle / ri-subtitle /
# pl-subtitle / st-subtitle). Order matches gr.TabbedInterface tab order,
# so index 0 (Morning Brief) is the initially-active screen.
NAV_SCREENS = [
    ("Morning Brief", "Single-glance daily summary before market open"),
    ("Decision Center", "Governed investment decisions"),
    ("Portfolio Intelligence", "Holdings, capital allocation, and current exposure"),
    ("Risk Intelligence", "Current risk-governor state and position sizing"),
    (
        "Performance & Learning",
        "Outcome history, attribution, and model confidence calibration",
    ),
    ("Settings", "User settings, thresholds, and notification preferences"),
]

_TIMEOUT_MS = 20_000


@pytest.fixture(scope="module")
def app_url():
    """Launch the REAL composed application on an ephemeral local port.

    Neutralizes ``bootstrap.fetch_trades_db_snapshot`` for the duration of
    app construction: this fixture is module-scoped and runs before
    conftest.py's function-scoped ``neutralize_trades_db_snapshot``
    autouse fixture, so without this guard ``build_trading_intelligence_app()``
    could reach the real snapshot fetch during module setup.
    """
    from applications.platform.integrations import IntegrationHealth, ReadResult

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "applications.trading_intelligence.bootstrap.fetch_trades_db_snapshot",
            lambda: ReadResult.failed(
                IntegrationHealth.not_configured("hf_trades_db_snapshot")
            ),
        )
        demo = build_trading_intelligence_app()
        demo.launch(
            prevent_thread_lock=True,
            quiet=True,
            show_error=True,
            show_api=False,
            server_name="127.0.0.1",
            inbrowser=False,
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


@pytest.fixture
def page(browser, app_url):
    context = browser.new_context()
    pg = context.new_page()
    console: list[str] = []
    pg.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
    pg.on("pageerror", lambda e: console.append(f"pageerror: {e}"))
    pg.__dict__["_ti_console"] = console

    pg.goto(app_url, wait_until="domcontentloaded", timeout=_TIMEOUT_MS)
    # Wait until _INNER_NAV_LINK_JS has finished wiring the spans: once all
    # six nav lists are in the DOM it sets style.cursor = "pointer" and
    # tabIndex = 0 on every managed .nav-item. This is the "the navigation
    # JavaScript has actually run" signal.
    pg.wait_for_function(
        """() => {
            const items = document.querySelectorAll('.aara-shell-nav-list .nav-item');
            if (items.length < 6) return false;
            const first = items[0];
            return first.style.cursor === 'pointer'
                && first.getAttribute('tabindex') === '0';
        }""",
        timeout=_TIMEOUT_MS,
    )
    try:
        yield pg
    finally:
        context.close()


def _wait_settled_on(page, marker_text):
    """Block until the tab transition has fully settled: exactly one
    ``.tabitem`` panel is shown AND it is the one carrying ``marker_text``.

    This is the synchronization point that makes the walk robust against
    gr.TabbedInterface's reactive re-selection (Decision Center's
    ``demo.load()`` re-registers child Tabs, which can transiently show
    zero or two panels). It waits on real DOM state, never on a timer.
    """
    page.wait_for_function(
        """(marker) => {
            const shown = Array.from(document.querySelectorAll('.tabitem')).filter(p => {
                const s = getComputedStyle(p);
                return s.display !== 'none' && s.visibility !== 'hidden';
            });
            return shown.length === 1 && shown[0].innerText.includes(marker);
        }""",
        arg=marker_text,
        timeout=_TIMEOUT_MS,
    )


def _active_nav_item(page, active_marker_text, label):
    """The ``.nav-item`` span for ``label`` inside the panel that is
    currently active -- identified by the marker of the screen we know is
    showing, not by a "visible=true" match that is ambiguous while two
    panels briefly coexist during a Gradio tab transition. Every screen
    renders its own copy of the nav; ``_INNER_NAV_LINK_JS`` wires them all
    to the same ``activateTab(label)``, so clicking the active panel's copy
    exercises a real, stable, on-screen handler.
    """
    panel = page.locator(".tabitem").filter(
        has=page.get_by_text(active_marker_text, exact=True)
    )
    return (
        panel.locator(".aara-shell-nav-list .nav-item")
        .filter(has_text=re.compile(rf"^{re.escape(label)}$"))
        .first
    )


def _marker(page, text):
    return page.get_by_text(text, exact=True)


def _diagnostics(page, tag):
    out_dir = Path(tempfile.gettempdir()) / "ti_nav_e2e"
    out_dir.mkdir(exist_ok=True)
    shot = out_dir / f"{tag}.png"
    try:
        page.screenshot(path=str(shot), full_page=True)
        shot_path = str(shot)
    except Exception:  # noqa: BLE001 - diagnostics must never mask the real failure
        shot_path = None
    try:
        panels = page.evaluate(
            """() => Array.from(document.querySelectorAll('.tabitem')).map(el => ({
                className: el.className,
                display: window.getComputedStyle(el).display,
                heading: (el.querySelector('h1, h2') || {}).textContent || null
            }))"""
        )
    except Exception as exc:  # noqa: BLE001
        panels = f"<evaluate failed: {exc}>"
    return {
        "tag": tag,
        "url": page.url,
        "screenshot": shot_path,
        "tabitem_panels": panels,
        "console": list(page.__dict__.get("_ti_console", [])),
    }


def _fail(page, tag, exc):
    print("\n=== TI NAV E2E FAILURE DIAGNOSTICS ===")
    print(json.dumps(_diagnostics(page, tag), indent=2, default=str))
    print("=== END DIAGNOSTICS ===")
    raise exc


def test_every_nav_item_activates_its_screen_and_hides_the_previous(page):
    """Click all six visible nav items in turn (five forward + back to the
    first) and assert, on every transition, that the target screen's marker
    becomes visible and the previously-active screen's marker becomes hidden."""
    try:
        # Baseline: tab 0 (Morning Brief) active and settled, a later screen hidden.
        _wait_settled_on(page, NAV_SCREENS[0][1])
        _sync_api.expect(_marker(page, NAV_SCREENS[0][1])).to_be_visible(
            timeout=_TIMEOUT_MS
        )
        _sync_api.expect(_marker(page, NAV_SCREENS[5][1])).to_be_hidden(
            timeout=_TIMEOUT_MS
        )

        previous_marker = NAV_SCREENS[0][1]
        walk = NAV_SCREENS[1:] + [NAV_SCREENS[0]]
        for label, marker in walk:
            _active_nav_item(page, previous_marker, label).click(timeout=_TIMEOUT_MS)
            # Synchronize on the real settled DOM state before asserting.
            _wait_settled_on(page, marker)
            _sync_api.expect(_marker(page, marker)).to_be_visible(
                timeout=_TIMEOUT_MS
            )
            _sync_api.expect(_marker(page, previous_marker)).to_be_hidden(
                timeout=_TIMEOUT_MS
            )
            previous_marker = marker
    except Exception as exc:  # noqa: BLE001 - re-raised by _fail after diagnostics
        _fail(page, "walk_all_six", exc)


def test_keyboard_enter_activates_the_focused_nav_item(page):
    """Focus a visible nav item and press Enter -> its screen activates and
    the previously-active screen is hidden (the keydown branch of
    _INNER_NAV_LINK_JS's wireNavItem handler)."""
    try:
        target_label, target_marker = NAV_SCREENS[3]  # Risk Intelligence
        _wait_settled_on(page, NAV_SCREENS[0][1])
        _sync_api.expect(_marker(page, NAV_SCREENS[0][1])).to_be_visible(
            timeout=_TIMEOUT_MS
        )

        _active_nav_item(page, NAV_SCREENS[0][1], target_label).focus()
        page.keyboard.press("Enter")

        _wait_settled_on(page, target_marker)
        _sync_api.expect(_marker(page, target_marker)).to_be_visible(
            timeout=_TIMEOUT_MS
        )
        _sync_api.expect(_marker(page, NAV_SCREENS[0][1])).to_be_hidden(
            timeout=_TIMEOUT_MS
        )
    except Exception as exc:  # noqa: BLE001
        _fail(page, "keyboard_enter", exc)


def test_keyboard_space_activates_the_focused_nav_item(page):
    """Same as the Enter test but with Space, which _INNER_NAV_LINK_JS
    handles via ``event.key === " "``."""
    try:
        target_label, target_marker = NAV_SCREENS[4]  # Performance & Learning
        _wait_settled_on(page, NAV_SCREENS[0][1])
        _sync_api.expect(_marker(page, NAV_SCREENS[0][1])).to_be_visible(
            timeout=_TIMEOUT_MS
        )

        _active_nav_item(page, NAV_SCREENS[0][1], target_label).focus()
        page.keyboard.press("Space")

        _wait_settled_on(page, target_marker)
        _sync_api.expect(_marker(page, target_marker)).to_be_visible(
            timeout=_TIMEOUT_MS
        )
        _sync_api.expect(_marker(page, NAV_SCREENS[0][1])).to_be_hidden(
            timeout=_TIMEOUT_MS
        )
    except Exception as exc:  # noqa: BLE001
        _fail(page, "keyboard_space", exc)
