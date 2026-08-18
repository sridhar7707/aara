"""Structural tests for Risk Intelligence's self-containment.

test_ui_structure.py already scans every file under ui/ (including this
package) for bot/dashboard/scheduler/sentinel_engine imports -- not
repeated here. This file covers what's unique to this package: no
coupling to ui/decision_center/ or ui/portfolio_intelligence/, and no
`RiskEvaluation` class name anywhere (the task's explicit non-goal).
"""
import ast
import importlib
import pathlib

import pytest

_PACKAGE_ROOT = pathlib.Path(__file__).resolve().parent.parent / "risk_intelligence"

_MODULES = [
    "applications.trading_intelligence.ui.risk_intelligence",
    "applications.trading_intelligence.ui.risk_intelligence.screen",
    "applications.trading_intelligence.ui.risk_intelligence.mock_data",
    "applications.trading_intelligence.ui.risk_intelligence.gradio_view",
    "applications.trading_intelligence.ui.risk_intelligence.theme",
]


@pytest.mark.parametrize("module_name", _MODULES)
def test_risk_intelligence_package_imports_cleanly(module_name):
    importlib.import_module(module_name)


def test_risk_intelligence_does_not_import_decision_center_or_portfolio_intelligence():
    forbidden = (
        "applications.trading_intelligence.ui.decision_center",
        "applications.trading_intelligence.ui.portfolio_intelligence",
    )
    py_files = list(_PACKAGE_ROOT.rglob("*.py"))
    assert py_files, "expected at least one .py file under ui/risk_intelligence/"

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


def test_risk_intelligence_does_not_define_a_riskevaluation_class():
    """Explicit compliance check: no `RiskEvaluation` (or equivalently
    contract-shaped) class is added anywhere in this package -- no such
    contract exists in sentinel_engine and none is proposed here."""
    py_files = list(_PACKAGE_ROOT.rglob("*.py"))

    for path in py_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name != "RiskEvaluation", (
                    f"{path}: must not define a class named RiskEvaluation"
                )
