"""CSS for the Risk Intelligence screen -- MVP.

Self-contained: does not import ui/decision_center/theme.py or
ui/portfolio_intelligence/theme.py, and does not require either to be
present. Reuses the same AARA primitive color values (navy/gold/warm
background) as plain literals here rather than importing them, per this
package's no-coupling scope. State badges deliberately avoid red/green
"stoplight" colors (brand/guidelines/FORBIDDEN_UI_PATTERNS.md's "no
flashing/blinking price-style indicators" discipline, applied here by the
same reasoning already used for Decision Center's BUY/SELL badges, which
use navy/gold tints rather than green/red) -- NORMAL/WARNING/DEFENSIVE are
distinguished by a neutral, gold, and stronger-navy tint respectively,
each carrying its own text label so color is never the only signal.
"""

CSS = """
:root {
  --ri-color-navy: #0B1F3A;
  --ri-color-gold: #C8A45D;
  --ri-color-background: #F8F7F3;
  --ri-color-surface: #FFFFFF;
  --ri-color-text: #1A1A1A;
  --ri-color-text-secondary: #666666;
  --ri-color-border: #E2E8F0;
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
  margin-top: 4px;
}

.ri-disclosure {
  border-left: 2px solid var(--ri-color-border);
  padding: 8px 0 8px 12px;
  margin: 8px 0;
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
  margin: 16px 0 6px 0;
}

.ri-current-state {
  padding: 12px;
  background: var(--ri-color-surface);
  border: 1px solid var(--ri-color-border);
  border-radius: 8px;
}

.ri-state-badge {
  display: inline-block;
  padding: 3px 10px;
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
  color: #8a6a2f;
}
.ri-state-badge.state-defensive {
  background: var(--ri-color-navy);
  color: var(--ri-color-surface);
}

.ri-trigger-reason {
  margin-top: 10px;
  font-size: 13px;
}
.ri-trigger-reason summary {
  cursor: pointer;
  font-weight: 600;
  color: var(--ri-color-navy);
}
.ri-trigger-reason .ri-trigger-body {
  margin-top: 6px;
  color: var(--ri-color-text-secondary);
  font-style: italic;
}

.ri-sizing-metrics {
  display: flex;
  gap: 24px;
  margin-top: 12px;
}
.ri-metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
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
  padding: 8px 0;
}
"""
