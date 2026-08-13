"""Gradio shell for the AARA Trading Intelligence Decision Center.

Thin rendering layer only: builds Gradio components, calls
DecisionCenterController methods, and maps the returned DecisionCenterScreen/
DecisionListArea/DecisionDetailArea into Gradio-friendly primitives (strings,
table rows, HTML fragments). No repository, service, or event access -- only
the controller, per controller.py's own rule that DecisionCenterController is
the only place in ui/ allowed to call Trading Intelligence services.
dashboard/'s existing Gradio app is separate, ADR-002-protected, and a
different brand (TradeGenius, not Sentinel Intelligence); this package never
imports it. theme.py's own docstring covers where the visual tokens used
below come from and, just as importantly, which parts of brand/ were
deliberately NOT reused and why.

Known-decision-ids limitation: DecisionCenterController.load_decisions()
takes an explicit decision_ids list -- there is no "list all decisions"
capability anywhere in this read chain (documented, deliberate, not fixed
here; see decision_query_service.py's docstring). This UI is constructed
with the list of ids its composition root already knows about (the ones it
seeded) and refreshes against that same known list.

Row selection: gr.Dataframe's `select` event (Gradio 4.44) passes a
gr.SelectData whose `row_value` is the entire selected row as a 1-D list,
in the same column order as _LIST_HEADERS -- so row_value[0] is the
Decision ID without needing a second lookup against the rendered rows.

Two "empty decision" contexts, two different messages: _format_detail()
(used for the initial/list-driven screen render) treats an empty detail as
"nothing selected yet" (e.g. no decisions exist at all) and shows a blank
state. _format_looked_up_detail() (used for row-select, which always names a
specific decision_id) treats the same empty detail as a genuine miss and
shows an explicit "not found" message. Both share _success_detail() for the
found-decision path; screen.py/controller.py have no notion of this
distinction -- it exists only here, in which call site is used.
_render_detail()/_format_looked_up_detail() are id-based lookup by design,
not by UI affordance -- row-select is their only caller today (no manual
Decision ID textbox in this UI; see AI-approved UX correction removing the
raw decision_id from user-facing surfaces, 2026-08-10), but a future
debug/admin surface could reuse the same method without touching
controller/service/repository code.

Evidence/Governance/Approval: rendered as small HTML record cards (one per
entry) rather than gr.Dataframe tables, so they read as decision
information rather than spreadsheet rows; an empty section is a single
quiet message, not an empty table with a header row. Read-error rendering
(ReadStatus.ERROR from screen.py, wired up in Slice 5) is unchanged in
substance -- same messages, same conditions -- only re-skinned as an HTML
message block instead of a single-row table.

Every HTML fragment below interpolates domain string fields (symbol,
evidence/governance/approval field values) into markup rendered directly
by gr.HTML(), which does not escape its input. decision_id is deliberately
excluded from every such fragment (the raw internal id is an investor-facing
UX concern, not a secret -- see AI-approved UX correction, 2026-08-10); it
still flows into the plain-text Decisions gr.Dataframe (which does not
render HTML) for row identification. None of DecisionContract/
EvidenceEntry/GovernanceEntry/ApprovalEntry constrain their string fields'
character content, so every such value is escaped with html.escape() before
interpolation -- this is the only thing standing between arbitrary field
content (e.g. a compromised evidence provider's `source`, or an `approved_by`
value) and script injection into this page.

V2 Visual Pass (2026-08-10): application shell (Sentinel Mark logo +
wordmark + descriptor + non-interactive nav), a page header, and a
strengthened decision list/hero/record-card presentation, built on top of
the structure above -- no controller/service/contract change. The Decisions
gr.Dataframe still carries decision_id as its first column (row selection in
_on_row_select still reads evt.row_value[0], unchanged) but that column is
hidden purely via theme.py's CSS (see its aara-decisions-table rule) rather
than dropped from the underlying data or looked up through per-instance
state -- DecisionCenterUI intentionally holds no mutable state between
render and select calls (a Gradio Blocks callback instance is shared across
concurrent sessions; see the Gradio Dual-Writer Race precedent), so
row-to-decision_id mapping stays entirely inside the row data Gradio already
round-trips through evt.row_value, never in an attribute on self.

V3 Decision Workspace pass (2026-08-10): the Decisions gr.Dataframe keeps
its native `.select()` event as the only selection mechanism (an Option
A/B/C spike concluded that restyling the native Dataframe -- Option C --
achieves everything a custom HTML navigator would, without a second
synchronized DOM or injected JS; see that spike's findings). Everything
V3 changes about the list is presentation: theme.py's CSS (root-caused and
fixed the Dataframe's own hardcoded orange selection ring and permanent
decorative scrollbar) and this file's Action column now rendering through
Dataframe's native `datatype="markdown"` per-column support (verified this
doesn't affect `evt.row_value[0]`, the only cell _on_row_select reads) for a
restrained BUY/SELL/HOLD badge consistent with the hero's own badge.

_DetailValues dropped its symbol/action positions in V3: those values
duplicated the hero (`{symbol} · {action}`) immediately below it for no
reason, so the separate Symbol/Action Textbox pair -- and the two tuple
positions feeding it -- were removed rather than hidden. Every caller
(_render_screen/_render_detail and both test files) was updated to the new,
shorter tuple; nothing in screen.py/controller.py has any notion of this
tuple, so this stays entirely inside gradio_view.py's own contract with
itself.

V3.1 Keyboard Accessibility Fix (2026-08-10): see _KEYBOARD_SELECTION_BRIDGE_JS
below for why a small JS bridge -- not a Python/CSS-only fix -- was necessary,
and exactly what it does and does not do. Summary: it translates
Enter/Space on a focused Decisions cell into a native click() on that same
cell, and nothing else; Gradio's own selection machinery (the .select()
event this file already listens to via list_output.select(...)) handles
every step after that unchanged.

V4 Decision Brief pass (2026-08-10), presentation-layer only -- no
controller/screen/projections/sentinel_engine change:

- Why?/Rationale section: _WHY_RATIONALE_HTML is a static gr.HTML block
  built once at build() time from a fixed literal, deliberately never added
  to detail_outputs/_DetailValues -- it does not read decision_id, the
  controller, or any DecisionDetailArea field, by design (there is no
  rationale/thesis data anywhere in this read chain, and this pass adds
  none: no LLM call, no inferred copy). It reads identically for every
  decision and for the empty/error states alike.
- Approval cards no longer show the V3 "Authorization Recorded" literal --
  that was presentation copy with no ApprovalEntry field behind it. The
  card header now carries exactly one item, entry.status itself (the real
  verdict, already positive/negative-colored), in the slot _record_card_html
  used to reserve for a fabricated label; approved_by/approved_at are
  rendered as-is from ApprovalEntry with no substitution for missing/empty
  values. Evidence/Governance cards are unaffected -- their record_type slot
  was always genuine entry data (evidence_type/policy_id), never a literal.
- Shell descriptor text changed from "Decision Intelligence" to "Trading
  Intelligence" (matching this app's own gr.Blocks title and product name);
  the Sentinel Mark logo asset/loading/sizing above is untouched -- brand
  guidance for this pass was explicit that the frozen mark itself must not
  change, only surrounding copy and layout may.
- "Governance" section relabeled "Governance & Policy" (this file's own
  label string only -- GovernanceEntry/policy_id semantics untouched).

V4 visual correction pass (2026-08-10), theme.py-only besides two markup
touches here: the record cards' box (border/radius/shadow/white panel) read
as a stack of separate dashboard cards on review, not the one continuous
institutional document V4 calls for. record_card_html's own HTML structure
is unchanged; theme.py reflows the same markup into dense ledger rows
separated by a hairline instead of a card boundary. The two markup changes:
elem_classes=["aara-hero-metrics"] on the Conviction/Last Updated Row (a
narrowly-scoped hook so theme.py can strip Gradio's own default bordered
".form" wrapper around grouped Textbox siblings, without touching ".form"
anywhere else in the app) and _WHY_RATIONALE_HTML's class changing from
aara-empty-message to the new aara-disclosure-message (same fixed text,
distinct treatment so it reads as a deliberate disclosure rather than an
empty-list state).

Detail Panel Polish pass (2026-08-12), gradio_view.py + theme.py:

- Section rhythm: Gradio's own default Column gap between stacked blocks
  is 16px (`--layout-gap`, confirmed by inspecting the installed `gradio`
  package's compiled default theme CSS -- not assumed). Each section
  label's own former `margin-top: var(--space-md)` (another 16px) stacked
  on top of that gap, giving ~32px between sections; removed so Gradio's
  existing 16px gap is the single source of the ~16px section rhythm,
  instead of two independent margins compounding.
- Header-to-metrics spacing tightened to ~12px via a small explicit
  negative margin on `.aara-hero-metrics`, offsetting the same 16px
  Column gap plus the header block's own reduced bottom padding -- the
  same negative-margin technique `.aara-shell-header` already uses, not a
  new pattern.
- Record cards (Evidence/Governance & Policy/Approval): `_record_list_html`
  now takes a `section_variant` string and wraps its non-empty-cards
  output in an additional `aara-record-list--{variant}` class --
  `_record_card_html`'s own `aara-record-card` class string is untouched,
  so existing tests asserting `'class="aara-record-card"'` as a substring
  are unaffected. Each section gets its own subtle background tint
  composed only from RGB triples already present in `:root`
  (`--action-hold-bg`'s gray for Evidence, gold's RGB for Governance,
  navy's RGB for Approval, each at a low alpha already precedented
  elsewhere in this file) -- no new custom property, no new base color.
- Selected decision row: recolored from the V3 gold treatment to a
  subtle navy surface tint + a 3px navy left indicator (was gold),
  reusing the same navy RGB triple already used for the row hover state
  and `--shadow-card`. Both the mouse (`:has(td.focus)`) and keyboard
  (`:has(td:focus-visible)`) selectors are still both present and
  restyled identically, so keyboard selection parity (V3.1's own fix) is
  unchanged.
- Section labels: tightened to a smaller, wider-tracked micro-label
  treatment (11px, more letter-spacing) distinct from the larger
  "Decision Intelligence" group label above them, which is unchanged.
- Approval's state pill (`aara-record-card-state`) gains the same subtle
  background-pill treatment BUY/SELL/HOLD already use (reusing
  `--action-buy-bg`/`--action-sell-bg` exactly, plus a neutral gray for
  Evidence/Governance's own "Attached"/"Evaluated" pills) instead of
  being bare colored text -- still text-label-first per
  FORBIDDEN_UI_PATTERNS.md's "color is never the only signal" rule, now
  visually consistent with the rest of the badge family. The hero action
  badge (`.aara-action-badge`) is compacted slightly (13px -> 12px,
  8px -> 7px horizontal padding) to match.
- Why?/Rationale: replaced the single-sentence disclosure with a two-line
  empty state ("Rationale not captured" / "The decision thesis has not
  yet been recorded.") -- still 100% static and decision-independent,
  still no rationale/thesis data of any kind invented or read from
  anywhere; only the presentation of the same "nothing here yet" fact
  changed.

Nav Coming Soon pass (2026-08-12), markup here + theme.py: the two muted
nav items (Portfolio Intelligence, Risk Intelligence) previously read as
plain dimmed text with no explanation for why they don't respond to a
click. Each now carries a small "Coming Soon" badge (_NAV_COMING_SOON_LABEL)
alongside its label -- still inside the same non-interactive <span
class="nav-item muted">, not a link/button, so no tabindex, href, or click
handler is added and no change to keyboard tab order occurs (a <span> was
never focusable to begin with). theme.py adds `cursor: default` to
.nav-item.muted as an explicit reinforcement, not a fix -- inline <span>s
already have no pointer cursor by default, and no :hover rule has ever
existed for .nav-item, so hover already implied nothing before this pass
either. The badge itself styles with tokens already defined in :root
(--space-xs, --radius-badge, --color-border-subtle, --color-text-secondary)
-- no new custom property introduced -- and inherits .nav-item's own
uppercase/letter-spacing/opacity rather than defining its own, so it reads
as part of the same muted label rather than a competing element. Sized to
stay within the nav item's own line-height (9px badge text against the
label's 13px), so .aara-shell-nav's height is unchanged from before this
pass -- confirmed by inspection, not by adding an explicit height.
"""
import base64
import html
import io
import pathlib
from typing import List, Tuple

