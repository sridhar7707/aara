import pytest

from applications.trading_intelligence.ui.shell import (
    SHELL_IDENTITY_HTML,
    SHELL_NAV_LABELS,
    build_shell_nav_html,
    load_shell_logo_data_uri,
)


def test_shell_nav_labels_are_the_three_shipped_screens_in_tab_order():
    assert SHELL_NAV_LABELS == ("Decision Center", "Portfolio Intelligence", "Risk Intelligence")


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
        "Decision Center</span>"
    ) in nav_html
    assert (
        '<span class="nav-item" role="tab" aria-selected="false">'
        "Risk Intelligence</span>"
    ) in nav_html
    assert nav_html.count('class="nav-item active"') == 1
    assert nav_html.count('aria-selected="true"') == 1
    assert nav_html.count('aria-selected="false"') == 2
    assert 'role="tablist"' in nav_html


def test_build_shell_nav_html_matches_decision_centers_own_markup_byte_for_byte():
    """Parity check against ui/decision_center/gradio_view.py's own
    _SHELL_NAV_HTML (Decision Center active, others plain) -- this test file
    (not shell.py itself, which never imports decision_center -- see its own
    docstring) is where that parity gets verified, so a future drift in
    either format is caught here."""
    from applications.trading_intelligence.ui.decision_center.gradio_view import _SHELL_NAV_HTML

    assert build_shell_nav_html("Decision Center") == _SHELL_NAV_HTML


def test_build_shell_nav_html_rejects_an_unknown_label():
    with pytest.raises(ValueError):
        build_shell_nav_html("Not A Real Screen")
