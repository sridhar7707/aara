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
"""
