"""Tests for applications.trading_intelligence.bootstrap.
build_trading_intelligence_app() -- the gr.TabbedInterface composition of
Decision Center + Portfolio Intelligence + Risk Intelligence.
"""
import gradio as gr

from applications.trading_intelligence.bootstrap import build_trading_intelligence_app


def test_returns_a_gradio_blocks_instance():
    app = build_trading_intelligence_app()

    assert isinstance(app, gr.Blocks)


def test_has_exactly_three_tabs_in_order():
    app = build_trading_intelligence_app()

    tab_labels = [
        block.label for block in app.blocks.values()
        if isinstance(block, gr.Tab)
    ]

    assert tab_labels == ["Decision Center", "Portfolio Intelligence", "Risk Intelligence"]


def test_title_matches_decision_centers_own_title():
    app = build_trading_intelligence_app()

    assert app.title == "AARA Trading Intelligence — Decision Center"


def test_css_includes_all_three_screens_own_styles():
    app = build_trading_intelligence_app()

    # Decision Center's own theme.py token; Portfolio Intelligence's own
    # theme.py class; Risk Intelligence's own theme.py class -- all three
    # must survive the TabbedInterface merge.
    assert "--color-navy-primary" in app.css
    assert ".pi-capital-summary" in app.css
    assert ".ri-current-state" in app.css


def test_head_includes_decision_centers_accessibility_bridges():
    app = build_trading_intelligence_app()

    assert "aara-live-announcer" in app.head
    assert "aara-decisions-table" in app.head


def test_head_includes_the_portfolio_nav_link_bridge():
    app = build_trading_intelligence_app()

    assert "aara-shell-nav-list" in app.head
    assert "Portfolio Intelligence" in app.head
    assert 'role", "link"' in app.head


def test_decision_center_content_is_present_in_the_composed_app():
    app = build_trading_intelligence_app()

    html_values = [
        block.value for block in app.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert any("Illustrative Data" in value for value in html_values)
    assert any("Decision Center" in value for value in html_values)


def test_portfolio_intelligence_content_is_present_in_the_composed_app():
    app = build_trading_intelligence_app()

    html_values = [
        block.value for block in app.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert any("Portfolio Intelligence" in value for value in html_values)

    dataframes = [block for block in app.blocks.values() if isinstance(block, gr.Dataframe)]
    assert any("pi-holdings-table" in (df.elem_classes or []) for df in dataframes)


def test_risk_intelligence_content_is_present_in_the_composed_app():
    app = build_trading_intelligence_app()

    html_values = [
        block.value for block in app.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert any("Risk Intelligence" in value for value in html_values)
    assert any("Current risk-governor state" in value for value in html_values)

    dataframes = [block for block in app.blocks.values() if isinstance(block, gr.Dataframe)]
    assert any("ri-history-table" in (df.elem_classes or []) for df in dataframes)


def test_refresh_double_submit_guard_chain_survives_composition():
    """Regression guard for the loading-states slice: the disable ->
    render -> enable .then() chain (see ui/decision_center/gradio_view.py)
    must remain intact -- same trigger_after linkage the standalone app
    has -- after being merged into the tabbed composition."""
    from applications.trading_intelligence.ui.decision_center.gradio_view import (
        DecisionCenterUI,
    )

    app = build_trading_intelligence_app()

    disable_dep = next(
        dep for dep in app.config["dependencies"]
        if app.fns[dep["id"]].fn is DecisionCenterUI._disable_refresh_button
    )
    enable_dep = next(
        dep for dep in app.config["dependencies"]
        if app.fns[dep["id"]].fn is DecisionCenterUI._enable_refresh_button
    )
    render_dep = next(
        dep for dep in app.config["dependencies"]
        if dep.get("trigger_after") == disable_dep["id"]
    )

    assert enable_dep["trigger_after"] == render_dep["id"]