import gradio as gr
from PIL import Image as PILImage

from applications.trading_intelligence.projections.approval_entry import ApprovalStatus
from applications.trading_intelligence.projections.decision_view import DecisionState, DecisionView
from applications.trading_intelligence.ui.decision_center.controller import DecisionCenterController
from applications.trading_intelligence.ui.decision_center.screen import (
    DecisionDetailArea,
    DecisionListArea,
    ReadStatus,
)
from applications.trading_intelligence.ui.decision_center.theme import CSS

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]


def _load_shell_logo_data_uri() -> str:
    """Loads the approved Sentinel Mark asset and returns it as a base64
    data: URI for direct <img src=...> embedding.

    Embedded as a data URI in a plain gr.HTML fragment, not via gr.Image:
    gr.Image only serves a bare path through Gradio's /file= route (403s
    unless the path is in the launcher's allowed_paths) and, even given a
    PIL.Image value, wraps the <img> in its own button/frame markup for
    upload/fullscreen affordances -- irrelevant chrome for a static shell
    logo, and a spurious keyboard-tab stop (a non-interactive brand mark
    shouldn't be in the tab order; see spec V2 Section 20). A data URI
    sidesteps both.

    Uses the favicon variant, not the "primary" sentinel_mark_v1.0_gold_on_navy
    asset LOGO_ASSET_GUIDE.md names as primary: that file's left ~40% is baked
    in as opaque white pixels (verified with PIL, not a rendering artifact),
    which isn't part of the documented lotus/circle/arrow design and reads as
    a broken image in a compact header -- flagged to the user as a brand-asset
    defect rather than worked around by cropping the frozen file. The favicon
    variant has genuine transparency around the same mark and renders cleanly
    on the shell's navy background. Its canvas still carries wide transparent
    side margins (the source file's own dimensions are documented as 32x32/
    256x256 but it actually ships at the primary asset's 2548x1402 canvas --
    also flagged to the user), so it's cropped here to its alpha-channel
    bounding box -- trimming empty margin, not any drawn design element -- to
    avoid rendering a mostly-blank rectangle in a compact header.
    """
    source = PILImage.open(
        str(_REPO_ROOT / "brand" / "logos" / "sentinel_mark_favicon_v1.0.png")
    ).convert("RGBA")
    cropped = source.crop(source.getchannel("A").getbbox())
    buffer = io.BytesIO()
    cropped.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


