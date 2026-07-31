---
component: decision_card
version: "1.0"
status: frozen
phase: "2A"
---

# Component: Decision Card

## Overview
Primary visual container for trade evaluations, evidence summaries, and audit fingerprints.

## Visual Specs
- **Background:** `var(--color-surface-white)`
- **Border:** `1px solid var(--color-border-subtle)`
- **Elevation:** `var(--shadow-card)`
- **Font:** Body uses `var(--font-primary)`, numbers/hashes use `var(--font-data)` with `font-variant-numeric: tabular-nums`

## Lifecycle States & Mappings

### 1. Pending
- **Condition:** Decision awaiting governance review or execution signal.
- **Visuals:** Uses `--status-pending` and `icon: decision_review_v1.0.svg`.

### 2. Approved
- **Condition:** Verified against all policy guardrails.
- **Visuals:** Uses `--status-approved` badge, approval timestamp, explicit audit fingerprint hash.

### 3. Deferred
- **Condition:** Execution postponed due to volatility or missing parameter.
- **Visuals:** Uses `--status-deferred` badge, required next action detail box.

### 4. Declined
- **Condition:** Risk Governor blocked execution.
- **Visuals:** Uses `--status-declined` border indicator, decline rationale text, audit reference hash.

### 5. Escalated
- **Condition:** Manual human intervention or approval required.
- **Visuals:** Uses `--status-escalated` container, execution action buttons disabled.

## Accessibility Contract
1. **Keyboard Navigable:** Card focusable using standard tab navigation (`tabindex="0"`).
2. **Focus Ring:** 2px focus ring using `var(--color-navy-primary)`.
3. **Screen Readers:** ARIA labels linking asset name (`aria-labelledby`) to decision status (`aria-describedby`).
4. **Touch Target Size:** Action buttons minimum **44x44px**.
5. **Multi-Modal Indicators:** Color is NEVER the sole indicator. Every state pairs color with text labels and semantic SVG icons (e.g., `[Icon] APPROVED`).
