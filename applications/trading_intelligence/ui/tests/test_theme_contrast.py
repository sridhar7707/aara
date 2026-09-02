"""WCAG contrast regression tests for the three documented color fixes in
theme.py (search that file for "WCAG contrast fix (live audit)"): each one
replaced a token that measured below its applicable floor during a manual
audit with a dedicated, darker value scoped to just that boundary/text role.
These tests turn that audit's numeric findings into a permanent regression
guard -- pure color math, no Gradio import, no rendering -- so a future edit
to any of the three tokens' hex values in theme.py's CSS text is caught here
instead of silently regressing back below the floor it was fixed to clear.

Tokens are read out of theme.py's own CSS string via regex rather than
duplicated as literal hex constants, so a value change in theme.py is what
this file actually tests, not a frozen snapshot of today's palette.

Background bases (#F8F7F3 warm page body, #F9FAFB Gradio's own Dataframe row
background) are not tokens -- they were confirmed by live-rendering the
Decision Center app and reading getComputedStyle() on real elements (see the
P2 WCAG Contrast verification pass), not assumed.
"""
import re

import pytest

from applications.trading_intelligence.ui.decision_center.theme import CSS

_WARM_BG = "#F8F7F3"  # --color-background-warm; also confirmed live as the
# Decision Journey / record-card surrounding background.
_WHITE_BG = "#FFFFFF"  # --color-surface-white; also confirmed live as the
# lifecycle dot's own fill (what its border sits against).
_TABLE_ROW_BG = "#F9FAFB"  # Gradio's own Dataframe row background, live-
# verified -- not an AARA token, not assumed to equal warm/white.

_NORMAL_TEXT_FLOOR = 4.5  # WCAG 2.1 SC 1.4.3
_UI_COMPONENT_FLOOR = 3.0  # WCAG 2.1 SC 1.4.11


def _token_hex(name: str) -> str:
    """The token's hex -- read directly, or from the `var(--aara-*,
    <literal>)` fallback for the `:root` entries the Batch B2 design-system
    migration aliased to shared tokens. The fallback literal is still the
    effective standalone-render value and the audited WCAG-safe one, so the
    contrast math below is unchanged."""
    match = re.search(
        rf"--{re.escape(name)}:\s*(?:var\(--[\w-]+,\s*)?(#[0-9A-Fa-f]{{6}})", CSS
    )
    assert match, f"expected a --{name} hex (solid or var() fallback) in theme.py's CSS"
    return match.group(1)


def _token_rgba(name: str):
    """Returns (hex_rgb, alpha) for a `--name: rgba(r, g, b, a);` token."""
    match = re.search(
        rf"--{re.escape(name)}:\s*rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)",
        CSS,
    )
    assert match, f"expected an rgba() --{name} token in theme.py's CSS"
    r, g, b, a = match.groups()
    return f"#{int(r):02X}{int(g):02X}{int(b):02X}", float(a)


def _linearize(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def _contrast_ratio(hex_a: str, hex_b: str) -> float:
    l1, l2 = _relative_luminance(hex_a), _relative_luminance(hex_b)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _blend_over(fg_hex: str, alpha: float, bg_hex: str) -> str:
    fg = fg_hex.lstrip("#")
    bg = bg_hex.lstrip("#")
    out = []
    for i in (0, 2, 4):
        f = int(fg[i:i + 2], 16)
        b = int(bg[i:i + 2], 16)
        out.append(round(f * alpha + b * (1 - alpha)))
    return "#{:02X}{:02X}{:02X}".format(*out)


# --------------------------------------------------------------------------
# --color-gold-accent-boundary: the WCAG-safe gold used for the focus ring,
# the active nav underline, and the active lifecycle dot -- a UI-component
# boundary role, not body text, so the 3:1 floor applies. Checked against
# every background it's live-rendered on (navy header, white nav/dot, warm
# page body).
# --------------------------------------------------------------------------
@pytest.mark.parametrize("background", [_WHITE_BG, _WARM_BG, "#0B1F3A"])
def test_gold_accent_boundary_meets_ui_component_floor(background):
    gold_boundary = _token_hex("color-gold-accent-boundary")
    ratio = _contrast_ratio(gold_boundary, background)
    assert ratio >= _UI_COMPONENT_FLOOR, (
        f"--color-gold-accent-boundary ({gold_boundary}) vs {background} is "
        f"{ratio:.2f}:1, below the {_UI_COMPONENT_FLOOR}:1 UI-component floor"
    )


# --------------------------------------------------------------------------
# --lifecycle-future: the only visual differentiator between a "complete"
# and a "not yet reached" lifecycle stage (both render their label in the
# same --color-text-secondary, confirmed live -- the dot fill/border and
# connector color are what actually carry that distinction), so this is a
# graphical object required to understand content, not decoration -- the
# 3:1 floor applies. Checked against both live-confirmed contexts: the dot's
# own white fill (border role) and the connector bar's warm page-body
# surroundings (fill role).
# --------------------------------------------------------------------------
@pytest.mark.parametrize("background", [_WHITE_BG, _WARM_BG])
def test_lifecycle_future_meets_ui_component_floor(background):
    lifecycle_future = _token_hex("lifecycle-future")
    ratio = _contrast_ratio(lifecycle_future, background)
    assert ratio >= _UI_COMPONENT_FLOOR, (
        f"--lifecycle-future ({lifecycle_future}) vs {background} is "
        f"{ratio:.2f}:1, below the {_UI_COMPONENT_FLOOR}:1 UI-component floor"
    )


# --------------------------------------------------------------------------
# --action-hold-fg: darkened from --color-text-secondary specifically because
# the alias failed 4.5:1 once composited over --action-hold-bg's own tint.
# Re-derives that composited color from the live CSS tokens (not a frozen
# snapshot) and checks it against both real surfaces that tint renders on:
# the warm page body (record cards) and Gradio's own Dataframe row
# background (list/verdict badges).
# --------------------------------------------------------------------------
@pytest.mark.parametrize("background", [_WARM_BG, _TABLE_ROW_BG])
def test_action_hold_fg_meets_text_floor_on_its_own_badge_tint(background):
    action_hold_fg = _token_hex("action-hold-fg")
    tint_hex, tint_alpha = _token_rgba("action-hold-bg")
    composited_bg = _blend_over(tint_hex, tint_alpha, background)
    ratio = _contrast_ratio(action_hold_fg, composited_bg)
    assert ratio >= _NORMAL_TEXT_FLOOR, (
        f"--action-hold-fg ({action_hold_fg}) on --action-hold-bg composited "
        f"over {background} ({composited_bg}) is {ratio:.2f}:1, below the "
        f"{_NORMAL_TEXT_FLOOR}:1 text floor"
    )
