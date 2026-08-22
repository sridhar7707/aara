"""CSS for the Decision Center Gradio shell.

Presentation only -- a plain string constant passed to `gr.Blocks(css=...)`
(gradio_view.py's own build() method). No data, no logic, no sentinel_engine/
bot/dashboard/scheduler import: this module is pure styling.

Token source: brand/design_system/tokens.css's primitive palette (color,
spacing, radius, shadow, font) is reused verbatim -- this app's own visual
identity is AARA/Sentinel Intelligence's, and brand/ is the frozen,
authoritative source for it. brand/ itself is never imported or modified;
the handful of values used here are copied, per DESIGN_TOKENS.md's own
documented Gradio integration pattern ("Gradio Implementation" section).
The one binary asset that can't be "copied" as a token -- the approved
Sentinel Mark logo (brand/logos/sentinel_mark_v1.0_gold_on_navy.png) -- is
referenced directly by gradio_view.py's application shell, per
LOGO_ASSET_GUIDE.md's own documented Gradio integration example. Its frozen
design rules require a Deep Navy background and a 200px minimum display
width; --color-navy-primary is used as the shell header's own background for
exactly that reason (see .aara-shell-header below) rather than placing the
mark on the page's warm-white body background, which the guide prohibits.

Deliberately NOT reused: brand's component-specific semantic tokens
(--status-pending/approved/deferred/declined/escalated, --governance-pass/
review/block) and their component specs (DECISION_CARD.md, GOVERNANCE_BADGE.md,
STATE_MAPPING.yaml). Those target a different, archived frontend
(archive/sentinel_phase2a_scaffold/) with a richer data model (conviction_score,
decision_quality_score, an approval-verdict state vocabulary) that doesn't
exist anywhere in this package's actual DecisionContract/DecisionView/
EvidenceEntry/GovernanceEntry/ApprovalEntry. Reusing those names for our
actual DecisionState lifecycle-stage vocabulary or BUY/SELL/HOLD would
misrepresent what they mean (see AI-approved UI/UX Visual Pass decision log,
2026-08-10) -- so this file defines its own, honestly-named --lifecycle-*/
--action-* tokens instead, built from the same primitive palette.

Also encodes brand/guidelines/FORBIDDEN_UI_PATTERNS.md's prohibitions: no
red/green stoplight action colors, no gauges/meters, no flashing or gimmick
motion (brand/design_system/MOTION_RULES.md's timing values are used for the
only transitions this stylesheet defines).

V3 Decision Workspace pass (2026-08-10) -- "the framework is invisible, the
decision is visible." Everything below was verified against the live-running
app's actual DOM (Playwright), not inferred from Gradio's source:

- Framework chrome removal: `footer` (Built with Gradio / Use via API) is
  Gradio's own always-rendered element -- suppressed the same way
  dashboard/layout.py already does (`footer { display: none !important; }`),
  an established pattern in this repo, not a new technique.
- Full-bleed shell: `.gradio-container` carries its own `padding: 16px 32px`
  and `max-width: 1280px` (measured, not assumed), which is what made the
  navy header read as a floating banner. The shell header/nav cancel that
  with the standard `calc(-50vw + 50%)` full-bleed technique rather than
  stripping the container's padding/max-width globally -- the rest of the
  page (list/detail columns) keeps its normal, comfortable margins; only the
  shell bleeds.
- Decision list selection: Gradio applies `box-shadow: rgb(249,115,22) ...
  inset` (hardcoded Tailwind orange-500) to the single clicked `td.focus` --
  this, not any row-level class, was the "orange ring" defect. Suppressed on
  `td.focus` and replaced with an intentional whole-row treatment via
  `tr:has(td.focus)` (native `:has()`, no JS) -- selector choice follows the
  brief's instruction to prefer semantic/attribute/structural selectors over
  Gradio's hashed `svelte-*` classes, though the `.focus`/`.table-wrap`
  Gradio-assigned class names themselves are unavoidable (they're the only
  hooks Gradio exposes for this state) and documented here for that reason.
- Keyboard parity: `:focus-visible` on the cell gets the same row treatment
  as mouse `.focus`, so Tab+Enter selection looks identical to a click
  instead of falling back to the browser's default outline.
- Scrollbar: the table's `overflow-x: scroll` was hardcoded by Gradio
  regardless of actual overflow (verified: content was 1px narrower than the
  scroll track). Suppressed on the x-axis only; the y-axis is deliberately
  left as `overflow-y: auto` (never `hidden`) on the row wrapper with an
  explicit `height`/`max-height` budget sized for the current row count --
  more decisions than fit will scroll, never clip invisibly.
"""

