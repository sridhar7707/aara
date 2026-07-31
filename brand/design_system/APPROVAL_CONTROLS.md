---
component: approval_controls
version: "1.0"
status: frozen
phase: "2A"
---

# Component: Approval Controls

## Overview
Three/four-button interface for the decision approval workflow (`docs/architecture/SENTINEL_COMPONENT_CATALOG.md`, Component 9): Approve / Defer / Reject, plus Escalate handling. Permission checks happen at the API layer -- per `docs/architecture/GRADIO_IMPLEMENTATION_GUIDE.md`, this component must never evaluate approval permissions itself.

## Visual Specs
- **Approve button:** `var(--status-approved)` background, white text
- **Defer button:** `var(--status-deferred)` background, white text
- **Reject button:** `var(--status-declined)` background, white text
- **Disabled:** `var(--color-text-secondary)`, no cursor

## States
- **Ready:** All buttons enabled per permissions returned by the API.
- **Submitting:** Approve button shows a spinner, disabled.
- **Disabled:** "Contact CRO" message if the user lacks permission.
- **Escalated:** Distinct styling when escalation is required.

## Required Fields
Per catalog data source: `decision_id`, `can_approve`, `requires_confirmation`, `is_escalated`.

## Accessibility Contract
1. **Keyboard Navigable:** All buttons reachable via standard tab navigation.
2. **Focus Ring:** 2px focus ring using `var(--color-navy-primary)` on the focused button.
3. **Screen Readers:** Each button has an explicit ARIA label naming the action and target decision.
4. **Touch Target Size:** Buttons minimum 44x44px.
