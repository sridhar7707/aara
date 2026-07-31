---
component: portfolio_health_card
version: "1.0"
status: frozen
phase: "2A"
---

# Component: Portfolio Health Card

## Overview
Displays a pre-calculated composite portfolio health score (0-100) with a metric breakdown (`docs/architecture/SENTINEL_COMPONENT_CATALOG.md`, Component 8). Renders only -- no calculation happens in the Gradio layer; the score arrives already computed from a projection view.

**Implementation note:** the current implementation module is `sentinel/frontend/components/health_score.py` (component name `HealthScore` in its own docstring). This spec and `brand/design_system/COMPONENT_REGISTRY.yaml` treat `PortfolioHealthCard` as the canonical name, with `HealthScore` as an alias to be retired once the implementation is renamed to match -- see the registry's `migration_note`.

## Visual Specs
- **Background:** `var(--color-surface-white)`
- **Border:** `1px solid var(--color-border-subtle)`
- **Elevation:** `var(--shadow-card)`
- **Font:** Body uses `var(--font-primary)`; the score itself uses `var(--font-data)` with `font-variant-numeric: tabular-nums`

## Score Bands
The catalog describes three score tiers (70+ / 50-69 / <50). This spec maps them onto the token system's existing 3-tier metric semantics rather than introducing new, undefined tokens:

| Range | Token | Meaning |
|---|---|---|
| 70-100 | `var(--metric-positive)` | Healthy |
| 50-69 | `var(--metric-neutral)` | Watch |
| 0-49 | `var(--metric-negative)` | At risk |

## Required Metrics
Per `brand/design_system/COMPONENT_REGISTRY.yaml`: `decision_quality_score`, `model_agreement` (both defined in `brand/METRIC_CONTRACT.yaml`).

## Accessibility Contract
1. **Keyboard Navigable:** Card focusable using standard tab navigation (`tabindex="0"`).
2. **Focus Ring:** 2px focus ring using `var(--color-navy-primary)`.
3. **Screen Readers:** ARIA label states the score in words (e.g. `aria-label="Portfolio health: 87 out of 100, Healthy"`), never color alone.
4. **Multi-Modal Indicators:** Color is NEVER the sole indicator of a score band; each band pairs color with a text label.
