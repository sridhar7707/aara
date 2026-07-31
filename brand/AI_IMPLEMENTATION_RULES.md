# AI Frontend Implementation Rules

Before generating or modifying any UI component or template, follow these mandatory steps:

1. **Read `BRAND_MANIFEST.yaml` & `STATE_MAPPING.yaml` First:** Validate all metric names, ranges, and domain state-to-token mappings.
2. **Search Existing Components:** Check `design_system/COMPONENT_REGISTRY.yaml` before creating any new file. Extend existing components rather than duplicating UI patterns.
3. **Consume CSS Variables:** Use `tokens.css` semantic variables (e.g., `var(--status-approved)`). Never hardcode hex colors.
4. **Follow Component Contracts:** Ensure components implement all lifecycle states (Pending, Approved, Deferred, Declined, Escalated) defined in their YAML/MD specs.
5. **Never Invent Metrics or Terminology:** Use approved vocabulary only (e.g., "Conviction Score", NOT "AI Confidence" or "Decision Conviction").
6. **Enforce Responsive Layouts:** Adhere to `design_system/MOBILE_COMPONENT_RULES.md` for vertical stacking on smaller viewports.
7. **Accessibility Mandatory:** Never use color alone for status; always include semantic icons and ARIA attributes.

## Conflict Resolution
If a requested UI feature conflicts with any brand asset, manifest rule, or accessibility contract:
**STOP immediately and request explicit clarification from the user.**
