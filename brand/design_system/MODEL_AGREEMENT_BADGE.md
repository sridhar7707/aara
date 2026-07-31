---
component: model_agreement_badge
version: "1.0"
status: frozen
phase: "2A"
---

# Component: Model Agreement Badge

## Overview
Shows model consensus at a glance (`docs/architecture/SENTINEL_COMPONENT_CATALOG.md`, Component 7) -- e.g. 3/3, 2/3, 1/3, 0/3 agreement. Confidence intervals only; per `docs/architecture/IMPLEMENTATION_HANDOFF.md`'s "Evidence > Predictions" principle, never certainty language.

**Naming note (pre-existing, not introduced by this spec):** the catalog's own summary list calls Component 7 "Model Agreement Indicator," but its in-section "Name:" field says `ModelAgreementBadge` -- an inconsistency inside `SENTINEL_COMPONENT_CATALOG.md` itself. The implementation module (`sentinel/frontend/components/model_agreement.py`) uses a third name, `ModelAgreement`. This spec and `COMPONENT_REGISTRY.yaml` use the in-section "Name:" field, `ModelAgreementBadge`, as canonical, with `ModelAgreement` as the registered alias.

## Visual Specs
- **Background:** `var(--color-surface-white)`
- **Font:** Fraction uses `var(--font-data)` with `font-variant-numeric: tabular-nums`; label uses `var(--font-primary)`

## States
- **Strong agreement (3/3):** `var(--metric-positive)`
- **Majority agreement (2/3):** `var(--metric-neutral)`
- **Minority/no agreement (1/3, 0/3):** `var(--metric-negative)`

## Required Metrics
`model_agreement` (`brand/METRIC_CONTRACT.yaml`).

## Accessibility Contract
1. **Keyboard Navigable:** Badge focusable via standard tab navigation.
2. **Focus Ring:** 2px focus ring using `var(--color-navy-primary)`.
3. **Screen Readers:** ARIA label states the fraction and agreement level in words.
4. **Multi-Modal Indicators:** Agreement level conveyed via text label, never color alone.
