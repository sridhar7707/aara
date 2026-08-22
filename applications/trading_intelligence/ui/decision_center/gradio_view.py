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

- Why?/Rationale section: _WHY_RATIONALE_HTML was originally a static
  gr.HTML block built once at build() time from a fixed literal, never
  wired into detail_outputs/_DetailValues -- superseded by the Decision
  Detail Depth pass below, which wires a real per-decision why_output.
  _WHY_RATIONALE_HTML itself is unchanged and still used verbatim as the
  zero-evidence fallback (there is still no rationale/thesis field
  anywhere in this read chain, and none is invented here either).
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

Decision Detail Depth pass (2026-08-16), application-layer only -- no
sentinel_engine/bot/dashboard/database/ledger change, no new domain field,
no new repository/query contract (per the preceding read-only audit):

- Why? summary: why_output is now wired into detail_outputs/_DetailValues
  and rendered by _format_why_summary_html, which composes a real sentence
  from the already-loaded EvidenceEntry(evidence_type, source) tuple on
  DecisionDetailArea (e.g. "1 NEWS_SENTIMENT signal from newsapi.") --
  falls back to the original, unchanged _WHY_RATIONALE_HTML when there is
  no evidence to summarize (including the evidence-read-error case, which
  already surfaces its own message in the Evidence section itself). No
  thesis/rationale field is read or invented.
- Audit Trail payload: each audit card now carries an expandable
  <details>/<summary> disclosure (_format_audit_detail_html) showing the
  event's restored event_id plus every key already present on
  Event.payload, exactly as DecisionQuery.get_decision_timeline() returns
  it -- no field invented or transformed beyond str()/escaping for
  display. Uses the same aara-record-field/record-label/record-value
  classes the record cards already use, so no new theme.py class is
  needed for it.
- Restored identifiers: EvidenceEntry.evidence_id, ApprovalEntry.
  approval_id, and AuditEntry.event_id (see their own projection modules)
  are mapped straight through from the sentinel_engine summary/event
  objects that already carried them -- decision_id remains excluded from
  every rendered fragment, unchanged from the 2026-08-10 UX correction.
- Decision Journey navigation: _lifecycle_track_html's four stage labels
  are now <a href="#..."> anchors to elem_ids already placed on
  header_output ("decision-created-section"), evidence_output
  ("evidence-section"), governance_output ("governance-section"), and
  approval_output ("approval-section") -- native in-page anchor jumps, no
  JS, no controller/status/lifecycle semantic change. theme.py gained one
  `text-decoration: none` line on `.aara-lifecycle-track .label` so the
  anchor doesn't pick up a default browser underline; no other CSS changed.

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
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
from PIL import Image as PILImage

from applications.trading_intelligence.projections.approval_entry import ApprovalStatus
from applications.trading_intelligence.projections.decision_view import DecisionState, DecisionView
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.ui.decision_center.controller import DecisionCenterController
from applications.trading_intelligence.ui.decision_center.screen import (
    DecisionDetailArea,
    DecisionListArea,
    ReadStatus,
    format_display_timestamp,
)
from applications.trading_intelligence.ui.decision_center.theme import CSS

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]

# gr.Dataframe's row-height-budget kwarg is named `height` on the gradio==
# 4.44.1 pin this app deploys with (requirements_trading_intelligence.txt)
# but was renamed `max_height` by gradio 5.x, which is what CI's shared
# requirements.txt resolves to on Python >=3.10. Same _gr_major-style
# compat convention as scripts/dashboard.py:80.
_gr_major = int(gr.__version__.split(".")[0])
_DATAFRAME_HEIGHT_KWARG = "height" if _gr_major < 5 else "max_height"


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

# P1 accessibility slice: live-region announcer setup. A separate, named JS
# constant -- not merged into _KEYBOARD_SELECTION_BRIDGE_JS above, an
# unrelated concern (keyboard selection vs. screen-reader announcements).
#
# Gradio 4.44.1's gr.HTML component exposes no Python-level hook to set
# arbitrary ARIA attributes on its own rendered host (elem_id/elem_classes
# are the only attribute hooks -- gradio.components.html.HTML.__init__ has
# no aria_* parameter). Verified directly against the shipped Svelte source,
# not assumed:
#   - gradio/_frontend_code/atoms/src/Block.svelte line 37: every gr.HTML
#     is wrapped in <svelte:element id={elem_id} class="block ...">, a
#     stable root element that is never destroyed and recreated when the
#     component's value later changes (only a Svelte prop update, not a
#     remount).
#   - gradio/_frontend_code/html/shared/HTML.svelte: the actual
#     {@html value} binding lives on a *descendant* <div class="prose ...">
#     inside that stable root -- only this inner content is replaced on each
#     update.
# Setting aria-live/aria-atomic/role once on the stable outer element (by
# id, found via document.getElementById) therefore persists across every
# later content update; a live-region attribute on an ancestor of the
# mutating content is standard, correct ARIA usage, not a workaround.
#
# The target element does not exist yet when this <script> parses (Gradio's
# own client-side app mounts asynchronously after page load), so a bounded
# polling loop -- not a MutationObserver, which would react to every future
# DOM change instead of just needing to find one element once -- retries
# briefly, applies the three attributes exactly once, then stops. Fails
# silently (no error, just stops polling) if the element is never found
# rather than throwing or polling forever.
_LIVE_ANNOUNCER_ELEM_ID = "aara-live-announcer"
_LIVE_REGION_SETUP_JS = f"""
<script>
(function () {{
  var attempts = 0;
  var maxAttempts = 100;
  var intervalId = setInterval(function () {{
    attempts += 1;
    var el = document.getElementById("{_LIVE_ANNOUNCER_ELEM_ID}");
    if (el) {{
      el.setAttribute("aria-live", "polite");
      el.setAttribute("aria-atomic", "true");
      el.setAttribute("role", "status");
      clearInterval(intervalId);
      return;
    }}
    if (attempts >= maxAttempts) {{
      clearInterval(intervalId);
    }}
  }}, 50);
}})();
</script>
"""

