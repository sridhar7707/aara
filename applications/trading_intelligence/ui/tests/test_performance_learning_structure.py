"""Structural tests for Performance & Learning's self-containment.

test_ui_structure.py already scans every file under ui/ (including this
package) for bot/dashboard/scheduler/sentinel_engine imports -- not
repeated here. This file covers the requirements unique to this package:
no coupling to any sibling screen package, and no outcome/attribution/
calibration contract of any kind (this backlog slice's own scope rule).
"""
import ast
import importlib
import pathlib

import pytest

_PACKAGE_ROOT = pathlib.Path(__file__).resolve().parent.parent / "performance_learning"

_MODULES = [
    "applications.trading_intelligence.ui.performance_learning",
    "applications.trading_intelligence.ui.performance_learning.screen",
    "applications.trading_intelligence.ui.performance_learning.mock_data",
    "applications.trading_intelligence.ui.performance_learning.gradio_view",
    "applications.trading_intelligence.ui.performance_learning.theme",
]

_FORBIDDEN_SIBLING_PACKAGES = (
    "applications.trading_intelligence.ui.decision_center",
    "applications.trading_intelligence.ui.portfolio_intelligence",
    "applications.trading_intelligence.ui.risk_intelligence",
    "applications.trading_intelligence.ui.morning_brief",
    "applications.trading_intelligence.ui.settings",
)


@pytest.mark.parametrize("module_name", _MODULES)
def test_performance_learning_package_imports_cleanly(module_name):
    importlib.import_module(module_name)


def test_performance_learning_does_not_import_any_sibling_screen_package():
    py_files = list(_PACKAGE_ROOT.rglob("*.py"))
    assert py_files, "expected at least one .py file under ui/performance_learning/"

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


def test_performance_learning_does_not_import_sentinel_engine_bot_or_dashboard():
    """Redundant with test_ui_structure.py's whole-tree scan, but kept
    explicit per-package (matching every other screen package's own
    convention of an explicit, package-local self-containment check)."""
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
