# Icon Usage & SVG Specifications

All icons in the Sentinel platform must strictly follow these structural rules:

## Technical Specs
- **ViewBox:** `0 0 24 24`
- **Stroke Width:** `2px` (constant)
- **Stroke Color:** `currentColor` (dynamic inheritance via CSS tokens)
- **Fill:** `none` (line-art icon style only)
- **Stroke Caps & Joins:** `stroke-linecap="round" stroke-linejoin="round"`

## Rules & Constraints
1. **Never use inline fill colors** on state icons inside the SVG XML. Use `currentColor` so state tokens control the color.
2. **Never scale icons non-proportionally.** Standard UI sizes are `16x16px` (dense tables), `20x20px` (inline badges), and `24x24px` (headers/cards).
3. **Always include accessibility attributes** on wrapper components (`aria-hidden="true"` when paired with visual text, or title tags when standalone).

## Icon Inventory (v1.0)
```
decision_review_v1.0.svg        → PENDING/DEFERRED states
governance_check_v1.0.svg       → APPROVED/ESCALATED states
risk_warning_v1.0.svg           → DECLINED state
```

## CSS Integration Example
```css
.icon-decision-review {
  width: 24px;
  height: 24px;
  color: var(--status-pending);  /* Dynamic color from tokens */
}
```

```html
<svg class="icon-decision-review" viewBox="0 0 24 24" aria-hidden="true">
  <!-- SVG path with stroke="currentColor" -->
</svg>
```
