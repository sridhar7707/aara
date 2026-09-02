"""Shared AARA Trading Intelligence design system.

Single source of truth for the product's visual *vocabulary* -- semantic
design tokens plus a small set of reusable presentation primitives -- so the
six screens stop each re-declaring the same values (audit finding D-01).

Presentation only: a plain CSS string constant (`DESIGN_SYSTEM_CSS`) merged
into the composed app by `bootstrap.build_trading_intelligence_app()` ahead
of every screen's own `theme.py` CSS. No data, no logic, no
sentinel_engine/bot/dashboard/scheduler import.

Token source: the same brand/design_system primitive palette (navy / gold /
warm background / slate text) that `ui/decision_center/theme.py` already
copies from -- this module makes that materialisation happen in ONE place
instead of six. brand/ itself is never imported or modified.

Where "shared" ends and "screen-specific" begins
------------------------------------------------
* SHARED (here): the `--aara-*` tokens and the `.aara-*` primitive classes.
* SCREEN-SPECIFIC (each screen's own theme.py): component rules unique to
  that screen -- Decision Center's lifecycle track / record cards, Risk
  Intelligence's state badge, Portfolio Intelligence's allocation bar, etc.

Design-system migration status:
* Morning Brief, Performance & Learning, Portfolio Intelligence (Batch A),
  Risk Intelligence, Settings (Batch B1): their colour `:root` entries now
  alias these tokens (`var(--aara-*, <literal>)` -- the literal is a
  standalone-render fallback; the composed app resolves through the shared
  token). The `--ri-space-*` / `--st-space-*` spacing guards in
  `test_*_structure.py` are unaffected -- spacing tokens were not migrated.
* Decision Center: NOT migrated yet. It carries test guards keyed to
  literal token text (`test_theme_contrast.py` hex extraction). Its
  migration -- and the matching guard updates -- is Batch B2.
* The `.aara-*` primitive classes below are defined but wired into no
  screen's markup yet. Batch B3 applies them.

Typeface decision (audit finding D-02)
--------------------------------------
The product standardises on a SYSTEM sans stack (`--aara-font-sans`). "Inter"
is kept only as an opportunistic first entry for environments where it is
locally installed; NO `@font-face` and NO external/network font is loaded,
so the *delivered* typeface is the platform UI sans everywhere. This makes
the rendered font honestly match the declared design system without adding a
runtime font dependency. `ui/decision_center/theme.py`'s existing
`.gradio-container * { font-family: var(--font-primary) }` rule is
unchanged; `--font-primary` continues to resolve to this same stack.

Colour safety
-------------
The negative / loss token (`--aara-negative-*`) is a restrained, desaturated
brick -- deliberately NOT a bright-red trading-dashboard colour, per
brand/guidelines/FORBIDDEN_UI_PATTERNS.md. Every status colour still carries
a text label in the markup that uses it; colour is never the only signal.
NORMAL / WARNING / DEFENSIVE semantic meaning is preserved exactly.
"""

