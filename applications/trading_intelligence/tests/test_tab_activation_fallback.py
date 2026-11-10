"""Regression tests for Gradio 5 tab navigation and the Decisions table header.

Gradio 4.44.1 renders every tab button with role="tab", so the app's nav scripts can click
them directly. Gradio 5.50 renders only the selected tab with role="tab"; the rest overflow
into the "..." dropdown, because the app hides Gradio's tab bar. Each nav script must fall
back to that dropdown. These are string-level guards: the browser behaviour was verified
with Playwright against both builds (all six nav items switch panels on each).
"""
import re

from applications.trading_intelligence.bootstrap import _INNER_NAV_LINK_JS
from applications.trading_intelligence.ui.decision_center import gradio_view as dc_view
from applications.trading_intelligence.ui.decision_center import theme as dc_theme
from applications.trading_intelligence.ui.morning_brief import gradio_view as mb_view


def test_every_nav_script_falls_back_to_the_overflow_dropdown():
    for name, js in (
        ("shell nav", _INNER_NAV_LINK_JS),
        ("morning brief drilldown", mb_view._DRILLDOWN_NAV_JS),
        ("risk reference link", dc_view._RISK_REFERENCE_NAV_LINK_JS),
    ):
        assert 'button[role="tab"]' in js, f"{name}: Gradio 4 path missing"
        assert ".overflow-dropdown button" in js, f"{name}: Gradio 5 fallback missing"


def test_gradio4_path_is_tried_before_the_overflow_fallback():
    for name, js in (
        ("shell nav", _INNER_NAV_LINK_JS),
        ("morning brief drilldown", mb_view._DRILLDOWN_NAV_JS),
        ("risk reference link", dc_view._RISK_REFERENCE_NAV_LINK_JS),
    ):
        assert js.index('button[role="tab"]') < js.index(".overflow-dropdown button"), name


def _column_shares(css: str) -> list[float]:
    return [float(v) for v in re.findall(r"--cell-width-[1-6]:\s*([0-9.]+)%", css)]


def test_decisions_column_shares_fill_the_table_exactly():
    shares = _column_shares(dc_theme.DECISION_CENTER_CSS) if hasattr(dc_theme, "DECISION_CENTER_CSS") else []
    if not shares:
        import inspect
        source = inspect.getsource(dc_theme)
        shares = _column_shares(source)
    assert len(shares) == 6
    assert abs(sum(shares) - 100.0) < 1e-9


def test_decisions_headers_wrap_instead_of_ellipsizing():
    import inspect
    source = inspect.getsource(dc_theme)
    assert ".aara-decisions-table table thead th .header-button" in source
    assert "text-overflow: clip !important" in source