# Gradio 4.44.1's Dataframe keyboard gap, and why this is the smallest fix
# that closes it:
#
# Table.svelte's row-selection state ("selected", a private [row, col] |
# false) is never exported as a Python prop or DOM attribute -- nothing in
# gr.Dataframe's constructor, no ARIA attribute, no ".select() event input"
# can set it. The only code path that ever sets it is a real `click` handler
# bound per-cell (`handle_cell_click`); Table.svelte's own keydown handler
# opens with `if (!selected) return;`, so from a cold state (Tab lands on a
# cell, nothing has ever been clicked) Enter/Space are no-ops -- confirmed
# by reading Gradio's own shipped Svelte source
# (gradio/_frontend_code/dataframe/shared/Table.svelte,
# EditableCell.svelte), not by guessing from compiled output. There is
# no supported non-JS way to reach this from Python or CSS.
#
# The fix below does exactly one thing: on Enter/Space, if the focused
# element is a real Decisions-table data cell, call cell.click() -- the
# same DOM method a real mouse click invokes, which Gradio's own
# `on:click={() => handle_cell_click(...)}` handler responds to identically
# either way. Everything after that (selection state, the .select() event,
# _on_row_select, _render_detail, controller/service calls, the detail
# re-render) is 100% unchanged native Gradio machinery -- this bridge knows
# nothing about decisions, symbols, or any domain concept, and never will,
# by construction (no application data is interpolated into it; see the
# guard clauses below).
#
# DOM contract this depends on (the one thing to revalidate after any
# Gradio version bump):
#   1. `.aara-decisions-table` -- our own elem_classes anchor, stable by
#      definition (we control it).
#   2. A real data cell is a `<td>` whose parent `<tr>` carries
#      `slot="tbody"` -- this is how Table.svelte's named-slot forwarding
#      marks genuine data rows, distinguishing them from its own hidden
#      column-width-measurement row (which carries no such attribute). This
#      is the one Gradio-internal implementation detail the bridge leans
#      on; no `svelte-*` hashed class is used anywhere in it.
#   3. Clicking that `<td>` (`cell.click()`) drives the same
#      `handle_cell_click` -> `selected = [i, j]` -> `dispatch("select",
#      ...)` path a real pointer click does.
# If a Gradio upgrade changes any of #2/#3, this block -- and only this
# block -- needs re-verification; nothing else in this file or theme.py
# depends on it.
_KEYBOARD_SELECTION_BRIDGE_JS = """
<script>
(function () {
  function findDecisionCell(target) {
    var cell = target && target.closest ? target.closest("td") : null;
    if (!cell || !cell.closest(".aara-decisions-table")) return null;
    var row = cell.parentElement;
    return row && row.getAttribute("slot") === "tbody" ? cell : null;
  }
  document.addEventListener("keydown", function (event) {
    if (event.defaultPrevented || event.repeat) return;
    if (event.key !== "Enter" && event.key !== " ") return;
    var cell = findDecisionCell(event.target);
    if (!cell) return;
    event.preventDefault();
    cell.click();
  });
})();
</script>
"""


