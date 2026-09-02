"""Tests for the shared design-system foundation (Batch A).

Covers `ui/design_system.py` -- the single source of truth for the product's
visual tokens and reusable primitives -- and its wiring into the composed
Trading Intelligence app.
"""
import re

from applications.trading_intelligence.ui.design_system import DESIGN_SYSTEM_CSS


# --- module shape --------------------------------------------------------------

def test_design_system_css_is_a_non_empty_string():
    assert isinstance(DESIGN_SYSTEM_CSS, str)
    assert DESIGN_SYSTEM_CSS.strip()
    assert ":root" in DESIGN_SYSTEM_CSS


def test_design_system_module_has_no_forbidden_imports():
    import applications.trading_intelligence.ui.design_system as mod
    import pathlib

    source = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for forbidden in ("import bot", "import dashboard", "import sentinel_engine", "import scheduler"):
        assert forbidden not in source


# --- semantic token set ------------------------------------------------------

_EXPECTED_COLOR_TOKENS = (
    "--aara-bg", "--aara-surface", "--aara-border", "--aara-text", "--aara-text-muted",
    "--aara-navy", "--aara-gold", "--aara-gold-boundary", "--aara-emerald",
    "--aara-status-neutral-bg", "--aara-status-neutral-fg",
    "--aara-status-warning-bg", "--aara-status-warning-fg",
    "--aara-status-defensive-bg", "--aara-status-defensive-fg",
    "--aara-negative-fg", "--aara-negative-bg",
)
_EXPECTED_SCALE_TOKENS = (
    "--aara-space-1", "--aara-space-2", "--aara-space-3", "--aara-space-4", "--aara-space-5",
    "--aara-radius-card", "--aara-radius-badge", "--aara-shadow-card",
)
_EXPECTED_TYPE_TOKENS = (
    "--aara-font-sans", "--aara-font-data",
    "--aara-type-page-title", "--aara-type-section-label", "--aara-type-body",
    "--aara-type-value", "--aara-type-caption",
)
_EXPECTED_LAYOUT_TOKENS = ("--aara-content-max",)


def test_all_semantic_tokens_are_declared():
    for token in (
        _EXPECTED_COLOR_TOKENS + _EXPECTED_SCALE_TOKENS
        + _EXPECTED_TYPE_TOKENS + _EXPECTED_LAYOUT_TOKENS
    ):
        assert f"{token}:" in DESIGN_SYSTEM_CSS, f"missing token {token}"


def test_spacing_scale_is_4_8_16_24_32():
    for i, px in ((1, 4), (2, 8), (3, 16), (4, 24), (5, 32)):
        assert f"--aara-space-{i}: {px}px;" in DESIGN_SYSTEM_CSS


def test_brand_values_match_the_product_palette():
    for token, value in (
        ("--aara-bg", "#F8F7F3"),
        ("--aara-surface", "#FFFFFF"),
        ("--aara-border", "#E2E8F0"),
        ("--aara-navy", "#0B1F3A"),
        ("--aara-gold", "#C8A45D"),
        ("--aara-gold-boundary", "#A8823D"),
        ("--aara-text", "#1A1A1A"),
        ("--aara-text-muted", "#666666"),
    ):
        assert f"{token}: {value};" in DESIGN_SYSTEM_CSS


# --- colour safety ---------------------------------------------------------

def test_negative_token_is_restrained_not_stoplight_red():
    """The loss cue must not be a bright-red trading-dashboard colour."""
    assert "--aara-negative-fg: #7A2E2E;" in DESIGN_SYSTEM_CSS
    lowered = DESIGN_SYSTEM_CSS.lower()
    for bright_red in ("#ff0000", "#f00;", "#ff0033", "#e53935", "#ff5252", "red;"):
        assert bright_red not in lowered


def test_no_bright_green_gain_colour_either():
    lowered = DESIGN_SYSTEM_CSS.lower()
    for stoplight_green in ("#00c853", "#00c805", "#00ff00", "green;"):
        assert stoplight_green not in lowered


