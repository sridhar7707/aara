"""Structural tests for Portfolio Intelligence's self-containment.

test_ui_structure.py already scans every file under ui/ (including this
package) for bot/dashboard/scheduler/sentinel_engine imports -- not
repeated here. This file only covers the requirement unique to this
package: no coupling to ui/decision_center/.
"""
import ast
import importlib
import pathlib

import pytest

_PACKAGE_ROOT = pathlib.Path(__file__).resolve().parent.parent / "portfolio_intelligence"

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