_SHELL_IDENTITY_HTML = (
    f'<img class="aara-shell-logo" src="{_load_shell_logo_data_uri()}" alt="AARA" />'
    '<div class="aara-shell-wordmark-group">'
    '<div class="aara-shell-wordmark">AARA</div>'
    '<div class="aara-shell-descriptor">Trading Intelligence</div>'
    "</div>"
)
_NAV_COMING_SOON_LABEL = "Coming Soon"
_NAV_COMING_SOON_BADGE_HTML = f'<span class="aara-nav-badge">{_NAV_COMING_SOON_LABEL}</span>'
_SHELL_NAV_HTML = (
    '<nav class="aara-shell-nav-list">'
    '<span class="nav-item active">Decision Center</span>'
    f'<span class="nav-item muted">Portfolio Intelligence{_NAV_COMING_SOON_BADGE_HTML}</span>'
    f'<span class="nav-item muted">Risk Intelligence{_NAV_COMING_SOON_BADGE_HTML}</span>'
    "</nav>"
)
_PAGE_HEADER_HTML = (
    '<h2 class="aara-eyebrow">Decision Center</h2>'
    '<div class="aara-page-subtitle">Governed investment decisions</div>'
)

_LIST_HEADERS = ["Decision ID", "Symbol", "Action", "Status", "Confidence"]
_LIST_DATATYPES = ["str", "str", "markdown", "str", "str"]
_MISSING_VALUE = "-"

