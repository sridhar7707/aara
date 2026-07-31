---
component: risk_governor_badge
version: "1.0"
status: frozen
phase: "2A"
---

# Component: Risk Governor Badge

## Overview
Displays the portfolio's current Risk Governor state (`docs/architecture/SENTINEL_COMPONENT_CATALOG.md`, Component 2). Sourced from `governance_state`; never computes risk state itself. 3-state model only (`NORMAL`/`WARNING`/`DEFENSIVE`) per the frozen enum in `sentinel/backend/domain/enums.py` -- do not add a fourth, `CRITICAL` visual state here.

## Visual Specs
- **Background:** `var(--color-surface-white)`
- **Border:** `1px solid var(--color-border-subtle)`
- **Font:** Label uses `var(--font-primary)`

## Lifecycle States & Mappings
Per `brand/STATE_MAPPING.yaml`'s `risk_governor` section (the source of truth -- do not restate these bindings elsewhere):

### 1. Normal
- **Condition:** Calm, operational.
- **Visuals:** `var(--status-approved)`, label "Normal Operation".

### 2. Warning
- **Condition:** Elevated attentiveness; investor must explicitly confirm approvals.
- **Visuals:** `var(--status-deferred)`, label "Warning Threshold".

### 3. Defensive
- **Condition:** Protective; CRO approval required for new decisions.
- **Visuals:** `var(--status-declined)`, label "Defensive Intervention".

**Canvas effect:** per the catalog, a Risk Governor state change is not badge-local -- the entire workspace background/border reflects the current state, not just this badge.

## Accessibility Contract
1. **Keyboard Navigable:** Badge focusable using standard tab navigation (`tabindex="0"`).
2. **Focus Ring:** 2px focus ring using `var(--color-navy-primary)`.
3. **Screen Readers:** ARIA label states the governance state in words (e.g. `aria-label="Risk Governor: Defensive Intervention"`), never color alone.
4. **Multi-Modal Indicators:** Color is NEVER the sole indicator. Every state pairs color with a text label.
