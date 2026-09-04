"""CSS for the Performance & Learning screen -- shell MVP.

Design-system migration (Batch A): the colour `:root` entries below now
alias the shared `--aara-*` tokens from `ui/design_system.py` (the single
source of truth -- audit finding D-01). Each keeps its former hex as a
`var(--aara-*, <literal>)` fallback so a standalone
`PerformanceLearningUI().build()` (no `bootstrap` composition) still renders
identically; the composed app resolves through the shared token. Every
`.pl-*` rule below is unchanged.
"""

CSS = """
:root {
  --pl-color-navy: var(--aara-navy, #0B1F3A);
  --pl-color-gold: var(--aara-gold, #C8A45D);
  --pl-color-background: var(--aara-bg, #F8F7F3);
  --pl-color-surface: var(--aara-surface, #FFFFFF);
  --pl-color-text: var(--aara-text, #1A1A1A);
  --pl-color-text-secondary: var(--aara-text-muted, #666666);
  --pl-color-border: var(--aara-border, #E2E8F0);
}

.gradio-container {
  background: var(--pl-color-background) !important;
}

.pl-page-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--pl-color-navy);
  margin: 0;
}
.pl-page-header .pl-subtitle {
  font-size: 14px;
  color: var(--pl-color-text-secondary);
  margin-top: 4px;
}

.pl-section-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--pl-color-text-secondary);
  margin: 16px 0 6px 0;
}

.pl-unavailable-message {
  font-size: 13px;
  font-style: italic;
  color: var(--pl-color-text-secondary);
  padding: 8px 0 8px 12px;
  border-left: 2px solid var(--pl-color-border);
  margin-bottom: 4px;
}

/* Wave 2B: Outcome History factual count line + table. Mirrors
   ui/risk_intelligence/theme.py's .ri-history-table conventions
   (monospace, tabular-nums); colours come from the shared --aara-*
   tokens via the --pl-* aliases above -- no new literals. */
.pl-summary {
  font-size: 13px;
  color: var(--pl-color-text);
  margin: 2px 0 10px 0;
}
.pl-outcome-table table tbody td {
  font-family: Monaco, "Courier New", monospace;
  font-variant-numeric: tabular-nums;
  font-size: 12px;
}
.pl-outcome-table table thead th {
  font-size: 11px;
  font-weight: 600;
  color: var(--pl-color-text-secondary);
}

/* Wave 3C: Decision Ledger Inspection. Additive; reuses the --pl-color-*
   tokens (which alias --aara-*) -- no new palette literals. Block-level,
   wrapping layout so nothing clips at 900px; native <details> for
   expand/collapse, no JS. */
.pl-dli { display: block; }
.pl-dli-freshness {
  font-size: 11px;
  color: var(--pl-color-text-secondary);
  margin: 2px 0 10px 0;
}
.pl-dli-list { display: flex; flex-direction: column; gap: 10px; }

.pl-dli-candidate {
  border: 1px solid var(--pl-color-border);
  border-radius: 8px;
  background: var(--pl-color-surface);
  padding: 12px 14px;
}
.pl-dli-candidate-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
}
.pl-dli-asset {
  font-size: 14px;
  font-weight: 700;
  color: var(--pl-color-navy);
}
.pl-dli-mono {
  font-family: Monaco, "Courier New", monospace;
  font-size: 11px;
  color: var(--pl-color-text-secondary);
  overflow-wrap: anywhere;
  word-break: break-word;
}
.pl-dli-ts {
  font-family: Monaco, "Courier New", monospace;
  font-size: 11px;
  color: var(--pl-color-text-secondary);
  font-variant-numeric: tabular-nums;
}
.pl-dli-candidate-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--pl-color-text-secondary);
}
.pl-dli-status { font-weight: 600; color: var(--pl-color-text); }
.pl-dli-screening {
  font-size: 11px;
  color: var(--pl-color-text-secondary);
  margin-top: 4px;
}
.pl-dli-flags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 6px;
  margin-top: 8px;
}
.pl-dli-flag {
  font-family: Monaco, "Courier New", monospace;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  border: 1px solid var(--pl-color-border);
  color: var(--pl-color-text-secondary);
  overflow-wrap: anywhere;
}
.pl-dli-flag--true { color: var(--pl-color-navy); border-color: var(--pl-color-navy); }
.pl-dli-terminal {
  margin-top: 8px;
  font-size: 12px;
  font-style: italic;
  color: var(--pl-color-text-secondary);
  padding-left: 10px;
  border-left: 2px solid var(--pl-color-border);
}

.pl-dli-decision {
  margin-top: 8px;
  border: 1px solid var(--pl-color-border);
  border-radius: 6px;
  background: var(--pl-color-background);
}
.pl-dli-decision-summary {
  cursor: pointer;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  font-size: 12px;
}
.pl-dli-decision-summary::-webkit-details-marker { display: none; }
.pl-dli-badge {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 2px 7px;
  border-radius: 3px;
  border: 1px solid var(--pl-color-border);
  color: var(--pl-color-text-secondary);
}
.pl-dli-badge--buy { color: var(--pl-color-navy); border-color: var(--pl-color-navy); }
.pl-dli-badge--sell { color: var(--pl-color-navy); border-color: var(--pl-color-navy); }
.pl-dli-badge--hold { color: var(--pl-color-text-secondary); }
.pl-dli-badge--reject { color: var(--pl-color-text-secondary); }
.pl-dli-badge-sub {
  font-size: 10px;
  color: var(--pl-color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.pl-dli-seq {
  font-family: Monaco, "Courier New", monospace;
  font-size: 10px;
  color: var(--pl-color-text-secondary);
  font-variant-numeric: tabular-nums;
}
.pl-dli-decision-body {
  padding: 4px 12px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.pl-dli-subgroup {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.pl-dli-subgroup:empty { display: none; }
.pl-dli-kv {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: 12px;
}
.pl-dli-k {
  min-width: 150px;
  color: var(--pl-color-text-secondary);
  text-transform: uppercase;
  font-size: 10px;
  letter-spacing: 0.04em;
}
.pl-dli-v {
  color: var(--pl-color-text);
  font-family: Monaco, "Courier New", monospace;
  font-size: 12px;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.pl-dli-muted { color: var(--pl-color-text-secondary); font-style: italic; }
.pl-dli-fact {
  font-size: 12px;
  color: var(--pl-color-text);
  padding: 4px 0 6px 0;
}
.pl-dli-fact--gate {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.pl-dli-boundary {
  margin-top: 16px;
  padding-top: 10px;
  border-top: 2px solid var(--pl-color-gold);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--pl-color-text-secondary);
  text-transform: uppercase;
}

@media (max-width: 960px) {
  .pl-dli-k { min-width: 0; }
  .pl-dli-kv { flex-direction: column; gap: 1px; }
}

/* Wave 3D: funnel summary panel + pure-CSS decision-state filter.
   Additive; reuses the --pl-color-* tokens only -- no new literals. The
   filter is a hidden native radio group; the :checked ~ rules below do
   all show/hide with zero JS. */
.pl-dli-funnel {
  border: 1px solid var(--pl-color-border);
  border-radius: 8px;
  background: var(--pl-color-surface);
  padding: 12px 14px;
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.pl-dli-funnel-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--pl-color-text-secondary);
  margin-bottom: 2px;
}
.pl-dli-funnel-line {
  font-size: 13px;
  color: var(--pl-color-text);
}
.pl-dli-funnel-headline {
  font-weight: 700;
  color: var(--pl-color-navy);
}
.pl-dli-funnel-sub {
  font-family: Monaco, "Courier New", monospace;
  font-size: 11px;
  color: var(--pl-color-text-secondary);
}
.pl-dli-funnel-why {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--pl-color-border);
}
.pl-dli-funnel-why-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--pl-color-text);
}
.pl-dli-funnel-why-line {
  font-size: 11px;
  color: var(--pl-color-text-secondary);
  margin: 2px 0 6px 0;
}
.pl-dli-funnel-gates {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 6px;
}
.pl-dli-funnel-gate {
  font-family: Monaco, "Courier New", monospace;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 3px;
  border: 1px solid var(--pl-color-border);
  color: var(--pl-color-text-secondary);
  overflow-wrap: anywhere;
}
.pl-dli-funnel-gate-n {
  font-weight: 700;
  color: var(--pl-color-navy);
}

.pl-dli-filter-radio {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
.pl-dli-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 6px;
  margin-bottom: 10px;
}
.pl-dli-filter-label {
  cursor: pointer;
  font-size: 11px;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid var(--pl-color-border);
  color: var(--pl-color-text-secondary);
  user-select: none;
}
.pl-dli-filter-label:hover { border-color: var(--pl-color-navy); }
.pl-dli-filter-n {
  font-family: Monaco, "Courier New", monospace;
  font-weight: 700;
}
#pl-dli-filter-all:checked ~ .pl-dli-filter label[for="pl-dli-filter-all"],
#pl-dli-filter-executed:checked ~ .pl-dli-filter label[for="pl-dli-filter-executed"],
#pl-dli-filter-hold:checked ~ .pl-dli-filter label[for="pl-dli-filter-hold"],
#pl-dli-filter-rejected:checked ~ .pl-dli-filter label[for="pl-dli-filter-rejected"],
#pl-dli-filter-no-decision:checked ~ .pl-dli-filter label[for="pl-dli-filter-no-decision"],
#pl-dli-filter-incomplete:checked ~ .pl-dli-filter label[for="pl-dli-filter-incomplete"] {
  background: var(--pl-color-navy);
  border-color: var(--pl-color-navy);
  color: var(--pl-color-surface);
}
#pl-dli-filter-executed:checked ~ .pl-dli-list .pl-dli-candidate:not(.pl-dli-candidate--executed),
#pl-dli-filter-hold:checked ~ .pl-dli-list .pl-dli-candidate:not(.pl-dli-candidate--hold),
#pl-dli-filter-rejected:checked ~ .pl-dli-list .pl-dli-candidate:not(.pl-dli-candidate--rejected),
#pl-dli-filter-no-decision:checked ~ .pl-dli-list .pl-dli-candidate:not(.pl-dli-candidate--no-decision),
#pl-dli-filter-incomplete:checked ~ .pl-dli-list .pl-dli-candidate:not(.pl-dli-candidate--incomplete) {
  display: none;
}
.pl-dli-candidate--executed {
  border-left: 3px solid var(--pl-color-gold);
}
"""
