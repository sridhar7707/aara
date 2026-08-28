"""Gradio shell for Morning Brief -- screen shell only.

Self-contained: does not import ui/decision_center/, ui/portfolio_intelligence/,
or ui/risk_intelligence/ (no cross-package import of any kind). No
controller, no service, no sentinel_engine/bot/dashboard import, and no
MorningBriefQuery of any kind (see screen.py's and mock_data.py's module
docstrings for why). Wired into bootstrap.py as the 4th Trading
Intelligence tab.

Data is fetched at render time, not build time: the UI takes a
`screen_provider` callable (bootstrap.py's `_build_morning_brief_screen`,
which assembles a MorningBriefScreen from LegacyCapitalSource,
LegacyRegimeSource, LegacyCandidateScreeningSource and AlpacaNewsSource)
and re-invokes it on every `demo.load()` and every Refresh click, so a
long-running Space shows data as of page load rather than app start. An
"As of {timestamp}" line reflects the last fetch. The Refresh button
reuses ui/decision_center/gradio_view.py's and
ui/portfolio_intelligence/gradio_view.py's disable -> render -> enable
double-submit guard. When neither `screen` nor `screen_provider` is
supplied the provider is `build_mock_screen` -- this package's own fixed
all-unavailable screen (not fabricated numbers; see mock_data.py's
docstring), never illustrative content.

Unlike ui/portfolio_intelligence/gradio_view.py and
ui/risk_intelligence/gradio_view.py, this screen renders no "Illustrative
Data" disclosure banner -- there is no illustrative data here to disclose,
real or otherwise: a section either shows its own real, adapter-sourced
available_summary (see bootstrap.py's _build_morning_brief_screen()) or
its own honest, fixed unavailable message, per docs/products/AARA_TRADING_
INTELLIGENCE_UI_SPECIFICATION.md Section 2's "Required information" for
Morning Brief and Section 7's "evidence over emotion" UX principle: mark
unbuilt functionality as unavailable rather than invent content to fill
it. This unit does not touch theme.py; the "As of" line reuses the
existing `.mb-subtitle` treatment.

AARA shell consistency pass: renders the same AARA logo header + inter-
screen nav Decision Center/Portfolio Intelligence/Risk Intelligence show,
via `ui/shell.py` (a sibling of all four screen packages, not owned by any
one of them).
"""
import html
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

import gradio as gr

from applications.trading_intelligence.ui.morning_brief.mock_data import build_mock_screen
from applications.trading_intelligence.ui.morning_brief.screen import (
    MorningBriefScreen,
    MorningBriefSection,
)
from applications.trading_intelligence.ui.morning_brief.theme import CSS
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html

_PAGE_HEADER_HTML = (
    '<div class="mb-page-header">'
    "<h2>Morning Brief</h2>"
    '<div class="mb-subtitle">Single-glance daily summary before market open</div>'
    "</div>"
)

_AS_OF_PREFIX = "As of "

# Local primitive, not a cross-package import (same "duplicate the
# primitive" convention ui/portfolio_intelligence/gradio_view.py uses for
# its own order-timestamp display): America/Chicago, DST-aware via
# zoneinfo, "%Y-%m-%d %H:%M %Z" -- the same wall-clock convention every
# other Trading Intelligence timestamp uses.
_DISPLAY_TIMEZONE = ZoneInfo("America/Chicago")


