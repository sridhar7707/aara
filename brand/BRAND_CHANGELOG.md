# Sentinel Brand Change Log

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
