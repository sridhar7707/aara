---
component: evidence_card
version: "1.0"
status: frozen
phase: "2A"
---

# Component: Evidence Card

## Overview
Displays a single evidence artifact with provenance (`docs/architecture/SENTINEL_COMPONENT_CATALOG.md`, Component 4) -- provider, version, data-as-of/recorded-at timestamps, confidence. Role-based payload filtering happens in the service layer, never in this component.

## Visual Specs
- **Background:** `var(--color-surface-white)`
- **Border:** `1px solid var(--color-border-subtle)`
- **Elevation:** `var(--shadow-card)`
- **Font:** Body uses `var(--font-primary)`; confidence/timestamps use `var(--font-data)` with `font-variant-numeric: tabular-nums`

## States
- **Collapsed:** Provider, version, confidence.
- **Expanded:** Full provenance + payload.
- **Inspecting:** Modal view with payload detail.

## Required Fields
Per catalog data source: `evidence_id`, `type`, `provider`, `provider_version`, `data_as_of`, `recorded_at`, `confidence`, `confidence_interval`.

## Accessibility Contract
1. **Keyboard Navigable:** Card focusable using standard tab navigation (`tabindex="0"`).
2. **Focus Ring:** 2px focus ring using `var(--color-navy-primary)`.
3. **Screen Readers:** ARIA label states provider + confidence in words.
4. **Multi-Modal Indicators:** Evidence type conveyed via icon + text label, never color alone.