# Canonical product values. These are the literals the six screens currently
# duplicate; consolidating them here does not change any rendered colour.
DESIGN_SYSTEM_CSS = """
:root {
  /* ---- Colour: surfaces & text ---- */
  --aara-bg: #F8F7F3;
  --aara-surface: #FFFFFF;
  --aara-border: #E2E8F0;
  --aara-text: #1A1A1A;
  --aara-text-muted: #666666;

  /* ---- Colour: brand ---- */
  --aara-navy: #0B1F3A;
  --aara-gold: #C8A45D;
  --aara-gold-boundary: #A8823D;   /* WCAG-safe gold for thin boundaries */
  --aara-emerald: #176B4D;

  /* ---- Colour: semantic status (text always accompanies these) ---- */
  --aara-status-neutral-bg: rgba(102, 102, 102, 0.10);
  --aara-status-neutral-fg: #5D5D5D;
  --aara-status-warning-bg: rgba(200, 164, 93, 0.20);
  --aara-status-warning-fg: #7C5F2A;
  --aara-status-defensive-bg: #0B1F3A;
  --aara-status-defensive-fg: #FFFFFF;

  /* ---- Colour: negative / loss (restrained, NOT stoplight red) ---- */
  --aara-negative-fg: #7A2E2E;
  --aara-negative-bg: rgba(122, 46, 46, 0.08);

  /* ---- Spacing scale ---- */
  --aara-space-1: 4px;
  --aara-space-2: 8px;
  --aara-space-3: 16px;
  --aara-space-4: 24px;
  --aara-space-5: 32px;

  /* ---- Radius & shadow ---- */
  --aara-radius-card: 8px;
  --aara-radius-badge: 4px;
  --aara-shadow-card: 0 1px 3px rgba(11, 31, 58, 0.06);

  /* ---- Typography ---- */
  --aara-font-sans: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --aara-font-data: Monaco, "Courier New", monospace;
  --aara-type-page-title: 20px;
  --aara-type-section-label: 11px;
  --aara-type-body: 14px;
  --aara-type-value: 18px;
  --aara-type-caption: 12px;

  /* ---- Layout ---- */
  --aara-content-max: 1160px;
}

/* ==========================================================================
   Reusable primitives.

   Defined here as the shared vocabulary; wired into NO screen's markup yet
   (Batch B3 applies them). Adding these class rules changes nothing that
   renders today.
   ========================================================================== */

.aara-card {
  background: var(--aara-surface);
  border: 1px solid var(--aara-border);
  border-radius: var(--aara-radius-card);
  box-shadow: var(--aara-shadow-card);
  padding: var(--aara-space-3);
}

/* Metric: tiny uppercase label above a prominent, right-aligned, tabular
   numeric value. */
.aara-metric { display: flex; flex-direction: column; gap: 2px; }
.aara-metric-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--aara-text-muted);
}
.aara-metric-value {
  font-family: var(--aara-font-data);
  font-variant-numeric: tabular-nums;
  font-size: var(--aara-type-value);
  font-weight: 700;
  color: var(--aara-navy);
  text-align: right;
}

/* Caption: quiet source / freshness / context metadata -- smaller than body
   and visually subordinate to the data it qualifies. */
.aara-caption {
  font-size: var(--aara-type-caption);
  color: var(--aara-text-muted);
  line-height: 1.4;
}

/* Disclosure: explanatory, non-primary information -- present but never
   competing with core data. Matches the muted italic left-rule language the
   screens already use. */
.aara-disclosure {
  border-left: 2px solid var(--aara-border);
  padding: var(--aara-space-1) 0 var(--aara-space-1) var(--aara-space-2);
  margin: var(--aara-space-1) 0;
}
.aara-disclosure-title { font-size: 13px; font-weight: 600; color: var(--aara-text-muted); }
.aara-disclosure-body { font-size: 13px; font-style: italic; color: var(--aara-text-muted); }

/* Status badge: compact pill; the text label in the markup always carries
   the meaning. NORMAL stays calm but is outlined so it still reads as an
   answer rather than disappearing. */
.aara-status-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: var(--aara-radius-badge);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.aara-status-badge--normal {
  background: var(--aara-surface);
  color: var(--aara-text-muted);
  border: 1px solid var(--aara-border);
}
.aara-status-badge--warning {
  background: var(--aara-status-warning-bg);
  color: var(--aara-status-warning-fg);
}
.aara-status-badge--defensive {
  background: var(--aara-status-defensive-bg);
  color: var(--aara-status-defensive-fg);
}
.aara-status-badge--neutral {
  background: var(--aara-status-neutral-bg);
  color: var(--aara-status-neutral-fg);
}

/* Empty / unavailable / not-recorded / not-configured -- one shared muted
   treatment for every "no data on this path" state. */
.aara-empty {
  font-size: 13px;
  font-style: italic;
  color: var(--aara-text-muted);
  padding: var(--aara-space-2) 0;
}

/* Subordinate / reference table (e.g. Portfolio Intelligence's Recent
   Orders) -- lighter and denser than a primary data table. */
.aara-table--secondary table tbody td { font-size: 12px; }

/* Numeric alignment convention (audit finding D-03): right-align numeric and
   timestamp columns, keep the identifier/text column left, retain tabular
   numerals. Applied per-screen (column semantics are screen-specific) -- see
   each screen's own theme.py. This helper is available for markup that can
   opt a single cell in directly. */
.aara-num { text-align: right; font-variant-numeric: tabular-nums; }

/* Centred reading container (audit finding D-09). The composed app already
   has a ~1280px `.gradio-container` cap; this narrower measure is available
   for Batch B3 to wrap long-form content columns. Not applied globally in
   Batch A -- the full-bleed shell header/nav depend on the existing
   container geometry. */
.aara-content {
  max-width: var(--aara-content-max);
  margin-left: auto;
  margin-right: auto;
}
"""
