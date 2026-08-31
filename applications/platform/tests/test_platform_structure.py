"""Structural tests for the applications.platform package.

Verifies imports and the dependency rule from
docs/platform/AARA_PLATFORM_SHELL_ARCHITECTURE.md Section 4 / this task's
"Platform layer must not know" list: no product package, sentinel_engine,
bot, or dashboard import anywhere under applications/platform/'s production
surface (identity/, entitlements/, registry/).

The forbidden-import scan deliberately excludes tests/ itself: integration
tests (test_trading_intelligence_registration.py) legitimately import a real
product descriptor to verify registration end-to-end -- that's a test
exercising the boundary, not a violation of it. The rule applies to what the
platform's importable code depends on, not to what its test suite is allowed
to construct.

Fake-implementation-satisfies-interface coverage lives in each contract's own
test file (test_authentication_provider.py, test_entitlement_checker.py,
test_product_registry.py) -- not duplicated here.
"""
import ast
import importlib
import pathlib

import pytest

_PLATFORM_ROOT = pathlib.Path(__file__).resolve().parent.parent

_MODULES = [
    "applications.platform",
    "applications.platform.identity",
    "applications.platform.identity.user",
    "applications.platform.identity.authentication_provider",
    "applications.platform.entitlements",
    "applications.platform.entitlements.entitlement_checker",
    "applications.platform.registry",
    "applications.platform.registry.product_registry",
    "applications.platform.shell",
    "applications.platform.shell.shell_model",
    "applications.platform.shell.shell_builder",
    "applications.platform.shell.platform_shell_view",
    "applications.platform.shell.shell_presenter",
    "applications.platform.workspaces",
    "applications.platform.workspaces.workspace",
    "applications.platform.workspaces.workspace_registry",
    "applications.platform.navigation",
    "applications.platform.navigation.navigation_item",
    "applications.platform.navigation.navigation_model",
    "applications.platform.navigation.navigation_builder",
    "applications.platform.integrations",
    "applications.platform.integrations.health",
    "applications.platform.integrations.classification",
    "applications.platform.integrations.capability",
]


@pytest.mark.parametrize("module_name", _MODULES)
def test_platform_package_imports_cleanly(module_name):
    importlib.import_module(module_name)


def test_platform_layer_does_not_import_products_sentinel_bot_or_dashboard():
    forbidden_prefixes = (
        "applications.trading_intelligence",
        "applications.wealth_intelligence",
        "sentinel_engine",
        "bot",
        "dashboard",
        "scheduler",
        "database",
        "ledger",
    )
    py_files = [
        path
        for path in _PLATFORM_ROOT.rglob("*.py")
        if "tests" not in path.relative_to(_PLATFORM_ROOT).parts
    ]
    assert py_files, "expected at least one production .py file under applications/platform/"

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
