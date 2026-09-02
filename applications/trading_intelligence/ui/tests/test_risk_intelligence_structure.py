"""Structural tests for Risk Intelligence's self-containment.

test_ui_structure.py already scans every file under ui/ (including this
package) for bot/dashboard/scheduler/sentinel_engine imports -- not
repeated here. This file covers what's unique to this package: no
coupling to ui/decision_center/ or ui/portfolio_intelligence/, no
`RiskEvaluation` class name anywhere (the task's explicit non-goal), and
no production module importing mock_data.py.
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


def test_risk_intelligence_theme_defines_local_spacing_tokens():
    """Local spacing-token extraction: theme.py must declare its own
    --ri-space-* custom properties rather than raw px literals or an
    import of another package's tokens (see test above)."""
    from applications.trading_intelligence.ui.risk_intelligence.theme import CSS

    for px in (2, 3, 4, 6, 8, 10, 12, 16, 24):
        assert f"--ri-space-{px}: {px}px;" in CSS, (
            f"expected a --ri-space-{px} token declared in theme.py's CSS"
        )


def test_risk_intelligence_theme_aliases_the_shared_colour_tokens():
    """Design-system migration (Batch B): theme.py's colour `:root` entries
    resolve through the shared `--aara-*` tokens from ui/design_system.py,
    each keeping its former hex as a `var(--aara-*, <literal>)` standalone-
    render fallback. Mirrors test_design_system.py's own
    test_migrated_screen_themes_alias_the_shared_colour_tokens (Batch A)."""
    from applications.trading_intelligence.ui.risk_intelligence.theme import CSS

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


def test_production_risk_modules_do_not_import_mock_data():
    """Production guarantee: the Risk Intelligence view (gradio_view.py)
    and the composition root (bootstrap.py) must not import or use
    risk_intelligence.mock_data / build_mock_screen. mock_data.py stays
    only for its own isolated unit test and must be unreachable from
    build_trading_intelligence_app() -- Risk Intelligence renders real /
    unavailable only."""
    view = (_PACKAGE_ROOT / "gradio_view.py").read_text(encoding="utf-8")
    bootstrap = (
        pathlib.Path(__file__).resolve().parents[2] / "bootstrap.py"
    ).read_text(encoding="utf-8")

    assert "risk_intelligence.mock_data" not in view
    assert "build_mock_screen" not in view
    assert "risk_intelligence.mock_data" not in bootstrap


def test_risk_intelligence_screen_current_defaults_to_none():
    """The production default RiskScreen() must represent no real risk
    data -- current is None, is_available is False -- so the view renders
    an explicit UNAVAILABLE state rather than a fabricated
    NORMAL/WARNING/DEFENSIVE snapshot."""
    from applications.trading_intelligence.ui.risk_intelligence.screen import RiskScreen

    screen = RiskScreen()
    assert screen.current is None
    assert screen.is_available is False
    assert screen.unavailable_message == "Risk Intelligence data is currently unavailable."


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
