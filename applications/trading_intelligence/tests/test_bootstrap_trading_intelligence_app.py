"""Tests for applications.trading_intelligence.bootstrap.
build_trading_intelligence_app() -- the gr.TabbedInterface composition of
Decision Center + Portfolio Intelligence + Risk Intelligence.
"""
import gradio as gr

from applications.trading_intelligence.bootstrap import build_trading_intelligence_app
from applications.trading_intelligence.ui.decision_center.gradio_view import (
    _SHELL_IDENTITY_HTML,
    _SHELL_NAV_HTML,
)
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html


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


def test_title_is_neutral_and_not_scoped_to_any_one_screen():
    """UI-polish audit (P1): gr.Blocks renders `title` as a visible page
    <h1>, not just the browser tab title -- reusing Decision Center's own
    title here left that <h1> reading "-- Decision Center" on the
    Portfolio/Risk Intelligence tabs too. The composed app now uses its own
    neutral title instead of any one screen's."""
    app = build_trading_intelligence_app()

    assert app.title == "AARA Trading Intelligence"


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


def test_head_includes_the_inner_nav_link_bridge_for_all_three_screens():
    """Generalized from a Portfolio-only bridge (see bootstrap.py's
    _INNER_NAV_LINK_JS docstring) once the AARA shell consistency pass gave
    Portfolio and Risk Intelligence their own inner nav -- including their
    own "Decision Center" item, whose bridge was the fix for a user-reported
    bug (inner "Decision Center" unclickable while on Portfolio
    Intelligence). Duplicate-navigation audit: the bridge now sets
    role="tab" (was role="link"), matching the inner nav's own static
    role="tab"/aria-selected markup now that it's the app's sole visible
    navigation."""
    app = build_trading_intelligence_app()

    assert "aara-shell-nav-list" in app.head
    assert "Decision Center" in app.head
    assert "Portfolio Intelligence" in app.head
    assert "Risk Intelligence" in app.head
    assert 'role", "tab"' in app.head


def test_shell_header_and_nav_are_present_on_all_three_tabs():
    """AARA shell consistency pass: Decision Center's own private shell
    identity constant is unchanged; its nav constant gained the ARIA tab
    markup described below, alongside Portfolio/Risk Intelligence's shared
    ui/shell.py equivalent, each marking itself active/selected."""
    app = build_trading_intelligence_app()

    html_values = [
        block.value for block in app.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]

    assert _SHELL_IDENTITY_HTML in html_values
    assert _SHELL_NAV_HTML in html_values
    assert SHELL_IDENTITY_HTML in html_values
    assert build_shell_nav_html("Portfolio Intelligence") in html_values
    assert build_shell_nav_html("Risk Intelligence") in html_values


def test_css_hides_only_the_outer_tabs_not_the_inner_nav():
    """Duplicate-navigation audit: composing all three screens produces two
    role="tablist" elements per screen (the outer native Gradio tabs, and
    each screen's own inner AARA nav) -- the composed app's CSS must hide
    only the outer one, explicitly excluding .aara-shell-nav-list, so the
    inner nav remains the app's one visible (and accessible) navigation."""
    app = build_trading_intelligence_app()

    assert '[role="tablist"]:not(.aara-shell-nav-list)' in app.css
    assert "display: none" in app.css


def test_css_hides_the_redundant_outer_title_block():
    """P3 Other Visual Polish audit: gr.TabbedInterface(title=...) renders
    the composed app's title as a plain, unstyled Gradio-default <h1>
    (wrapped in Gradio's own .prose class) directly above the fully-branded
    .aara-shell-header, which already states the same identity. The
    composed app's CSS must hide that whole title block."""
    app = build_trading_intelligence_app()

    assert ".block:has(.prose h1:not(.aara-eyebrow))" in app.css
    assert "display: none" in app.css


def test_css_title_hiding_selector_does_not_hide_aara_own_headings():
    """P0 regression (live-DOM audit): Decision Center's heading-hierarchy
    fix promoted its own page header from `<h2 class="aara-eyebrow">` to
    `<h1 class="aara-eyebrow">`. Since gr.HTML output is also wrapped in
    Gradio's `.prose` class, a bare `.block:has(.prose h1)` selector started
    matching -- and hiding -- that legitimate page header too, alongside
    Gradio's own unstyled default title. The selector must exclude any h1
    carrying `aara-eyebrow` so only Gradio's classless default title is
    hidden."""
    app = build_trading_intelligence_app()

    assert ":not(.aara-eyebrow)" in app.css
    assert ".block:has(.prose h1)" not in app.css.replace(
        ".block:has(.prose h1:not(.aara-eyebrow))", ""
    )


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
