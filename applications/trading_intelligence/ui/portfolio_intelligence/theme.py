"""CSS for the Portfolio Intelligence screen -- MVP.

Self-contained: does not import ui/decision_center/theme.py and does not
require it to be present. Reuses the same AARA primitive color values
(navy/gold/warm background) as plain literals here rather than importing
them, per this package's "no coupling to decision_center" scope -- if the
two screens are composed together later (see the approved TabbedInterface
analysis), duplicated literal color values are harmless; a Python import
between the two screen packages would not be.
"""

CSS = """
:root {
  --pi-color-navy: #0B1F3A;
  --pi-color-gold: #C8A45D;
  --pi-color-background: #F8F7F3;
  --pi-color-surface: #FFFFFF;
  --pi-color-text: #1A1A1A;
  --pi-color-text-secondary: #666666;
  --pi-color-border: #E2E8F0;
}

.gradio-container {
  background: var(--pi-color-background) !important;
}

.pi-page-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--pi-color-navy);
  margin: 0;
}
.pi-page-header .pi-subtitle {
  font-size: 14px;
  color: var(--pi-color-text-secondary);
  margin-top: 4px;
}

.pi-disclosure {
  border-left: 2px solid var(--pi-color-border);
  padding: 8px 0 8px 12px;
  margin: 8px 0;
}
.pi-disclosure-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--pi-color-text-secondary);
}
.pi-disclosure-body {
  font-size: 13px;
  font-style: italic;
  color: var(--pi-color-text-secondary);
}

.pi-section-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--pi-color-text-secondary);
  margin: 16px 0 6px 0;
}

.pi-capital-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 12px;
  background: var(--pi-color-surface);
  border: 1px solid var(--pi-color-border);
  border-radius: 8px;
}
.pi-metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 120px;
}
.pi-metric-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--pi-color-text-secondary);
}
.pi-metric-value {
  font-size: 18px;
  font-weight: 700;
  font-family: Monaco, "Courier New", monospace;
  color: var(--pi-color-navy);
}

.pi-allocation-bar {
  display: flex;
  height: 10px;
  border-radius: 5px;
  overflow: hidden;
  border: 1px solid var(--pi-color-border);
}
.pi-allocation-bar .invested { background: var(--pi-color-navy); }
.pi-allocation-bar .cash { background: var(--pi-color-gold); }
.pi-allocation-legend {
  display: flex;
  gap: 16px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--pi-color-text-secondary);
}
.pi-allocation-legend .swatch {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  margin-right: 4px;
}
.pi-allocation-legend .invested .swatch { background: var(--pi-color-navy); }
.pi-allocation-legend .cash .swatch { background: var(--pi-color-gold); }

.pi-holdings-table table tbody td:first-child {
  font-weight: 600;
  color: var(--pi-color-navy);
}
.pi-holdings-table table tbody td {
  font-family: Monaco, "Courier New", monospace;
  font-variant-numeric: tabular-nums;
}

.pi-empty-message {
  font-size: 13px;
  font-style: italic;
  color: var(--pi-color-text-secondary);
  padding: 8px 0;
}
"""
