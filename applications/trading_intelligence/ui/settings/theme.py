"""CSS for the Settings screen -- shell MVP.

Design-system migration (Batch B): the colour `:root` entries below now
alias the shared `--aara-*` tokens from `ui/design_system.py` (the single
source of truth -- audit finding D-01). Each keeps its former hex as a
`var(--aara-*, <literal>)` fallback so a standalone `SettingsUI().build()`
(no `bootstrap` composition) still renders identically; the composed app
resolves through the shared token. The `--st-space-*` spacing tokens and
every `.st-*` rule below are unchanged.
"""

CSS = """
:root {
  --st-color-navy: var(--aara-navy, #0B1F3A);
  --st-color-gold: var(--aara-gold, #C8A45D);
  --st-color-background: var(--aara-bg, #F8F7F3);
  --st-color-surface: var(--aara-surface, #FFFFFF);
  --st-color-text: var(--aara-text, #1A1A1A);
  --st-color-text-secondary: var(--aara-text-muted, #666666);
  --st-color-border: var(--aara-border, #E2E8F0);

  --st-space-4: 4px;
  --st-space-6: 6px;
  --st-space-8: 8px;
  --st-space-12: 12px;
  --st-space-16: 16px;
}

.gradio-container {
  background: var(--st-color-background) !important;
}

/* Mirrors design_system.py's shared .aara-page-title primitive
   (identical values) so a standalone SettingsUI().build() (no
   design_system.py loaded) still renders the same page title as the
   composed app. Normal-case, not uppercase/tracked (visual-quality pass,
   2026-09-17) -- see that primitive's own comment for why. */
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
   keyboard user would otherwise get zero visual indication of which
   radio is focused. V3 made these controls non-interactive (see
   gradio_view.py) -- a disabled input is not focusable, so this rule is
   currently inert; it and its .st-preference-control hook are retained
   so focus parity is already in place if the controls ever become
   interactive again. !important is required, not optional, for the same
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

/* Visual-quality pass (2026-09-17): this control's own wrapper (a
   Gradio "block") carries Gradio's raw default card chrome -- its own
   border-radius and box-shadow, not this app's standard 8px/subtle-
   shadow values every other screen's own cards were just normalized to.
   Live-verified: noticeably heavier default shadow than the rest of the
   app. Border/background/padding are left as Gradio's own defaults
   (already a plain white surface + light border, close enough not to
   risk disturbing the block's internal layout); only elevation is
   corrected to match. */
.st-preference-control {
  border-radius: 8px !important;
  box-shadow: 0 1px 3px rgba(11, 31, 58, 0.06) !important;
}

/* Impeccable critique finding #3: these two preference controls are
   intentionally non-interactive (gradio_view.py sets interactive=False --
   nothing consumes their value, see screen.py's own docstring), but
   rendered with no visual distinction from a live control: Gradio's base
   theme leaves accent-color: auto (native browser blue) on the radio dot
   and opacity: 1 on the disabled label -- live-verified via a rendered
   DOM inspection (getComputedStyle), the same way the focus-visible rule
   above was verified. cursor: not-allowed already applies natively on a
   disabled input/label (also confirmed live) -- no rule needed for that
   part. `.disabled` and `.selected` are Gradio's own real, stable classes
   on the rendered <label> (confirmed via that same inspection), not the
   hashed svelte-* build class, which is why this targets them instead of
   inventing a new hook. Scoped to this screen's own .st-preference-control
   -- no other screen renders a gr.Radio with interactive=False today, so
   this cannot leak onto or collide with anything else. Text is never the
   ONLY signal removed here: the "not currently configurable" disclosure
   above each control already states the condition in words (see
   .st-session-only-notice above); this is the visual reinforcement,
   reusing this file's own --st-color-* aliases (which themselves resolve
   through --aara-navy / --aara-text-muted) rather than a new color.

   Corrected 2026-09-18: the original 0.55 opacity, stacked on top of the
   label's own --st-color-text-secondary (already --aara-text-muted,
   #666666), computed to ~2.2:1 contrast against the white card -- WCAG AA
   requires 4.5:1 for text; "Dark"/"Off" were reported as genuinely
   unreadable, not just de-emphasized. 0.85 keeps the same "clearly not
   the active option" signal (still visibly dimmer than the ~13:1-contrast
   enabled label) while landing at ~3.9:1 -- legible, and still above the
   3:1 floor WCAG itself uses for large-scale/non-text UI distinctions,
   even though disabled controls are technically exempt from the 4.5:1 text
   minimum. */
.st-preference-control input[type="radio"] {
  accent-color: var(--st-color-navy);
}
.st-preference-control label.disabled {
  opacity: 0.85;
}
.st-preference-control label.disabled .ml-2 {
  color: var(--st-color-text-secondary);
}
"""
