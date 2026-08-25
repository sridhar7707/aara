import pytest

from applications.trading_intelligence.ui.shell import (
    SHELL_IDENTITY_HTML,
    SHELL_NAV_LABELS,
    build_shell_nav_html,
    load_shell_logo_data_uri,
)


def test_shell_nav_labels_are_the_six_shipped_screens_in_tab_order():
    assert SHELL_NAV_LABELS == (
        "Morning Brief", "Decision Center", "Portfolio Intelligence", "Risk Intelligence",
        "Performance & Learning", "Settings",
    )


def test_load_shell_logo_data_uri_returns_a_png_data_uri():
    data_uri = load_shell_logo_data_uri()

    assert data_uri.startswith("data:image/png;base64,")


def test_shell_identity_html_embeds_the_logo_and_wordmark():
    assert 'class="aara-shell-logo"' in SHELL_IDENTITY_HTML
    assert "AARA" in SHELL_IDENTITY_HTML
    assert "Trading Intelligence" in SHELL_IDENTITY_HTML


def test_build_shell_nav_html_marks_exactly_the_requested_label_active():
    """Duplicate-navigation audit: each item now carries role="tab" and
    aria-selected, matching the outer gr.TabbedInterface tabs' own ARIA
    pattern -- this nav becomes the app's one accessible tablist once the
    outer tabs are hidden (see bootstrap.py's _TABBED_LAYOUT_CSS)."""
    nav_html = build_shell_nav_html("Portfolio Intelligence")

    assert (
        '<span class="nav-item active" role="tab" aria-selected="true">'
        "Portfolio Intelligence</span>"
    ) in nav_html
    assert (
        '<span class="nav-item" role="tab" aria-selected="false">'
        "Morning Brief</span>"
    ) in nav_html
    assert (
        '<span class="nav-item" role="tab" aria-selected="false">'
        "Decision Center</span>"
    ) in nav_html
    assert (
        '<span class="nav-item" role="tab" aria-selected="false">'
        "Risk Intelligence</span>"
    ) in nav_html
    assert (
        '<span class="nav-item" role="tab" aria-selected="false">'
        "Performance & Learning</span>"
    ) in nav_html
    assert (
        '<span class="nav-item" role="tab" aria-selected="false">'
        "Settings</span>"
    ) in nav_html
    assert nav_html.count('class="nav-item active"') == 1
    assert nav_html.count('aria-selected="true"') == 1
    assert nav_html.count('aria-selected="false"') == 5
    assert 'role="tablist"' in nav_html


def test_build_shell_nav_html_diverges_from_decision_centers_own_markup_by_exactly_morning_brief_performance_learning_and_settings():
    """Known, accepted divergence (see shell.py's own module docstring):
    ui/decision_center/gradio_view.py's own _SHELL_NAV_HTML is a private
    literal that predates Morning Brief, Performance & Learning, and
    Settings, and is out of scope for the backlog slices that added them
    to SHELL_NAV_LABELS -- it was NOT modified. This replaces the previous
    byte-for-byte parity assertion (no longer true) with an explicit check
    of exactly what changed: this module's version now includes Morning
    Brief, Performance & Learning, and Settings entries Decision Center's
    own copy lacks, and is otherwise identical."""
    from applications.trading_intelligence.ui.decision_center.gradio_view import _SHELL_NAV_HTML

    this_modules_version = build_shell_nav_html("Decision Center")
    morning_brief_entry = '<span class="nav-item" role="tab" aria-selected="false">Morning Brief</span>'
    performance_learning_entry = (
        '<span class="nav-item" role="tab" aria-selected="false">Performance & Learning</span>'
    )
    settings_entry = '<span class="nav-item" role="tab" aria-selected="false">Settings</span>'

    assert this_modules_version != _SHELL_NAV_HTML
    assert morning_brief_entry in this_modules_version
    assert performance_learning_entry in this_modules_version
    assert settings_entry in this_modules_version
    assert morning_brief_entry not in _SHELL_NAV_HTML
    assert performance_learning_entry not in _SHELL_NAV_HTML
    assert settings_entry not in _SHELL_NAV_HTML
    without_added_entries = this_modules_version.replace(
        morning_brief_entry, "",
    ).replace(
        performance_learning_entry, "",
    ).replace(
        settings_entry, "",
    )
    assert without_added_entries == _SHELL_NAV_HTML


def test_build_shell_nav_html_rejects_an_unknown_label():
    with pytest.raises(ValueError):
        build_shell_nav_html("Not A Real Screen")
