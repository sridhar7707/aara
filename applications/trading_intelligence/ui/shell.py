"""Shared AARA shell (logo/wordmark header + inter-screen nav) for Trading
Intelligence screens that are not Decision Center.

Why this exists: `ui/decision_center/gradio_view.py` already defines its own
private `_load_shell_logo_data_uri()`/`_SHELL_IDENTITY_HTML`/`_SHELL_NAV_HTML`
and is the one screen that must stay byte-for-byte unchanged (its own tests
pin its exact markup). Portfolio Intelligence and Risk Intelligence each
document themselves as not importing `ui/decision_center/` (see their own
module docstrings and `tests/test_portfolio_intelligence_structure.py` /
`test_risk_intelligence_structure.py`), so this module -- a sibling of all
three screen packages, not owned by any one of them -- is the shared source
those two screens reuse instead of each defining their own copy. This keeps
the shell to two implementations (Decision Center's own, and this one shared
by Portfolio/Risk) rather than three independently-drifting copies of the
same logo-loading/cropping logic and nav markup.

CSS is deliberately NOT duplicated here. `.aara-shell-header`/`.aara-shell-nav`/
`.nav-item` and the `--color-*`/`--space-*` tokens they use are already
defined in `ui/decision_center/theme.py`'s CSS, and `bootstrap.py`'s
`build_trading_intelligence_app()` already merges all three screens' CSS
(`decision_blocks.css`, `portfolio_blocks.css`, `risk_blocks.css`) into one
`<style>` block for the composed app -- so Decision Center's shell CSS is
already globally available on every tab once composed. This module only
needs to reuse those existing class names, not restate their rules.
"""
import base64
import io
import pathlib

from PIL import Image as PILImage

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

SHELL_NAV_LABELS = ("Decision Center", "Portfolio Intelligence", "Risk Intelligence")


def load_shell_logo_data_uri() -> str:
    """Loads the approved Sentinel Mark asset and returns it as a base64
    data: URI for direct <img src=...> embedding.

    Identical asset choice and crop-to-alpha-bbox logic as
    `ui/decision_center/gradio_view.py`'s own `_load_shell_logo_data_uri` --
    see that function's docstring for why the favicon variant (not the
    "primary" gold-on-navy asset) is used and why it's cropped. Duplicated
    here (not imported from decision_center) per this module's own docstring:
    Decision Center stays unowned by, and unaware of, this shared module.
    """
    source = PILImage.open(
        str(_REPO_ROOT / "brand" / "logos" / "sentinel_mark_favicon_v1.0.png")
    ).convert("RGBA")
    cropped = source.crop(source.getchannel("A").getbbox())
    buffer = io.BytesIO()
    cropped.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


SHELL_IDENTITY_HTML = (
    f'<img class="aara-shell-logo" src="{load_shell_logo_data_uri()}" alt="AARA" />'
    '<div class="aara-shell-wordmark-group">'
    '<div class="aara-shell-wordmark">AARA</div>'
    '<div class="aara-shell-descriptor">Trading Intelligence</div>'
    "</div>"
)


def build_shell_nav_html(active_label: str) -> str:
    """Builds the same `<nav class="aara-shell-nav-list">` markup pattern
    Decision Center's own `_SHELL_NAV_HTML` uses (identical class names, so
    it renders with Decision Center's already-shared CSS), parameterized on
    which label carries the `nav-item active` class -- Decision Center's own
    copy stays a hardcoded literal marking itself active; this is the
    equivalent for whichever screen calls it marking itself active instead.
    """
    if active_label not in SHELL_NAV_LABELS:
        raise ValueError(f"active_label must be one of {SHELL_NAV_LABELS!r}, got {active_label!r}")
    items = "".join(
        f'<span class="nav-item active">{label}</span>' if label == active_label
        else f'<span class="nav-item">{label}</span>'
        for label in SHELL_NAV_LABELS
    )
    return f'<nav class="aara-shell-nav-list">{items}</nav>'
