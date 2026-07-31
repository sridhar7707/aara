# Sentinel Brand Change Log

## Version 1.0.3 (2026-07-31)
**Status:** FROZEN — Design Governance v1.1, Stage 1: GovernancePanel Reconciliation (maintenance release)

**Scope:** `brand/design_system/COMPONENT_REGISTRY.yaml` + 1 new specification (`GOVERNANCE_PANEL.md`) + `tools/validators/registry_validator.py`'s coverage logic. No token, color, typography, or accessibility changes.

### Decision
**`GovernancePanel` is resolved as a distinct, deliberately-scoped, not-yet-built component — not a naming mistake for `GovernanceBadge`.** `lifecycle: unresolved` → `lifecycle: planned`.

Initial evidence (no implementation, no catalog listing under this name, `GovernanceBadge` exists and covers "governance status badge") suggested a simple typo. That was tested against the entry's own pre-existing metadata before deciding, and the two didn't agree: `GovernancePanel`'s `states` (`NORMAL`/`WARNING`/`DEFENSIVE`) and `owner` ("Risk & Policy Engine") match `RiskGovernorBadge` exactly — `GovernanceBadge`'s actual catalog-defined states are `PASS`/`ESCALATED`/`BREACH`, a different vocabulary entirely. A straight rename would have silently discarded that deliberately-authored content, or kept it and misdescribed `GovernanceBadge` with states it's never had.

Resolution: `GovernancePanel` and `GovernanceBadge` are different concepts that solve different UI problems — `GovernanceBadge` is a compact status indicator for cards/tables/lists (implemented); `GovernancePanel` is a richer composite view (policy checks, rule evaluations, Risk Governor state, approval history, audit references) that embeds Risk Governor state as one element, which is exactly why its states/owner resembled `RiskGovernorBadge`'s rather than `GovernanceBadge`'s. Both concepts are retained. `GovernancePanel` gets a specification (`brand/design_system/GOVERNANCE_PANEL.md`) now; implementation stays deferred.

### Changes
- `GovernancePanel`: `lifecycle: unresolved` → `planned`, `note:` rewritten to record this decision and its evidence, `specification:` added.
- Created `brand/design_system/GOVERNANCE_PANEL.md`.
- `registry_validator.py`'s `REGISTRY_COVERAGE` check reworked to match registry entries against the catalog's actual `**Name:**` fields (identity-based) rather than inferring catalog membership from `lifecycle != unresolved`. That heuristic would have wrongly counted `GovernancePanel` as "covering" a catalog component now that it's `planned` — it still isn't one of the catalog's 9 documented components, planned or not.

### Design Governance v1.1 status after this release
- Stage 1 (resolve `GovernancePanel`) — **done**.
- Stage 2 (reconcile catalog/registry/implementation) — done (v1.0.2).
- Stage 3 (CI enforcement, phased informational-then-enforcing) — not started; this was the last blocker per the agreed sequencing.
- Still open, both documentation-only and out of scope for the registry: `SENTINEL_COMPONENT_CATALOG.md`'s internal name inconsistencies (2 components) and its color-palette mismatch against `tokens.css` (flagged in v1.0.1).

---

## Version 1.0.2 (2026-07-31)
**Status:** FROZEN — Design Governance v1.1, Stage 2: Full Catalog Reconciliation (maintenance release)

**Scope:** `brand/design_system/COMPONENT_REGISTRY.yaml` + 6 new component specifications. No token, color, typography, or accessibility changes.

### Changes
- Registered the 6 catalog components that were implemented but never tracked: `GovernanceBadge`, `EvidenceCard`, `ApprovalControls`, `ChainOfCustodyTimeline`, `AuditFingerprintCard`, `ModelAgreementBadge`. Registry now covers all 9 catalog components with a resolved identity (`GovernancePanel` remains the sole exception — see below).
- Created their 6 missing specification docs, following the same rule as v1.0.1's two: cite only real tokens from `tokens.css`, never `SENTINEL_COMPONENT_CATALOG.md`'s disconnected color palette.
- Found 2 more naming-drift cases identical to `PortfolioHealthCard`/`HealthScore`: `ChainOfCustodyTimeline` (catalog) vs. `ChainTimeline` (`chain_timeline.py`). Both resolved via the same `canonical_name`/`aliases` pattern, not a silent rename.
- Found 2 components where the catalog **disagrees with itself** — not introduced by this registry, just surfaced: Component 6's in-section "Name:" field says `AuditFingerprintCard`, but the catalog's own end-of-document summary calls it `AuditFingerprintDisplay`; Component 7's "Name:" field says `ModelAgreementBadge`, but its own section heading says "Model Agreement Indicator." Both resolved by treating the in-section "Name:" field as canonical and registering every variant (including the implementation's own name) as an alias, so no lookup silently 404s. The catalog's internal inconsistency itself is unresolved — a documentation fix, not a registry one.
- Deliberately left `owner` and `criticality` unset on all 6 new entries — see `metadata.unassigned_fields_note`. Neither field has a source document to derive a value from; guessing plausible-sounding ones would be exactly the kind of unverified inference this whole reconciliation effort has been working against.
- `tools/validators/registry_validator.py`'s coverage check now separates resolved components (counted against the catalog) from `lifecycle: unresolved` ones (reported separately) — after this change, counting `GovernancePanel` as a 10th "registered" component against a 9-component catalog would itself have been misleading.

