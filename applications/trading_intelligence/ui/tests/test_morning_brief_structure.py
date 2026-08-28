"""Structural tests for Morning Brief's self-containment.

test_ui_structure.py already scans every file under ui/ (including this
package) for bot/dashboard/scheduler/sentinel_engine imports -- not
repeated here. This file covers the requirements unique to this package:
no coupling to any sibling screen package, and no MorningBriefQuery
wiring of any kind (the frozen IA's semantic rule this backlog slice must
not violate).
"""
import ast
import importlib
import pathlib
import re

import pytest

from applications.trading_intelligence.ui.morning_brief.theme import CSS

_PACKAGE_ROOT = pathlib.Path(__file__).resolve().parent.parent / "morning_brief"

_GRADIO_VIEW = _PACKAGE_ROOT / "gradio_view.py"

_MODULES = [
    "applications.trading_intelligence.ui.morning_brief",
    "applications.trading_intelligence.ui.morning_brief.screen",
    "applications.trading_intelligence.ui.morning_brief.mock_data",
    "applications.trading_intelligence.ui.morning_brief.gradio_view",
    "applications.trading_intelligence.ui.morning_brief.theme",
]

_FORBIDDEN_SIBLING_PACKAGES = (
    "applications.trading_intelligence.ui.decision_center",
    "applications.trading_intelligence.ui.portfolio_intelligence",
    "applications.trading_intelligence.ui.risk_intelligence",
)


@pytest.mark.parametrize("module_name", _MODULES)
def test_morning_brief_package_imports_cleanly(module_name):
    importlib.import_module(module_name)


def test_available_summary_selector_is_defined_in_theme():
    assert ".mb-available-summary " in CSS or ".mb-available-summary{" in CSS, (
        ".mb-available-summary is referenced by gradio_view.py but has no rule in theme.py"
    )


def test_no_mb_css_class_in_the_view_markup_is_left_unstyled():
    """Every `mb-*` class name that appears in gradio_view.py's rendered
    markup must have a matching rule in this package's own theme.py.
    `.mb-available-summary` shipped referenced but unstyled; this lock
    prevents that class of regression recurring."""
    source = _GRADIO_VIEW.read_text(encoding="utf-8")
    referenced = set(re.findall(r"mb-[a-z0-9-]+", source))
    assert referenced, "expected mb-* class references in gradio_view.py"
    missing = sorted(cls for cls in referenced if f".{cls}" not in CSS)
    assert not missing, f"mb-* classes referenced but not styled in theme.py: {missing}"


def test_morning_brief_does_not_import_any_sibling_screen_package():
    py_files = list(_PACKAGE_ROOT.rglob("*.py"))
    assert py_files, "expected at least one .py file under ui/morning_brief/"

    for path in py_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(_FORBIDDEN_SIBLING_PACKAGES), (
                        f"{path}: forbidden import {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(_FORBIDDEN_SIBLING_PACKAGES), (
                    f"{path}: forbidden import from {module!r}"
                )


def test_morning_brief_does_not_import_or_instantiate_morning_brief_query():
    """MorningBriefQuery (sentinel_engine.queries.morning_brief_query) is
    SHARED/Core-directed (Q11) and already used by Wealth Intelligence, but
    this backlog slice explicitly does not wire it in. Checked via AST
    (no `import`/`from ... import` naming morning_brief_query or
    MorningBriefQuery, and no `MorningBriefQuery(...)` call anywhere) --
    deliberately NOT a raw substring scan, since this package's own
    docstrings legitimately name "MorningBriefQuery" in prose to document
    that it is *not* wired (see screen.py/mock_data.py/gradio_view.py
    module docstrings); a substring check would false-positive on that
    honest self-documentation."""
    py_files = list(_PACKAGE_ROOT.rglob("*.py"))
    assert py_files, "expected at least one .py file under ui/morning_brief/"

    for path in py_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "morning_brief_query" not in alias.name, (
                        f"{path}: forbidden import {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "morning_brief_query" not in module, (
                    f"{path}: forbidden import from {module!r}"
                )
                assert not any(alias.name == "MorningBriefQuery" for alias in node.names), (
                    f"{path}: forbidden import of MorningBriefQuery"
                )
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "MorningBriefQuery":
                    raise AssertionError(f"{path}: forbidden instantiation of MorningBriefQuery")


def test_morning_brief_does_not_import_sentinel_engine_bot_or_dashboard():
    """Redundant with test_ui_structure.py's whole-tree scan, but kept
    explicit per-package (matching
    test_portfolio_intelligence_structure.py's/
    test_risk_intelligence_structure.py's own convention of an explicit,
    package-local self-containment check)."""
    forbidden = ("sentinel_engine", "bot", "dashboard", "scheduler", "database", "ledger")
    py_files = list(_PACKAGE_ROOT.rglob("*.py"))

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
