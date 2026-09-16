"""CSS for the Morning Brief screen -- shell MVP.

Design-system migration (Batch A): the colour `:root` entries below now
alias the shared `--aara-*` tokens from `ui/design_system.py` (the single
source of truth -- audit finding D-01). Each keeps its former hex as a
`var(--aara-*, <literal>)` fallback so a standalone `MorningBriefUI().build()`
(no `bootstrap` composition) still renders identically; the composed app
resolves through the shared token. Every `.mb-*` rule below is unchanged.
"""

CSS = """
:root {
  --mb-color-navy: var(--aara-navy, #0B1F3A);
  --mb-color-gold: var(--aara-gold, #C8A45D);
  --mb-color-background: var(--aara-bg, #F8F7F3);
  --mb-color-surface: var(--aara-surface, #FFFFFF);
  --mb-color-text: var(--aara-text, #1A1A1A);
  --mb-color-text-secondary: var(--aara-text-muted, #666666);
  --mb-color-border: var(--aara-border, #E2E8F0);
}

.gradio-container {
  background: var(--mb-color-background) !important;
}

.mb-page-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--mb-color-navy);
  margin: 0;
}
.mb-page-header .mb-subtitle {
  font-size: 14px;
  color: var(--mb-color-text-secondary);
  margin-top: 4px;
}

.mb-section-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--mb-color-text-secondary);
  margin: 16px 0 6px 0;
}

.mb-unavailable-message {
  font-size: 13px;
  font-style: italic;
  color: var(--mb-color-text-secondary);
  padding: 8px 0 8px 12px;
  border-left: 2px solid var(--mb-color-border);
  margin-bottom: 4px;
}

/* A section's real, adapter-sourced summary. Deliberately distinct from
   .mb-unavailable-message: solid primary text (not muted italic) and a
   gold accent border, so a populated section reads as real content. */
.mb-available-summary {
  font-size: 13px;
  color: var(--mb-color-text);
  padding: 8px 0 8px 12px;
  border-left: 2px solid var(--mb-color-gold);
  margin-bottom: 4px;
}

/* Sprint 1: Portfolio Value Trend chart. */
.mb-portfolio-history-chart {
  margin: 4px 0;
}

/* Decision Activity & Risk State Context sprint: wrapper spacing for the
   two new facts near Portfolio Snapshot. Content styling (available vs.
   unavailable) is fully reused from .mb-available-summary / the shared
   integration-health renderer -- these two rules only control the gap
   between the two facts and the Portfolio Value Trend chart below them. */
.mb-decision-activity-output,
.mb-risk-state-output {
  margin-bottom: 4px;
}

/* Sprint 8B (Command Center): KPI card strip, top of page. */
.mb-kpi-row {
  display: block;
}
.mb-kpi-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 4px 0 8px 0;
}
.mb-kpi-card {
  flex: 1 1 140px;
  background: var(--mb-color-surface);
  border: 1px solid var(--mb-color-border);
  border-radius: 6px;
  padding: 10px 14px;
}
.mb-kpi-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--mb-color-text-secondary);
}
.mb-kpi-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--mb-color-navy);
  margin-top: 2px;
}

/* The Portfolio Value Trend chart, promoted to the page's visual
   centerpiece -- extra breathing room around the larger chart. */
.mb-hero-chart {
  margin: 4px 0 8px 0;
}

/* Sprint 8B: Portfolio Drawdown chart, directly under Value Trend. */
.mb-portfolio-drawdown-chart {
  margin: 4px 0 8px 0;
}

/* Sprint 8B: condensed Morning Brief card grid -- the four existing
   frozen-IA sections plus Decision Activity / Current Risk State, wrapped
   in cards inside one row rather than a long vertical stack. Content
   styling within each card is fully reused (.mb-section-label,
   .mb-available-summary, .mb-unavailable-message, the shared integration-
   health renderer) -- these rules only control the card container. */
.mb-brief-grid {
  gap: 10px;
  margin: 4px 0;
}
.mb-brief-card {
  background: var(--mb-color-surface);
  border: 1px solid var(--mb-color-border);
  border-radius: 6px;
  padding: 10px 14px;
}
.mb-brief-card .mb-section-label {
  margin-top: 0;
}

/* Sprint 8B: drill-down navigation cards, bottom of page. */
.mb-drilldown-row {
  gap: 10px;
  margin: 4px 0 12px 0;
}
.mb-drilldown-card {
  background: var(--mb-color-surface);
  border: 1px solid var(--mb-color-border);
  border-radius: 6px;
  padding: 12px 14px;
  transition: border-color 0.15s ease;
}
.mb-drilldown-card:hover {
  border-color: var(--mb-color-gold);
}
.mb-drilldown-card-inner {
  display: block;
}
.mb-drilldown-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--mb-color-navy);
}
.mb-drilldown-desc {
  font-size: 12px;
  color: var(--mb-color-text-secondary);
  margin-top: 4px;
}
"""