_DECISION_READ_ERROR_MESSAGE = "Unable to load this decision."
_DECISION_NOT_FOUND_MESSAGE = "No decision found for this ID."
_EVIDENCE_EMPTY_MESSAGE = "No evidence attached yet."
_GOVERNANCE_EMPTY_MESSAGE = "No governance evaluation recorded."
_APPROVAL_EMPTY_MESSAGE = "No approval recorded."
_EVIDENCE_ERROR_MESSAGE = "Evidence is temporarily unavailable."
_GOVERNANCE_ERROR_MESSAGE = "Governance information is temporarily unavailable."
_APPROVAL_ERROR_MESSAGE = "Approval information is temporarily unavailable."

# Static, not decision-dependent -- see module docstring's V4 Decision Brief
# and Detail Panel Polish pass notes. Rendered verbatim for every decision
# and never wired into detail_outputs/_DetailValues.
_WHY_RATIONALE_TITLE = "Rationale not captured"
_WHY_RATIONALE_BODY = "The decision thesis has not yet been recorded."
_WHY_RATIONALE_HTML = (
    '<div class="aara-disclosure-message">'
    f'<div class="aara-disclosure-title">{html.escape(_WHY_RATIONALE_TITLE)}</div>'
    f'<div class="aara-disclosure-body">{html.escape(_WHY_RATIONALE_BODY)}</div>'
    "</div>"
)

_ACTION_BADGE_CLASSES = {"BUY": "action-buy", "SELL": "action-sell", "HOLD": "action-hold"}

_LIFECYCLE_STAGES = [
    (DecisionState.DECISION_CREATED, "Created"),
    (DecisionState.EVIDENCE_ATTACHED, "Evidence"),
    (DecisionState.GOVERNANCE_EVALUATED, "Governance"),
    (DecisionState.APPROVAL_RECORDED, "Approval"),
]

_DetailValues = Tuple[str, str, str, str, str, str, str]


