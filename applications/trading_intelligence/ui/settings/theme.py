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

  --st-space-4: 4px;
  --st-space-6: 6px;
  --st-space-8: 8px;
  --st-space-12: 12px;
  --st-space-16: 16px;
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
  margin-top: var(--st-space-4);
}

.st-section-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--st-color-text-secondary);
  margin: var(--st-space-16) 0 var(--st-space-6) 0;
}

.st-unavailable-message {
  font-size: 13px;
  font-style: italic;
  color: var(--st-color-text-secondary);
  padding: var(--st-space-8) 0 var(--st-space-8) var(--st-space-12);
  border-left: 2px solid var(--st-color-border);
  margin-bottom: var(--st-space-4);
}

.st-session-only-notice {
  font-size: 12px;
  font-style: italic;
  color: var(--st-color-text-secondary);
  padding: 0 0 var(--st-space-6) var(--st-space-12);
  margin-bottom: var(--st-space-4);
}

/* Accessibility parity pass: visible keyboard focus for the Display
   Theme / Show In-App Notifications radio controls -- live-verified
   (getComputedStyle on a real Tab-focused radio): Gradio's own base
   theme renders these with outline: none and a focus box-shadow whose
   color resolves to fully transparent (rgba(0, 0, 0, 0)), so a
   keyboard user currently gets zero visual indication of which radio
   is focused. !important is required, not optional, for the same
   reason ui/risk_intelligence/theme.py's own Accessibility parity pass
   needed it: this is overriding Gradio's own already-!important-or-
   equivalent-specificity base styling, not merely adding a new rule
   into empty space. Scoped to this screen's own new
   .st-preference-control hook (see gradio_view.py) rather than a bare
   `input[type="radio"]` selector -- no other screen in this composed
   app renders a radio input today, so this cannot leak onto or collide
   with anything else, but scoping to a local, purpose-built class
   keeps that true even if one is added later. --st-color-navy already
   passes the WCAG 3:1 UI-component-boundary floor against the white/
   warm surfaces this control sits on, so no new color token is
   needed. */
.st-preference-control input[type="radio"]:focus-visible {
  outline: 2px solid var(--st-color-navy) !important;
  outline-offset: 2px;
}
"""