# P1 accessibility slice: dataframe selection ARIA sync. A third, independent
# JS bridge (not merged into either bridge above -- distinct concern from
# both keyboard activation and live-region announcement): the Decisions
# gr.Dataframe renders with role="grid" (Gradio's own Table.svelte), but
# never sets aria-selected anywhere -- selection is conveyed only visually,
# via theme.py's `tr:has(td.focus)` CSS. A screen-reader user browsing the
# grid with table/grid navigation (not just listening to the one-time
# live-region announcement) has no programmatic way to determine which row
# is currently selected. Verified directly against the shipped Svelte source
# (gradio/_frontend_code/dataframe/shared/Table.svelte), not assumed.
#
# Reuses exactly the same DOM contract V3.1's keyboard bridge already
# depends on and documents above (.aara-decisions-table anchor; a real data
# row is a `tr[slot="tbody"]`; Gradio's own click handler marks the selected
# cell with a `td.focus` class) -- no new contract introduced. Both mouse
# clicks and keyboard selection (via the bridge above, which calls a real
# cell.click()) converge on this same `.focus` class, so one sync function
# covers both input methods uniformly.
#
# A MutationObserver -- not a one-shot event listener -- is used because
# aria-selected must stay correct as an ongoing state, not just at the
# moment of selection (mirroring why the CSS `:has()` selector is itself
# continuously reactive, not a one-time style). `childList: true` also
# covers Refresh replacing the table's rows wholesale. The target table does
# not exist when this <script> parses (Gradio's client mounts
# asynchronously), so the same bounded-polling-then-attach pattern as
# _LIVE_REGION_SETUP_JS above is used: retry briefly, then either attach the
# observer (running one initial sync so every row carries an explicit
# aria-selected="false"/"true" from the start, not just after the first
# mutation) or give up silently if the table is never found.
_SELECTION_ARIA_SYNC_JS = """
<script>
(function () {
  function syncSelectedRow(table) {
    var rows = table.querySelectorAll('tr[slot="tbody"]');
    rows.forEach(function (row) {
      var isSelected = !!row.querySelector("td.focus");
      row.setAttribute("aria-selected", isSelected ? "true" : "false");
    });
  }
  function findInteractiveTable() {
    // .aara-decisions-table contains two <table> elements: Gradio's own
    // hidden column-width-measurement table (zero tr[slot="tbody"] rows)
    // and the real, virtualized, interactive table the rows above are
    // documented against -- .querySelector() alone would silently bind to
    // whichever renders first in DOM order (the empty one), so every
    // candidate is checked for a real data row instead of trusting order.
    var tables = document.querySelectorAll(".aara-decisions-table table");
    for (var i = 0; i < tables.length; i++) {
      if (tables[i].querySelector('tr[slot="tbody"]')) {
        return tables[i];
      }
    }
    return null;
  }
  var attempts = 0;
  var maxAttempts = 100;
  var intervalId = setInterval(function () {
    attempts += 1;
    var table = findInteractiveTable();
    if (table) {
      clearInterval(intervalId);
      syncSelectedRow(table);
      var observer = new MutationObserver(function () {
        syncSelectedRow(table);
      });
      observer.observe(table, {
        attributes: true, attributeFilter: ["class"], childList: true, subtree: true,
      });
      return;
    }
    if (attempts >= maxAttempts) {
      clearInterval(intervalId);
    }
  }, 50);
})();
</script>
"""

# P1 accessibility slice: Decisions grid accessible name. A fourth,
# independent JS bridge (not merged into any bridge above -- distinct
# concern from keyboard activation, live-region announcement, and
# selection ARIA sync): the Decisions gr.Dataframe below is passed
# label="Decisions" (show_label=False only suppresses the *visible* label
# row above the table -- it has no effect on this), but that label never
# reaches the interactive grid element a screen reader actually names.
# Verified directly against the shipped Svelte source
# (gradio/_frontend_code/dataframe/shared/Table.svelte), not assumed:
#   - The focusable, ARIA-grid landmark is `<div class="table-wrap"
#     role="grid" tabindex="0">`.
#   - `label` only ever reaches a `<caption class="sr-only">{label}</caption>`
#     nested inside the two *child* <table> elements that div wraps (the
#     hidden column-width-measurement table and the real, interactive
#     VirtualTable) -- never as an attribute on the role="grid" div itself.
#   - A <caption> names its own <table>; it does not propagate to an
#     ancestor carrying an explicit ARIA role, and role="grid" does not
#     compute its accessible name from subtree content the way a native
#     <table> does from <caption>. So the grid element a screen reader
#     actually lands on and announces has no programmatic accessible name
#     at all, despite label="Decisions" being set in Python.
# There is no supported non-JS way to close this gap: no aria_* kwarg
# exists on gr.Dataframe (same constraint the keyboard bridge above
# documents), and this needs an attribute, not rendered content, so CSS
# cannot do it either. The fix below does exactly one thing: find
# .aara-decisions-table's role="grid" element and set
# aria-label="Decisions" on it once -- the same literal text already
# passed as label= in Python, not a new/different string.
#
# A one-shot bounded poll (not a MutationObserver) is sufficient here,
# following _LIVE_REGION_SETUP_JS's own precedent rather than
# _SELECTION_ARIA_SYNC_JS's: this div is created once by Table.svelte and
# never destroyed/recreated by Refresh or row selection (only the row data
# inside it mutates), so a name set once persists for the life of the
# page -- unlike aria-selected in _SELECTION_ARIA_SYNC_JS, which tracks an
# ongoing state change and needs to keep re-syncing.
_ACCESSIBLE_NAME_SETUP_JS = """
<script>
(function () {
  var attempts = 0;
  var maxAttempts = 100;
  var intervalId = setInterval(function () {
    attempts += 1;
    var grid = document.querySelector('.aara-decisions-table [role="grid"]');
    if (grid) {
      grid.setAttribute("aria-label", "Decisions");
      clearInterval(intervalId);
      return;
    }
    if (attempts >= maxAttempts) {
      clearInterval(intervalId);
    }
  }, 50);
})();
</script>
"""