class DecisionCenterUI:
    def __init__(self, controller: DecisionCenterController, decision_ids: List[str]):
        self._controller = controller
        self._decision_ids = list(decision_ids)

    def build(self) -> gr.Blocks:
        with gr.Blocks(
            title="AARA Trading Intelligence — Decision Center", css=CSS,
            head=_KEYBOARD_SELECTION_BRIDGE_JS,
        ) as demo:
            gr.HTML(_SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(_SHELL_NAV_HTML, elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML, elem_classes=["aara-page-header"])

            with gr.Row(elem_classes=["aara-layout-row"]):
                with gr.Column(scale=3, min_width=380, elem_classes=["aara-list-column"]):
                    with gr.Row(elem_classes=["aara-list-toolbar"]):
                        gr.Markdown(
                            '<h2 class="aara-eyebrow">Decisions</h2>',
                            elem_classes=["aara-list-toolbar-label"],
                        )
                        refresh_button = gr.Button(
                            "↻ Refresh", size="sm", scale=0,
                            elem_classes=["aara-refresh-button"],
                        )
                    list_output = gr.Dataframe(
                        # height is a navigator viewport budget, not a fit for
                        # today's 3 seed rows -- ~9-10 rows before Gradio's
                        # own virtualized table (VirtualTable.svelte) caps
                        # and scrolls internally, so this must not be
                        # re-tuned as seed/demo data changes; it works
                        # unmodified whether there are 3 decisions or 500.
                        headers=_LIST_HEADERS, datatype=_LIST_DATATYPES, interactive=False,
                        label="Decisions", show_label=False, height=340,
                        elem_classes=["aara-decisions-table"],
                    )

                with gr.Column(scale=4, elem_classes=["aara-detail-column"]):
                    gr.Markdown(
                        '<h2 class="aara-eyebrow">Decision Intelligence</h2>',
                        elem_classes=["aara-section-label", "aara-section-label--group"],
                    )
                    header_output = gr.HTML()
                    with gr.Row(elem_classes=["aara-hero-metrics"]):
                        conviction_output = gr.Textbox(
                            label="Conviction", interactive=False,
                            elem_classes=["aara-field-value", "aara-conviction-value"],
                        )
                        updated_output = gr.Textbox(
                            label="Last Updated", interactive=False,
                            elem_classes=["aara-field-value"],
                        )
                    gr.Markdown(
                        '<h3 class="aara-eyebrow">Why?</h3>', elem_classes=["aara-section-label"],
                    )
                    gr.HTML(_WHY_RATIONALE_HTML)
                    gr.Markdown(
                        '<h3 class="aara-eyebrow">Decision Journey</h3>',
                        elem_classes=["aara-section-label"],
                    )
                    lifecycle_output = gr.HTML()
                    gr.Markdown(
                        '<h3 class="aara-eyebrow">Evidence</h3>', elem_classes=["aara-section-label"],
                    )
                    evidence_output = gr.HTML()
                    gr.Markdown(
                        '<h3 class="aara-eyebrow">Governance & Policy</h3>',
                        elem_classes=["aara-section-label"],
                    )
                    governance_output = gr.HTML()
                    gr.Markdown(
                        '<h3 class="aara-eyebrow">Approval</h3>', elem_classes=["aara-section-label"],
                    )
                    approval_output = gr.HTML()

            detail_outputs = [
                header_output, lifecycle_output, conviction_output, updated_output,
                evidence_output, governance_output, approval_output,
            ]
            screen_outputs = [list_output] + detail_outputs

            refresh_button.click(fn=self._render_screen, inputs=None, outputs=screen_outputs)
            demo.load(fn=self._render_screen, inputs=None, outputs=screen_outputs)

            list_output.select(fn=self._on_row_select, inputs=None, outputs=detail_outputs)

        return demo

    def _render_screen(
        self,
    ) -> Tuple[List[List[str]], str, str, str, str, str, str, str]:
        screen = self._controller.load_screen(self._decision_ids)
        list_rows = self._format_list_rows(screen.list_area)
        detail_values = self._format_detail(screen.detail_area)
        return (list_rows,) + detail_values

    def _render_detail(self, decision_id: str) -> _DetailValues:
        if not decision_id:
            return self._empty_detail()
        detail_area = self._controller.load_decision_detail(decision_id)
        return self._format_looked_up_detail(detail_area)

    def _on_row_select(self, evt: gr.SelectData) -> _DetailValues:
        if not evt.selected or not evt.row_value:
            return self._empty_detail()
        return self._render_detail(evt.row_value[0])

    @staticmethod
    def _format_list_rows(list_area: DecisionListArea) -> List[List[str]]:
        return [
            [
                view.decision_id,
                view.symbol,
                DecisionCenterUI._list_action_badge_html(view.action),
                view.status.value.replace("_", " ").title(),
                f"{view.confidence * 100:.0f}%",
            ]
            for view in list_area.decisions
        ]

    @staticmethod
    def _list_action_badge_html(action: str) -> str:
        """The Action column renders through the Dataframe's own
        datatype="markdown" support (verified against the running app: it
        doesn't affect evt.row_value[0], the only cell _on_row_select reads,
        so this is safe alongside the existing selection flow) -- same
        escaping discipline as every other domain string interpolated in
        this file, even though the Dataframe's markdown renderer, not
        gr.HTML(), is what turns this into markup here."""
        css_class = _ACTION_BADGE_CLASSES.get(action, "action-hold")
        escaped = html.escape(action)
        return f'<span class="aara-list-action-badge {css_class}">{escaped}</span>'

    @staticmethod
    def _format_detail(detail_area: DecisionDetailArea) -> _DetailValues:
        """Empty here means 'nothing selected yet' -- used by the initial/
        list-driven screen render, never a failed lookup."""
        if detail_area.decision_status is ReadStatus.ERROR:
            return DecisionCenterUI._decision_error_detail()
        if detail_area.is_empty:
            return DecisionCenterUI._empty_detail()
        return DecisionCenterUI._success_detail(detail_area)

    @staticmethod
    def _format_looked_up_detail(detail_area: DecisionDetailArea) -> _DetailValues:
        """Empty here means the searched-for decision_id genuinely wasn't
        found -- used by row-select (and any future id-based caller), which
        always names a specific id."""
        if detail_area.decision_status is ReadStatus.ERROR:
            return DecisionCenterUI._decision_error_detail()
        if detail_area.is_empty:
            return DecisionCenterUI._missing_decision_detail()
        return DecisionCenterUI._success_detail(detail_area)

    @staticmethod
    def _success_detail(detail_area: DecisionDetailArea) -> _DetailValues:
        decision = detail_area.decision
        return (
            DecisionCenterUI._decision_header_html(decision),
            DecisionCenterUI._lifecycle_track_html(decision.status),
            detail_area.confidence_display,
            detail_area.timestamp_display,
            DecisionCenterUI._format_evidence_html(detail_area),
            DecisionCenterUI._format_governance_html(detail_area),
            DecisionCenterUI._format_approval_html(detail_area),
        )

    @staticmethod
    def _format_evidence_html(detail_area: DecisionDetailArea) -> str:
        if detail_area.evidence_status is ReadStatus.ERROR:
            return DecisionCenterUI._error_message_html(_EVIDENCE_ERROR_MESSAGE)
        cards = [
            DecisionCenterUI._record_card_html(
                entry.evidence_type,
                "Attached",
                [
                    ("Source", entry.source, False),
                    ("Attached", entry.attached_at.strftime("%Y-%m-%d %H:%M UTC"), True),
                ],
                "neutral",
            )
            for entry in detail_area.evidence
        ]
        return DecisionCenterUI._record_list_html(cards, _EVIDENCE_EMPTY_MESSAGE, "evidence")

    @staticmethod
    def _format_governance_html(detail_area: DecisionDetailArea) -> str:
        if detail_area.governance_status is ReadStatus.ERROR:
            return DecisionCenterUI._error_message_html(_GOVERNANCE_ERROR_MESSAGE)
        cards = [
            DecisionCenterUI._record_card_html(
                entry.policy_id,
                "Evaluated",
                [
                    ("Enabled", "Yes" if entry.enabled else "No", False),
                    ("Evaluated", entry.evaluated_at.strftime("%Y-%m-%d %H:%M UTC"), True),
                ],
                "neutral",
            )
            for entry in detail_area.governance
        ]
        return DecisionCenterUI._record_list_html(cards, _GOVERNANCE_EMPTY_MESSAGE, "governance")

    @staticmethod
    def _format_approval_html(detail_area: DecisionDetailArea) -> str:
        if detail_area.approvals_status is ReadStatus.ERROR:
            return DecisionCenterUI._error_message_html(_APPROVAL_ERROR_MESSAGE)
        cards = [
            DecisionCenterUI._record_card_html(
                "",  # no fabricated label -- the verdict below is the card's identity
                entry.status.value.replace("_", " ").title(),
                [
                    ("Approved By", entry.approved_by, False),
                    ("Approved At", entry.approved_at.strftime("%Y-%m-%d %H:%M UTC"), True),
                ],
                "positive" if entry.status is ApprovalStatus.APPROVED else "negative",
            )
            for entry in detail_area.approvals
        ]
        return DecisionCenterUI._record_list_html(cards, _APPROVAL_EMPTY_MESSAGE, "approval")

    @staticmethod
    def _decision_header_html(decision: DecisionView) -> str:
        badge = DecisionCenterUI._action_badge_html(decision.action)
        return (
            '<div class="aara-decision-header">'
            f'<div class="identity-line">{html.escape(decision.symbol)} &middot; {badge}</div>'
            "</div>"
        )

    @staticmethod
    def _missing_decision_header_html() -> str:
        return (
            '<div class="aara-decision-header">'
            f'<div class="identity-message">{_DECISION_NOT_FOUND_MESSAGE}</div>'
            "</div>"
        )

    @staticmethod
    def _decision_error_header_html() -> str:
        return (
            '<div class="aara-decision-header">'
            f'<div class="identity-error">{_DECISION_READ_ERROR_MESSAGE}</div>'
            "</div>"
        )

    @staticmethod
    def _action_badge_html(action: str) -> str:
        css_class = _ACTION_BADGE_CLASSES.get(action, "action-hold")
        return f'<span class="aara-action-badge {css_class}">{html.escape(action)}</span>'

    @staticmethod
    def _lifecycle_track_html(status: DecisionState) -> str:
        stage_values = [stage for stage, _ in _LIFECYCLE_STAGES]
        current_index = stage_values.index(status)
        segments = []
        for index, (_, label) in enumerate(_LIFECYCLE_STAGES):
            if index > 0:
                connector_class = "complete" if index <= current_index else ""
                segments.append(f'<span class="connector {connector_class}"></span>')
            if index < current_index:
                stage_class = "complete"
            elif index == current_index:
                stage_class = "active"
            else:
                stage_class = ""
            segments.append(
                f'<span class="stage {stage_class}"><span class="dot"></span>'
                f'<span class="label">{html.escape(label)}</span></span>'
            )
        return '<div class="aara-lifecycle-track">' + "".join(segments) + "</div>"

    @staticmethod
    def _record_card_html(
        record_type: str, state: str, fields: List[Tuple[str, str, bool]], state_variant: str,
    ) -> str:
        """record_type/state form the card's header row (record type, then
        state, then source/value, then timestamp -- the latter two come from
        `fields`). Both are escaped like every other interpolated value
        here, even though today's callers only ever pass real
        DecisionState-adjacent data (evidence_type/policy_id/entry.status),
        never unescaped external input.

        record_type may be "" (Approval's only caller, V4 on): ApprovalEntry
        carries no field distinct from status/approved_by/approved_at, so
        there is no legitimate value left for a separate identity label once
        the V3 "Authorization Recorded" placeholder was removed -- the type
        span is omitted entirely rather than rendered empty, leaving `state`
        (entry.status, already positive/negative-colored) as the header's
        only, and entirely real, content.

        Each field is (label, value, is_tabular). is_tabular opts a field
        into monospace/tabular-nums styling -- reserved for genuinely
        numeric/timestamp values (Attached/Evaluated/Approved At), never
        identifiers or names (Source, Enabled, Approved By), correcting the
        V2 pass's blanket monospace-everywhere regression.

        state_variant picks the state pill's color and must be one of
        "neutral" (evidence/governance -- Attached/Evaluated describe that a
        record exists, not a verdict), "positive" (an APPROVED approval), or
        "negative" (a REJECTED approval) -- never a bare red/green pair on
        their own; the pill's text label is what actually carries the
        meaning, matching FORBIDDEN_UI_PATTERNS.md's "color is never the
        only semantic indicator" rule."""
        field_html = "".join(
            '<div class="aara-record-field">'
            f'<span class="record-label">{html.escape(label)}</span>'
            f'<span class="record-value{" record-value--tabular" if is_tabular else ""}">'
            f'{html.escape(value)}</span>'
            "</div>"
            for label, value, is_tabular in fields
        )
        type_html = (
            f'<span class="aara-record-card-type">{html.escape(record_type)}</span>'
            if record_type else ""
        )
        return (
            '<div class="aara-record-card">'
            f'<div class="aara-record-card-header">{type_html}'
            f'<span class="aara-record-card-state aara-record-card-state--{state_variant}">'
            f'{html.escape(state)}</span>'
            "</div>"
            f'<div class="aara-record-card-fields">{field_html}</div>'
            "</div>"
        )

    @staticmethod
    def _record_list_html(cards: List[str], empty_message: str, section_variant: str) -> str:
        """section_variant is an internal, fixed literal ("evidence"/
        "governance"/"approval"), never domain data, so it is interpolated
        unescaped -- the same treatment _record_card_html already gives its
        own state_variant parameter."""
        if not cards:
            return f'<div class="aara-empty-message">{html.escape(empty_message)}</div>'
        return (
            f'<div class="aara-record-list aara-record-list--{section_variant}">'
            + "".join(cards) + "</div>"
        )

    @staticmethod
    def _error_message_html(message: str) -> str:
        return f'<div class="aara-error-message">{html.escape(message)}</div>'

    @staticmethod
    def _empty_detail() -> _DetailValues:
        return ("", _MISSING_VALUE, _MISSING_VALUE, _MISSING_VALUE, "", "", "")

    @staticmethod
    def _missing_decision_detail() -> _DetailValues:
        return (
            DecisionCenterUI._missing_decision_header_html(),
            _MISSING_VALUE, _MISSING_VALUE, _MISSING_VALUE, "", "", "",
        )

    @staticmethod
    def _decision_error_detail() -> _DetailValues:
        return (
            DecisionCenterUI._decision_error_header_html(),
            _MISSING_VALUE, _MISSING_VALUE, _MISSING_VALUE, "", "", "",
        )
