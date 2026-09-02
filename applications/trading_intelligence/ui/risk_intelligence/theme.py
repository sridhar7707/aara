"""CSS for the Risk Intelligence screen -- MVP.

Design-system migration (Batch B): the colour `:root` entries below now
alias the shared `--aara-*` tokens from `ui/design_system.py` (the single
source of truth -- audit finding D-01). Each keeps its former hex as a
`var(--aara-*, <literal>)` fallback so a standalone
`RiskIntelligenceUI().build()` (no `bootstrap` composition) still renders
identically; the composed app resolves through the shared token. The
`--ri-space-*` spacing tokens and every `.ri-*` rule below are unchanged.

State badges deliberately avoid red/green "stoplight" colors
(brand/guidelines/FORBIDDEN_UI_PATTERNS.md's "no flashing/blinking
price-style indicators" discipline, applied here by the same reasoning
already used for Decision Center's BUY/SELL badges, which use navy/gold
tints rather than green/red) -- NORMAL/WARNING/DEFENSIVE are distinguished
by a neutral, gold, and stronger-navy tint respectively, each carrying its
own text label so color is never the only signal.
"""

CSS = """
:root {
  --ri-color-navy: var(--aara-navy, #0B1F3A);
  --ri-color-gold: var(--aara-gold, #C8A45D);
  --ri-color-background: var(--aara-bg, #F8F7F3);
  --ri-color-surface: var(--aara-surface, #FFFFFF);
  --ri-color-text: var(--aara-text, #1A1A1A);
  --ri-color-text-secondary: var(--aara-text-muted, #666666);
  --ri-color-border: var(--aara-border, #E2E8F0);

  --ri-space-2: 2px;
  --ri-space-3: 3px;
  --ri-space-4: 4px;
  --ri-space-6: 6px;
  --ri-space-8: 8px;
  --ri-space-10: 10px;
  --ri-space-12: 12px;
  --ri-space-16: 16px;
  --ri-space-24: 24px;
}

.gradio-container {
  background: var(--ri-color-background) !important;
}

.ri-page-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--ri-color-navy);
  margin: 0;
}
.ri-page-header .ri-subtitle {
  font-size: 14px;
  color: var(--ri-color-text-secondary);
  margin-top: var(--ri-space-4);
}

.ri-disclosure {
  border-left: 2px solid var(--ri-color-border);
  padding: var(--ri-space-8) 0 var(--ri-space-8) var(--ri-space-12);
  margin: var(--ri-space-8) 0;
}
.ri-disclosure-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ri-color-text-secondary);
}
.ri-disclosure-body {
  font-size: 13px;
  font-style: italic;
  color: var(--ri-color-text-secondary);
}

.ri-section-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ri-color-text-secondary);
  margin: var(--ri-space-16) 0 var(--ri-space-6) 0;
}

.ri-current-state {
  padding: var(--ri-space-12);
  background: var(--ri-color-surface);
  border: 1px solid var(--ri-color-border);
  border-radius: 8px;
}

.ri-state-badge {
  display: inline-block;
  padding: var(--ri-space-3) var(--ri-space-10);
  border-radius: 4px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.ri-state-badge.state-normal {
  background: rgba(102, 102, 102, 0.10);
  color: var(--ri-color-text-secondary);
}
.ri-state-badge.state-warning {
  background: rgba(200, 164, 93, 0.20);
  /* WCAG contrast fix: #8a6a2f measured ~4.30:1 against this badge's actual
     rendered (blended) background, below the 4.5:1 AA text floor. Same hue,
     darkened, verified 5.11:1 against the blended background. */
  color: #7c5f2a;
}
.ri-state-badge.state-defensive {
  background: var(--ri-color-navy);
  color: var(--ri-color-surface);
}

.ri-trigger-reason {
  margin-top: var(--ri-space-10);
  font-size: 13px;
}
.ri-trigger-reason summary {
  cursor: pointer;
  font-weight: 600;
  color: var(--ri-color-navy);
}
.ri-trigger-reason .ri-trigger-body {
  margin-top: var(--ri-space-6);
  color: var(--ri-color-text-secondary);
  font-style: italic;
}

.ri-sizing-metrics {
  display: flex;
  gap: var(--ri-space-24);
  margin-top: var(--ri-space-12);
}
.ri-metric {
  display: flex;
  flex-direction: column;
  gap: var(--ri-space-2);
}
.ri-metric-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ri-color-text-secondary);
}
.ri-metric-value {
  font-size: 18px;
  font-weight: 700;
  font-family: Monaco, "Courier New", monospace;
  color: var(--ri-color-navy);
}
.ri-metric-value.ri-gap-nonzero {
  color: #8a6a2f;
}

.ri-history-table table tbody td:nth-child(2) {
  font-weight: 600;
}
.ri-history-table table tbody td {
  font-family: Monaco, "Courier New", monospace;
  font-variant-numeric: tabular-nums;
}

.ri-empty-message {
  font-size: 13px;
  font-style: italic;
  color: var(--ri-color-text-secondary);
  padding: var(--ri-space-8) 0;
}

.ri-history-detail-list {
  margin-top: var(--ri-space-8);
  display: flex;
  flex-direction: column;
  gap: var(--ri-space-8);
}
.ri-history-detail-card {
  padding: var(--ri-space-10) var(--ri-space-12);
  background: var(--ri-color-surface);
  border: 1px solid var(--ri-color-border);
  border-radius: 8px;
  font-size: 13px;
}
.ri-history-detail-card summary {
  cursor: pointer;
  list-style: none;
}
.ri-history-detail-card summary::-webkit-details-marker {
  display: none;
}
.ri-history-detail-timestamp {
  margin-left: var(--ri-space-8);
  color: var(--ri-color-text-secondary);
  font-size: 12px;
}
.ri-record-card-fields {
  margin-top: var(--ri-space-8);
  display: flex;
  flex-direction: column;
  gap: var(--ri-space-6);
}
.ri-record-field {
  display: flex;
  justify-content: space-between;
  gap: var(--ri-space-12);
}
.ri-record-field .record-label {
  color: var(--ri-color-text-secondary);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}
.ri-record-field .record-value {
  color: var(--ri-color-text);
  text-align: right;
  white-space: normal;
  word-break: break-word;
}
.ri-record-field .record-value.ri-gap-nonzero {
  color: #8a6a2f;
}

/* Accessibility parity pass: visible keyboard focus for this page's native
   <details>/<summary> disclosures (trigger reason, evaluation-history
   cards) -- previously unstyled, falling back to each browser's own
   default (or absent) focus indicator. Scoped to these two existing,
   RI-local selectors rather than a page-wide `.gradio-container
   summary:focus-visible` rule (the pattern ui/decision_center/theme.py
   uses), so this rule can never affect any <summary> outside this
   screen. --ri-color-navy already passes the WCAG 3:1 UI-component-
   boundary floor against every surface it's used against on this page
   (see .ri-trigger-reason summary and .ri-metric-value's own use of
   it), so no new color token is needed.

   !important is required, not optional: bootstrap.py concatenates
   every screen's CSS into one composed stylesheet, and Decision
   Center's own `.gradio-container summary:focus-visible` rule already
   ships with `!important` (theme.py's own P1 accessibility slice) --
   a page-wide selector matching every <summary> in the composed
   document, including this screen's. `!important` always wins over a
   non-`!important` declaration regardless of selector specificity or
   source order, so without it here this rule is silently inert in the
   real composed app (live-verified: a Tab-focused RI summary rendered
   Decision Center's gold-boundary outline, not this navy one, until
   this was added) -- scoping alone only prevents this rule from ever
   leaking onto Decision Center's own elements; it does not protect
   this rule from being overridden itself. */
.ri-trigger-reason summary:focus-visible,
.ri-history-detail-card summary:focus-visible {
  outline: 2px solid var(--ri-color-navy) !important;
  outline-offset: 2px;
}

/* Screen-reader-only utility: local copy of the same visually-hidden-but-
   present technique ui/decision_center/theme.py's own .aara-sr-only
   already uses (WAI-ARIA Authoring Practices / Bootstrap's .sr-only) --
   not imported, per this package's no-coupling scope. Backs the
   live-region announcer element in gradio_view.py. */
.ri-sr-only {
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
