"""CSS for the Performance & Learning screen -- shell MVP.

Self-contained: does not import ui/decision_center/theme.py,
ui/portfolio_intelligence/theme.py, ui/risk_intelligence/theme.py,
ui/morning_brief/theme.py, or ui/settings/theme.py, and does not require
any of them to be present. Reuses the same AARA primitive color values
(navy/gold/warm background) as plain literals here rather than importing
them, per this product's established no-coupling-between-screen-packages
convention.
"""

CSS = """
:root {
  --pl-color-navy: #0B1F3A;
  --pl-color-gold: #C8A45D;
  --pl-color-background: #F8F7F3;
  --pl-color-surface: #FFFFFF;
  --pl-color-text: #1A1A1A;
  --pl-color-text-secondary: #666666;
  --pl-color-border: #E2E8F0;
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
"""
