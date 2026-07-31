# Sentinel Intelligence Design Tokens

**Version:** 1.0  
**Status:** FROZEN  
**Date:** 2026-07-30  
**Purpose:** Reusable design values for consistent UI implementation

---

## Spacing Scale

```
0   = 0px      (no space)
1   = 4px      (base unit, tight)
2   = 8px      (xs)
3   = 12px     (sm)
4   = 16px     (md, default)
5   = 20px     (lg)
6   = 24px     (xl)
8   = 32px     (2xl)
12  = 48px     (3xl)
16  = 64px     (4xl)
20  = 80px     (5xl)
24  = 96px     (6xl)
```

**CSS Variables:**
```css
:root {
  --space-0:  0px;
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-12: 48px;
  --space-16: 64px;
  --space-20: 80px;
  --space-24: 96px;
}
```

**Usage:**
- Padding: `--space-4` (16px default)
- Margin: `--space-4` (16px default)
- Gaps: `--space-3` (12px)
- Section spacing: `--space-8` or `--space-12` (32-48px)

---

## Typography Scale

**Font Families:**
```
Headings:    Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
Body Text:   Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
Monospace:   "Monaco", "Courier New", monospace (for data/code)
```

**Font Sizes:**
```
xs  = 12px   (labels, captions)
sm  = 14px   (secondary text)
md  = 16px   (body, default)
lg  = 18px   (larger body)
xl  = 20px   (subheadings)
2xl = 24px   (section headings)
3xl = 30px   (page headings)
4xl = 36px   (hero/title)
```

**Font Weights:**
```
Regular   = 400  (body text)
Medium    = 500  (labels, toggles)
Semibold  = 600  (subheadings)
Bold      = 700  (headings, emphasis)
```

**Line Heights:**
```
Tight   = 1.2  (headings)
Normal  = 1.5  (body text)
Relaxed = 1.75 (large blocks)
```

**CSS Variables:**
```css
:root {
  --font-family-base: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-family-mono: "Monaco", "Courier New", monospace;
  
  --font-size-xs:  12px;
  --font-size-sm:  14px;
  --font-size-md:  16px;
  --font-size-lg:  18px;
  --font-size-xl:  20px;
  --font-size-2xl: 24px;
  --font-size-3xl: 30px;
  --font-size-4xl: 36px;
  
  --font-weight-regular:   400;
  --font-weight-medium:    500;
  --font-weight-semibold:  600;
  --font-weight-bold:      700;
  
  --line-height-tight:   1.2;
  --line-height-normal:  1.5;
  --line-height-relaxed: 1.75;
}
```

---

## Border & Shadow

**Border Radius:**
```
none = 0px      (no rounding)
sm   = 4px      (slight rounding)
md   = 8px      (standard rounding)
lg   = 12px     (prominent rounding)
full = 9999px   (pill/circle)
```

**Border Width:**
```
none = 0px
thin = 1px   (subtle)
base = 2px   (standard)
thick = 3px  (emphasis)
```

**Shadows:**
```
none  = no shadow
sm    = 0 1px 2px rgba(0,0,0,0.05)
md    = 0 4px 6px rgba(0,0,0,0.1)
lg    = 0 10px 15px rgba(0,0,0,0.15)
xl    = 0 20px 25px rgba(0,0,0,0.2)
```

---

## Component Sizing

**Touch Targets (Accessibility):**
```
Minimum touch target = 44px x 44px (mobile)
Preferred          = 48px x 48px (optimal)
Compact            = 40px x 40px (desktop, acceptable)
```

**Button Sizes:**
```
Small      = 32px height (compact interfaces)
Medium     = 40px height (default)
Large      = 48px height (primary CTAs)
Extra Large = 56px height (hero buttons)
```

**Input Field Heights:**
```
Small  = 32px (compact forms)
Medium = 40px (standard)
Large  = 48px (mobile-friendly)
```

**Card Widths:**
```
Narrow  = 300px (mobile cards)
Medium  = 400px (standard cards)
Wide    = 600px (detailed cards)
Full    = 100% (full-width)
```

---

## Responsive Breakpoints

```
Mobile      = 320px - 767px   (xs, sm, md)
Tablet      = 768px - 1023px  (lg)
Desktop     = 1024px+         (xl, 2xl)
```

**CSS Media Queries:**
```css
/* Mobile First */
@media (min-width: 768px) {  /* Tablet */
  /* tablet styles */
}

@media (min-width: 1024px) { /* Desktop */
  /* desktop styles */
}

@media (max-width: 767px) {  /* Mobile only */
  /* mobile-specific */
}
```

---

## Z-Index Scale

```
0   = Default (content)
10  = Dropdowns, tooltips
20  = Modals, overlays
30  = Notifications, alerts
40  = Tooltips on modals
50  = Toast messages
100 = System alerts
```

**Usage:**
```css
.dropdown { z-index: 10; }
.modal { z-index: 20; }
.notification { z-index: 30; }
.toast { z-index: 50; }
```

---

## Animation & Transitions

**Durations:**
```
Fast    = 150ms (subtle interactions)
Normal  = 300ms (standard transitions)
Slow    = 500ms (important transitions)
```

**Easing Functions:**
```
ease-in-out = cubic-bezier(0.4, 0, 0.2, 1)  (smooth)
ease-out    = cubic-bezier(0, 0, 0.2, 1)    (snappy)
ease-in     = cubic-bezier(0.4, 0, 1, 1)    (acceleration)
linear      = linear                         (steady)
```

**CSS Variables:**
```css
:root {
  --transition-fast:   150ms ease-in-out;
  --transition-normal: 300ms ease-in-out;
  --transition-slow:   500ms ease-in-out;
}
```

---

## Color Tokens (Reference)

See `SENTINEL_COLOR_PALETTE.json` for complete color specifications.

**Quick Reference:**
```css
:root {
  --color-navy-primary:      #0B1F3A;
  --color-emerald-secondary: #176B4D;
  --color-gold-accent:       #C8A45D;
  --color-background-warm:   #F8F7F3;
  --color-text-primary:      #1A1A1A;
  --color-text-secondary:    #666666;
}
```

---

## Implementation Rules

**✅ DO:**
- Use CSS variables for all design tokens
- Define tokens at `:root` level
- Use consistent naming convention
- Scale up/down from base units
- Test touch targets at 44px minimum

**❌ DO NOT:**
- Hardcode pixel values
- Use arbitrary spacing
- Mix token scales (use consistent scale)
- Reduce touch targets below 40px
- Use breakpoints other than defined ones

---

## Gradio Implementation

```python
import gradio as gr

# Apply tokens via CSS
custom_css = """
:root {
  --color-navy-primary: #0B1F3A;
  --color-emerald-secondary: #176B4D;
  --color-gold-accent: #C8A45D;
  --color-background-warm: #F8F7F3;
  --space-4: 16px;
  --font-size-md: 16px;
}

body {
  background-color: var(--color-background-warm);
  color: var(--color-text-primary);
  font-size: var(--font-size-md);
}

button {
  padding: var(--space-3) var(--space-4);
  border-radius: 8px;
}
"""

with gr.Blocks(css=custom_css) as app:
    gr.Markdown("# Sentinel Intelligence")
    # Use variables throughout
```

---

## Status

✅ FROZEN — All design tokens locked  
⏳ READY FOR IMPLEMENTATION  
📝 Version 1.0 (2026-07-30)

**Do not modify without architecture review.**
