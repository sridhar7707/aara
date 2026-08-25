"""CSS for the Morning Brief screen -- shell MVP.

Self-contained: does not import ui/decision_center/theme.py,
ui/portfolio_intelligence/theme.py, or ui/risk_intelligence/theme.py, and
does not require any of them to be present. Reuses the same AARA primitive
color values (navy/gold/warm background) as plain literals here rather
than importing them, per this product's established no-coupling-between-
screen-packages convention.
"""

CSS = """
:root {
  --mb-color-navy: #0B1F3A;
  --mb-color-gold: #C8A45D;
  --mb-color-background: #F8F7F3;
  --mb-color-surface: #FFFFFF;
  --mb-color-text: #1A1A1A;
  --mb-color-text-secondary: #666666;
  --mb-color-border: #E2E8F0;
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
"""
