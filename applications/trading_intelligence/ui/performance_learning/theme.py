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
"""
