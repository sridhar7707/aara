---
component: audit_fingerprint_card
version: "1.0"
status: frozen
phase: "2A"
---

# Component: Audit Fingerprint Card

## Overview
Displays cryptographic proof of decision integrity (`docs/architecture/SENTINEL_COMPONENT_CATALOG.md`, Component 6) -- a governance signature hash, ledger verification status, and last-verified timestamp.

**Naming note (pre-existing, not introduced by this spec):** the catalog's own Component 6 section header says "Name: AuditFingerprintCard," but the catalog's end-of-document summary list calls the same component "AuditFingerprintDisplay" -- an inconsistency inside `SENTINEL_COMPONENT_CATALOG.md` itself. The implementation module (`sentinel/frontend/components/audit_fingerprint.py`) uses a third name, `AuditFingerprint`, in its own docstring. This spec and `COMPONENT_REGISTRY.yaml` use the in-section "Name:" field, `AuditFingerprintCard`, as canonical (the most specific of the three), with `AuditFingerprint` as the registered alias.

## Visual Specs
- **Hash:** `var(--font-data)`, `var(--color-text-secondary)`
- **Status:** "Verified" in `var(--status-approved)`, "Tampered" in `var(--status-declined)`
- **Background:** `var(--color-surface-white)`, border `1px solid var(--color-border-subtle)`

## States
- **Default:** Hash displayed, status shown.
- **Verifying:** Spinner, "Verifying hash...".
- **Verified:** `var(--status-approved)` checkmark, verification timestamp shown.
- **Tampered:** `var(--status-declined)`, hash mismatch details shown.

## Accessibility Contract
1. **Keyboard Navigable:** Card and copy-hash control focusable via standard tab navigation.
2. **Focus Ring:** 2px focus ring using `var(--color-navy-primary)`.
3. **Screen Readers:** ARIA label states verification status in words.
4. **Multi-Modal Indicators:** Status conveyed via icon + text label, never color alone.
