"""Shared AARA shell (logo/wordmark header + inter-screen nav) for Trading
Intelligence screens that are not Decision Center.

Why this exists: `ui/decision_center/gradio_view.py` already defines its own
private `_load_shell_logo_data_uri()`/`_SHELL_IDENTITY_HTML`/`_SHELL_NAV_HTML`.
Portfolio Intelligence, Risk Intelligence, Morning Brief, Performance &
Learning, and Settings each document themselves as not importing
`ui/decision_center/` (see their own module docstrings and
`tests/test_portfolio_intelligence_structure.py` /
`test_risk_intelligence_structure.py` / `test_morning_brief_structure.py` /
`test_performance_learning_structure.py` / `test_settings_structure.py`),
so this module -- a sibling of all six screen packages, not owned by any
one of them -- is the shared source those five screens reuse instead of
each defining their own copy. This keeps the shell to two implementations
(Decision Center's own, and this one shared by Portfolio/Risk/Morning
Brief/Performance & Learning/Settings) rather than six independently-
drifting copies of the same logo-loading/cropping logic and nav markup.
This is the complete, frozen six-screen set per
`docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` Section 1.

Known, accepted divergence: `ui/decision_center/gradio_view.py`'s own
`_SHELL_NAV_HTML` is a private literal that predates Morning Brief,
Performance & Learning, and Settings, and is out of scope for the backlog
slices that added them to `SHELL_NAV_LABELS` below -- it still lists only
Decision Center/Portfolio Intelligence/Risk Intelligence, so
`build_shell_nav_html("Decision Center")` (this module's version) and
`_SHELL_NAV_HTML` (Decision Center's own) are no longer byte-for-byte
identical -- Decision Center's own inner nav omits the Morning Brief,
Performance & Learning, and Settings tabs. Reconciling them requires
editing `ui/decision_center/gradio_view.py`, which is a separate, future
change.

CSS is deliberately NOT duplicated here. `.aara-shell-header`/`.aara-shell-nav`/
`.nav-item` and the `--color-*`/`--space-*` tokens they use are already
defined in `ui/decision_center/theme.py`'s CSS, and `bootstrap.py`'s
`build_trading_intelligence_app()` already merges all six screens' CSS
(`morning_brief_blocks.css`, `decision_blocks.css`, `portfolio_blocks.css`,
`risk_blocks.css`, `performance_learning_blocks.css`, `settings_blocks.css`)
into one `<style>` block for the composed app -- so Decision Center's
shell CSS is already globally available on every tab once composed. This
module only needs to reuse those existing class names, not restate their
rules.
"""
import base64
import io
import pathlib

from PIL import Image as PILImage

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

SHELL_NAV_LABELS = (
    "Morning Brief", "Decision Center", "Portfolio Intelligence", "Risk Intelligence",
    "Performance & Learning", "Settings",
)


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

    Duplicate-navigation audit (this pass): the composed app's outer
    gr.TabbedInterface tabs are the real ARIA Tabs pattern already
    (role="tablist"/"tab"/aria-selected on native Gradio buttons) and are
    now hidden in the composed app via bootstrap.py's _TABBED_LAYOUT_CSS, so
    this markup -- the one visible nav row left -- carries that same
    role="tablist"/"tab"/aria-selected pattern itself instead of the
    role="link" it used before. bootstrap.py's _INNER_NAV_LINK_JS still finds
    and wires each item by its text content and forwards clicks/Enter/Space
    to the (now hidden but still functional) real tab button, unchanged.
    """
    if active_label not in SHELL_NAV_LABELS:
        raise ValueError(f"active_label must be one of {SHELL_NAV_LABELS!r}, got {active_label!r}")
    items = "".join(
        f'<span class="nav-item active" role="tab" aria-selected="true">{label}</span>'
        if label == active_label
        else f'<span class="nav-item" role="tab" aria-selected="false">{label}</span>'
        for label in SHELL_NAV_LABELS
    )
    return f'<nav class="aara-shell-nav-list" role="tablist">{items}</nav>'
