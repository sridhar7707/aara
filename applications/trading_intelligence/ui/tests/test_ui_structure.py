"""Structural tests for the trading_intelligence UI ownership boundary.

Verifies the ui/ package imports cleanly and that it never imports bot,
dashboard, scheduler, or sentinel_engine directly -- the UI must consume
application services (services/.DecisionQueryService), never reach past them.
"""
import ast
import importlib
import pathlib

import pytest

_UI_ROOT = pathlib.Path(__file__).resolve().parent.parent

_MODULES = [
    "applications.trading_intelligence.ui",
    "applications.trading_intelligence.ui.decision_center",
    "applications.trading_intelligence.ui.decision_center.screen",
    "applications.trading_intelligence.ui.decision_center.mock_data",
    "applications.trading_intelligence.ui.decision_center.controller",
    "applications.trading_intelligence.ui.decision_center.theme",
]


@pytest.mark.parametrize("module_name", _MODULES)
def test_ui_package_imports_cleanly(module_name):
    importlib.import_module(module_name)


def test_ui_does_not_import_bot_dashboard_scheduler_or_sentinel_engine_directly():
    forbidden_prefixes = ("bot", "dashboard", "scheduler", "sentinel_engine")
    py_files = list(_UI_ROOT.rglob("*.py"))
    assert py_files, "expected at least one .py file under applications/trading_intelligence/ui/"

    for path in py_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes), (
                        f"{path}: forbidden import {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(forbidden_prefixes), (
                    f"{path}: forbidden import from {module!r}"
                )


def test_controller_does_not_import_mock_data():
    """Inverse of test_screen_components_do_not_import_services_directly:
    the controller must load real decisions through DecisionQueryService
    only -- mock_data.py stays a standalone demo module, never a production
    dependency of the controller flow (Phase 5A: Decision Center Real Data
    Wiring, requirement 2)."""
    forbidden = ("applications.trading_intelligence.ui.decision_center.mock_data",)
    path = _UI_ROOT / "decision_center" / "controller.py"

    assert path.exists(), f"expected {path} to exist"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), (
                    f"{path}: {alias.name!r} must not be imported by the controller"
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith(forbidden), (
                f"{path}: {module!r} must not be imported by the controller"
            )


def test_screen_components_do_not_import_services_directly():
    """UI components (screen.py, mock_data.py) must not call services --
    only decision_center/controller.py may. Enforces the integration boundary
    from Phase 3I: DecisionCenterScreen -> DecisionCenterController ->
    DecisionQueryService, never Screen -> Service directly."""
    forbidden = ("applications.trading_intelligence.services",)
    ui_component_files = [
        _UI_ROOT / "decision_center" / "screen.py",
        _UI_ROOT / "decision_center" / "mock_data.py",
    ]

    for path in ui_component_files:
        assert path.exists(), f"expected {path} to exist"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden), (
                        f"{path}: {alias.name!r} must not be imported directly by UI components"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(forbidden), (
                    f"{path}: {module!r} must not be imported directly by UI components"
                )
