---
component: chain_of_custody_timeline
version: "1.0"
status: frozen
phase: "2A"
---

# Component: Chain of Custody Timeline

## Overview
Renders the decision's chain-of-custody lineage as a linear, vertical timeline (`docs/architecture/SENTINEL_COMPONENT_CATALOG.md`, Component 5) -- an 8-9 step journey from a projection view. Immutable, audit-complete; all roles can view.

**Implementation note:** the current implementation module is `sentinel/frontend/components/chain_timeline.py` (component name `ChainTimeline` in its own docstring). This spec and `COMPONENT_REGISTRY.yaml` use the catalog's `ChainOfCustodyTimeline` as canonical, with `ChainTimeline` as an alias -- same pattern as `PortfolioHealthCard`/`HealthScore`.

## Visual Specs
- **Layout:** Linear, vertical (never a graph).
- **Per-step:** Number, name, timestamp, status indicator, summary.
- **Font:** Body `var(--font-primary)`; timestamps/hashes `var(--font-data)` with `font-variant-numeric: tabular-nums`.

## States
- **Completed step:** `var(--status-approved)`
- **Active step:** `var(--status-deferred)`
- **Pending step:** `var(--color-text-secondary)`
- **Verifying:** spinner during hash verification.
- **Verified:** `var(--status-approved)`, "Verified" label.
- **Tampered:** `var(--status-declined)`, "ALERT: Hash mismatch" label.

## Accessibility Contract
1. **Keyboard Navigable:** Each step focusable in sequence via standard tab navigation.
2. **Focus Ring:** 2px focus ring using `var(--color-navy-primary)`.
3. **Screen Readers:** Each step's ARIA label states step name, status, and timestamp.
4. **Multi-Modal Indicators:** Status conveyed via icon + text label, never color alone.
