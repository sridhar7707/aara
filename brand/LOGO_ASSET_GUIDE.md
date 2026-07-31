# Sentinel Intelligence Logo Assets

**Version:** 1.0  
**Status:** FROZEN  
**Date:** 2026-07-30

---

## Official Logo Files

All logo files should be saved in this `/brand/` directory.

### Primary Asset
**File:** `sentinel_mark_v1.0_gold_on_navy.png`
- **Dimensions:** 2548x1402px
- **Format:** PNG with transparency
- **Colors:** Muted Gold (#C8A45D) + Forest Emerald (#176B4D) on Deep Navy (#0B1F3A)
- **Usage:** Primary logo for app header, brand materials
- **Min Display Size:** 200px width

### Monochrome Version
**File:** `sentinel_mark_v1.0_white_on_navy.png`
- **Dimensions:** 2548x1402px
- **Format:** PNG with transparency
- **Colors:** White on Deep Navy background
- **Usage:** When color version is not appropriate
- **Use Cases:** Grayscale printing, accessible contexts

### Favicon Asset
**File:** `sentinel_mark_favicon_v1.0.png`
- **Dimensions:** 32x32px (or 256x256px for scaling)
- **Format:** PNG with transparency
- **Colors:** Full color (gold + emerald)
- **Usage:** Browser tabs, app launcher icons
- **Scaling:** Square 1:1 aspect ratio

### Icon Variants (Future)
Reserved for future use:
- `sentinel_mark_v1.0_outline.svg` (vector outline)
- `sentinel_mark_v1.0_solid_color.png` (single color options)
- `sentinel_mark_v1.0_text_lockup.png` (logo + wordmark)

---

## Logo Design Specifications

**Design Elements (Immutable):**

| Element | Color | Meaning |
|---------|-------|---------|
| Circular Border | Muted Gold (#C8A45D) | Contains, unifies, premium |
| Lotus Flower | Muted Gold (#C8A45D) | Clarity, wisdom, governance |
| Upward Arrow | Muted Gold (#C8A45D) | Growth, intelligence, trajectory |
| Tech Lines | Forest Emerald (#176B4D) | AI intelligence, data flow |
| Background | Deep Navy (#0B1F3A) | Institutional, authoritative |

**Design Rules (Enforced):**
- ✅ Maintain aspect ratio (approx 1.8:1)
- ✅ Preserve all elements and colors
- ✅ Use only on Deep Navy (#0B1F3A) backgrounds
- ✅ Minimum 200px width for clarity
- ❌ No distortion or rotation
- ❌ No color modifications
- ❌ No element removal or simplification
- ❌ No use on warm white backgrounds

---

## Integration Instructions

### For Gradio Frontend

```python
# app.py or main entry point
import gradio as gr
from PIL import Image

# Load logo
logo = Image.open("brand/sentinel_mark_v1.0_gold_on_navy.png")

# Use in interface
with gr.Blocks(theme=gr.themes.Soft()) as app:
    with gr.Row():
        gr.Image(value=logo, scale=1, show_label=False, show_download_button=False)
        gr.Markdown("# Sentinel Intelligence")
    
    # Rest of app...
```

### For Web/HTML

```html
<header class="app-header">
    <img src="/brand/sentinel_mark_v1.0_gold_on_navy.png" 
         alt="Sentinel Intelligence Logo" 
         class="logo"
         width="200" 
         height="112">
    <h1>Sentinel Intelligence</h1>
</header>
```

### For Favicons

```html
<link rel="icon" type="image/png" href="/brand/sentinel_mark_favicon_v1.0.png">
<link rel="apple-touch-icon" href="/brand/sentinel_mark_favicon_v1.0.png">
```

---

## Asset Status

| Asset | Status | Location |
|-------|--------|----------|
| Primary Logo (Gold) | ✅ SAVED | `/brand/sentinel_mark_v1.0_gold_on_navy.png` |
| Monochrome Logo (White) | ⏳ NEEDED | `/brand/sentinel_mark_v1.0_white_on_navy.png` |
| Favicon | ⏳ NEEDED | `/brand/sentinel_mark_favicon_v1.0.png` |
| Usage Guide | ✅ THIS FILE | `/brand/LOGO_ASSET_GUIDE.md` |

---

## Referenced In

- **BRAND_STRATEGY.md** — Official brand identity, usage rules
- **GRADIO_IMPLEMENTATION_GUIDE.md** — Frontend integration
- **SENTINEL_DESIGN_SYSTEM_FINAL.md** — Color tokens alignment

---

## Version History

| Version | Date | Status | Notes |
|---------|------|--------|-------|
| 1.0 | 2026-07-30 | FROZEN | Official logo approved |

**Do not modify or update without architecture review.**
