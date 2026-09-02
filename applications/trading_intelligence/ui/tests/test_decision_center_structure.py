"""Structural tests for Decision Center's theme after the Batch B2
design-system migration.

test_ui_structure.py already scans ui/ for forbidden sibling imports and
test_theme_contrast.py covers the three WCAG contrast fixes -- neither is
repeated here. This file covers what Batch B2 introduced:

* theme.py's colour `:root` entries now alias the shared `--aara-*` tokens
  from ui/design_system.py, each keeping its former hex as a
  `var(--aara-*, <literal>)` standalone-render fallback (audit finding
  D-01). Mirrors test_risk_intelligence_structure.py /
  test_settings_structure.py's own alias guards (Batch B1).
* the duplicate *bare* `.aara-disclosure-title` / `.aara-disclosure-body`
  declarations that shadowed the identical shared primitives are gone so
  design_system.py is the single authority for them (audit finding R-1);
  Decision Center retains only a wrapper-scoped
  `.aara-disclosure-message .aara-disclosure-title/-body` variant, kept so
  a standalone `DecisionCenterUI().build()` still renders identically (D1).
"""
from applications.trading_intelligence.ui.decision_center.theme import CSS
from applications.trading_intelligence.ui.design_system import DESIGN_SYSTEM_CSS


def test_decision_center_theme_aliases_the_shared_colour_tokens():
    """Every colour `:root` entry resolves through a shared `--aara-*`
    token, each keeping its former hex as a `var(--aara-*, <literal>)`
    standalone-render fallback (the composed app resolves through the
    shared token)."""
    for alias in (
        "--color-navy-primary: var(--aara-navy, #0B1F3A);",
        "--color-emerald-secondary: var(--aara-emerald, #176B4D);",
        "--color-gold-accent: var(--aara-gold, #C8A45D);",
        "--color-gold-accent-boundary: var(--aara-gold-boundary, #A8823D);",
        "--color-background-warm: var(--aara-bg, #F8F7F3);",
        "--color-surface-white: var(--aara-surface, #FFFFFF);",
        "--color-text-primary: var(--aara-text, #1A1A1A);",
        "--color-text-secondary: var(--aara-text-muted, #666666);",
        "--color-border-subtle: var(--aara-border, #E2E8F0);",
    ):
        assert alias in CSS, f"expected shared-token alias {alias!r} in theme.py's CSS"


def test_decision_center_theme_preserves_its_screen_specific_semantic_colours():
    """The DC-specific lifecycle / trade-action vocabulary has no
    established shared equivalent (see theme.py's module docstring, which
    deliberately keeps it distinct from brand's --status-* tokens) and
    stays local, literal, and unchanged by the migration."""
    for literal in (
        "--lifecycle-future: #7C8CA0;",
        "--action-buy-bg: rgba(23, 107, 77, 0.10);",
        "--action-sell-bg: rgba(11, 31, 58, 0.08);",
        "--action-hold-bg: rgba(102, 102, 102, 0.10);",
        "--action-hold-fg: #5D5D5D;",
    ):
        assert literal in CSS, f"expected DC-local semantic colour {literal!r} unchanged"


def test_decision_center_theme_no_longer_shadows_shared_disclosure_primitives():
    """Audit finding R-1: theme.py used to redeclare the *bare*
    `.aara-disclosure-title` / `.aara-disclosure-body` selectors (both
    `color: var(--color-text-secondary)`), shadowing the identical shared
    primitives in design_system.py. The bare selectors are removed here so
    design_system.py stays the single authority for them. Decision Center
    keeps only a *scoped* variant, `.aara-disclosure-message
    .aara-disclosure-title/-body`, which matches nothing outside its own
    wrapper markup and exists to preserve standalone DecisionCenterUI
    appearance (the composed app, which loads DESIGN_SYSTEM_CSS, renders
    byte-identically either way -- see D1 investigation)."""
    # No bare (line-start) redeclaration in Decision Center's theme.
    assert "\n.aara-disclosure-title {" not in CSS
    assert "\n.aara-disclosure-body {" not in CSS
    # The authoritative bare primitives still live in the shared system.
    assert ".aara-disclosure-title {" in DESIGN_SYSTEM_CSS
    assert ".aara-disclosure-body {" in DESIGN_SYSTEM_CSS
    # Decision Center keeps only the wrapper-scoped variant.
    assert ".aara-disclosure-message .aara-disclosure-title {" in CSS
    assert ".aara-disclosure-message .aara-disclosure-body {" in CSS


def test_decision_center_scoped_disclosure_rules_preserve_the_shared_typography():
    """The DC-scoped `.aara-disclosure-message .aara-disclosure-title/-body`
    rules must carry the same typography as the shared primitives so
    standalone and composed renders match: title 13px / 600, body 13px /
    italic."""
    title_block = CSS.split(".aara-disclosure-message .aara-disclosure-title {", 1)[1].split("}", 1)[0]
    assert "font-size: 13px;" in title_block
    assert "font-weight: 600;" in title_block

    body_block = CSS.split(".aara-disclosure-message .aara-disclosure-body {", 1)[1].split("}", 1)[0]
    assert "font-size: 13px;" in body_block
    assert "font-style: italic;" in body_block


def test_decision_center_theme_keeps_its_disclosure_message_wrapper():
    """`.aara-disclosure-message` is Decision-Center-specific markup
    (gradio_view.py emits it as the disclosure container) with no shared
    equivalent -- it is preserved verbatim, still keyed to the migrated
    border token."""
    assert ".aara-disclosure-message {" in CSS
    assert "border-left: 2px solid var(--color-border-subtle);" in CSS


def test_decision_center_theme_css_has_balanced_braces():
    """Cheap structural-validity guard: the disclosure de-duplication must
    not leave a dangling or unclosed rule block."""
    assert CSS.count("{") == CSS.count("}")