# P2 #6 (Loading States/Usability audit): Decision Journey anchor targets
# accessible-focus fix. _lifecycle_track_html's four stage links are real
# <a href="#..."> anchors to decision-created-section/evidence-section/
# governance-section/approval-section (see build() below and that
# function's own docstring) -- deliberately implemented as native in-page
# anchor jumps, no JS, when added. That's sufficient for a mouse user (the
# browser scrolls the target into view), but per the HTML fragment-
# navigation algorithm a plain, non-focusable element (each target is a
# bare gr.HTML(elem_id=...) <div>, confirmed by grep: no tabindex is set
# on any of the four anywhere in this file) never actually receives DOM
# focus on jump -- only a focusable target does. A keyboard or
# screen-reader user activating one of these links therefore gets no
# focus change and no announcement of having arrived at the section; only
# the visual scroll (imperceptible to them) occurs. Fifth, independent JS
# bridge (distinct concern from keyboard activation, live-region
# announcement, selection ARIA sync, and grid accessible name above): sets
# tabindex="-1" once on each of the four targets so the browser's own
# native fragment-focus behavior actually focuses them (no click/keydown
# handler needed -- the browser does this automatically once the target is
# focusable), and so each also picks up the existing generic
# `[tabindex]:focus-visible` outline rule in theme.py (added for this same
# Decision Journey feature's link-focus styling) with no new CSS.
#
# One-shot bounded poll, not a MutationObserver -- same reasoning as
# _ACCESSIBLE_NAME_SETUP_JS above: each of these four elements is Gradio's
# own stable per-component root div (Block.svelte -- never destroyed and
# recreated when the component's value later changes, only its inner
# content), created once and never replaced by Refresh or row selection,
# so setting the attribute once persists for the life of the page.
_JOURNEY_TARGET_FOCUS_SETUP_JS = """
<script>
(function () {
  var TARGET_IDS = [
    "decision-created-section", "evidence-section",
    "governance-section", "approval-section",
  ];
  var attempts = 0;
  var maxAttempts = 100;
  var intervalId = setInterval(function () {
    attempts += 1;
    var found = 0;
    TARGET_IDS.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) {
        el.setAttribute("tabindex", "-1");
        found += 1;
      }
    });
    if (found === TARGET_IDS.length) {
      clearInterval(intervalId);
      return;
    }
    if (attempts >= maxAttempts) {
      clearInterval(intervalId);
    }
  }, 50);
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
_SHELL_NAV_HTML = (
    '<nav class="aara-shell-nav-list" role="tablist">'
    '<span class="nav-item active" role="tab" aria-selected="true">Decision Center</span>'
    # Portfolio Intelligence and Risk Intelligence both shipped as real
    # screens (reachable via the gr.TabbedInterface composition in
    # bootstrap.py's build_trading_intelligence_app(), one level above this
    # module) -- "Coming Soon" is no longer true for either, so the badge
    # and muted styling are dropped from both. This module still never
    # imports or references the outer Tabs/TabbedInterface (self-contained
    # screens, unchanged); this is a copy fix only, not a real link to the
    # other tabs.
    #
    # Duplicate-navigation audit (this pass): the outer gr.TabbedInterface
    # tabs are now hidden in the composed app (bootstrap.py's
    # _TABBED_LAYOUT_CSS), leaving this nav as the one visible row -- it now
    # carries the same role="tablist"/"tab"/aria-selected pattern the outer
    # tabs already had, via ui/shell.py's build_shell_nav_html("Decision
    # Center") equivalent (kept as this module's own literal, matching
    # ui/shell.py's byte-for-byte parity test in ui/tests/test_shell.py).
    '<span class="nav-item" role="tab" aria-selected="false">Portfolio Intelligence</span>'
    '<span class="nav-item" role="tab" aria-selected="false">Risk Intelligence</span>'
    "</nav>"
)
_PAGE_HEADER_HTML = (
    '<h1 class="aara-eyebrow">Decision Center</h1>'
    '<div class="aara-page-subtitle">Governed investment decisions</div>'
)

_LIST_HEADERS = ["Decision ID", "Symbol", "Action", "Status", "Confidence", "Last Updated", "Verdict"]
_LIST_DATATYPES = ["str", "str", "markdown", "str", "str", "str", "markdown"]
_MISSING_VALUE = "-"

_DECISION_READ_ERROR_MESSAGE = "Unable to load this decision."
_DECISION_NOT_FOUND_MESSAGE = "No decision found for this ID."
_SELECT_DECISION_MESSAGE = "Select a decision to view details"
_EVIDENCE_EMPTY_MESSAGE = "No evidence attached yet."
_GOVERNANCE_EMPTY_MESSAGE = "No governance evaluation recorded."
_APPROVAL_EMPTY_MESSAGE = "No approval recorded."
_AUDIT_EMPTY_MESSAGE = "No audit events recorded."
_EVIDENCE_ERROR_MESSAGE = "Evidence is temporarily unavailable."
_GOVERNANCE_ERROR_MESSAGE = "Governance information is temporarily unavailable."
_APPROVAL_ERROR_MESSAGE = "Approval information is temporarily unavailable."
_AUDIT_ERROR_MESSAGE = "Audit trail is temporarily unavailable."

# MVP Loading States slice: _empty_detail()'s prior "" for why/evidence/
# governance/approval/audit rendered as literal blank space under each
# section heading -- no cue that the blank is because nothing is selected
# yet (initial zero-decisions load, or a deselect) rather than a rendering
# gap. Reuses the same aara-empty-message class every other "this section
# has no records" case in this file already uses (e.g. _EVIDENCE_EMPTY_MESSAGE
# via _record_list_html) -- no new CSS class, no new component.
_SELECT_DECISION_HTML = f'<div class="aara-empty-message">{html.escape(_SELECT_DECISION_MESSAGE)}</div>'

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

# P2 Why/Rationale error-wording fix (UI-completion audit): _WHY_RATIONALE_HTML
# above and this block render for two genuinely different situations that
# previously shared the exact same "Rationale not captured / thesis has not
# yet been recorded" wording -- a decision that has no evidence yet (still
# _WHY_RATIONALE_HTML's job) vs. a decision whose Evidence read failed
# (detail_area.evidence_status is ReadStatus.ERROR, which also forces
# evidence to () -- structurally indistinguishable from "no evidence" to
# _why_summary_sentence, but not the same fact). Telling a user "not yet
# recorded" during a transient read failure misstates a temporary system
# problem as a permanent absence of data. Reuses _EVIDENCE_ERROR_MESSAGE
# verbatim as the body -- the exact same sentence the Evidence section
# itself already shows for this identical failure (_format_evidence_html) --
# rather than inventing new copy, so the two surfaces can never say
# different things about the same read error.
_WHY_EVIDENCE_ERROR_TITLE = "Rationale unavailable"
_WHY_EVIDENCE_ERROR_HTML = (
    '<div class="aara-disclosure-message">'
    f'<div class="aara-disclosure-title">{html.escape(_WHY_EVIDENCE_ERROR_TITLE)}</div>'
    f'<div class="aara-disclosure-body">{html.escape(_EVIDENCE_ERROR_MESSAGE)}</div>'
    "</div>"
)

# P2 Why/Rationale trust clarification (UI-completion audit, ADR-037-adjacent
# but not authorized or governed by it -- wording only, no data/semantics
# change): the real-evidence sentence _why_summary_sentence composes below
# lists what evidence is attached (type/source), which reads as a causal
# "why" without being one. Appended (not a separate constant rendered
# elsewhere) so the announced and visible text can never drift, matching
# this file's existing single-source-of-truth discipline for this sentence.
# Deliberately not applied to _WHY_RATIONALE_HTML's zero-evidence fallback --
# "Rationale not captured" already makes no thesis/causal claim to clarify.
_WHY_EVIDENCE_CLARIFICATION = (
    "Evidence attached to this decision — not a recorded investment "
    "thesis or causal explanation."
)

# Slice 1 (UI-completion audit): static, decision-independent disclosure --
# no RiskEvaluation/RiskEntry contract or reader exists anywhere in this
# codebase. Built once at build() time like _SHELL_NAV_HTML, never wired
# into detail_outputs/_DetailValues/any callback path -- unlike
# _WHY_RATIONALE_HTML, which the Decision Detail Depth pass wired into the
# dynamic render path, this block must stay static, so it deliberately does
# not follow that later precedent.
_RISK_CONTEXT_TITLE = "Risk context not yet available"
_RISK_CONTEXT_BODY = "Position-level risk analysis has not yet been implemented for this workspace."
_RISK_CONTEXT_HTML = (
    '<div class="aara-disclosure-message">'
    f'<div class="aara-disclosure-title">{html.escape(_RISK_CONTEXT_TITLE)}</div>'
    f'<div class="aara-disclosure-body">{html.escape(_RISK_CONTEXT_BODY)}</div>'
    "</div>"
)

# P1 (Decision Center UI audit): the header's "Risk Reference (raw,
# unresolved)" field is an opaque DecisionContract pointer (see
# _raw_reference_fields_html) -- without this note, showing a real-looking
# reference value next to a decision could be read as if some risk
# analysis already exists, even though _RISK_CONTEXT_HTML (the Risk
# section) separately states Risk Intelligence is not implemented. This is
# wording only: it does not resolve, interpret, or validate the reference,
# and does not touch Evidence Reference, which has no such ambiguity since
# the Evidence section is real. Reuses the body-only aara-disclosure-message
# variant _format_why_summary_html already uses -- no new CSS class.
_RISK_REFERENCE_CLARIFICATION = (
    "This is an opaque pointer, not resolved risk analysis -- Risk "
    "Intelligence is not currently implemented for this workspace."
)
_RISK_REFERENCE_CLARIFICATION_HTML = (
    '<div class="aara-disclosure-message">'
    f'<div class="aara-disclosure-body">{html.escape(_RISK_REFERENCE_CLARIFICATION)}</div>'
    "</div>"
)

# P0 illustrative-data disclosure (UI-completion Product/UX audit): static,
# decision-independent, persistent -- built once at build() time like
# _SHELL_NAV_HTML, never wired into detail_outputs/_DetailValues/any
# callback path. Placed at the page-header level (every load, before any
# decision-specific content) rather than inside a single decision's detail
# panel, since it applies to the whole screen, not one decision. Deliberately
# names only "decisions and supporting data" in general -- it must not
# assert or deny that governance, approvals, audit events, persistence,
# authentication, brokerage connectivity, or any other production capability
# exists; that is out of scope for a single disclosure line.
_ILLUSTRATIVE_DATA_TITLE = "Illustrative Data"
_ILLUSTRATIVE_DATA_BODY = (
    "The decisions and supporting data shown here are illustrative and are "
    "not real trading activity."
)
_ILLUSTRATIVE_DATA_HTML = (
    '<div class="aara-disclosure-message">'
    f'<div class="aara-disclosure-title">{html.escape(_ILLUSTRATIVE_DATA_TITLE)}</div>'
    f'<div class="aara-disclosure-body">{html.escape(_ILLUSTRATIVE_DATA_BODY)}</div>'
    "</div>"
)

# P1 UI-only timestamp-semantics disclosure (GOOGL/dec-seed-004 timestamp
# audit): "Last Updated" in the Decisions table (and the mirrored Last
# Updated field in Decision Intelligence, via screen.py's own
# timestamp_display) is not always narrative/seed-timeline data -- for a
# decision whose latest recorded lifecycle stage is Governance Evaluated,
# GovernanceService.evaluate_policy() stamps real evaluation-time
# (datetime.utcnow(), sentinel_engine/services/governance_service.py) --
# unlike every other lifecycle step, which uses a caller-supplied/seed
# timestamp -- and that is out of scope to change without touching
# sentinel_engine (see bootstrap.py's own _seed_decisions() docstring).
# Same static/decision-independent/persistent pattern as
# _ILLUSTRATIVE_DATA_HTML above -- a separate disclosure because it covers
# a different topic (timestamp semantics, not data authenticity) that
# _ILLUSTRATIVE_DATA_BODY's own docstring deliberately keeps out of scope
# for that single line. Placed in the list toolbar, directly associated
# with the Decisions table's own "Last Updated" column.
_TIMESTAMP_DISCLOSURE_TITLE = "About Last Updated"
_TIMESTAMP_DISCLOSURE_BODY = (
    '"Last Updated" may represent the latest lifecycle event recorded '
    "for a decision, including governance evaluation time."
)
_TIMESTAMP_DISCLOSURE_HTML = (
    '<div class="aara-disclosure-message">'
    f'<div class="aara-disclosure-title">{html.escape(_TIMESTAMP_DISCLOSURE_TITLE)}</div>'
    f'<div class="aara-disclosure-body">{html.escape(_TIMESTAMP_DISCLOSURE_BODY)}</div>'
    "</div>"
)

_ACTION_BADGE_CLASSES = {"BUY": "action-buy", "SELL": "action-sell", "HOLD": "action-hold"}

_LIFECYCLE_STAGES = [
    (DecisionState.DECISION_CREATED, "Created", "decision-created-section"),
    (DecisionState.EVIDENCE_ATTACHED, "Evidence", "evidence-section"),
    (DecisionState.GOVERNANCE_EVALUATED, "Governance", "governance-section"),
    (DecisionState.APPROVAL_RECORDED, "Approval", "approval-section"),
]

# (header, lifecycle, conviction, updated, status, why, evidence, governance,
# approval, audit) -- why sits between status and evidence, not after audit,
# so every existing `*_, evidence_html, governance_html, approval_html,
# audit_html = ...`-style unpack in the test suite keeps addressing the same
# trailing four elements unchanged.
_DetailValues = Tuple[str, str, str, str, str, str, str, str, str, str]

# Audit Trail payload disclosure allowlist (P0 fix, accessibility/completeness
# audit): every key the real sentinel_engine event producers currently put on
# Event.payload, across all four implemented event types --
# DecisionService.create_decision() (DECISION_CREATED: symbol, action,
# confidence, evidence_reference, risk_reference), EvidenceService.
# associate_evidence() (EVIDENCE_ATTACHED: evidence_id, evidence_type,
# source, data), GovernanceService.evaluate_policy() (GOVERNANCE_EVALUATED:
# policy_id, enabled), GovernanceService.record_approval()
# (APPROVAL_RECORDED: approval_id, status, approved_by). Mirrors
# _format_evidence_detail_html's own allowlist discipline (there, ADR-037's
# 5 metadata keys). decision_id is deliberately never in this set: every one
# of those four real payloads also includes it, and the old
# _format_audit_detail_html rendered every payload key unfiltered, leaking
# it into the Audit Trail's expandable disclosure -- the same raw internal
# identifier already excluded, and tested as excluded, from every other
# rendered fragment (see _decision_header_html).
_AUDIT_PAYLOAD_ALLOWED_KEYS = frozenset({
    "symbol", "action", "confidence", "evidence_reference", "risk_reference",
    "evidence_id", "evidence_type", "source", "data",
    "policy_id", "enabled",
    "approval_id", "status", "approved_by",
})


class DecisionCenterUI:
    def __init__(self, controller: DecisionCenterController, decision_ids: List[str]):
        self._controller = controller
        self._decision_ids = list(decision_ids)

    def build(self) -> gr.Blocks:
        with gr.Blocks(
            title="AARA Trading Intelligence — Decision Center", css=CSS,
            head=(
                _KEYBOARD_SELECTION_BRIDGE_JS + _LIVE_REGION_SETUP_JS
                + _SELECTION_ARIA_SYNC_JS + _ACCESSIBLE_NAME_SETUP_JS
                + _JOURNEY_TARGET_FOCUS_SETUP_JS
            ),
        ) as demo:
            gr.HTML(_SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(_SHELL_NAV_HTML, elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML, elem_classes=["aara-page-header"])
            gr.HTML(_ILLUSTRATIVE_DATA_HTML)
            # P1 accessibility slice: visually hidden, screen-reader-only
            # live region -- see _LIVE_REGION_SETUP_JS above for how
            # aria-live/aria-atomic/role get attached to this element's
            # stable host, and _announce_screen/_announce_row_select below
            # for what populates it. Empty initial value; never rendered
            # with visible content of its own.
            live_announcer = gr.HTML(
                value="", elem_id=_LIVE_ANNOUNCER_ELEM_ID, elem_classes=["aara-sr-only"],
            )

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
                    gr.HTML(
                        _TIMESTAMP_DISCLOSURE_HTML,
                        elem_classes=["aara-list-timestamp-disclosure"],
                    )
                    list_output = gr.Dataframe(
                        # height/max_height (see _DATAFRAME_HEIGHT_KWARG) is a
                        # navigator viewport budget, not a fit for today's 3
                        # seed rows -- ~9-10 rows before Gradio's own
                        # virtualized table (VirtualTable.svelte) caps and
                        # scrolls internally, so this must not be re-tuned as
                        # seed/demo data changes; it works unmodified whether
                        # there are 3 decisions or 500.
                        headers=_LIST_HEADERS, datatype=_LIST_DATATYPES, interactive=False,
                        label="Decisions", show_label=False,
                        elem_classes=["aara-decisions-table"],
                        **{_DATAFRAME_HEIGHT_KWARG: 340},
                    )
                    # Quiet message below the (still-rendered, headers-only)
                    # table when there are zero decisions -- reuses the same
                    # aara-empty-message treatment the Evidence/Governance/
                    # Approval sections already use, so no new CSS class or
                    # theme.py change is needed. Empty string when the list is
                    # non-empty, per _format_list_empty_message_html below.
                    list_empty_output = gr.HTML()

                with gr.Column(scale=4, elem_classes=["aara-detail-column"]):
                    gr.Markdown(
                        '<h2 class="aara-eyebrow">Decision Intelligence</h2>',
                        elem_classes=["aara-section-label", "aara-section-label--group"],
                    )
                    header_output = gr.HTML(elem_id="decision-created-section")
                    with gr.Row(elem_classes=["aara-hero-metrics"]):
                        conviction_output = gr.Textbox(
                            label="Confidence", interactive=False,
                            elem_classes=["aara-field-value", "aara-conviction-value"],
                        )
                        updated_output = gr.Textbox(
                            label="Last Updated", interactive=False,
                            elem_classes=["aara-field-value"],
                        )
                        status_output = gr.Textbox(
                            label="Status", interactive=False,
                            elem_classes=["aara-field-value"],
                        )
                    # P2 Why/Rationale heading-clarity fix (UI-completion
                    # audit): "Why?" reads as a promise of a causal
                    # explanation this panel has never provided -- its own
                    # content was already carrying that clarification in
                    # prose (_WHY_EVIDENCE_CLARIFICATION: "not a recorded
                    # investment thesis or causal explanation"), forcing a
                    # sighted or screen-reader user to read the body before
                    # learning what the heading actually means. "Evidence
                    # Summary" states the section's real scope directly in
                    # the heading itself -- same short, sibling-parallel
                    # style as "Evidence"/"Governance & Policy"/"Approval"
                    # below, makes no causal claim, and does not need to
                    # change to keep matching this file's fallback/error
                    # copy (_WHY_RATIONALE_HTML, _WHY_EVIDENCE_ERROR_HTML),
                    # which already states plainly when nothing has been
                    # captured. why_output/detail_outputs and every
                    # controller/screen.py contract are unchanged -- this is
                    # the rendered heading string only.
                    gr.Markdown(
                        '<h3 class="aara-eyebrow">Evidence Summary</h3>',
                        elem_classes=["aara-section-label"],
                    )
                    why_output = gr.HTML()
                    gr.Markdown(
                        '<h3 class="aara-eyebrow">Decision Journey</h3>',
                        elem_classes=["aara-section-label"],
                    )
                    lifecycle_output = gr.HTML()
                    gr.Markdown(
                        '<h3 class="aara-eyebrow">Evidence</h3>', elem_classes=["aara-section-label"],
                    )
                    evidence_output = gr.HTML(elem_id="evidence-section")
                    gr.Markdown(
                        '<h3 class="aara-eyebrow">Governance & Policy</h3>',
                        elem_classes=["aara-section-label"],
                    )
                    governance_output = gr.HTML(elem_id="governance-section")
                    gr.Markdown(
                        '<h3 class="aara-eyebrow">Approval</h3>', elem_classes=["aara-section-label"],
                    )
                    approval_output = gr.HTML(elem_id="approval-section")
                    gr.Markdown(
                        '<h3 class="aara-eyebrow">Risk</h3>', elem_classes=["aara-section-label"],
                    )
                    gr.HTML(_RISK_CONTEXT_HTML)
                    gr.Markdown(
                        '<h3 class="aara-eyebrow">Audit Trail</h3>',
                        elem_classes=["aara-section-label"],
                    )
                    audit_output = gr.HTML()

            detail_outputs = [
                header_output, lifecycle_output, conviction_output, updated_output,
                status_output, why_output, evidence_output, governance_output, approval_output,
                audit_output,
            ]
            screen_outputs = [list_output, list_empty_output] + detail_outputs
            # Session-scoped (per Gradio Blocks session, not a self attribute --
            # see this module's own docstring on why DecisionCenterUI holds no
            # mutable state on self) so Refresh can re-select the decision the
            # user had open instead of always falling back to the first row.
            selected_decision_id = gr.State(None)

            # MVP Loading States slice: double-submit guard. Refresh's own
            # render call is unchanged (_render_screen, same inputs/outputs)
            # -- only wrapped in a .then() chain that disables the button
            # immediately on click and re-enables it once _render_screen
            # returns, so a second click while a render is already in
            # flight cannot dispatch a second concurrent call. The
            # live-region listener below (refresh_button.click(fn=self.
            # _announce_screen, ...)) is a separate, independent listener
            # registration on the same trigger -- untouched by this chain.
            refresh_button.click(
                fn=self._disable_refresh_button, inputs=None, outputs=[refresh_button],
            ).then(
                fn=self._render_screen, inputs=[selected_decision_id], outputs=screen_outputs,
            ).then(
                fn=self._enable_refresh_button, inputs=None, outputs=[refresh_button],
            )
            demo.load(fn=self._render_screen, inputs=None, outputs=screen_outputs)

            list_output.select(
                fn=self._on_row_select, inputs=None,
                outputs=[selected_decision_id] + detail_outputs,
            )

            # P1 accessibility slice: independent listeners on the same
            # three triggers above, targeting only live_announcer -- the
            # three listeners above, and their own outputs, are unchanged.
            demo.load(fn=self._announce_screen, inputs=None, outputs=[live_announcer])
            refresh_button.click(
                fn=self._announce_screen, inputs=[selected_decision_id],
                outputs=[live_announcer],
            )
            list_output.select(
                fn=self._announce_row_select, inputs=None, outputs=[live_announcer],
            )

        return demo

    @staticmethod
    def _disable_refresh_button() -> Dict[str, Any]:
        """First link in the Refresh double-submit guard chain (see
        build()) -- returns a Gradio update disabling the button the
        instant it's clicked, before _render_screen runs."""
        return gr.update(interactive=False)

    @staticmethod
    def _enable_refresh_button() -> Dict[str, Any]:
        """Last link in the Refresh double-submit guard chain (see
        build()) -- re-enables the button once _render_screen has returned,
        success or not (a .then() step always runs after its predecessor
        completes)."""
        return gr.update(interactive=True)

    def _render_screen(
        self, selected_id: Optional[str] = None,
    ) -> Tuple[List[List[str]], str, str, str, str, str, str, str, str, str, str, str]:
        """selected_id is None only when nothing has been explicitly picked
        yet (initial demo.load(), or Refresh before any row click) --
        controller.load_screen()'s own default for that case is
        list_area.decisions[0] in original, unsorted order, which no longer
        matches _format_list_rows' newest-first table. Resolving that here
        (asking the controller for the newest id by name, via the same
        selected_id parameter it already accepts for an explicit pick) keeps
        the initial detail pane in sync with the sorted top row without
        touching controller.py's own default-selection logic. Once a row is
        actually clicked, _on_row_select supplies a real selected_id and
        this branch never runs again for that session."""
        if selected_id is None:
            selected_id = self._newest_decision_id()
        screen = self._controller.load_screen(self._decision_ids, selected_id)
        list_rows = self._format_list_rows(screen.list_area)
        list_empty_message = self._format_list_empty_message_html(screen.list_area)
        detail_values = self._format_detail(screen.detail_area)
        return (list_rows, list_empty_message) + detail_values

    def _newest_decision_id(self) -> Optional[str]:
        """Same ordering key as _format_list_rows (updated_at descending) --
        deliberately re-fetches list_area rather than trying to share one
        with _render_screen's own later call, since selected_id must be
        resolved before controller.load_screen() runs (it's an input to
        that call, not derivable from its output)."""
        decisions = self._controller.load_decisions(self._decision_ids).decisions
        if not decisions:
            return None
        return max(decisions, key=lambda view: view.updated_at).decision_id

    def _render_detail(self, decision_id: str) -> _DetailValues:
        if not decision_id:
            return self._empty_detail()
        detail_area = self._controller.load_decision_detail(decision_id)
        return self._format_looked_up_detail(detail_area)

    def _on_row_select(
        self, evt: gr.SelectData,
    ) -> Tuple[Optional[str], str, str, str, str, str, str, str, str, str, str]:
        if not evt.selected or not evt.row_value:
            return (None,) + self._empty_detail()
        decision_id = evt.row_value[0]
        return (decision_id,) + self._render_detail(decision_id)

    def _announce_screen(self, selected_id: Optional[str] = None) -> str:
        """P1 accessibility slice: populates live_announcer for both
        demo.load() and refresh_button.click() (Option 1 -- shared wording,
        see the approved proposal). A second, independent listener on each
        trigger (see build()) -- never touches _render_screen()'s own return
        shape or its screen_outputs. selected_id is accepted, unused, only
        because refresh_button.click() wires this fn with
        inputs=[selected_decision_id] (Gradio calls fn with one positional
        argument per declared input); demo.load() wires inputs=None, calling
        this with zero arguments, covered by the default.

        Reuses _newest_decision_id()'s own already-accepted duplicate-fetch
        pattern (see that method's docstring) rather than inventing a new
        one or touching controller.py/screen.py: a second
        load_decisions() call, independent of _render_screen()'s own via
        load_screen()."""
        count = len(self._controller.load_decisions(self._decision_ids).decisions)
        noun = "decision" if count == 1 else "decisions"
        return f"Decision Center updated. Showing {count} {noun}."

    def _announce_row_select(self, evt: gr.SelectData) -> str:
        """P1 accessibility slice, extended by the P2 Why/Rationale
        accessibility pass: populates live_announcer for
        list_output.select() -- a second, independent listener (see
        build()), never touching _on_row_select()'s own return shape or
        detail_outputs.

        P1 originally derived this wording entirely from evt.row_value,
        deliberately avoiding a second controller call ("Option 1 --
        shared wording, see the approved proposal"). The P2 investigation
        found that minimal wording ("Decision selected: {symbol}.") left
        screen-reader users with no indication that a rationale -- the
        same one sighted users see appear in the Why? panel below -- was
        even available, let alone what it said; closing that gap requires
        the decision's evidence, which row_value alone doesn't carry. This
        now makes one additional controller call per selection, following
        the same already-accepted duplicate-fetch precedent
        _announce_screen uses above (re-fetching via load_decisions()
        instead of threading _render_screen's result) -- these announcer
        listeners stay deliberately independent of the render listeners
        rather than sharing state with them.

        Reuses _why_summary_sentence -- the exact plain-text logic
        _format_why_summary_html already renders into the Why? panel --
        so the announcement and the visible panel can never drift out of
        sync.

        P2 Loading States accessibility pass: a read error and an empty
        (not-found) result previously both fell back to the same bare
        "Decision selected: {symbol}." wording -- indistinguishable from a
        normal successful selection to a screen-reader user, even though
        the visible header simultaneously shows a distinct
        _DECISION_READ_ERROR_MESSAGE / _DECISION_NOT_FOUND_MESSAGE (see
        _decision_error_header_html/_missing_decision_header_html). Each
        case now reuses those exact same constants in the announcement, so
        a screen-reader user gets the same failure information a sighted
        user already sees, and the wording can never drift between the two
        surfaces. Checked in the same order _format_looked_up_detail
        already uses (ReadStatus.ERROR before is_empty). Empty string on
        deselection/no-row, matching _on_row_select's own guard -- nothing
        to announce when nothing was selected.

        P1 accessibility audit fix: a successful decision-level load can
        still have one or more of its four sections (Evidence/Governance/
        Approval/Audit Trail) fail independently -- controller.py's own
        load_decision_detail() isolates each read behind its own
        ReadStatus. Previously only the visible section HTML showed
        _EVIDENCE_ERROR_MESSAGE/etc. (_format_evidence_html and siblings);
        the live region said nothing, so a screen-reader user had no signal
        a section failed short of manually navigating into it. Reuses
        _section_error_summary (built from the same *_ERROR_MESSAGE
        constants those section renderers already use) and appends it here
        -- no new domain semantics, no change to the decision-level
        error/not-found/success branches above.

        P2 Why/Rationale error-wording fix (UI-completion audit): an
        evidence read failure previously fell through to the same
        "{_WHY_RATIONALE_TITLE}. {_WHY_RATIONALE_BODY}" wording a
        genuinely evidence-free decision gets (_why_summary_sentence
        returns None for both -- evidence_status ERROR forces evidence to
        () same as a real empty result), announcing a transient failure as
        if the thesis had permanently "not yet been recorded". Now checked
        before falling into _why_summary_sentence, mirroring
        _format_why_summary_html's own evidence_status check for the
        visible panel."""
        if not evt.selected or not evt.row_value:
            return ""
        decision_id = evt.row_value[0]
        symbol = evt.row_value[1]
        detail_area = self._controller.load_decision_detail(decision_id)
        if detail_area.decision_status is ReadStatus.ERROR:
            return f"Decision selected: {symbol}. {_DECISION_READ_ERROR_MESSAGE}"
        if detail_area.is_empty:
            return f"Decision selected: {symbol}. {_DECISION_NOT_FOUND_MESSAGE}"
        if detail_area.evidence_status is ReadStatus.ERROR:
            # P2 Why/Rationale error-wording fix: short title only -- the
            # detailed _EVIDENCE_ERROR_MESSAGE sentence is not repeated here
            # since section_errors below already appends it (evidence_status
            # ERROR is always the first thing _section_error_summary reports),
            # matching _format_why_summary_html's own visible title/body
            # split for the same case (_WHY_EVIDENCE_ERROR_HTML).
            summary = f"{_WHY_EVIDENCE_ERROR_TITLE}."
        else:
            summary = self._why_summary_sentence(detail_area.evidence)
            if summary is None:
                summary = f"{_WHY_RATIONALE_TITLE}. {_WHY_RATIONALE_BODY}"
        section_errors = DecisionCenterUI._section_error_summary(detail_area)
        if section_errors:
            return f"Decision selected: {symbol}. {summary} {section_errors}"
        return f"Decision selected: {symbol}. {summary}"

    @staticmethod
    def _section_error_summary(detail_area: DecisionDetailArea) -> str:
        """Announces which detail sections failed to load, reusing the
        exact same _EVIDENCE_ERROR_MESSAGE/_GOVERNANCE_ERROR_MESSAGE/
        _APPROVAL_ERROR_MESSAGE/_AUDIT_ERROR_MESSAGE constants each
        section's own inline HTML already shows (_format_evidence_html/
        _format_governance_html/_format_approval_html/_format_audit_html)
        -- no new domain semantics, just relaying an already-computed
        ReadStatus to the live region. Fixed Evidence -> Governance ->
        Approval -> Audit Trail order, matching the detail panel's own
        top-to-bottom section order. Empty string when every section
        succeeded (the common case), so callers don't append a stray
        trailing space."""
        messages = []
        if detail_area.evidence_status is ReadStatus.ERROR:
            messages.append(_EVIDENCE_ERROR_MESSAGE)
        if detail_area.governance_status is ReadStatus.ERROR:
            messages.append(_GOVERNANCE_ERROR_MESSAGE)
        if detail_area.approvals_status is ReadStatus.ERROR:
            messages.append(_APPROVAL_ERROR_MESSAGE)
        if detail_area.audit_trail_status is ReadStatus.ERROR:
            messages.append(_AUDIT_ERROR_MESSAGE)
        return " ".join(messages)

    @staticmethod
    def _format_list_rows(list_area: DecisionListArea) -> List[List[str]]:
        """Rendered newest-first (DecisionView.updated_at descending) --
        DecisionListArea itself carries no ordering guarantee (whatever the
        controller/query-service returned), so this is the one place that
        decides display order. _render_screen's own _newest_decision_id()
        uses the same ordering key to keep the initial (no-selection-yet)
        detail pane in sync with this table's top row."""
        decisions = sorted(list_area.decisions, key=lambda view: view.updated_at, reverse=True)
        return [
            [
                view.decision_id,
                view.symbol,
                DecisionCenterUI._list_action_badge_html(view.action),
                view.status.value.replace("_", " ").title(),
                f"{view.confidence * 100:.0f}%",
                format_display_timestamp(view.updated_at),
                DecisionCenterUI._verdict_badge_html(view.approval_status),
            ]
            for view in decisions
        ]

    @staticmethod
    def _format_list_empty_message_html(list_area: DecisionListArea) -> str:
        """DecisionListArea.empty_state_message is already computed and
        tested (screen.py/controller.py/integration tests) -- this only
        renders it. None (list is non-empty) maps to "", so the message
        never appears alongside real rows."""
        if list_area.empty_state_message is None:
            return ""
        return f'<div class="aara-empty-message">{html.escape(list_area.empty_state_message)}</div>'

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
    def _verdict_badge_html(status: Optional[ApprovalStatus]) -> str:
        """Verdict column, same markdown-column pattern as the Action badge
        above. status is None when no approval has been recorded yet for
        that decision -- rendered as the plain _MISSING_VALUE dash, not a
        fabricated "Pending" badge (ApprovalStatus has no PENDING member and
        this slice does not add one). Reuses the existing
        positive/negative approval-verdict color vocabulary already
        established for the Decision Detail approval card
        (_format_approval_html) -- never a bare red/green pair alone, per
        this file's existing accessibility discipline."""
        if status is None:
            return _MISSING_VALUE
        is_approved = status is ApprovalStatus.APPROVED
        css_class = "verdict-approved" if is_approved else "verdict-rejected"
        label = "Approved" if is_approved else "Rejected"
        return f'<span class="aara-list-verdict-badge {css_class}">{html.escape(label)}</span>'

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
            DecisionCenterUI._decision_header_html(
                decision, detail_area.evidence_reference, detail_area.risk_reference,
            ),
            DecisionCenterUI._lifecycle_track_html(decision.status),
            detail_area.confidence_display,
            detail_area.timestamp_display,
            detail_area.status_display,
            DecisionCenterUI._format_why_summary_html(detail_area),
            DecisionCenterUI._format_evidence_html(detail_area),
            DecisionCenterUI._format_governance_html(detail_area),
            DecisionCenterUI._format_approval_html(detail_area),
            DecisionCenterUI._format_audit_html(detail_area),
        )

    @staticmethod
    def _why_summary_sentence(evidence: Tuple[EvidenceEntry, ...]) -> Optional[str]:
        """Plain-text rationale sentence, factored out of
        _format_why_summary_html so the P2 accessibility pass's
        _announce_row_select can announce the same rationale a sighted
        user sees in the Why? panel instead of re-deriving it. Composes a
        real, decision-specific summary from already-loaded EvidenceEntry
        data (evidence_type/source) -- the one real signal already
        available in this read chain, not a substitute for a
        thesis/rationale field (none exists anywhere, and this pass
        invents none). None when there is no evidence to summarize --
        including the evidence-read-error case (detail_area.evidence is
        empty then too) -- callers render their own fallback for that
        case, since the HTML and plain-text renderings of "no rationale"
        differ (_WHY_RATIONALE_HTML's two-line disclosure vs. a single
        announced sentence).

        P2 trust clarification pass: _WHY_EVIDENCE_CLARIFICATION is appended
        to the composed sentence itself (not rendered as a second, separate
        fragment by callers) so _format_why_summary_html's visible panel and
        _announce_row_select's screen-reader announcement always carry the
        identical clarification -- no new data, no change to what evidence
        is summarized or how, only this one sentence appended to the end."""
        if not evidence:
            return None
        if len(evidence) == 1:
            entry = evidence[0]
            return (
                f"1 {entry.evidence_type} signal from {entry.source}. "
                f"{_WHY_EVIDENCE_CLARIFICATION}"
            )
        descriptions = "; ".join(
            f"{entry.evidence_type} from {entry.source}" for entry in evidence
        )
        return f"{len(evidence)} signals: {descriptions}. {_WHY_EVIDENCE_CLARIFICATION}"

    @staticmethod
    def _format_why_summary_html(detail_area: DecisionDetailArea) -> str:
        """P2 Why/Rationale error-wording fix: evidence_status is checked
        first, and separately from "no evidence to summarize" -- an
        evidence read failure now renders _WHY_EVIDENCE_ERROR_HTML (reusing
        _EVIDENCE_ERROR_MESSAGE, the same wording the Evidence section
        itself already shows for this identical failure) instead of
        falling into the same "Rationale not captured" wording a genuinely
        evidence-free decision gets. Falls back to the original, unchanged
        _WHY_RATIONALE_HTML only for the real zero-evidence case. See
        _why_summary_sentence for the shared summary logic (also used by
        _announce_row_select)."""
        if detail_area.evidence_status is ReadStatus.ERROR:
            return _WHY_EVIDENCE_ERROR_HTML
        summary = DecisionCenterUI._why_summary_sentence(detail_area.evidence)
        if summary is None:
            return _WHY_RATIONALE_HTML
        return (
            '<div class="aara-disclosure-message">'
            f'<div class="aara-disclosure-body">{html.escape(summary)}</div>'
            "</div>"
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
                    ("Attached", format_display_timestamp(entry.attached_at), True),
                ],
                "neutral",
                DecisionCenterUI._format_evidence_detail_html(entry.data.get("metadata", {})),
            )
            for entry in detail_area.evidence
        ]
        return DecisionCenterUI._record_list_html(cards, _EVIDENCE_EMPTY_MESSAGE, "evidence")

    @staticmethod
    def _format_evidence_detail_html(metadata: Dict[str, Any]) -> str:
        """Expandable, structured presentation of exactly the five
        ADR-037-authorized EvidenceEntry.data["metadata"] keys --
        shap_drivers, is_degraded, val_loss, raw_score, headlines -- each
        rendered only when present, nothing invented or transformed beyond
        display formatting. Any other current or future metadata key is
        not rendered. signal/confidence are top-level siblings of metadata
        on EvidenceEntry.data, never part of the metadata dict this
        function receives, so they can never appear here structurally --
        see _format_evidence_html's call site.

        Reuses _format_audit_detail_html's own <details>/<summary>
        disclosure and aara-record-card-fields/aara-record-field/
        record-label/record-value markup rather than introducing new,
        unstyled classes. Returns "" (no disclosure at all) when none of
        the five keys are present, matching the pre-ADR-037 card exactly.

        val_loss=None and an empty headlines list both render an explicit
        "N/A" -- never Python's None/[] reprs, never a blank field."""
        rows: List[Tuple[str, str]] = []

        if "shap_drivers" in metadata:
            rows.extend(
                (str(driver["feature"]), str(driver["shap_value"]))
                for driver in metadata["shap_drivers"]
            )

        if "is_degraded" in metadata:
            rows.append(("Model Degraded", "Yes" if metadata["is_degraded"] else "No"))

        if "val_loss" in metadata:
            val_loss = metadata["val_loss"]
            rows.append(("Validation Loss", "N/A" if val_loss is None else str(val_loss)))

        if "raw_score" in metadata:
            rows.append(("Raw Sentiment Score", str(metadata["raw_score"])))

        if "headlines" in metadata:
            headlines = metadata["headlines"]
            if headlines:
                rows.extend(("Headline", str(headline)) for headline in headlines)
            else:
                rows.append(("Headlines", "N/A"))

        if not rows:
            return ""

        field_html = "".join(
            '<div class="aara-record-field">'
            f'<span class="record-label">{html.escape(label)}</span>'
            f'<span class="record-value">{html.escape(value)}</span>'
            "</div>"
            for label, value in rows
        )
        return (
            '<details class="aara-payload-disclosure">'
            "<summary>Details</summary>"
            f'<div class="aara-record-card-fields">{field_html}</div>'
            "</details>"
        )

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
                    ("Evaluated", format_display_timestamp(entry.evaluated_at), True),
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
        cards = []
        for entry in detail_area.approvals:
            is_approved = entry.status is ApprovalStatus.APPROVED
            # P3 visual-polish fix (Finding 2): a REJECTED entry previously
            # still read "Approved By"/"Approved At" right next to its own
            # REJECTED pill -- self-contradictory wording, live-verified on
            # dec-seed-005/TSLA. ApprovalEntry.approved_by/approved_at
            # themselves are untouched (still the one real field pair on
            # the record regardless of verdict) -- only the display label
            # text is conditional on the same entry.status already used two
            # lines below to pick the pill's positive/negative color.
            by_label = "Approved By" if is_approved else "Recorded By"
            at_label = "Approved At" if is_approved else "Recorded At"
            cards.append(
                DecisionCenterUI._record_card_html(
                    "",  # no fabricated label -- the verdict below is the card's identity
                    entry.status.value.replace("_", " ").title(),
                    [
                        (by_label, entry.approved_by, False),
                        (at_label, format_display_timestamp(entry.approved_at), True),
                    ],
                    "positive" if is_approved else "negative",
                )
            )
        return DecisionCenterUI._record_list_html(cards, _APPROVAL_EMPTY_MESSAGE, "approval")

    @staticmethod
    def _format_audit_html(detail_area: DecisionDetailArea) -> str:
        if detail_area.audit_trail_status is ReadStatus.ERROR:
            return DecisionCenterUI._error_message_html(_AUDIT_ERROR_MESSAGE)
        cards = [
            DecisionCenterUI._record_card_html(
                entry.event_type.replace("_", " ").title(),
                "Recorded",
                [("Recorded At", format_display_timestamp(entry.created_at), True)],
                "neutral",
                DecisionCenterUI._format_audit_detail_html(entry.event_id, entry.payload),
            )
            for entry in detail_area.audit_trail
        ]
        return DecisionCenterUI._record_list_html(cards, _AUDIT_EMPTY_MESSAGE, "audit")

    @staticmethod
    def _format_audit_detail_html(event_id: str, payload: Dict[str, Any]) -> str:
        """Expandable, structured presentation of what
        DecisionQuery.get_decision_timeline() already returns on the
        underlying Event -- event_id plus every _AUDIT_PAYLOAD_ALLOWED_KEYS
        payload key, as-is, nothing invented or transformed beyond
        str()/html.escape() for display. Any other payload key -- most
        notably decision_id, which every real Event.payload carries -- is
        silently dropped; see _AUDIT_PAYLOAD_ALLOWED_KEYS's own comment for
        why. Native <details>/<summary> disclosure, no JS. Reuses the record
        card's own aara-record-card-fields/aara-record-field/record-label/
        record-value classes rather than introducing new, unstyled ones."""
        rows = [("Event ID", event_id)]
        rows.extend(
            (str(key), str(value))
            for key, value in payload.items()
            if key in _AUDIT_PAYLOAD_ALLOWED_KEYS
        )
        field_html = "".join(
            '<div class="aara-record-field">'
            f'<span class="record-label">{html.escape(label)}</span>'
            f'<span class="record-value">{html.escape(value)}</span>'
            "</div>"
            for label, value in rows
        )
        return (
            '<details class="aara-payload-disclosure">'
            "<summary>Details</summary>"
            f'<div class="aara-record-card-fields">{field_html}</div>'
            "</details>"
        )

    @staticmethod
    def _decision_header_html(
        decision: DecisionView,
        evidence_reference: Optional[str] = None,
        risk_reference: Optional[str] = None,
    ) -> str:
        badge = DecisionCenterUI._action_badge_html(decision.action)
        references_html = DecisionCenterUI._raw_reference_fields_html(
            evidence_reference, risk_reference,
        )
        return (
            '<div class="aara-decision-header">'
            f'<div class="identity-line">{html.escape(decision.symbol)} &middot; {badge}</div>'
            f"{references_html}"
            "</div>"
        )

    @staticmethod
    def _raw_reference_fields_html(
        evidence_reference: Optional[str], risk_reference: Optional[str],
    ) -> str:
        """evidence_reference/risk_reference are opaque DecisionContract
        pointer strings (see decision_query_service.py's
        get_decision_references()) -- displayed verbatim, labeled explicitly
        as raw/unresolved, never interpreted, resolved, or validated here,
        per the read-only audit that scoped this P0 change. Reuses the
        existing aara-record-card-fields/aara-record-field/record-label/
        record-value classes (theme.py) the Evidence/Governance/Approval/
        Audit record cards already use, so this reads as the same visual
        language rather than a new component. None means the caller has no
        reference data (e.g. the blank/not-found/error detail states, which
        never construct a decision header with references at all) -- no
        field is rendered for a None value. When risk_reference is present,
        appends _RISK_REFERENCE_CLARIFICATION_HTML (P1, Decision Center UI
        audit) so the raw pointer can't be mistaken for resolved Risk
        Intelligence -- Evidence Reference is unaffected, since only the
        Risk field carries that ambiguity."""
        fields = [
            (label, value)
            for label, value in (
                ("Evidence Reference (raw, unresolved)", evidence_reference),
                ("Risk Reference (raw, unresolved)", risk_reference),
            )
            if value is not None
        ]
        if not fields:
            return ""
        field_html = "".join(
            '<div class="aara-record-field">'
            f'<span class="record-label">{html.escape(label)}</span>'
            f'<span class="record-value">{html.escape(value)}</span>'
            "</div>"
            for label, value in fields
        )
        clarification_html = (
            _RISK_REFERENCE_CLARIFICATION_HTML if risk_reference is not None else ""
        )
        return f'<div class="aara-record-card-fields">{field_html}</div>{clarification_html}'

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
        """Each stage label is a native #anchor link to the already-existing
        detail section it names (decision-created-section on header_output,
        evidence-section/governance-section/approval-section on their own
        gr.HTML() outputs) -- no JS, no new controller/status/lifecycle
        semantics, just an in-page jump to a section that already renders
        that data."""
        stage_values = [stage for stage, _, _ in _LIFECYCLE_STAGES]
        current_index = stage_values.index(status)
        segments = []
        for index, (_, label, anchor_id) in enumerate(_LIFECYCLE_STAGES):
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
                f'<a class="label" href="#{anchor_id}">{html.escape(label)}</a></span>'
            )
        return '<div class="aara-lifecycle-track">' + "".join(segments) + "</div>"

    @staticmethod
    def _record_card_html(
        record_type: str, state: str, fields: List[Tuple[str, str, bool]], state_variant: str,
        extra_html: str = "",
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
        only semantic indicator" rule.

        extra_html is appended after the fields block, unescaped (the
        caller is responsible for escaping anything it interpolates) --
        Audit's only caller today, carrying the expandable payload
        disclosure from _format_audit_detail_html; empty string (the
        default) for every other caller, so their markup is unchanged."""
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
            f'{extra_html}'
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
        return (
            "", _MISSING_VALUE, _MISSING_VALUE, _MISSING_VALUE, _MISSING_VALUE,
            _SELECT_DECISION_HTML, _SELECT_DECISION_HTML, _SELECT_DECISION_HTML,
            _SELECT_DECISION_HTML, _SELECT_DECISION_HTML,
        )

    @staticmethod
    def _missing_decision_detail() -> _DetailValues:
        return (
            DecisionCenterUI._missing_decision_header_html(),
            _MISSING_VALUE, _MISSING_VALUE, _MISSING_VALUE, _MISSING_VALUE,
            "", "", "", "", "",
        )

    @staticmethod
    def _decision_error_detail() -> _DetailValues:
        return (
            DecisionCenterUI._decision_error_header_html(),
            _MISSING_VALUE, _MISSING_VALUE, _MISSING_VALUE, _MISSING_VALUE,
            "", "", "", "", "",
        )