# --- typeface decision (D-02) -------------------------------------------------

def test_font_stack_is_system_sans_with_no_network_font():
    # No @font-face / external font is loaded anywhere in the shared system.
    assert "@font-face" not in DESIGN_SYSTEM_CSS
    assert "fonts.googleapis" not in DESIGN_SYSTEM_CSS
    assert "fonts.gstatic" not in DESIGN_SYSTEM_CSS
    # The stack is a real system fallback chain (Inter only opportunistically first).
    m = re.search(r"--aara-font-sans:\s*([^;]+);", DESIGN_SYSTEM_CSS)
    assert m, "expected --aara-font-sans declaration"
    stack = m.group(1)
    assert "-apple-system" in stack and "Segoe UI" in stack and "sans-serif" in stack
    assert stack.strip().startswith("Inter,")  # opportunistic first, not the only option


# --- reusable primitives ---------------------------------------------------

_EXPECTED_PRIMITIVES = (
    ".aara-card", ".aara-metric", ".aara-metric-label", ".aara-metric-value",
    ".aara-caption", ".aara-disclosure", ".aara-disclosure-title", ".aara-disclosure-body",
    ".aara-status-badge",
    ".aara-status-badge--normal", ".aara-status-badge--warning",
    ".aara-status-badge--defensive", ".aara-status-badge--neutral",
    ".aara-empty", ".aara-table--secondary", ".aara-num", ".aara-content",
)


def test_all_primitives_are_defined():
    for selector in _EXPECTED_PRIMITIVES:
        assert f"{selector} " in DESIGN_SYSTEM_CSS or f"{selector}{{" in DESIGN_SYSTEM_CSS \
            or f"{selector}," in DESIGN_SYSTEM_CSS, f"missing primitive {selector}"


def test_metric_value_is_right_aligned_and_tabular():
    block = DESIGN_SYSTEM_CSS.split(".aara-metric-value")[1].split("}")[0]
    assert "text-align: right" in block
    assert "tabular-nums" in block


def test_num_helper_right_aligns():
    block = DESIGN_SYSTEM_CSS.split(".aara-num")[1].split("}")[0]
    assert "text-align: right" in block


# --- composition wiring --------------------------------------------------------

def test_composed_app_css_includes_the_design_system_first():
    from applications.trading_intelligence import bootstrap

    app = bootstrap.build_trading_intelligence_app()
    css = app.css or ""
    assert DESIGN_SYSTEM_CSS in css
    # Shared tokens come before any screen consumes them: the design-system
    # block precedes the first screen-specific class rule.
    ds_at = css.index("--aara-navy")
    first_screen_at = min(
        css.index(marker) for marker in (".mb-", ".pi-", ".ri-", ".pl-", ".st-", ".aara-shell-header")
        if marker in css
    )
    assert ds_at < first_screen_at


# --- migrated screens alias the shared tokens (Batch A scope) ----------------

def test_migrated_screen_themes_alias_the_shared_colour_tokens():
    from applications.trading_intelligence.ui.morning_brief.theme import CSS as MB
    from applications.trading_intelligence.ui.performance_learning.theme import CSS as PL
    from applications.trading_intelligence.ui.portfolio_intelligence.theme import CSS as PI

    for css in (MB, PL, PI):
        assert "var(--aara-navy, #0B1F3A)" in css
        assert "var(--aara-bg, #F8F7F3)" in css
        assert "var(--aara-text-muted, #666666)" in css


def test_portfolio_intelligence_right_aligns_numeric_table_columns():
    from applications.trading_intelligence.ui.portfolio_intelligence.theme import CSS as PI

    # Holdings numeric columns (2..5), Positions (2..7), Orders (5..7).
    assert ".pi-holdings-table table tbody td:nth-child(5)" in PI
    assert ".pi-alpaca-positions-table table tbody td:nth-child(7)" in PI
    assert ".pi-alpaca-orders-table table tbody td:nth-child(5)" in PI
    # the identifier column is NOT force-right-aligned
    assert ".pi-holdings-table table tbody td:nth-child(1)" not in PI