def _format_as_of_html(moment: datetime) -> str:
    """Render-time "as of" stamp for the whole screen. Reuses the existing
    `.mb-subtitle` treatment (muted secondary text, already defined in
    this package's theme.py and used by `_PAGE_HEADER_HTML`) rather than
    introducing a new styled class."""
    stamp = moment.astimezone(_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")
    return f'<div class="mb-subtitle">{html.escape(_AS_OF_PREFIX + stamp)}</div>'


class MorningBriefUI:
    def __init__(
        self,
        screen: Optional[MorningBriefScreen] = None,
        *,
        screen_provider: Optional[Callable[[], MorningBriefScreen]] = None,
    ):
        """Render-time data model. `screen_provider` (bootstrap.py's
        `_build_morning_brief_screen`) is re-invoked on every `demo.load()`
        and every Refresh click, so a long-running Space shows data as of
        page load, not app start. A fixed `screen` (tests) is wrapped in a
        constant provider. When neither is supplied the provider is
        `build_mock_screen` -- this package's own fixed all-unavailable
        screen, never a fabricated one.

        The provider is also called once here so `self._screen` describes
        the build-time snapshot -- the same value bootstrap.py computed
        eagerly before this slice. `build()` renders from that snapshot and
        wires `demo.load()` to refresh it immediately on page load."""
        if screen_provider is not None:
            self._screen_provider = screen_provider
        elif screen is not None:
            self._screen_provider = lambda: screen
        else:
            self._screen_provider = build_mock_screen
        self._screen = self._screen_provider()

    def build(self) -> gr.Blocks:
        initial = self._screen
        with gr.Blocks(
            title="AARA Trading Intelligence — Morning Brief", css=CSS,
        ) as demo:
            gr.HTML(SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(build_shell_nav_html("Morning Brief"), elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML)
            refresh_button = gr.Button(
                "↻ Refresh", size="sm", scale=0, elem_classes=["aara-refresh-button"],
            )
            as_of_output = gr.HTML(_format_as_of_html(self._now()))

            section_bodies = []
            for section in initial.sections:
                gr.HTML(self._format_section_label_html(section))
                section_bodies.append(gr.HTML(self._section_body_html(section)))

            outputs = [as_of_output, *section_bodies]

            # Same disable -> render -> enable double-submit guard chain as
            # ui/decision_center/ and ui/portfolio_intelligence/: a second
            # click while a render is in flight cannot dispatch a second
            # concurrent fetch. _render is wired identically to demo.load()
            # (same fn, same inputs=None, same outputs) -- only wrapped in
            # the .then() chain here.
            refresh_button.click(
                fn=self._disable_refresh_button, inputs=None, outputs=[refresh_button],
            ).then(
                fn=self._render, inputs=None, outputs=outputs,
            ).then(
                fn=self._enable_refresh_button, inputs=None, outputs=[refresh_button],
            )
            demo.load(fn=self._render, inputs=None, outputs=outputs)

        return demo

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _disable_refresh_button() -> Dict[str, Any]:
        """First link in the Refresh double-submit guard chain (see
        build()) -- disables the button the instant it is clicked, before
        _render runs. Mirrors ui/decision_center/ and
        ui/portfolio_intelligence/."""
        return gr.update(interactive=False)

    @staticmethod
    def _enable_refresh_button() -> Dict[str, Any]:
        """Last link in the Refresh double-submit guard chain (see
        build()) -- re-enables the button once _render has returned,
        success or not."""
        return gr.update(interactive=True)

    def _render(self) -> Tuple[Dict[str, Any], ...]:
        """Re-fetch through the provider and return one Gradio update per
        dynamic output, in build()'s `outputs` order (the "As of" line
        first, then one body per section in MorningBriefScreen.sections
        order). Called by demo.load() on page load and by the Refresh
        chain. A provider that now returns an all-unavailable screen
        collapses every section back to its own explicit unavailable
        message -- there is no mock/illustrative fallback anywhere in this
        path."""
        screen = self._screen_provider()
        return (
            gr.update(value=_format_as_of_html(self._now())),
            *(
                gr.update(value=self._section_body_html(section))
                for section in screen.sections
            ),
        )

    @staticmethod
    def _section_body_html(section: MorningBriefSection) -> str:
        if section.is_available:
            return MorningBriefUI._format_available_summary_html(section)
        return MorningBriefUI._format_unavailable_message_html(section)

    @staticmethod
    def _format_section_label_html(section: MorningBriefSection) -> str:
        return f'<div class="mb-section-label">{html.escape(section.title)}</div>'

    @staticmethod
    def _format_unavailable_message_html(section: MorningBriefSection) -> str:
        return (
            '<div class="mb-unavailable-message">'
            f'{html.escape(section.unavailable_message)}'
            "</div>"
        )

    @staticmethod
    def _format_available_summary_html(section: MorningBriefSection) -> str:
        return (
            '<div class="mb-available-summary">'
            f'{html.escape(section.available_summary)}'
            "</div>"
        )
