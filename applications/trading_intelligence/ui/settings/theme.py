"""CSS for the Settings screen -- shell MVP.

Self-contained: does not import ui/decision_center/theme.py,
ui/portfolio_intelligence/theme.py, ui/risk_intelligence/theme.py, or
ui/morning_brief/theme.py, and does not require any of them to be present.
Reuses the same AARA primitive color values (navy/gold/warm background) as
plain literals here rather than importing them, per this product's
established no-coupling-between-screen-packages convention.
"""

CSS = """
:root {
  --st-color-navy: #0B1F3A;
  --st-color-gold: #C8A45D;
  --st-color-background: #F8F7F3;
  --st-color-surface: #FFFFFF;
  --st-color-text: #1A1A1A;
  --st-color-text-secondary: #666666;
  --st-color-border: #E2E8F0;
}

.gradio-container {
  background: var(--st-color-background) !important;
}

.st-page-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--st-color-navy);
  margin: 0;
}
.st-page-header .st-subtitle {
  font-size: 14px;
  color: var(--st-color-text-secondary);
  margin-top: 4px;
}

.st-section-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--st-color-text-secondary);
  margin: 16px 0 6px 0;
}

.st-unavailable-message {
  font-size: 13px;
  font-style: italic;
  color: var(--st-color-text-secondary);
  padding: 8px 0 8px 12px;
  border-left: 2px solid var(--st-color-border);
  margin-bottom: 4px;
}
"""
