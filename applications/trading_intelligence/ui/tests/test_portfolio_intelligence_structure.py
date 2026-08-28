"""Structural tests for Portfolio Intelligence's self-containment.

test_ui_structure.py already scans every file under ui/ (including this
package) for bot/dashboard/scheduler/sentinel_engine imports -- not
repeated here. This file only covers the requirement unique to this
package: no coupling to ui/decision_center/, plus a lock that every
`pi-*` CSS class the view markup references has a matching rule in this
package's own theme.py (an orphan selector renders unstyled).
"""
import ast
import importlib
import pathlib
import re

import pytest

from applications.trading_intelligence.ui.portfolio_intelligence.theme import CSS

_PACKAGE_ROOT = pathlib.Path(__file__).resolve().parent.parent / "portfolio_intelligence"

_GRADIO_VIEW = _PACKAGE_ROOT / "gradio_view.py"

# The Alpaca Paper sections (2026-08-27 units) reference these -- locked
# explicitly so a future removal from theme.py is caught here.
_REQUIRED_ALPACA_SELECTORS = (
    ".pi-alpaca-badge",
    ".pi-alpaca-unavailable",
    ".pi-alpaca-positions-table",
    ".pi-alpaca-orders-table",
    ".pi-alpaca-orders-truncation",
)

_MODULES = [
    "applications.trading_intelligence.ui.portfolio_intelligence",
    "applications.trading_intelligence.ui.portfolio_intelligence.screen",
    "applications.trading_intelligence.ui.portfolio_intelligence.mock_data",
    "applications.trading_intelligence.ui.portfolio_intelligence.gradio_view",
    "applications.trading_intelligence.ui.portfolio_intelligence.theme",
]


@pytest.mark.parametrize("module_name", _MODULES)
def test_portfolio_intelligence_package_imports_cleanly(module_name):
    importlib.import_module(module_name)


def test_alpaca_paper_section_selectors_are_defined_in_theme():
    for selector in _REQUIRED_ALPACA_SELECTORS:
        assert f"{selector} " in CSS or f"{selector}," in CSS or f"{selector}{{" in CSS, (
            f"{selector} is referenced by gradio_view.py but has no rule in theme.py"
        )


def test_production_portfolio_modules_do_not_import_mock_data():
    """Production guarantee: neither the Portfolio Intelligence view
    (gradio_view.py) nor the composition root (bootstrap.py) may import
    or use portfolio_intelligence.mock_data / build_mock_screen /
    build_mock_portfolio_screen. mock_data.py stays only for isolated
    unit tests and must be unreachable from build_trading_intelligence_app()."""
    view = (_PACKAGE_ROOT / "gradio_view.py").read_text(encoding="utf-8")
    bootstrap = (
        pathlib.Path(__file__).resolve().parents[2] / "bootstrap.py"
    ).read_text(encoding="utf-8")

    for label, source in (("gradio_view.py", view), ("bootstrap.py", bootstrap)):
        assert "portfolio_intelligence.mock_data" not in source, (
            f"{label} imports portfolio_intelligence.mock_data"
        )
        assert "build_mock_portfolio_screen" not in source, (
            f"{label} references build_mock_portfolio_screen"
        )
    # gradio_view.py must not import build_mock_screen at all (bootstrap.py
    # legitimately imports other screens' build_mock_screen; scope this
    # check to the portfolio view module).
    assert "build_mock_screen" not in view, (
        "portfolio_intelligence/gradio_view.py imports build_mock_screen"
    )


def test_no_ui_mock_data_module_feeds_the_alpaca_sections():
    """Production guardrail: the Alpaca Paper Account / Positions (Unit 1)
    and Recent Orders (Unit 3) sections are real / unavailable / empty
    only. No mock_data.py anywhere under ui/ may reference an Alpaca
    source or construct an Alpaca projection, so those sections can never
    be fed illustrative data."""
    ui_root = _PACKAGE_ROOT.parent
    forbidden = (
        "AlpacaPaperSource", "AlpacaNewsSource", "AlpacaPaperOrdersSource",
        "AlpacaAccountSnapshot", "AlpacaPosition", "AlpacaOrder",
        "AlpacaOrdersSnapshot", "alpaca",
    )
    mock_files = sorted(ui_root.glob("*/mock_data.py"))
    assert mock_files, "expected mock_data.py modules under ui/"
    for path in mock_files:
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, (
                f"{path}: mock/illustrative data must not reference {token!r}"
            )


def test_no_pi_css_class_in_the_view_markup_is_left_unstyled():
    """Every `pi-*` class name that appears in gradio_view.py's rendered
    markup must have a matching rule in this package's own theme.py. The
    Alpaca Paper Account / Positions / Recent Orders sections shipped
    referencing five selectors that theme.py never defined; this lock
    prevents that class of regression recurring."""
    source = _GRADIO_VIEW.read_text(encoding="utf-8")
    referenced = set(re.findall(r"pi-[a-z0-9-]+", source))
    assert referenced, "expected pi-* class references in gradio_view.py"
    missing = sorted(cls for cls in referenced if f".{cls}" not in CSS)
    assert not missing, f"pi-* classes referenced but not styled in theme.py: {missing}"


def test_portfolio_intelligence_does_not_import_decision_center():
    forbidden = ("applications.trading_intelligence.ui.decision_center",)
    py_files = list(_PACKAGE_ROOT.rglob("*.py"))
    assert py_files, "expected at least one .py file under ui/portfolio_intelligence/"

    for path in py_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden), (
                        f"{path}: forbidden import {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(forbidden), (
                    f"{path}: forbidden import from {module!r}"
                )