### Not done in this release (per agreed Design Governance v1.1 sequencing)
- **`GovernancePanel`'s identity is still unresolved** — explicitly deferred, not decided this pass. It has no implementation and no matching catalog entry.
- CI enforcement (making `tools/validate_brand_system.py` a required PR/release gate) — intentionally sequenced *after* full reconciliation, per Stage 3 of the agreed plan, and further staged as informational-then-enforcing once adopted, to avoid gating on an imperfect baseline.
- `SENTINEL_COMPONENT_CATALOG.md`'s own internal name inconsistencies (2 components) and its color-palette mismatch against `tokens.css` (flagged in v1.0.1) remain open — both are catalog-document fixes, not registry ones.

---

## Version 1.0.1 (2026-07-31)
**Status:** FROZEN — Component Registry Synchronization (maintenance release)

**Scope:** `brand/design_system/COMPONENT_REGISTRY.yaml` only. No token, color, typography, accessibility, or component *contract* (states/metrics/audit requirements) changes.

### Changes
- Added a `lifecycle` field (`implemented` / `planned` / `unresolved` / `deprecated`) to every registered component, replacing the old boolean `deprecated: false`. `tools/validators/registry_validator.py` now enforces different rules per lifecycle value instead of one-size-fits-all.
- **DecisionCard:** `file:` path corrected to `sentinel/frontend/components/decision_card.py` (was a stale pre-implementation guess, `frontend/components/DecisionCard`). No other change — implementation and specification already matched.
- **RiskGovernorBadge:** `file:` path corrected the same way. Its specification was missing entirely (`RISK_GOVERNOR_BADGE.md` never existed) — created, sourced from `docs/architecture/SENTINEL_COMPONENT_CATALOG.md` Component 2 and the token bindings already frozen in `STATE_MAPPING.yaml`.
- **PortfolioHealthCard:** the implementation exists but under the name `HealthScore` (`sentinel/frontend/components/health_score.py`). Treated as the same component under a `canonical_name`/`aliases` pattern rather than either renaming the code or the registry entry outright — see the entry's `migration_note`. Specification created (`PORTFOLIO_HEALTH_CARD.md`).
- **GovernancePanel:** left deliberately unresolved (`lifecycle: unresolved`, with a `note:` explaining why) rather than guessed. It matches neither an implementation file nor any entry in `SENTINEL_COMPONENT_CATALOG.md` — the catalog's closest entry, "GovernanceBadge," is a different concept (a status badge vs. a panel) and may or may not be what this entry originally meant. Needs a human decision before it can be marked `implemented` or `planned`.
- Added a `metadata.coverage` note: the catalog documents 9 reusable components; this registry tracks 4. The other 5 (`GovernanceBadge`, `EvidenceCard`, `ChainOfCustodyTimeline`, `AuditFingerprintCard`, `ModelAgreementBadge`) are implemented but were never registered — deliberately not added in this pass rather than added by inference. `tools/validate_brand_system.py` now reports the live registered/expected count on every run (`REGISTRY_COVERAGE`, informational, non-blocking).

### Not done in this release
- GovernancePanel's true identity (typo for GovernanceBadge, or a distinct never-built component).
- Registering the 5 implemented-but-untracked components.
- Reconciling `SENTINEL_COMPONENT_CATALOG.md`'s color palette (e.g. Crimson `#A52834`, Slate Blue `#4B5D73`) against `tokens.css`'s actual, smaller token set — the two currently disagree, discovered while writing the two new specs above; both new specs cite only real tokens from `tokens.css`, not the catalog's colors.

---

## Version 1.0 (2026-07-30)
**Status:** FROZEN — Initial Production Design System Release

### Locked Decisions
- **Canvas/Theme:** Warm White (`#F8F7F3`) base canvas exclusively; dark mode explicitly deferred to Phase 3.
- **Metric Schema:** Strict five-metric vocabulary (`conviction_score`, `decision_quality_score`, `evidence_strength`, `model_agreement`, `model_confidence`).
- **State Governance:** 3-state Risk Governor (`NORMAL`, `WARNING`, `DEFENSIVE`) and 5-state Decision Lifecycle (`PENDING`, `APPROVED`, `DEFERRED`, `DECLINED`, `ESCALATED`).
- **Typography & Precision:** Inter primary stack; Monaco tabular monospace for all financial numbers and hashes.
- **Icon Infrastructure:** Vector SVG standard (`24x24` viewBox, `2px` stroke width) with enforced file naming rules.
- **Multi-Device Architecture:** Responsive-first vertical stacking rules.

---

## Change Governance Policy
Any future modifications to colors, typography, metric schemas, state mappings, or component contracts **MUST** fulfill the following requirements:
1. Increment system versioning in `BRAND_MANIFEST.yaml` and `VERSION_LOCK.yaml`.
2. Document architectural rationale and migration paths in this changelog.
3. Pass all automated validations via `tools/validate_brand_system.py`.
