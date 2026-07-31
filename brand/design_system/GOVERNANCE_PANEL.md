---
component: governance_panel
version: "1.0"
status: frozen
phase: "2A"
---

# Component: Governance Panel

## Overview
A richer, composite governance view -- policy checks, rule evaluations, current Risk Governor state, approval history, and audit references in one panel. Distinct from `GovernanceBadge` (`brand/design_system/GOVERNANCE_BADGE.md`), which is a compact status indicator meant to embed in cards, tables, and lists. `GovernancePanel` is the expanded, standalone view; `GovernanceBadge` is the summary.

**Provenance:** this component existed only as a `COMPONENT_REGISTRY.yaml` entry with no implementation, specification, or catalog listing until the 2026-07-31 reconciliation (`BRAND_CHANGELOG.md` v1.0.3). Its original registry metadata (states, owner, required fields) matched `RiskGovernorBadge`'s almost exactly, which raised the question of whether it was a naming mistake for `GovernanceBadge` (different states entirely: `PASS/ESCALATED/BREACH`) rather than a real, separate concept. Resolved as a distinct, deliberately-scoped, not-yet-built component: it embeds Risk Governor state as one element of a larger audit view, which is exactly why its states/owner look like `RiskGovernorBadge`'s rather than `GovernanceBadge`'s.

**Status:** `lifecycle: planned` in the registry. No implementation exists yet (`sentinel/frontend/components/` has no `governance_panel.py`). This spec exists so a future implementation has a contract to build against, per the registry's own rule that `planned` components require a specification before `file:`.

## Visual Specs
- **Background:** `var(--color-surface-white)`
- **Border:** `1px solid var(--color-border-subtle)`
- **Elevation:** `var(--shadow-card)`
- **Font:** Body `var(--font-primary)`; hashes/timestamps `var(--font-data)` with `font-variant-numeric: tabular-nums`

## Lifecycle States & Mappings
Embeds the same 3-state Risk Governor model as `RiskGovernorBadge`, per `brand/STATE_MAPPING.yaml`'s `risk_governor` section:

### 1. Normal
- **Visuals:** `var(--status-approved)`, label "Normal Operation".

### 2. Warning
- **Visuals:** `var(--status-deferred)`, label "Warning Threshold".

### 3. Defensive
- **Visuals:** `var(--status-declined)`, label "Defensive Intervention".

## Required Fields
`governance_checks`, `policy_version`, `audit_reference` (carried over from the original registry entry -- these describe the audit-trail content that distinguishes this panel from the badge's single-status display).

## Accessibility Contract
1. **Keyboard Navigable:** Panel and each expandable section focusable via standard tab navigation.
2. **Focus Ring:** 2px focus ring using `var(--color-navy-primary)`.
3. **Screen Readers:** ARIA label states the Risk Governor state and policy version in words.
4. **Multi-Modal Indicators:** State conveyed via icon + text label, never color alone.
