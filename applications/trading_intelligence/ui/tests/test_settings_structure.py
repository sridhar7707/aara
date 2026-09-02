"""Structural tests for Settings' self-containment.

test_ui_structure.py already scans every file under ui/ (including this
package) for bot/dashboard/scheduler/sentinel_engine imports -- not
repeated here. This file covers the requirements unique to this package:
no coupling to any sibling screen package, and no persistence/
configuration contract of any kind (this backlog slice's own scope rule).
"""
import ast
import importlib
import pathlib

import pytest

_PACKAGE_ROOT = pathlib.Path(__file__).resolve().parent.parent / "settings"

_MODULES = [
    "applications.trading_intelligence.ui.settings",
    "applications.trading_intelligence.ui.settings.screen",
    "applications.trading_intelligence.ui.settings.mock_data",
    "applications.trading_intelligence.ui.settings.gradio_view",
    "applications.trading_intelligence.ui.settings.theme",
]

_FORBIDDEN_SIBLING_PACKAGES = (
    "applications.trading_intelligence.ui.decision_center",
    "applications.trading_intelligence.ui.portfolio_intelligence",
    "applications.trading_intelligence.ui.risk_intelligence",
    "applications.trading_intelligence.ui.morning_brief",
)


@pytest.mark.parametrize("module_name", _MODULES)
def test_settings_package_imports_cleanly(module_name):
    importlib.import_module(module_name)


def test_settings_does_not_import_any_sibling_screen_package():
    py_files = list(_PACKAGE_ROOT.rglob("*.py"))
    assert py_files, "expected at least one .py file under ui/settings/"

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


def test_settings_theme_defines_local_spacing_tokens():
    """Local spacing-token extraction: theme.py must declare its own
    --st-space-* custom properties rather than raw px literals or an
    import of another package's tokens (see test above)."""
    from applications.trading_intelligence.ui.settings.theme import CSS

    for px in (4, 6, 8, 12, 16):
        assert f"--st-space-{px}: {px}px;" in CSS, (
            f"expected a --st-space-{px} token declared in theme.py's CSS"
        )


def test_settings_theme_aliases_the_shared_colour_tokens():
    """Design-system migration (Batch B): theme.py's colour `:root` entries
    resolve through the shared `--aara-*` tokens from ui/design_system.py,
    each keeping its former hex as a `var(--aara-*, <literal>)` standalone-
    render fallback. Mirrors test_design_system.py's own
    test_migrated_screen_themes_alias_the_shared_colour_tokens (Batch A)."""
    from applications.trading_intelligence.ui.settings.theme import CSS

    for alias in (
        "var(--aara-navy, #0B1F3A)",
        "var(--aara-gold, #C8A45D)",
        "var(--aara-bg, #F8F7F3)",
        "var(--aara-surface, #FFFFFF)",
        "var(--aara-text, #1A1A1A)",
        "var(--aara-text-muted, #666666)",
        "var(--aara-border, #E2E8F0)",
    ):
        assert alias in CSS, f"expected shared-token alias {alias!r} in theme.py's CSS"


def test_settings_does_not_import_sentinel_engine_bot_or_dashboard():
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
