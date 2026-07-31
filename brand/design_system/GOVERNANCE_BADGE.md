---
component: governance_badge
version: "1.0"
status: frozen
phase: "2A"
---

# Component: Governance Badge

## Overview
Displays governance evaluation status (`docs/architecture/SENTINEL_COMPONENT_CATALOG.md`, Component 1). Sourced from `decision.governance.status`; renders only, no evaluation logic.

## Visual Specs
- **Background:** `var(--color-surface-white)`
- **Border:** `1px solid var(--color-border-subtle)`
- **Font:** Label uses `var(--font-primary)`

## States
- **PASS:** `var(--status-approved)`
- **ESCALATED:** `var(--status-escalated)`
- **BREACH:** `var(--status-declined)`

## Accessibility Contract
1. **Keyboard Navigable:** Badge focusable using standard tab navigation (`tabindex="0"`).
2. **Focus Ring:** 2px focus ring using `var(--color-navy-primary)`.
3. **Screen Readers:** ARIA label states the status in words, never color alone.
4. **Multi-Modal Indicators:** Shape/icon + text conveys meaning, not color alone (per catalog).
