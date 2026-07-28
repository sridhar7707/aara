"""
Playwright visual UI check for TradeGenius dashboard.

Starts the real dashboard (dashboard/app.py — the FastAPI-wrapped Gradio app
that's actually deployed to HuggingFace Spaces), opens every tab, asserts
every key section is visible, and takes a full-page screenshot. Run this
manually any time you want to verify the look & feel and data is showing
correctly.

Requires a real gradio>=5.0 install (needs Python>=3.10 — see
docs/DEPENDENCIES.md; local dev on Python 3.9 cannot run this). Run it with
whichever interpreter has the real requirements.txt/requirements_space.txt
installed:

Usage:
    python tests/check_ui.py                # headless
    python tests/check_ui.py --headed       # watch the browser live
    python tests/check_ui.py --no-server    # server already on :7860

Screenshots saved to:  tests/snapshots/playwright/<YYYYMMDD_HHMMSS>/
Update TAB_SPECS whenever a section heading or key text changes in the dashboard.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Windows consoles often default to cp1252, which can't encode the checkmark/
# cross glyphs this script prints — reconfigure before any output happens.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

BASE_DIR  = Path(__file__).parent.parent
DASH_URL  = "http://localhost:7860"
SNAP_ROOT = Path(__file__).parent / "snapshots" / "playwright"

_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_RESET  = "\033[0m"
_BOLD   = "\033[1m"


def _ok(msg: str)   -> None: print(f"  {_GREEN}✓{_RESET} {msg}")
def _fail(msg: str) -> None: print(f"  {_RED}✗{_RESET} {msg}")
def _warn(msg: str) -> None: print(f"  {_YELLOW}~{_RESET} {msg}")
def _head(msg: str) -> None: print(f"\n{_BOLD}{msg}{_RESET}")


# Per-tab check specs: (display_name, tab_button_text, assertions, wait_secs)
# Assertions: (description, selector)
#   selector starts with "not:" -> content must be ABSENT
#   "not:text=unavailable" is the universal crash detector (safe_render error card)
#
# Matches the current 8-tab dashboard/app.py structure (Brief/Portfolio/Analytics/
# Capital/Trades/Performance/Journal/Settings). Update whenever a tab's section
# titles change.
TAB_SPECS: list[tuple[str, str, list[tuple[str, str]], float]] = [
    (
        "Brief",
        "Brief",
        [
            ("No component crash cards",         "not:text=unavailable"),
            ("Portfolio value shown ($)",        "text=$"),
            ("Decision bar rendered",            "text=Today"),
            ("Morning brief rendered",           "text=Portfolio Health"),
            ("Positions snapshot rendered",      "text=Position"),
        ],
        4.0,
    ),
    (
        "Portfolio",
        "Portfolio",
        [
            ("No component crash cards",         "not:text=unavailable"),
            ("Weekly summary rendered",          "text=Week"),
            ("Portfolio Health hero rendered",   "text=Portfolio Health"),
            ("Today stat shown in hero",         "text=Today"),
            ("Equity chart rendered",            "#equity-chart"),
            ("Open positions rendered",          "text=Position"),
            ("Trade log rendered",               "text=Trade"),
        ],
        4.0,
    ),
    (
        "Analytics",
        "Analytics",
        [
            ("No component crash cards",         "not:text=unavailable"),
            ("Decision Center rendered",         "text=Decision Center"),
            ("Watchlist rendered",               "text=Watch"),
            ("Market mood rendered",             "text=Market Mood"),
            ("Risk panel rendered",              "text=Risk"),
            ("News rendered",                    "text=News"),
        ],
        5.0,
    ),
    (
        "Capital",
        "Capital",
        [
            ("No component crash cards",         "not:text=unavailable"),
            ("Capital overview rendered",        "text=Initial Deposit"),
            ("Managed Capital Pool shown",       "text=Capital Pool"),
            ("Tradeable cash row shown",          "text=Tradeable"),
            ("Reserve row shown",                "text=Reserve"),
            ("Invested row shown",               "text=Invested"),
            ("Profit breakdown rendered",        "text=Realized"),
            ("Reinvestment toggle shown",        "text=Reinvest"),
        ],
        3.0,
    ),
    (
        "Trades",
        "Trades",
        [
            ("No component crash cards",         "not:text=unavailable"),
            ("Top picks rendered",               "text=Buy Picks"),
            ("Trade frequency rendered",         "text=This Week"),
            ("Buy candidates rendered",          "text=Buy"),
            ("Signal history rendered",          "text=Signal"),
            ("Recommendation history rendered",  "text=Recommendation"),
        ],
        3.0,
    ),
    (
        "Performance",
        "Performance",
        [
            ("No component crash cards",         "not:text=unavailable"),
            ("Institutional metrics rendered",   "text=Win Rate"),
            ("Attribution by holding shown",     "text=By Holding"),
            ("vs SPY column shown",              "text=vs SPY"),
            ("Confidence Calibration rendered",  "text=Confidence Calibration"),
            ("Counterfactual Analysis rendered", "text=Counterfactual Analysis"),
            ("Investor view rendered",           "text=Investor"),
        ],
        4.0,
    ),
    (
        "Journal",
        "Journal",
        [
            ("No component crash cards",         "not:text=unavailable"),
            ("Trade Journal rendered",           "text=Trade Journal"),
        ],
        3.0,
    ),
    (
        "Settings",
        "Settings",
        [
            ("No component crash cards",         "not:text=unavailable"),
            ("Risk tolerance radio shown",       "text=Risk Tolerance"),
            ("Stop-loss slider shown",           "text=Stop-Loss"),
            ("Max position slider shown",        "text=Max Position"),
            ("Max drawdown slider shown",        "text=Drawdown"),
            ("Notifications checkbox shown",     "text=Notification"),
        ],
        2.0,
    ),
]


# -- Server management ---------------------------------------------------------

def _server_alive() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(f"{DASH_URL}/config", timeout=2)
        return True
    except Exception:
        return False


def start_server() -> subprocess.Popen:
    print("Starting dashboard server (dashboard/app.py) ...")
    return subprocess.Popen(
        [sys.executable, "dashboard/app.py"],
        cwd=str(BASE_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_server(timeout: int = 120) -> bool:
    print(f"Waiting for server on {DASH_URL} (up to {timeout}s) ...", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _server_alive():
            print("  ready")
            return True
        time.sleep(2)
        print(".", end="", flush=True)
    print()
    return False


# -- Assertion runner -----------------------------------------------------------

def _check(page, description: str, selector: str) -> tuple[bool, str]:
    # dashboard/app.py pre-renders every tab's content into the DOM at startup
    # and tab-switching only toggles visibility — so an unscoped page.locator()
    # search can match hidden content belonging to a completely different,
    # inactive tab (e.g. another tab's own "Win Rate" stat or "Buy" badge).
    # Scoping to the one visible [role="tabpanel"] avoids that cross-tab
    # false-negative entirely.
    panel = page.locator('[role="tabpanel"]:visible')
    if selector.startswith("not:"):
        inner = selector[4:]
        try:
            if panel.locator(inner).count() > 0:
                return False, f"Unexpected content found: {inner!r}"
            return True, ""
        except Exception:
            return True, ""
    try:
        panel.locator(selector).first.wait_for(state="visible", timeout=5_000)
        return True, ""
    except Exception as exc:
        return False, str(exc)[:120]


def run_all_tabs(page, snap_dir: Path) -> list[dict]:
    results = []
    # Not "networkidle" — Gradio keeps a live SSE/WebSocket connection open for
    # timer ticks, so the network never goes idle and this would always time out.
    page.goto(DASH_URL, wait_until="load", timeout=60_000)
    time.sleep(3)

    for tab_name, btn_text, assertions, wait_secs in TAB_SPECS:
        _head(f"[{tab_name}]")
        checks: list[tuple[bool, str, str]] = []

        clicked = False
        for selector in [f'[role="tab"]:has-text("{btn_text}")',
                         f'button:has-text("{btn_text}")',
                         f'text="{btn_text}"']:
            try:
                page.locator(selector).first.click(timeout=6_000)
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            _fail(f"Could not click tab '{tab_name}'")
            results.append({"tab": tab_name, "passed": False,
                            "checks": [(False, "Tab click failed", "")],
                            "screenshot": None})
            continue

        time.sleep(wait_secs)

        for desc, sel in assertions:
            ok, detail = _check(page, desc, sel)
            checks.append((ok, desc, detail))
            _ok(desc) if ok else _fail(f"{desc}  {detail}")

        snap_path = snap_dir / f"{tab_name.lower()}.png"
        try:
            page.screenshot(path=str(snap_path), full_page=True)
            _ok(f"Screenshot -> {snap_path.relative_to(BASE_DIR)}")
        except Exception as exc:
            _warn(f"Screenshot failed: {exc}")
            snap_path = None

        results.append({
            "tab":        tab_name,
            "passed":     all(ok for ok, _, _ in checks),
            "checks":     checks,
            "screenshot": snap_path,
        })

    return results


# -- Report -----------------------------------------------------------------

def print_report(results: list[dict], snap_dir: Path) -> int:
    _head("=" * 60)
    _head("REPORT")
    print("=" * 60)
    for r in results:
        status = f"{_GREEN}PASS{_RESET}" if r["passed"] else f"{_RED}FAIL{_RESET}"
        print(f"  {status}  {r['tab']}")
        for ok, desc, detail in r["checks"]:
            if not ok:
                print(f"         ✗ {desc}")
                if detail:
                    print(f"           {detail}")

    failed = [r for r in results if not r["passed"]]
    print(f"\n  Tabs passed : {len(results) - len(failed)}/{len(results)}")
    print(f"  Screenshots : {snap_dir}\n")
    if failed:
        print(f"{_RED}{_BOLD}  {len(failed)} tab(s) FAILED{_RESET}")
        return 1
    print(f"{_GREEN}{_BOLD}  All {len(results)} tabs passed ✓{_RESET}")
    return 0


# -- Entry point --------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="TradeGenius Playwright UI check")
    parser.add_argument("--headed",    action="store_true",
                        help="Show browser window (default: headless)")
    parser.add_argument("--no-server", action="store_true",
                        help="Skip server startup -- assume :7860 is already running")
    parser.add_argument("--timeout",   type=int, default=120,
                        help="Server startup timeout in seconds (default 120)")
    args = parser.parse_args()

    proc = None
    if args.no_server:
        if not _server_alive():
            print(f"{_RED}Error: --no-server set but nothing is running on {DASH_URL}{_RESET}")
            sys.exit(1)
        print(f"Using existing server on {DASH_URL}")
    else:
        if _server_alive():
            print(f"Server already running on {DASH_URL} -- skipping startup")
        else:
            proc = start_server()
            if not wait_for_server(timeout=args.timeout):
                print(f"{_RED}Server did not start within {args.timeout}s{_RESET}")
                if proc:
                    proc.terminate()
                sys.exit(1)

    stamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_dir = SNAP_ROOT / stamp
    snap_dir.mkdir(parents=True, exist_ok=True)

    exit_code = 1
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not args.headed)
            page    = browser.new_context(
                viewport={"width": 1440, "height": 900}
            ).new_page()
            results   = run_all_tabs(page, snap_dir)
            browser.close()
        exit_code = print_report(results, snap_dir)
    except ImportError:
        print(f"{_RED}playwright not installed. Run: pip install playwright && playwright install chromium{_RESET}")
    finally:
        if proc:
            proc.terminate()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