CSS = """
:root {
  --color-navy-primary: #0B1F3A;
  --color-emerald-secondary: #176B4D;
  --color-gold-accent: #C8A45D;
  /* WCAG contrast fix (live audit): #C8A45D is ~2.2:1 against the
     surrounding surfaces it sits on as a thin boundary (focus ring, active
     underline, active lifecycle dot) -- below the 3:1 UI-component floor.
     Dedicated darker gold for those three boundary roles only; the base
     --color-gold-accent (used for larger/text contexts that already pass)
     is untouched. */
  --color-gold-accent-boundary: #A8823D;
  --color-background-warm: #F8F7F3;
  --color-surface-white: #FFFFFF;
  --color-text-primary: #1A1A1A;
  --color-text-secondary: #666666;
  --color-border-subtle: #E2E8F0;

  --font-primary: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-data: Monaco, "Courier New", monospace;

  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;

  --radius-card: 8px;
  --radius-badge: 4px;
  --shadow-card: 0 1px 3px rgba(11, 31, 58, 0.06);

  --transition-standard: 200ms ease-in-out;

  /* Lifecycle stage tokens (DecisionState) -- our own vocabulary, not
     brand's --status-* (see module docstring). */
  /* WCAG contrast fix (live audit): --color-border-subtle measured ~1.15:1
     against the surrounding warm/white surfaces where it was used as the
     future-stage dot border and connector -- effectively invisible,
     against the 3:1 UI-component/graphical-object floor. Dedicated darker
     slate for this future-stage boundary only; --color-border-subtle's
     other (decorative, non-essential) hairline/divider uses are untouched. */
  --lifecycle-future: #7C8CA0;
  --lifecycle-active: var(--color-gold-accent-boundary);
  --lifecycle-complete: var(--color-emerald-secondary);

  /* Trade action tokens (BUY/SELL/HOLD) -- quiet tints, never red/green. */
  --action-buy-bg: rgba(23, 107, 77, 0.10);
  --action-buy-fg: var(--color-emerald-secondary);
  --action-sell-bg: rgba(11, 31, 58, 0.08);
  --action-sell-fg: var(--color-navy-primary);
  --action-hold-bg: rgba(102, 102, 102, 0.10);
  /* WCAG contrast fix (live audit): aliasing --color-text-secondary here
     fails 4.5:1 in the two contexts that stack --action-hold-bg's own tint
     on top of another translucent surface (selected decision-list row, and
     the neutral record-card pill nested inside its own tinted card) --
     everywhere else the alias already passed. Dedicated darker value scoped
     to this token only; --color-text-secondary itself, and its other
     already-passing uses, are untouched. */
  --action-hold-fg: #5D5D5D;
}

/* ==========================================================================
   Framework chrome removal.
   ========================================================================== */
footer { display: none !important; }

.gradio-container {
  background: var(--color-background-warm) !important;
  font-family: var(--font-primary) !important;
}

.gradio-container * {
  font-family: var(--font-primary);
}

/* ==========================================================================
   Application shell -- full-bleed logo/wordmark/descriptor + non-interactive
   nav. .gradio-container has its own padding/max-width (see module
   docstring); these two elements cancel it with the standard viewport
   full-bleed technique so only the shell reaches the true edges.
   ========================================================================== */
.aara-shell-header,
.aara-shell-nav {
  width: 100vw !important;
  max-width: 100vw !important;
  margin-left: calc(-50vw + 50%) !important;
  margin-right: calc(-50vw + 50%) !important;
  border-radius: 0 !important;
}
.aara-shell-header {
  background: var(--color-navy-primary) !important;
  padding: var(--space-sm) calc(50vw - 50% + var(--space-lg)) !important;
  margin-top: -16px !important;
}
/* The logo is a plain inline <img> (data: URI, see gradio_view.py's
   _load_shell_logo_data_uri) inside the gr.HTML fragment above -- no
   Gradio Image-component wrapper to fight, so this is the only rule the
   mark itself needs. Its own PNG content is already transparent outside
   the mark, so the shell's navy background shows through directly. */
.aara-shell-header img.aara-shell-logo {
  display: inline-block;
  height: 44px;
  width: 44px;
  object-fit: contain;
  vertical-align: middle;
  margin-right: var(--space-md);
}
.aara-shell-header .aara-shell-wordmark-group {
  display: inline-flex;
  flex-direction: column;
  justify-content: center;
  vertical-align: middle;
  line-height: 1.2;
}
.aara-shell-header .aara-shell-wordmark {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--color-surface-white);
}
.aara-shell-header .aara-shell-descriptor {
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--color-gold-accent);
  text-transform: uppercase;
}
.aara-shell-nav {
  background: var(--color-surface-white) !important;
  border-bottom: 1px solid var(--color-border-subtle);
  padding: 0 calc(50vw - 50% + var(--space-lg)) !important;
}
.aara-shell-nav-list {
  display: flex;
  gap: var(--space-lg);
}
.aara-shell-nav-list .nav-item {
  display: inline-block;
  padding: var(--space-sm) 0;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  border-bottom: 2px solid transparent;
}
.aara-shell-nav-list .nav-item.active {
  color: var(--color-navy-primary);
  border-bottom-color: var(--color-gold-accent-boundary);
}
.aara-shell-nav-list .nav-item.muted {
  color: var(--color-text-secondary);
  cursor: default;
}
/* Coming Soon badge: no separate typographic treatment (uppercase/
   letter-spacing/opacity all inherit from .nav-item.muted above) so it
   reads as part of the same muted label, not a competing element. Only
   already-defined tokens are used -- no new custom property. */
.aara-shell-nav-list .nav-item.muted .aara-nav-badge {
  display: inline-block;
  margin-left: var(--space-xs);
  padding: 1px 6px;
  border-radius: var(--radius-badge);
  background: var(--color-border-subtle);
  color: var(--color-text-secondary);
  vertical-align: middle;
}

/* ==========================================================================
   Page header -- eyebrow-styled H1 title + subtitle (P2 #1, Decision
   Center UI audit: promoted from a plain H2 so the page has exactly one
   semantic H1).
   ========================================================================== */
.aara-page-header {
  padding: var(--space-lg) 0 var(--space-sm) 0 !important;
}
.aara-eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin: 0;
}
.aara-page-header h1.aara-eyebrow {
  font-size: 22px;
  color: var(--color-navy-primary);
  letter-spacing: 0.04em;
}
.aara-page-header .aara-page-subtitle {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-top: var(--space-xs);
}

/* Section labels inside the detail column (Evidence / Governance & Policy /
   Approval, etc.) -- compact institutional micro-labels: small, wider
   tracking than the page-level eyebrow, distinct from the larger
   "Decision Intelligence" group label below. margin-top is deliberately 0
   -- Gradio's own default Column gap between stacked blocks is already
   16px (--layout-gap, confirmed against the installed gradio package's
   compiled theme CSS), so an additional top margin here would compound
   into a much larger gap than intended; that single 16px gap is now the
   only source of the ~16px rhythm between detail-panel sections. */
.aara-section-label h2.aara-eyebrow,
.aara-section-label h3.aara-eyebrow {
  font-size: 11px;
  color: var(--color-text-secondary);
  letter-spacing: 0.08em;
  margin: 0 0 var(--space-xs) 0;
}
.aara-section-label--group h2.aara-eyebrow {
  font-size: 13px;
  color: var(--color-navy-primary);
  margin-top: 0;
}

/* Two-column layout; stacks below the tablet breakpoint. list:detail is
   deliberately closer to balanced than a 40:60 split -- the list needs room
   to breathe and the compacted detail content no longer needs the extra
   width the V2 pass left as dead whitespace. */
@media (max-width: 1100px) {
  .aara-layout-row { flex-direction: column !important; }
  .aara-list-column, .aara-detail-column { width: 100% !important; flex: none !important; }
}

/* ==========================================================================
   Decision list toolbar (replaces the full-width default Refresh button).
   ========================================================================== */
.aara-list-column { padding: 0 var(--space-lg) !important; }

.aara-list-toolbar {
  align-items: center !important;
  justify-content: space-between !important;
  padding: 0 0 var(--space-xs) 0 !important;
  gap: var(--space-sm) !important;
}
.aara-list-toolbar-label h2 {
  font-size: 12px !important;
  font-weight: 600 !important;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-secondary) !important;
  margin: 0 !important;
}
.aara-refresh-button {
  flex: none !important;
  min-width: 0 !important;
}
.aara-refresh-button button {
  background: transparent !important;
  border: 1px solid var(--color-border-subtle) !important;
  color: var(--color-text-secondary) !important;
  font-size: 12px !important;
  font-weight: 600 !important;
  box-shadow: none !important;
  padding: 4px var(--space-sm) !important;
}
.aara-refresh-button button:hover {
  border-color: var(--color-gold-accent-boundary) !important;
  color: var(--color-navy-primary) !important;
}

/* ==========================================================================
   Decision list navigator -- the Decisions gr.Dataframe.
   ========================================================================== */

/* Decision ID stays in the underlying row data (row-selection depends on
   it -- see gradio_view.py's _on_row_select) but is not primary user-facing
   information, so its column is hidden visually only. */
.aara-decisions-table table thead th:first-child,
.aara-decisions-table table tbody td:first-child {
  display: none !important;
}

/* The real scrolling element is VirtualTable.svelte's own <table class="table">
   (a stable, non-hashed class -- confirmed by reading Gradio's shipped Svelte
   source, not inferred from compiled output), not the outer .table-wrap
   (Table.svelte's wrapper, which Gradio itself sets to overflow:hidden and
   isn't where scrolling happens at all -- targeting it, as an earlier pass
   of this file did, achieves nothing real). VirtualTable hardcodes
   `overflow-y: scroll` and `overflow-x: scroll` unconditionally in its own
   stylesheet -- an always-visible track regardless of actual overflow, which
   was the permanent decorative scrollbar (both axes). overflow-x is
   suppressed outright (columns always fit); overflow-y is downgraded to
   `auto` so a track appears only when content actually exceeds the height
   budget below -- true at 3 seed rows, still true and still scrollable at
   500 real decisions.

   The height budget itself is Gradio's own height prop -- `height=` on
   gradio 4.44.1, renamed `max_height=` on gradio 5.x (gradio_view.py's
   _DATAFRAME_HEIGHT_KWARG resolves which one to pass) -- which VirtualTable
   already uses to compute a
   content-fit height when rows fit and to cap-and-virtualize when they
   don't (read in refresh_height_map()/get_max() -- confirmed this is a
   genuine virtualized/windowed table, not a plain scrolling div, so it
   stays performant at large row counts by construction, not by any CSS
   here). No CSS max-height is set in this file for exactly that reason --
   one would fight the component's own already-correct sizing instead of
   deferring to it. */
.aara-decisions-table table {
  overflow-x: hidden !important;
  overflow-y: auto !important;
  /* P3 visual-polish fix (Finding 1): VirtualTable.svelte sizes each column
     to its own measured, unwrapped content width (each th/td carries an
     inline `width: var(--cell-width-N)`, computed by Gradio's own JS and
     set on the ancestor `.table-wrap`), then sums those to however wide
     the <table> itself becomes -- confirmed live: 6 visible columns (a 7th,
     Decision ID, is display:none above and so excluded from the browser's
     table layout algorithm entirely) measured ~747px, while this table's
     actual container is ~480-590px at realistic desktop widths (bounded by
     .gradio-container's own max-width: 1280px, confirmed unaffected by
     viewport width beyond that) and narrower still once stacked on mobile.
     overflow-x: hidden above was written on the (once-true, now false --
     see the scrolling-element comment below) assumption that columns
     always fit; instead the two rightmost columns (Last Updated, Verdict)
     were silently clipped off-screen entirely, with no scrollbar to reach
     them -- Verdict was unreachable in every configuration tested.
     table-layout: fixed makes the table's own width (100%, i.e. exactly
     its container's width) and each column's share of it authoritative,
     overriding Gradio's content-measured var()s below instead of merely
     fighting them by specificity. */
  table-layout: fixed !important;
  width: 100% !important;
}
/* Overrides Gradio's own JS-computed --cell-width-N custom properties
   (set inline, non-!important, on this same .table-wrap by
   VirtualTable.svelte) with fixed percentages summing to 100% -- an
   !important custom-property declaration in this stylesheet still wins
   over a plain inline one, and keeps winning across Gradio's own re-renders
   (row selection, Refresh), since the cascade is recomputed each time, not
   snapshotted once. --cell-width-0 (Decision ID, hidden) is included only
   for completeness -- display:none already excludes it from layout.
   Percentages are sized from canvas-measured text widths (actual font/
   weight/letter-spacing this table renders, not guessed) of the widest
   real content per column, live-verified against actual rendered content
   at both the 1440px and 900px (mobile-stacked) widths this fix targets:
   Symbol/Action/Confidence/Verdict each need just enough for their
   genuinely short, header-driven-or-badge-driven content (e.g. Confidence's
   own header text is wider than any "NN%" value it holds; Verdict's widest
   content is the "APPROVED" badge, not its header) to stay on one line;
   Status and Last Updated -- by far the longest strings ("Governance
   Evaluated", full date+time) -- get the two largest shares and wrap onto
   two lines instead, below, rather than trying to fit either on one line. */
.aara-decisions-table .table-wrap {
  --cell-width-0: 0% !important;
  --cell-width-1: 12% !important;
  --cell-width-2: 12% !important;
  --cell-width-3: 19% !important;
  --cell-width-4: 17% !important;
  --cell-width-5: 22% !important;
  --cell-width-6: 18% !important;
}
.aara-decisions-table table thead th {
  padding: 6px 4px !important;
  border: none !important;
  border-bottom: 1px solid var(--color-border-subtle) !important;
  background: transparent !important;
  font-size: 12px !important;
}
/* Sort remains functional (native Dataframe behavior, not removed) -- only
   the always-visible sort-icon clutter is suppressed. */
.aara-decisions-table table thead svg {
  display: none !important;
}
.aara-decisions-table table tbody td {
  padding: 7px 4px !important;
  border: none !important;
  border-bottom: 1px solid var(--color-border-subtle) !important;
  font-size: 12px !important;
}
/* Gradio's own VirtualTable.svelte adds a "no-wrap" class to .table-wrap
   (white-space: nowrap on every cell), which is exactly right for
   Symbol/Action/Confidence/Verdict -- short, fixed-vocabulary content
   (ticker symbols, BUY/SELL/HOLD and APPROVED/REJECTED badges, percentages)
   that should never break mid-word. overflow/text-overflow is a defensive
   fallback (ellipsis, not an overlapping/clipped badge) for the rare case
   content still doesn't fit its fixed share above. Status and Last Updated
   are the opposite case -- genuinely long text ("Governance Evaluated",
   full date+time strings) that the fixed percentages above deliberately
   don't try to fit on one line -- so only these two columns opt back into
   wrapping, onto two lines, instead of either overflowing or truncating
   real information. */
.aara-decisions-table table thead th,
.aara-decisions-table table tbody td {
  overflow: hidden;
  text-overflow: ellipsis;
}
.aara-decisions-table table thead th:nth-child(4),
.aara-decisions-table table tbody td:nth-child(4),
.aara-decisions-table table thead th:nth-child(6),
.aara-decisions-table table tbody td:nth-child(6) {
  white-space: normal !important;
  text-overflow: clip;
}
.aara-decisions-table table tbody tr[slot="tbody"] {
  cursor: pointer;
  transition: background var(--transition-standard);
}
.aara-decisions-table table tbody tr[slot="tbody"]:hover td {
  background: rgba(11, 31, 58, 0.03) !important;
}

/* Selection: Gradio's own hardcoded orange box-shadow on the clicked
   td.focus (see module docstring) -- suppressed and replaced with an
   intentional whole-row navy surface tint + a 3px navy left indicator,
   applied identically for mouse (.focus) and keyboard (:focus-visible) so
   the two input methods look the same (Detail Panel Polish pass:
   recolored from V3's gold treatment to navy, reusing the exact navy RGB
   triple already used for this table's own :hover tint and for
   --shadow-card -- no new color). */
.aara-decisions-table table tbody td.focus,
.aara-decisions-table table tbody td:focus-visible {
  box-shadow: none !important;
  outline: none !important;
}
.aara-decisions-table table tbody tr[slot="tbody"]:has(td.focus) td,
.aara-decisions-table table tbody tr[slot="tbody"]:has(td:focus-visible) td {
  background: rgba(11, 31, 58, 0.08) !important;
}
.aara-decisions-table table tbody tr[slot="tbody"]:has(td.focus) td:first-child,
.aara-decisions-table table tbody tr[slot="tbody"]:has(td:focus-visible) td:first-child {
  box-shadow: inset 3px 0 0 var(--color-navy-primary) !important;
}

/* Action column badge (BUY/SELL/HOLD), rendered as markdown by the
   Dataframe's per-column datatype -- reuses the same restrained tint
   vocabulary as the detail hero's action badge. */
.aara-decisions-table table tbody td .aara-list-action-badge {
  display: inline-block;
  padding: 1px 7px;
  border-radius: var(--radius-badge);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.aara-list-action-badge.action-buy { background: var(--action-buy-bg); color: var(--action-buy-fg); }
.aara-list-action-badge.action-sell { background: var(--action-sell-bg); color: var(--action-sell-fg); }
.aara-list-action-badge.action-hold { background: var(--action-hold-bg); color: var(--action-hold-fg); }

/* Verdict column badge (Approved/Rejected) -- reuses the same
   positive/negative tint vocabulary as the Decision Detail approval card
   (aara-record-card-state), itself built on the buy/sell tokens above, so
   no new color token is introduced for this slice. */
.aara-decisions-table table tbody td .aara-list-verdict-badge {
  display: inline-block;
  padding: 1px 7px;
  border-radius: var(--radius-badge);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.aara-list-verdict-badge.verdict-approved { background: var(--action-buy-bg); color: var(--action-buy-fg); }
.aara-list-verdict-badge.verdict-rejected { background: var(--action-sell-bg); color: var(--action-sell-fg); }

/* Symbol prominence (spec V3 Section 5). */
.aara-decisions-table table tbody td:nth-child(2) {
  font-weight: 600;
  color: var(--color-navy-primary);
}
/* Confidence is a genuine numeric value -- tabular figures. */
.aara-decisions-table table tbody td:nth-child(5) {
  font-family: var(--font-data);
  font-variant-numeric: tabular-nums;
}

/* Flattened read-only fields (Conviction, Last Updated): no border/
   background/resize handle -- reads as label:value text, not a disabled
   form input. Both remaining fields are genuinely numeric/timestamp values,
   so keeping tabular/monospace styling here is correct, not a regression. */
.aara-field-value textarea,
.aara-field-value input {
  background: transparent !important;
  border: none !important;
  resize: none !important;
  color: var(--color-text-primary) !important;
  font-family: var(--font-data) !important;
  font-variant-numeric: tabular-nums;
  padding: var(--space-xs) 0 !important;
  box-shadow: none !important;
}
.aara-field-value .wrap { border: none !important; background: transparent !important; }
/* Gradio wraps every component (not just the grouped .form around both of
   them) in its own ".block" div with a white background + padding by
   default -- the .form fix above strips the shared group's own border, but
   each individual block's white background was still enough, against the
   page's off-white body, to read as two small panels. .aara-field-value is
   only ever applied to these two Textboxes (see gradio_view.py), so this is
   safe to strip unconditionally. */
.aara-field-value {
  background: transparent !important;
  box-shadow: none !important;
  border: none !important;
  padding: 0 !important;
}
.aara-field-value label > span {
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 11px !important;
  color: var(--color-text-secondary) !important;
}

/* Confidence/Last Updated must read as part of the hero/identity block, not
   as their own panel -- Gradio auto-wraps grouped form components (two
   Textbox siblings in a Row) in its own bordered/shadowed ".form" div, which
   .aara-field-value above never addressed (it only strips each input's own
   border). elem_classes=["aara-hero-metrics"] on that Row (gradio_view.py)
   gives this a stable, narrowly-scoped hook instead of stripping every
   ".form" panel in the app.

   Header-to-metrics spacing (~12px): .aara-decision-header's own bottom
   padding (below) contributes 4px, Gradio's default 16px Column gap
   contributes another 16px, so this negative top margin pulls the metrics
   row back up by 8px -- net 4 + 16 - 8 = 12px -- the same negative-margin
   technique .aara-shell-header already uses to cancel unwanted default
   spacing, not a new one. */
.aara-hero-metrics,
.aara-hero-metrics.form,
.aara-hero-metrics > .form {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  border-radius: 0 !important;
  padding: 0 !important;
  margin: -8px 0 0 0 !important;
}
/* Gradio's own ".form" gives grouped Textbox siblings a 1px gap by default
   (a hairline meant for visually-joined form fields) -- too tight for two
   distinct hero metrics read side by side. */
.aara-hero-metrics > .form { gap: var(--space-xl) !important; }

/* Conviction gets stronger visual hierarchy than Last Updated -- the number
   stays the point, no gauge/meter. */
.aara-conviction-value textarea,
.aara-conviction-value input {
  font-size: 26px !important;
  font-weight: 700 !important;
  color: var(--color-navy-primary) !important;
}

/* Decision identity header ("hero") -- the single source of identity; no
   redundant Symbol/Action fields repeat these values below it. Bottom
   padding reduced from --space-md (16px) to --space-xs (4px) as part of
   tightening header-to-metrics spacing -- see .aara-hero-metrics's own
   comment for the full 12px accounting. */
.aara-decision-header {
  padding: var(--space-sm) 0 var(--space-xs) 0;
}
.aara-decision-header .identity-line {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-navy-primary);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  letter-spacing: -0.01em;
}
.aara-decision-header .identity-message {
  font-size: 15px;
  color: var(--color-text-secondary);
  font-style: italic;
}
.aara-decision-header .identity-error {
  font-size: 15px;
  color: var(--color-navy-primary);
  font-weight: 500;
}

/* BUY/SELL/HOLD badge -- subtle tint, never color alone (text always
   present). Compacted slightly (13px -> 12px, 8px -> 7px horizontal
   padding) as part of the Detail Panel Polish pass so it reads as an
   understated institutional label rather than a retail-style pill. */
.aara-action-badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: var(--radius-badge);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.aara-action-badge.action-buy { background: var(--action-buy-bg); color: var(--action-buy-fg); }
.aara-action-badge.action-sell { background: var(--action-sell-bg); color: var(--action-sell-fg); }
.aara-action-badge.action-hold { background: var(--action-hold-bg); color: var(--action-hold-fg); }

/* Four-stage lifecycle track -- stronger visual weight than V2 (thicker
   connectors, larger markers) so it reads as a governed journey rather than
   a generic form wizard, without inventing per-stage data. */
.aara-lifecycle-track {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  padding: var(--space-sm) 0 var(--space-md) 0;
}
.aara-lifecycle-track .stage {
  display: flex;
  align-items: center;
  gap: 6px;
}
.aara-lifecycle-track .dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid var(--lifecycle-future);
  background: var(--color-surface-white);
  transition: background var(--transition-standard), border-color var(--transition-standard);
}
.aara-lifecycle-track .stage.complete .dot {
  background: var(--lifecycle-complete);
  border-color: var(--lifecycle-complete);
}
.aara-lifecycle-track .stage.active .dot {
  background: var(--lifecycle-active);
  border-color: var(--lifecycle-active);
  box-shadow: 0 0 0 3px rgba(200, 164, 93, 0.20);
}
.aara-lifecycle-track .label {
  font-size: 13px;
  color: var(--color-text-secondary);
  text-decoration: none; /* stage labels are #anchor links (Decision Detail Depth pass) */
}
.aara-lifecycle-track .stage.active .label {
  color: var(--color-text-primary);
  font-weight: 700;
}
.aara-lifecycle-track .stage.complete .label {
  color: var(--color-text-secondary);
}
.aara-lifecycle-track .connector {
  width: 32px;
  height: 2px;
  background: var(--lifecycle-future);
}
.aara-lifecycle-track .connector.complete { background: var(--lifecycle-complete); }

/* Evidence / Governance & Policy / Approval -- distinct subtle record-card
   surfaces (Detail Panel Polish pass, superseding V4's hairline-separated
   ledger-row treatment). record_card_html's header/fields markup is
   unchanged (see gradio_view.py) -- only the surface treatment changed:
   each section's cards get their own low-alpha background tint via the
   aara-record-list--{evidence,governance,approval} wrapper class
   _record_list_html now emits, composed only from RGB triples already
   present in :root (no new custom property, no new base color):
   --action-hold-bg's gray for Evidence, gold's RGB for Governance, navy's
   RGB for Approval. Internal padding is ~12px (was 7px 0) now that each
   card is a real, if subtle, surface rather than a borderless row; the
   border-bottom hairline that used to separate rows is replaced by a
   small gap between cards instead. min-width on the header keeps the
   fields column starting at roughly the same horizontal position down
   the list, a ledger/register alignment cue independent of the surface
   change. */
.aara-record-list { display: flex; flex-direction: column; gap: var(--space-xs); }
.aara-record-list--evidence .aara-record-card { background: var(--action-hold-bg); }
.aara-record-list--governance .aara-record-card { background: rgba(200, 164, 93, 0.08); }
.aara-record-list--approval .aara-record-card { background: rgba(11, 31, 58, 0.05); }
.aara-record-list--audit .aara-record-card { background: var(--action-hold-bg); }
.aara-record-card {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  column-gap: var(--space-lg);
  row-gap: 2px;
  padding: 12px;
  border-radius: var(--radius-card);
}
.aara-record-card-header {
  display: flex;
  align-items: baseline;
  gap: var(--space-sm);
  flex: 0 0 auto;
  min-width: 150px;
}
.aara-record-card-type {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}
/* State pill: BUY/SELL/HOLD-style compact background pill (Detail Panel
   Polish pass), not bare colored text -- text label always carries the
   meaning (Attached/Evaluated/Approved/Rejected), color is never the only
   signal, per FORBIDDEN_UI_PATTERNS.md. Backgrounds reuse the exact same
   tokens the action badges already use (--action-buy-bg/--action-sell-bg)
   plus the same neutral gray as Evidence's own card surface above -- no
   new color introduced. */
.aara-record-card-state {
  display: inline-block;
  padding: 1px 6px;
  border-radius: var(--radius-badge);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
/* Neutral: Evidence/Governance's Attached/Evaluated describe that a record
   exists, not a verdict. Positive/negative: an approval's real verdict. */
.aara-record-card-state--neutral {
  background: var(--action-hold-bg);
  color: var(--action-hold-fg);
}
.aara-record-card-state--positive {
  background: var(--action-buy-bg);
  color: var(--color-emerald-secondary);
}
.aara-record-card-state--negative {
  background: var(--action-sell-bg);
  color: var(--color-navy-primary);
}
.aara-record-card-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 4px var(--space-lg);
  flex: 1 1 auto;
}
.aara-record-field { display: flex; align-items: baseline; gap: 4px; }
.aara-record-field .record-label {
  font-size: 10px;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.aara-record-field .record-label::after { content: ":"; }
/* Identifiers/names (evidence source, approver, etc.) stay sans-serif --
   only genuinely tabular/numeric/timestamp values get monospace, per the
   correction to the V2 blanket-monospace regression. */
.aara-record-field .record-value {
  font-size: 13px;
  color: var(--color-text-primary);
}
.aara-record-field .record-value--tabular {
  font-family: var(--font-data);
  font-variant-numeric: tabular-nums;
}
.aara-empty-message {
  font-size: 13px;
  font-style: italic;
  color: var(--color-text-secondary);
  padding: var(--space-sm) 0;
}
/* Why?/Rationale disclosure: an intentional, two-line muted empty state --
   not an empty-list state (contrast .aara-empty-message above, used when a
   section genuinely has no records) and not an error (contrast
   .aara-error-message below, which keeps its red/navy alert treatment).
   The thin neutral rule reads as a deliberate margin note within the
   document, using the same hairline language as the ledger rows above
   rather than any warning color. Title/body are two distinct lines (Detail
   Panel Polish pass) -- gradio_view.py's own docstring covers why this is
   still 100% static, decision-independent copy, not real rationale data. */
.aara-disclosure-message {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-xs) 0 var(--space-xs) var(--space-sm);
  border-left: 2px solid var(--color-border-subtle);
}
.aara-disclosure-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
}
.aara-disclosure-body {
  font-size: 13px;
  font-style: italic;
  color: var(--color-text-secondary);
}
.aara-error-message {
  font-size: 13px;
  color: var(--color-navy-primary);
  background: rgba(11, 31, 58, 0.05);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-card);
  padding: var(--space-sm) var(--space-md);
}

/* Keyboard focus visibility -- buttons and any interactive element get an
   obvious, consistent focus ring.
   P2 #2 fix: the Decision Journey's four stage links
   (.aara-lifecycle-track .label, see gradio_view.py's _lifecycle_track_html)
   are plain <a href="#..."> anchors -- natively focusable without a
   tabindex attribute, so they matched neither `button:focus-visible` nor
   `[tabindex]:focus-visible` above and fell through to no visible focus
   ring at all (or the browser default, inconsistent with every other
   focusable element in this app). These are also the only <a> elements
   anywhere in this application (verified: grep for "<a " across
   applications/trading_intelligence/ finds only these four), so adding a
   generic `a:focus-visible` selector, scoped to .gradio-container like the
   rules above, has no blast radius beyond them -- same declaration reused
   verbatim, no new color or visual style introduced. */
.gradio-container button:focus-visible,
.gradio-container [tabindex]:focus-visible,
.gradio-container a:focus-visible {
  outline: 2px solid var(--color-gold-accent-boundary) !important;
  outline-offset: 2px;
}

/* ==========================================================================
   Loading state (MVP Loading States slice). Gradio's own default pending/
   processing treatment -- not a custom spinner or skeleton system -- is
   kept as the mechanism; only its stock colors/typography are restyled to
   the AARA palette instead of Gradio's default gray/accent-orange. Class
   names (.eta-bar, .generating, .meta-text, .progress-text) are Gradio's
   own, confirmed against the installed gradio==4.44.1 package's compiled
   CSS (site-packages/gradio/templates/frontend/assets/Index-*.css) -- not
   invented here. Gradio scopes its own rules with two chained
   svelte-hash classes (e.g. .generating.svelte-au1olv.svelte-au1olv),
   giving them higher specificity than a plain single-class selector here
   would have without !important -- the same override technique already
   used throughout this file (framework chrome removal, table overflow,
   selection ring), not a new pattern.
   .eta-bar: the translucent sweep that fills a pending component left to
   right; recolored from Gradio's default --background-fill-secondary gray
   to the same low-alpha navy tint already used for the Approval record
   card surface (rgba(11, 31, 58, 0.05), reused verbatim -- no new color).
   .generating: the pulsing border Gradio draws around a component while
   its callback is in flight; recolored from Gradio's default orange
   accent to --color-gold-accent-boundary, the same WCAG-safe gold already
   used for focus rings and the active lifecycle-track dot -- consistent
   with, not a new addition to, this file's boundary-role gold. The pulse
   animation itself is Gradio's own and is left running (not a red/green
   blinking ticker -- FORBIDDEN_UI_PATTERNS.md's actual prohibition -- so
   nothing here conflicts with it).
   .meta-text / .progress-text: the small "processing | X.Xs" badge Gradio
   overlays on a pending component; restyled to the same card surface,
   border, and monospace data font already used elsewhere in this sheet
   (--color-surface-white, --color-border-subtle, --font-data) instead of
   Gradio's plain default text-on-transparent, so it reads as part of this
   theme rather than as leftover framework chrome. */
.eta-bar {
  background: rgba(11, 31, 58, 0.05) !important;
  opacity: 1 !important;
}
.generating {
  border-color: var(--color-gold-accent-boundary) !important;
  background: transparent !important;
}
.meta-text,
.progress-text {
  background: var(--color-surface-white) !important;
  color: var(--color-text-secondary) !important;
  font-family: var(--font-data) !important;
  border: 1px solid var(--color-border-subtle) !important;
  border-radius: var(--radius-badge) !important;
}

/* Screen-reader-only utility (P1 accessibility slice): visually hidden but
   still present in the accessibility tree -- the standard clip+1px
   technique (matches WAI-ARIA Authoring Practices / Bootstrap's own
   .sr-only), not display:none or visibility:hidden, both of which remove
   an element from the accessibility tree entirely and would defeat the
   live-region announcement this class exists for
   (gradio_view.py's live_announcer). No layout impact: absolutely
   positioned and 1px square, so it never affects the flow of surrounding
   visible content. */
.aara-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
"""
