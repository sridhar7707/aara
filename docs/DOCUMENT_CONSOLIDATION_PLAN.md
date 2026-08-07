# Document Consolidation Plan

**Purpose:** a safe, reviewable plan to reduce documentation duplication across `docs/` while preserving architecture history. This plan does not itself move, merge, or delete anything — it is the roadmap a future PR (or series of PRs) should follow.
**Input:** `docs/DOCUMENT_GOVERNANCE_MATRIX.md` (134 documents, read in full before drafting this plan).
**Canonical-selection rule used throughout:** when two or more documents cover the same topic, the one in the highest tier below wins as canonical; lower tiers become supporting references.

1. ADR
2. Frozen architecture document
3. Product Requirements Document (PRD)
4. Architecture specification
5. Implementation plan
6. Design document
7. Analysis document
8. Historical notes

---

## Document Family: ADRs

All 8 are the repo's highest authority tier by definition. This family has no internal duplication — each ADR covers a distinct decision — so the action set is narrow: keep everything, fix two internal-consistency issues, and grow the family correctly going forward (see the misfiled-doc relocation in the Trading Intelligence family below).

| Current Document | Recommendation | Reason |
|---|---|---|
| decisions/ADR-001-sentinel-engine-structure.md | KEEP | Foundational, uncontested, cited by 4 later ADRs |
| decisions/ADR-002-bot-runtime-protection.md | KEEP | Active freeze, still in force except ADR-006's narrow exception |
| decisions/ADR-003-aara-identity-and-product-access.md | KEEP | Recorded requirement, not yet implemented — correctly scoped |
| decisions/ADR-004-sentinel-ledger-ownership-strategy.md | KEEP | Deliberate deferral record; revisit trigger is Phase 1A window close |
| decisions/ADR-005-platform-shell-model.md | KEEP | Documentation-only analysis, no conflicting doc exists |
| decisions/ADR-006-confidence-integrity-phase1-exception.md | KEEP | Valid narrow exception to ADR-002, tested (1274 tests) |
| decisions/ADR-007-aara-platform-hierarchy.md | KEEP, but resolve status | Still "Proposed" — needs a formal Acceptance decision before it can be cited as binding; verify against `AARA_ARCHITECTURE_AUTHORITY.md` whether a real flat-vs-nested conflict remains |
| decisions/ADR-008-sentinel-scaffold-disposition.md | KEEP, fix wording | Header says "Archive Executed" while body says "does not perform the archive" — reconcile the two statements so the record is internally consistent |

**Canonical documents:** every ADR is canonical for its own decision; no consolidation applies within this family.

**Overlap analysis:** none — this is the one family in the repo with zero duplicate-risk findings in the matrix.

---

## Document Family: Architecture Authority & Governance Documents

These are the meta-documents that are supposed to tell every other document which tier it belongs to. The matrix's single biggest finding is that these documents disagree with each other, which is why so much of the rest of the tree has ambiguous authority.

| Current Document | Recommendation | Reason |
|---|---|---|
| architecture/ARCHITECTURE_FREEZE_STATUS.md | KEEP as canonical freeze registry | Most specific, most recently authoritative freeze list (25 docs); becomes the single source of truth once reconciled with INDEX |
| architecture/ARCHITECTURE_INDEX.md | MERGE into ARCHITECTURE_FREEZE_STATUS.md | Self-contradicts (Active list vs. its own Authority Hierarchy section disagree on `PHASE_2_UI_UX_REQUIREMENTS` vs. `_FORMAL`); its useful content (the 4-level hierarchy) should be folded into the freeze registry rather than maintained as a second, disagreeing document |
| platform/AARA_ARCHITECTURE_AUTHORITY.md | KEEP as canonical for `docs/platform/` and `docs/products/` | Correctly states the code>ADR>platform-docs>draft-architecture hierarchy; needs its "current document roles" table expanded to cover the ~24 files across `docs/platform/` and `docs/products/` it currently doesn't individually rule on |
| architecture/PRD_ARCHITECTURE_RECONCILIATION.md | KEEP | Gold cross-reference record of gaps/decisions from the Phase 2A reconciliation; historical but still the only record of *why* certain P0/P1 fixes were made |
| architecture/DOCUMENTATION_COMPLETENESS_AUDIT.md | DEPRECATE, then ARCHIVE | Its flagged gaps (`EXPORT_ACCESS_POLICY.md`, `GOVERNANCE_STATUS_MAPPING.md`) are now closed — content is historical, not actionable |
| architecture/DOCUMENT_UPDATE_CHECKLIST.md | DEPRECATE, then ARCHIVE | Near-duplicate of DOCUMENTATION_COMPLETENESS_AUDIT.md's schedule section; both trackers are closed out by `ARCHITECTURE_FREEZE_STATUS.md`'s "What Changed" section |

**Canonical document:** `architecture/ARCHITECTURE_FREEZE_STATUS.md` for the architecture-tier freeze registry; `platform/AARA_ARCHITECTURE_AUTHORITY.md` for platform/product-tier authority. Two canonical documents are appropriate here because they govern genuinely different folders — but they must cross-link to each other, which they currently do not.

**Overlap analysis:**
- `ARCHITECTURE_FREEZE_STATUS.md` vs. `ARCHITECTURE_INDEX.md` — **FREEZE_STATUS should remain authoritative**; INDEX's disagreeing "20 active docs" list and its internal self-contradiction should be resolved by merging INDEX's genuinely useful 4-level hierarchy section into FREEZE_STATUS and retiring INDEX as a separate document. Content to move: the Level 1–4 hierarchy table. Content to discard: the disagreeing "Active(20)/Obsolete(38)" list, once verified against the merged registry.
- `DOCUMENTATION_COMPLETENESS_AUDIT.md` and `DOCUMENT_UPDATE_CHECKLIST.md` — both become **supporting historical references only**; no content needs to move since `ARCHITECTURE_FREEZE_STATUS.md` already independently documents "What Changed in This Session."

---

## Document Family: Frozen Core Architecture Specification Documents

The technical backbone: domain model, event model, data schema, and the API/UI/implementation contracts that were frozen together in the Phase 2A freeze (2026-07-30). These are tier-2 (frozen architecture) by the canonical-selection rule and should not be touched outside the amendment process.

| Current Document | Recommendation | Reason |
|---|---|---|
| architecture/DECISION_INTELLIGENCE_ARCHITECTURE.md | KEEP (canonical, Level 1) | Highest-authority frozen doc per the hierarchy — domain & behavior |
| architecture/TRADING_CONSTITUTION.md | KEEP | Level 1, immutable governance rules; fix version-number discrepancy (doc says v1.0, freeze registry says v1.2) |
| architecture/SYSTEM_EVENT_MODEL_v1.2.md | KEEP | Level 2; fix internal DRAFT/FROZEN header inconsistency |
| architecture/SQLITE_LEDGER_SCHEMA_v1.2.md | KEEP | Level 2, downstream of Event Model |
| architecture/DERIVED_STATE_VIEWS_v1.2.md | KEEP | Level 2, interlocking triad with the two above |
| architecture/DECISION_INTELLIGENCE_PROJECTION_MODEL.md | KEEP | Companion to Derived State Views — read-model/API shape |
| architecture/API_REQUIREMENTS_v1.0.md | KEEP, flag incomplete | Level 3, frozen but missing access-control/export endpoints per its own gap list |
| architecture/PHASE_2_BACKEND_REQUIREMENTS.md | KEEP | Application-services layer spec, in official freeze list |
| architecture/PHASE_2A_ARCHITECTURE_FREEZE_ADDENDUM.md | KEEP | Records 3 final decisions (5-metric framework, API tiering, tax/SQL-view boundary) — load-bearing for downstream docs |
| architecture/EXPORT_ACCESS_POLICY.md | KEEP | Fills a documented P0 gap, frozen |
| architecture/GOVERNANCE_STATUS_MAPPING.md | KEEP | Fills a documented P1 gap, frozen |
| architecture/GRADIO_IMPLEMENTATION_GUIDE.md | KEEP | Level 4 implementation guidance, frozen |
| architecture/IMPLEMENTATION_HANDOFF.md | KEEP | Level 4, primary handoff doc alongside the Addendum |
| architecture/PHASE_2_IMPLEMENTATION_ROADMAP_FINAL.md | KEEP | Sequencing doc for the frozen architecture, not itself frozen but non-conflicting |
| architecture/BRAND_STRATEGY.md | KEEP, fix version label | Frozen v2.0 per governance docs but header still says v1.0 — update the header, no content change needed |

**Canonical documents:** `DECISION_INTELLIGENCE_ARCHITECTURE.md` (Level 1), `SYSTEM_EVENT_MODEL_v1.2.md` (Level 2 entry point), `API_REQUIREMENTS_v1.0.md` + `PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md` (Level 3, the latter lives in the UI/UX family below), `IMPLEMENTATION_HANDOFF.md` (Level 4).

**Overlap analysis:** this family has low internal duplication risk — each document has a distinct, non-overlapping scope. The only action items are metadata corrections (version labels, DRAFT/FROZEN header consistency), not content merges.

---

## Document Family: Sentinel Engine Documents

The largest consolidation opportunity in the repo. Two authoring tiers exist side by side: a **vision tier** (philosophical, aspirational, zero code references) and a **grounded tier** (cites real file paths, test counts, ADRs).

| Current Document | Recommendation | Reason |
|---|---|---|
| platform/SENTINEL_INTELLIGENCE_ENGINE_ARCHITECTURE.md | KEEP (canonical merge target) | Broadest-scope vision-tier doc; best "start here" entry point |
| platform/SENTINEL_ENGINE_SERVICE_ARCHITECTURE.md | **MERGE into SENTINEL_INTELLIGENCE_ENGINE_ARCHITECTURE.md** | ~80% identical content (philosophy, layers, migration map, runtime flow, future-expansion roster) written independently with zero cross-references; keep only its unique API-contract and migration-map sections |
| platform/SENTINEL_ENGINE_RUNTIME_FLOW.md | KEEP (canonical for runtime lifecycle) | Same content is independently restated in Service Architecture §9 and Intelligence Engine Architecture §6 — this doc should be the *only* copy; replace the other two with one-line links |
| platform/SENTINEL_ENGINE_GOVERNANCE_ARCHITECTURE.md | KEEP (canonical for governance layer) | Overlaps Intelligence Engine Architecture §4.4; keep the dedicated doc (more depth), replace the master doc's section with a link |
| platform/SENTINEL_ENGINE_MEMORY_ARCHITECTURE.md | KEEP (canonical for memory layer) | Same pattern — overlaps §4.3 |
| platform/SENTINEL_ENGINE_REASONING_ARCHITECTURE.md | KEEP (canonical for reasoning layer) | Same pattern — overlaps §4.1 |
| platform/SENTINEL_ENGINE_EVENT_ARCHITECTURE.md | KEEP, trim overlap | Vision-tier; distinct scope from grounded `TRADING_INTELLIGENCE_EVENT_MODEL.md` so not a cross-family duplicate, but restates the master doc's event philosophy |
| platform/SENTINEL_ENGINE_DEPLOYMENT_ARCHITECTURE.md | KEEP | Unique topic, no duplication found |
| platform/SENTINEL_ENGINE_SECURITY_AND_PRIVACY_ARCHITECTURE.md | KEEP | Unique topic, no duplication found |
| platform/SENTINEL_ENGINE_DOMAIN_VOCABULARY.md | KEEP | Reference-only by design; preserves pre-ADR-008 terminology |
| platform/SENTINEL_ENGINE_AI_ORCHESTRATION_ARCHITECTURE.md | KEEP, needs review | Vision-tier, aspirational product roster (CFO/Tax/Estate/Retirement) not reflected in real 2-product scope; not adjudicated by the Authority doc |
| platform/SENTINEL_ENGINE_DATA_MODEL.md | KEEP, needs review | Same governance gap; verify 8 domain objects against real implemented `sentinel_engine/` contracts before treating as authoritative |
| platform/SENTINEL_ENGINE_BOUNDARY_AND_API_CONTRACTS.md | KEEP (with reinterpretation) | The one Sentinel foundation doc the Authority doc actually ruled on — capability-verb model stands, literal package layout is superseded by ADR-001 |
| platform/SENTINEL_ENGINE_PHASE1_DECISION_LIFECYCLE.md | KEEP | Only grounded, current-dated (2026-08-06) doc in the vision-tier set; add to Authority index |
| platform/PHASE_0_ARCHITECTURE_VALIDATION_REPORT.md | KEEP | Historical validation record for the sentinel/ → sentinel_engine/ archival; add to Authority index |
| implementation/SENTINEL_EXTRACTION_PLAN.md | KEEP (canonical implementation record) | Most rigorously maintained doc in the whole tree; live execution/status log, Phases 0-7 + 2A marked COMPLETE |

**Canonical documents:** `SENTINEL_INTELLIGENCE_ENGINE_ARCHITECTURE.md` (vision/entry-point), `SENTINEL_ENGINE_RUNTIME_FLOW.md` (runtime lifecycle), `SENTINEL_ENGINE_BOUNDARY_AND_API_CONTRACTS.md` (as reinterpreted by the Authority doc), `SENTINEL_EXTRACTION_PLAN.md` (implementation record).

**Overlap analysis:**
- `SENTINEL_ENGINE_SERVICE_ARCHITECTURE.md` → **merge into** `SENTINEL_INTELLIGENCE_ENGINE_ARCHITECTURE.md`. Authoritative side: Intelligence Engine Architecture (broader scope, matches the doc-roles table's implicit "master doc" role). Content to move: the unique API-contract (`analyze/explain/remember/evaluate/recommend`) and migration-mapping sections. Content to discard: the duplicated philosophy/layers/runtime sections.
- `SENTINEL_ENGINE_RUNTIME_FLOW.md` stays authoritative for runtime lifecycle; `SERVICE_ARCHITECTURE.md` §9 and `INTELLIGENCE_ENGINE_ARCHITECTURE.md` §6 should be **summarized to a one-line pointer**, not duplicated in full.
- `SENTINEL_ENGINE_GOVERNANCE_ARCHITECTURE.md` / `MEMORY_ARCHITECTURE.md` / `REASONING_ARCHITECTURE.md` remain authoritative for their layers (more depth than the master doc's summary sections); `INTELLIGENCE_ENGINE_ARCHITECTURE.md` §4.1/4.3/4.4 should be **summarized**, content not duplicated.

---

## Document Family: AARA Platform Documents

Covers the platform shell, navigation, identity/access, and product/workspace registration model.

| Current Document | Recommendation | Reason |
|---|---|---|
| platform/AARA_PLATFORM_SHELL_ARCHITECTURE.md | KEEP (canonical) | Foundational — cited by 4 other docs in this family as authority |
| products/AARA_PLATFORM_USER_EXPERIENCE.md | KEEP, merge candidate | Same commit as Product Navigation Architecture; grounds itself in ADR-003 |
| products/AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md | **MERGE into AARA_PLATFORM_USER_EXPERIENCE.md** | Explicitly extends that doc's Section 2 — natural single "Platform Shell & Navigation" document |
| platform/AARA_NAVIGATION_MODEL_ARCHITECTURE.md | KEEP, flag for review | Platform-level nav composition (Product > Workspace); shares an unresolved "visibility inheritance" question with Workspace Registration — resolve the question once, in one place |
| platform/AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md | KEEP | Good discipline — explicitly refines, doesn't contradict, ADR-003 |
| platform/AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md | KEEP or MERGE with Workspace Registration | Companion/prerequisite to Workspace Registration, one granularity level up; consider one doc with two sections |
| platform/AARA_WORKSPACE_REGISTRATION_ARCHITECTURE.md | KEEP or MERGE with Product Registration | Same open question ("visibility inheritance") as Product Registration and Navigation Model — three docs currently track one open question separately |
| platform/AARA_WORKSPACE_ACTIVATION_ARCHITECTURE.md | **MERGE with AARA_WORKSPACE_ENTRY_ARCHITECTURE.md** | Same missing "workspace entry resolver" problem, analyzed twice |
| platform/AARA_WORKSPACE_ENTRY_ARCHITECTURE.md | **MERGE target for Workspace Activation** | Names the resolver; Activation doc adds the options analysis for the same gap — read as one continuous document, currently split in two |
| platform/AARA_PLATFORM_ARCHITECTURE.md | MERGE (hierarchy section only) into AARA_ARCHITECTURE_AUTHORITY.md | Long-term vision doc; its hierarchy diagram is the one ADR-007 cites as already-reconciled — fold that diagram into the Authority doc rather than maintaining two hierarchy statements. Aspirational product roster (CFO/Tax/Estate/Retirement) should not be treated as scope until a PRD exists for each |
| platform/DASHBOARD_DEPENDENCY_REDUCTION_PLAN.md | KEEP | Distinct topic (dashboard/bot coupling ahead of extraction); sync its own "Draft" self-label to the Authority doc's "Authoritative, no option chosen" classification |

**Canonical documents:** `AARA_PLATFORM_SHELL_ARCHITECTURE.md` for shell responsibilities; `AARA_PLATFORM_USER_EXPERIENCE.md` (post-merge) for shell UX and navigation; `platform/AARA_ARCHITECTURE_AUTHORITY.md` for the platform brand/hierarchy (already the canonical governance doc, listed in its own family above).

**Overlap analysis:**
- `AARA_WORKSPACE_ACTIVATION_ARCHITECTURE.md` + `AARA_WORKSPACE_ENTRY_ARCHITECTURE.md` — **Entry Architecture becomes authoritative** (it names the missing component); Activation's options analysis is **moved in** as that document's "Implementation Options" section. No independent second document needed.
- `AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md` + `AARA_WORKSPACE_REGISTRATION_ARCHITECTURE.md` — **both remain authoritative** for their own granularity level (product vs. workspace); the shared open question about visibility inheritance should be **resolved once** (via a small ADR or a shared decision note) and referenced by both, rather than tracked independently in three places (these two plus `AARA_NAVIGATION_MODEL_ARCHITECTURE.md`).
- `AARA_PLATFORM_USER_EXPERIENCE.md` + `AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md` — **User Experience becomes authoritative**; Navigation Architecture's content is **moved in** as an extension section, since it already explicitly extends the former's Section 2.

---

## Document Family: Trading Intelligence Documents

The largest family (28 documents) — the most fully-built product, including its own "Confidence Integrity" sub-effort.

| Current Document | Recommendation | Reason |
|---|---|---|
| products/AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md | KEEP (canonical PRD-tier), needs update | Vision/scope/6-screen workspace anchor; Sections 6/10 still say "no code exists" — now false, correct in place |
| products/AARA_TRADING_INTELLIGENCE_MVP_SCOPE_DECISION.md | **KEEP content, RELOCATE to docs/decisions/ as a new ADR** | Functions exactly like a binding ADR (cites prior analysis, makes one final call, never touches code) but lives among design docs — misfiled, not a content problem |
| products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_CAPABILITY_MODEL.md | KEEP (canonical rollup) | Deliberate synthesis of the 5 capability-design docs below; self-declares it doesn't re-derive their findings |
| products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md | KEEP (detail layer) | Foundational screen design, cited as authority by 5 other docs |
| products/AARA_TRADING_INTELLIGENCE_EVIDENCE_DESIGN.md | KEEP (detail layer) | One of the 5 docs synthesized by the Capability Model |
| products/AARA_TRADING_INTELLIGENCE_GOVERNANCE_INTELLIGENCE_DESIGN.md | KEEP (detail layer) | Same; also explicitly defers ADR-004 ledger ownership |
| products/AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md | KEEP (detail layer) | Same; note the "Risk Intelligence" naming collision with the UI Specification doc — glossary fix needed, not a merge |
| products/AARA_TRADING_INTELLIGENCE_APPLICATION_COMPOSITION_DESIGN.md | KEEP | Composition/wiring detail, corrects two other docs found stale vs. real code |
| products/AARA_TRADING_INTELLIGENCE_DEMO_RUNTIME_DESIGN.md | KEEP | Most recently written; extends Composition Design's gap list |
| products/AARA_TRADING_INTELLIGENCE_MVP_EXPERIENCE_DESIGN.md | KEEP as narrative reference | Journey/readiness content already restated as "final" in MVP_SCOPE_DECISION — treat that doc as authoritative for scope, this one for narrative/journey detail |
| platform/TRADING_INTELLIGENCE_BOUNDARY.md | KEEP, sync self-label | TI vs. sentinel_engine ownership; self-labels "Draft" while Authority doc calls it "Authoritative" — fix the label |
| platform/TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md | KEEP | Package structure/dependency direction for `applications/trading_intelligence/`; add to Authority index |
| platform/TRADING_INTELLIGENCE_EVENT_MODEL.md | KEEP, sync self-label | Same stale "Draft"/"Authoritative" mismatch as Boundary doc |
| platform/TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md | KEEP | Cited as authority by 2 other docs but absent from the Authority index — add it |
| platform/TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md | KEEP, add banner | **Confirmed NOT superseded** by the Read Integration Design doc (different topic — ownership vs. read-path); add a "see ADR-004" banner and rename to reduce the discoverability hazard from its near-identical name |
| platform/TRADING_INTELLIGENCE_SENTINEL_READ_INTEGRATION_DESIGN.md | KEEP | Its recommended Option A is confirmed already implemented in `adapters/sentinel_projection_decision_source.py` |
| architecture/DECISION_CONFIDENCE_INTEGRITY_DESIGN.md | KEEP (chain origin) | 1st in the 5-doc Confidence Integrity chain; note the hash-chain claim later corrected by the Schema Change Review |
| architecture/CONFIDENCE_EDGE_CASE_ANALYSIS.md | KEEP (2nd in chain) | Stress-test that found the division-by-zero bug the origin doc missed |
| architecture/DECISION_EVENT_SCHEMA_CHANGE_REVIEW.md | KEEP (3rd in chain) | Genuine correction document, not a duplicate |
| architecture/CONFIDENCE_POLICY_DECISIONS.md | KEEP (chain decision record) | Resolves 2 open formula questions; flag `CONFLICT_THRESHOLD=0.40` as an uncalibrated starting value |
| architecture/CONFIDENCE_DECISION_POLICY_DESIGN.md | KEEP (last in chain) | Synthesizes the chain into the final evidence/policy layering |
| architecture/RISK_GOVERNOR_SAFETY_AUDIT.md | KEEP | Independent code audit, found a real High-severity confidence-drift gap |
| architecture/SHADOW_INVESTOR_MODE.md | KEEP, update framing | Mechanics remain valid; phase-timing framing (Phase 1A-1B) is superseded by the requirements matrix's Phase 3 decision |
| architecture/TRADING_CONSTITUTION.md | KEEP | Frozen governance rules (see Frozen Core Architecture family for version-label note) |
| product/CONFIDENCE_EXPLANATION_UX.md | **KEEP content, RELOCATE to docs/products/** | Lone file in singular `docs/product/`; the doc itself flags this — pure location fix, no content change |
| implementation/AARA_TRADING_INTELLIGENCE_IMPLEMENTATION_ROADMAP.md | KEEP, consider rename | Genuinely distinct scope from `IMPLEMENTATION_MASTER_ROADMAP.md` but the near-identical name is a discoverability risk |
| implementation/CONFIDENCE_INTEGRITY_IMPLEMENTATION_PLAN.md | KEEP | Phased build plan reconciling the 5-doc confidence chain into one module + Shadow Mode |
| implementation/PHASE_2B_DECISION_INTELLIGENCE_IMPLEMENTATION_PLAN.md | KEEP, update | "No files created" claim is now false — `bot/decision_engine/` already exists; update Section 3 to reflect shipped modules |

**Canonical documents:** `AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` (PRD tier); `AARA_TRADING_INTELLIGENCE_DECISION_CENTER_CAPABILITY_MODEL.md` (canonical rollup of the 5 capability designs); `TRADING_INTELLIGENCE_BOUNDARY.md` (ownership boundary); `DECISION_CONFIDENCE_INTEGRITY_DESIGN.md` (confidence chain origin, refined by `CONFIDENCE_DECISION_POLICY_DESIGN.md`).

**Overlap analysis:**
- The 5 capability-design docs (Decision Center, Evidence, Governance, Risk Intelligence Design, plus the UI Specification in the UI/UX family) are **deliberate layering, not duplication** — `DECISION_CENTER_CAPABILITY_MODEL.md` stays the canonical rollup; the 5 remain the authoritative detail layer for their own capability. No content should move; state the layering explicitly in the family index instead.
- The 5-document Confidence Integrity chain (`DECISION_CONFIDENCE_INTEGRITY_DESIGN` → `CONFIDENCE_EDGE_CASE_ANALYSIS` → `DECISION_EVENT_SCHEMA_CHANGE_REVIEW` → `CONFIDENCE_POLICY_DECISIONS` → `CONFIDENCE_DECISION_POLICY_DESIGN`) is a **sequential correction/refinement chain**, confirmed by timestamp order and cross-references — each stays authoritative for its own step; do not merge, but do add a one-line "this chain reads in order: ..." pointer at the top of the first document.
- `TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md` vs. `TRADING_INTELLIGENCE_SENTINEL_READ_INTEGRATION_DESIGN.md` — **both remain authoritative**, near-identical names notwithstanding; they answer different questions (ledger ownership vs. read-path). No merge; rename one or both and add explicit "not the same decision as X" cross-links.
- `AARA_TRADING_INTELLIGENCE_MVP_EXPERIENCE_DESIGN.md` vs. `AARA_TRADING_INTELLIGENCE_MVP_SCOPE_DECISION.md` — **Scope Decision becomes authoritative** for the final journey/readiness matrix (it explicitly restates the Experience Design's content as "final"); Experience Design remains a **supporting narrative reference**, content not deleted since it has more prose detail.

---

## Document Family: Wealth Intelligence Documents

| Current Document | Recommendation | Reason |
|---|---|---|
| products/AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md | KEEP, mark **needs reconciliation** | Describes an aspirational product (Plaid aggregation, Wealth X-Ray/Map, 5 MVP capabilities) with **zero matching code** — the shipped `applications/wealth_intelligence/` app is a minimal Decision-Center clone. This is a doc/code drift problem, not a duplication problem; do not archive, but flag prominently until either the code catches up or the doc is rescoped to match what's actually shipping next |

**Canonical document:** this is the only Wealth Intelligence document, so it is canonical by default — but it should not be treated as a reliable PRD until reconciled against shipped code.

**Overlap analysis:** none — this family has exactly one document and no duplication risk. The risk here is doc-vs-code drift, tracked separately from consolidation.

---

## Document Family: UI/UX Documents

| Current Document | Recommendation | Reason |
|---|---|---|
| architecture/PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md | KEEP (canonical) | Frozen v2.0, in the official freeze list, the doc `IMPLEMENTATION_HANDOFF.md` directs engineers to |
| architecture/PHASE_2_UI_UX_REQUIREMENTS.md | **DEPRECATE, then ARCHIVE** | Original v1.0, not in the freeze list, explicitly flagged elsewhere as needing design-system alignment — superseded by the FORMAL version |
| architecture/SENTINEL_DESIGN_SYSTEM_FINAL.md | KEEP (canonical design tokens) | Frozen v2.0 visual design system |
| architecture/SENTINEL_COMPONENT_CATALOG.md | KEEP | Companion component library, frozen |
| design/AARA_UI_UX_DESIGN_SYSTEM.md | KEEP as reference, reconcile | Platform-wide principles doc with 6 unresolved Open Design Decisions (Section 10) — reconcile against SENTINEL_DESIGN_SYSTEM_FINAL.md's token set before either is cited as final |
| root/DESIGN_SYSTEM.md | KEEP, rescope explicitly | Legacy Gradio dashboard tokens; claim of being "single source of truth for all visual decisions" is now false given SENTINEL_DESIGN_SYSTEM_FINAL.md exists — add an explicit "scope: legacy dashboard only" banner rather than archiving, since the legacy dashboard is still live |
| architecture/QA_ACCEPTANCE_SPECIFICATION_v1.1.md | KEEP (canonical QA suite) | Broader, versioned, self-declared frozen architectural-compliance suite |
| architecture/UI_ACCEPTANCE_TESTS.md | **MERGE into QA_ACCEPTANCE_SPECIFICATION_v1.1.md** | Earlier-generation, narrower browser/UI test spec; QA_ACCEPTANCE_SPECIFICATION already covers broader ground at a higher version |
| architecture/RESPONSIVE_WEB_REQUIREMENTS_v1.0.md | KEEP | Small, tightly scoped, frozen; companion to the design system docs |
| products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md | KEEP | Establishes the 6-screen TI structure every downstream doc builds on |
| products/AARA_TRADING_INTELLIGENCE_UI_IMPLEMENTATION_PLAN.md | KEEP | Frozen code-location decision (Option C), confirmed by real code in `applications/wealth_intelligence/ui/` |

**Canonical documents:** `PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md` (platform-wide UI/UX requirements), `SENTINEL_DESIGN_SYSTEM_FINAL.md` (design tokens), `QA_ACCEPTANCE_SPECIFICATION_v1.1.md` (QA/acceptance testing), `AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` (TI screen content, product-tier).

**Overlap analysis:**
- `PHASE_2_UI_UX_REQUIREMENTS.md` vs. `_FORMAL.md` — **FORMAL is authoritative**; the plain version should be marked superseded immediately (Phase 1) and archived once confirmed nothing still links to it (Phase 3).
- `UI_ACCEPTANCE_TESTS.md` vs. `QA_ACCEPTANCE_SPECIFICATION_v1.1.md` — **QA_ACCEPTANCE_SPECIFICATION becomes authoritative**; UI_ACCEPTANCE_TESTS' browser/UI-specific test cases should be **moved in** as a subsection if not already covered, then the standalone file archived.
- `root/DESIGN_SYSTEM.md` vs. `architecture/SENTINEL_DESIGN_SYSTEM_FINAL.md` — **not a true duplicate**, a scope split (legacy dashboard vs. new platform). Both stay, but the root doc's "single source of truth" claim must be narrowed to its actual scope so readers don't wrongly treat it as platform-wide.

---

## Document Family: Requirements Documents

| Current Document | Recommendation | Reason |
|---|---|---|
| architecture/SENTINEL_PRODUCT_REQUIREMENTS_DOCUMENT.md | KEEP (canonical PRD, principles layer) | Top-level vision/6 frozen design principles — highest authority tier (PRD) in this family |
| architecture/PRODUCT_SPECIFICATION_DETAILED.md | KEEP (detail layer), resolve conflict | Personas/workflows/30+ requirements; matrix found it labeled FROZEN in one registry and ACTIVE in another — resolve against the reconciled freeze registry (see Architecture Authority family) |
| architecture/SENTINEL_UXRD_COMPREHENSIVE.md | KEEP (detail layer), consider merge | Screen-by-screen UI mapping, 72KB, largest file in the repo; not in the freeze list despite same-minute timestamp as the frozen Formal UI/UX doc — either state its layering explicitly under the PRD, or fold its screen content into `PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md` (UI/UX family) and demote this to reference status |
| root/REQUIREMENTS.md | KEEP (canonical for legacy bot feature tracking) | Auto-generated, continuously current; scope is legacy bot/dashboard SPECs only — not a duplicate of the PRD family, a different tracking layer |
| root/SUCCESS_METRICS.md | KEEP | Primary/secondary metrics tied to `GOALS.md`; distinct from product requirements |

**Canonical document:** `SENTINEL_PRODUCT_REQUIREMENTS_DOCUMENT.md` is canonical per the PRD>architecture-spec ordering rule; `PRODUCT_SPECIFICATION_DETAILED.md` and `SENTINEL_UXRD_COMPREHENSIVE.md` are its detail layers.

**Overlap analysis:** this is the 3-way overlap flagged repeatedly in the matrix. **No document currently states the PRD → detailed-spec → UXRD layering explicitly**, which is why it reads as duplication rather than intentional structure. Recommended resolution: add one sentence to the top of each of the three documents stating its place in the layering (e.g., "This document expands on `SENTINEL_PRODUCT_REQUIREMENTS_DOCUMENT.md` §X with persona-level detail; see `SENTINEL_UXRD_COMPREHENSIVE.md` for screen-level detail"). If, after that, the UXRD is found to duplicate `PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md` more than it adds, fold its content there instead and archive it. Do not merge all three into one document — 123KB combined is too large for any single audience to use.

---

## Document Family: Implementation Documents

| Current Document | Recommendation | Reason |
|---|---|---|
| implementation/CODEBASE_MIGRATION_MATRIX.md | KEEP (canonical table), trim status section | Named "Authoritative" by the Authority doc, backed by ADR-001; its trailing status section contradicts ADR-002's freeze and the now-complete extraction — trim that section, keep the mapping table |
| implementation/IMPLEMENTATION_MASTER_ROADMAP.md | **DEPRECATE, then ARCHIVE** | Day-1 (2026-08-04) artifact, never updated; factually stale (says Sentinel Extraction "NOT STARTED" when it's COMPLETE per `SENTINEL_EXTRACTION_PLAN.md`); already excluded from the Authority doc's roles table |
| implementation/CODEBASE_INVENTORY.md | **DEPRECATE, then ARCHIVE or MERGE** into docs/analysis | Same Day-1 staleness pattern; superseded in practice by the `BOT_*` analysis docs, which are more rigorous and self-corrected |
| implementation/CI_SENTINEL_ENGINE_TEST_INTEGRATION_PLAN.md | **DEPRECATE, then ARCHIVE** | Its proposed CI diff is verified already merged into `.github/workflows/ci.yml`; header still claims "not applied" |

**Canonical document:** `CODEBASE_MIGRATION_MATRIX.md` (module-mapping table only, once trimmed). `SENTINEL_EXTRACTION_PLAN.md` is the canonical live-status log but lives in the Sentinel Engine family above since its subject matter belongs there.

**Overlap analysis:** all three archive candidates in this family share one root cause — they were written on Day 1 of the AARA migration (2026-08-04) as planning snapshots and were never updated as later, more rigorous documents (`SENTINEL_EXTRACTION_PLAN.md`, the `BOT_*` analysis docs, `CODEBASE_MIGRATION_MATRIX.md`) superseded them in practice without anyone formally marking them so.

---

## Document Family: Historical / Codebase Analysis Documents

| Current Document | Recommendation | Reason |
|---|---|---|
| analysis/BOT_DEPENDENCY_MAP.md | KEEP | Named "Authoritative findings" by the Authority doc; contains its own in-doc self-correction |
| analysis/BOT_EXTRACTION_CANDIDATES.md | KEEP | Named "Authoritative findings"; cited by ADR-002 |
| analysis/BOT_RUNTIME_BASELINE.md | KEEP | Named "Authoritative findings"; directly informs ADR-002 |
| analysis/TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md | KEEP | Named "Authoritative findings"; identified an un-inventoried 4th ledger |
| analysis/TRADING_INTELLIGENCE_SENTINEL_READ_MODEL_ANALYSIS.md | KEEP | Proposal-stage, gated by ADR-004; not yet implemented but still the only design analysis on this topic |
| root/PHASE_PLAN_decision_intelligence.md | **ARCHIVE** once confirmed superseded | Explicitly self-labeled "not project documentation, don't commit it"; overlaps `DECISION_INTELLIGENCE_ARCHITECTURE.md` and `DECISION_INTELLIGENCE_PROJECTION_MODEL.md`, both of which are now frozen and further along |
| specs/SPEC_01_portfolio_health_score.md | **ARCHIVE** | Fully implemented; superseded in function by `docs/REQUIREMENTS.md` |
| specs/SPEC_02_rich_telegram_alerts.md | **ARCHIVE** | Same |
| specs/SPEC_03_since_yesterday_panel.md | **ARCHIVE** | Same |
| specs/SPEC_04_ai_action_column.md | **ARCHIVE** | Same |
| specs/SPEC_05_daily_summary_alert.md | **ARCHIVE** | Same |
| specs/SPEC_06A_portfolio_performance_periods.md | **ARCHIVE** | Same |
| specs/SPEC_06B_per_stock_performance_columns.md | **ARCHIVE** | Same |
| specs/SPEC_06C_sparkline_charts.md | **ARCHIVE** | Same |
| specs/SPEC_07_ui_ux_test_suite.md | **ARCHIVE** | Same |
| specs/SPEC_08_ui_change_log.md | **ARCHIVE** | Same |
| specs/SPEC_09_living_requirements_tracker.md | **DEPRECATE first (fix stale status), then ARCHIVE** | Internally says "In Progress" while its own output (`docs/REQUIREMENTS.md`) confirms the described tool shipped 2026-06-26 — fix the label before archiving so the historical record isn't misleading |
| superpowers/plans/2026-07-31-sentinel-phase2a-governance-freeze.md | **ARCHIVE** | AI-agent working plan; confirmed already executed (`tools/validate_all.py` exists, same commit date) |

**Canonical documents:** none — by definition this family is informational/historical, feeding decisions elsewhere rather than being cited as source of truth.

**Overlap analysis:** the 11 `docs/specs/*` files and the superpowers plan are not duplicates of *each other* — they're duplicates of function with documents elsewhere (`docs/REQUIREMENTS.md`, `tools/validate_all.py`). The correct move is archival with a superseded-by pointer, not merging.

---

## Document Family: Operations Documents

| Current Document | Recommendation | Reason |
|---|---|---|
| root/BACKUP_RECOVERY.md | KEEP | Accurate, current backup/restore procedure |
| root/EXTERNAL_SERVICES.md | KEEP | Accurate, current external API inventory |
| root/NFR.md | KEEP, refresh data | Point-in-time performance numbers, ~6 weeks stale; refresh is already tracked in TECHNICAL_DEBT.md |
| root/RISK_REGISTER.md | KEEP | Bot-specific risk register; no platform-level equivalent exists yet — not a duplication problem, a coverage gap |
| root/TECHNICAL_DEBT.md | KEEP | Best-maintained document in the whole root batch |
| root/RELEASES.md | KEEP, update | "Upcoming" section incorrectly says no planned releases despite active AARA work |
| root/DEPENDENCIES.md | KEEP | Actively maintained |
| root/UI_CHANGELOG.md | KEEP, investigate | Auto-generated tool appears to have stopped recording entries since 2026-06-14 despite ongoing dashboard changes — a tooling bug, not a documentation problem; investigate separately from this consolidation |

**Canonical document:** each is canonical for its own operational topic; no overlap exists within this family.

**Overlap analysis:** none.

---

## Document Family: Legacy Trading Intelligence Bot Documents (Root Governance)

| Current Document | Recommendation | Reason |
|---|---|---|
| root/ARCHITECTURE.md | KEEP, rename/rescope | Describes the legacy single-bot architecture accurately; name collides directly with the `docs/architecture/` folder — rename to something like `LEGACY_BOT_ARCHITECTURE.md` or add an explicit "legacy scope only" banner |
| root/DESIGN_PRINCIPLES.md | KEEP, reconcile vs. ADRs | Still enforced, load-bearing; verify no conflicting statements against ADR-001 through ADR-008 |
| root/GOALS.md | KEEP, verify vs. product docs | Matches the win-rate ≥60% north star; verify it doesn't conflict with `docs/products/AARA_TRADING_INTELLIGENCE_*` product-level goals as those mature |
| root/README.md | KEEP, expand | Currently indexes only the 16 root files; must be expanded to reference every subfolder in the AARA-era tree (see Recommended Future Structure) |

**Canonical document:** `root/README.md` should become the single entry point once expanded — right now it silently omits ~117 newer documents.

**Overlap analysis:** none within this family — the risk here is omission (the AARA tree isn't indexed), not duplication.

---

## Proposed Final Documentation Structure

```
docs/
├── README.md                     # single entry point — indexes every folder below, including archive/
├── decisions/                    # ADRs only — binding once status = Accepted
│   └── ADR-NNN-*.md
├── architecture/
│   ├── FREEZE_STATUS.md          # merged ARCHITECTURE_FREEZE_STATUS.md + ARCHITECTURE_INDEX.md
│   ├── platform/                 # AARA_ARCHITECTURE_AUTHORITY.md, AARA_PLATFORM_*, workspace/product registration
│   ├── sentinel_engine/          # SENTINEL_ENGINE_*, SENTINEL_INTELLIGENCE_ENGINE_ARCHITECTURE.md, SENTINEL_EXTRACTION_PLAN.md
│   └── products/                 # frozen core specs (DECISION_INTELLIGENCE_ARCHITECTURE.md, SYSTEM_EVENT_MODEL_v1.2.md, etc.)
├── products/
│   ├── trading_intelligence/     # all AARA_TRADING_INTELLIGENCE_* + platform/TRADING_INTELLIGENCE_* + confidence chain
│   └── wealth_intelligence/      # AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md (flagged for reconciliation)
├── implementation/                # roadmaps and phase plans — explicitly non-authoritative for decisions
├── operations/                    # BACKUP_RECOVERY, EXTERNAL_SERVICES, NFR, RISK_REGISTER, DEPENDENCIES, RELEASES, TECHNICAL_DEBT, UI_CHANGELOG
├── analysis/                      # BOT_*, TRADING_INTELLIGENCE_*_ANALYSIS — read-only findings
├── legacy/                        # LEGACY_BOT_ARCHITECTURE.md (renamed), DESIGN_PRINCIPLES.md, GOALS.md, legacy DESIGN_SYSTEM.md
└── archive/                       # superseded/completed docs, moved not deleted, path preserved
    ├── specs/                     # docs/specs/SPEC_01-09
    ├── implementation/            # IMPLEMENTATION_MASTER_ROADMAP.md, CODEBASE_INVENTORY.md, CI_SENTINEL_ENGINE_TEST_INTEGRATION_PLAN.md
    ├── architecture/               # DOCUMENTATION_COMPLETENESS_AUDIT.md, DOCUMENT_UPDATE_CHECKLIST.md, PHASE_2_UI_UX_REQUIREMENTS.md (non-formal)
    └── plans/                     # docs/superpowers/plans/*
```

This is a **target**, not an immediate mandate. Moving 134 files is itself a structural change and should go through the same review discipline as any other architectural change — see the phased migration below.

---

## Migration Phases

### Phase 1 — No-risk actions (do first, no content moves)
- Expand `platform/AARA_ARCHITECTURE_AUTHORITY.md`'s "current document roles" table to individually name the ~24 `docs/platform/` and `docs/products/` files it currently doesn't rule on.
- Add a superseded-banner (`> Superseded by: <path>`) to: `architecture/PHASE_2_UI_UX_REQUIREMENTS.md`, `implementation/IMPLEMENTATION_MASTER_ROADMAP.md`, `implementation/CODEBASE_INVENTORY.md`, `implementation/CI_SENTINEL_ENGINE_TEST_INTEGRATION_PLAN.md`, `architecture/DOCUMENTATION_COMPLETENESS_AUDIT.md`, `architecture/DOCUMENT_UPDATE_CHECKLIST.md`.
- Fix the stale status label on `specs/SPEC_09_living_requirements_tracker.md` ("In Progress" → "Complete").
- Fix self-label mismatches: `platform/TRADING_INTELLIGENCE_BOUNDARY.md` and `TRADING_INTELLIGENCE_EVENT_MODEL.md` ("Draft" → "Authoritative"), `platform/DASHBOARD_DEPENDENCY_REDUCTION_PLAN.md` (sync to Authority doc's classification).
- Fix version-label drift: `architecture/BRAND_STRATEGY.md` (v1.0 header → v2.0), `architecture/TRADING_CONSTITUTION.md` (v1.0 → v1.2 to match the freeze registry), `architecture/SYSTEM_EVENT_MODEL_v1.2.md` (DRAFT/FROZEN header inconsistency).
- Fix `decisions/ADR-008-sentinel-scaffold-disposition.md`'s header/body wording inconsistency.
- Add cross-links: `root/README.md` gets a new section indexing `docs/architecture/`, `docs/platform/`, `docs/products/`, `docs/decisions/`, `docs/design/`, `docs/implementation/`, `docs/analysis/`.
- Add "see ADR-004" banner to `platform/TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md`.
- Resolve `decisions/ADR-007-aara-platform-hierarchy.md`'s status: confirm whether the flat-vs-nested conflict still applies to the current text, then move it to Accepted or revise it.

None of the above deletes, moves, or merges content — every action is additive (a banner, a label fix, a table row) or corrects a factual header claim to match the document's own body. Fully reversible with a single revert.

### Phase 2 — Safe consolidation (after Phase 1 banners have been live and reviewed)
- **Merge:** `platform/AARA_WORKSPACE_ACTIVATION_ARCHITECTURE.md` → `AARA_WORKSPACE_ENTRY_ARCHITECTURE.md`.
- **Merge:** `platform/SENTINEL_ENGINE_SERVICE_ARCHITECTURE.md` → `SENTINEL_INTELLIGENCE_ENGINE_ARCHITECTURE.md` (keep unique API-contract/migration-map sections).
- **Merge:** `products/AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md` → `AARA_PLATFORM_USER_EXPERIENCE.md`.
- **Merge:** `architecture/UI_ACCEPTANCE_TESTS.md` → `QA_ACCEPTANCE_SPECIFICATION_v1.1.md`.
- **Merge:** `architecture/ARCHITECTURE_INDEX.md`'s hierarchy section → `ARCHITECTURE_FREEZE_STATUS.md`, then retire INDEX as a standalone document.
- **Relocate:** `docs/product/CONFIDENCE_EXPLANATION_UX.md` → `docs/products/CONFIDENCE_EXPLANATION_UX.md`.
- **Relocate + rename:** `docs/products/AARA_TRADING_INTELLIGENCE_MVP_SCOPE_DECISION.md` → `docs/decisions/ADR-009-trading-intelligence-mvp-scope.md` (or next available ADR number).
- **Move historical documents:** all 11 `docs/specs/*` → `docs/archive/specs/`; `docs/superpowers/plans/2026-07-31-sentinel-phase2a-governance-freeze.md` → `docs/archive/plans/`.
- Trim the stale trailing status section of `implementation/CODEBASE_MIGRATION_MATRIX.md` (keep the mapping table).

Each merge/move should be its own small PR with a redirect stub left at the old path (`> Moved to: <new path>`) for at least one review cycle before the stub itself is removed.

### Phase 3 — Long-term cleanup (after Phase 2 merges are confirmed stable)
- Archive (physically move to `docs/archive/`) the documents marked DEPRECATE in Phase 1, once confirmed no other document still links to them at their old path: `implementation/IMPLEMENTATION_MASTER_ROADMAP.md`, `implementation/CODEBASE_INVENTORY.md`, `implementation/CI_SENTINEL_ENGINE_TEST_INTEGRATION_PLAN.md`, `architecture/DOCUMENTATION_COMPLETENESS_AUDIT.md`, `architecture/DOCUMENT_UPDATE_CHECKLIST.md`, `architecture/PHASE_2_UI_UX_REQUIREMENTS.md`, `root/PHASE_PLAN_decision_intelligence.md`.
- Rename `root/ARCHITECTURE.md` and rescope `root/DESIGN_SYSTEM.md` to remove the naming collisions with `docs/architecture/` and `docs/architecture/SENTINEL_DESIGN_SYSTEM_FINAL.md`.
- Resolve the 3-way PRD/spec/UXRD layering in the Requirements family — either document the layering explicitly or fold `SENTINEL_UXRD_COMPREHENSIVE.md`'s screen content into `PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md`.
- Execute the full folder restructure described in "Proposed Final Documentation Structure," once every merge/archive above has landed and the redirect stubs have been live for at least one review cycle.
- Investigate and fix the `root/UI_CHANGELOG.md` tracking gap (separate from documentation consolidation, but blocks trusting that document as current).

---

# Documents That Must NOT Be Modified

The following may only change via their own defined amendment process — never a silent edit:

**ADR documents** (`docs/decisions/`) — amend only by superseding with a new ADR, never by editing an Accepted ADR's decision text in place:
- ADR-001-sentinel-engine-structure.md
- ADR-002-bot-runtime-protection.md
- ADR-003-aara-identity-and-product-access.md
- ADR-004-sentinel-ledger-ownership-strategy.md
- ADR-005-platform-shell-model.md
- ADR-006-confidence-integrity-phase1-exception.md
- ADR-008-sentinel-scaffold-disposition.md
- (ADR-007 is still Proposed — it may be revised toward Acceptance, which is expected lifecycle, not a prohibited modification; once Accepted, it joins this list.)

**Frozen architecture documents** (`docs/architecture/ARCHITECTURE_FREEZE_STATUS.md`'s 25-document registry, plus `docs/platform/PHASE_0_ARCHITECTURE_VALIDATION_REPORT.md`) — amend only via an explicit addendum (the `PHASE_2A_ARCHITECTURE_FREEZE_ADDENDUM.md` model) or a narrowly-scoped ADR exception (the `ADR-006` model):
- API_REQUIREMENTS_v1.0.md, ARCHITECTURE_FREEZE_STATUS.md, BRAND_STRATEGY.md, DECISION_INTELLIGENCE_ARCHITECTURE.md, DECISION_INTELLIGENCE_PROJECTION_MODEL.md, DERIVED_STATE_VIEWS_v1.2.md, EXPORT_ACCESS_POLICY.md, GOVERNANCE_STATUS_MAPPING.md, GRADIO_IMPLEMENTATION_GUIDE.md, IMPLEMENTATION_HANDOFF.md, PHASE_2A_ARCHITECTURE_FREEZE_ADDENDUM.md, PHASE_2_BACKEND_REQUIREMENTS.md, PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md, QA_ACCEPTANCE_SPECIFICATION_v1.1.md, RESPONSIVE_WEB_REQUIREMENTS_v1.0.md, SENTINEL_COMPONENT_CATALOG.md, SENTINEL_DESIGN_SYSTEM_FINAL.md, SENTINEL_PRODUCT_REQUIREMENTS_DOCUMENT.md, SHADOW_INVESTOR_MODE.md, SQLITE_LEDGER_SCHEMA_v1.2.md, SYSTEM_EVENT_MODEL_v1.2.md, TRADING_CONSTITUTION.md (all `docs/architecture/`); PHASE_0_ARCHITECTURE_VALIDATION_REPORT.md (`docs/platform/`); AARA_TRADING_INTELLIGENCE_MVP_SCOPE_DECISION.md and AARA_TRADING_INTELLIGENCE_UI_IMPLEMENTATION_PLAN.md (`docs/products/`).
- Exception: metadata-only fixes identified in Phase 1 (version-label corrections, header-consistency fixes) are permitted since they correct the document to match its own already-recorded status — they are not changes to frozen *content*.

**Completed phase documents** — historical record of what already happened; edit only to append new phases, never to alter the record of completed ones:
- `implementation/SENTINEL_EXTRACTION_PLAN.md` — Phases 0-7 and 2A sections are a closed historical record; only new phase sections may be appended.
- `platform/PHASE_0_ARCHITECTURE_VALIDATION_REPORT.md` — a point-in-time validation snapshot, not a living document.
- `decisions/ADR-008-sentinel-scaffold-disposition.md` — records a completed archive action (commit `1fcc77b`); do not retroactively alter what it says was done, only fix the wording inconsistency noted in Phase 1.

**Historical decision records** — closed logs of decisions already made, kept for audit trail:
- `architecture/PRD_ARCHITECTURE_RECONCILIATION.md`
- `architecture/CONFIDENCE_POLICY_DECISIONS.md`
- `architecture/DECISION_EVENT_SCHEMA_CHANGE_REVIEW.md` (the correction record itself, not the document it corrects)

---

# Recommended Documentation Rules

**One source of truth per topic.** Every topic (a decision, a data model, a screen, a policy) should have exactly one document that is authoritative for it. When this plan identifies two documents covering the same topic, one becomes canonical and the other becomes either a merged-in section, a supporting reference with an explicit "see X for the authoritative version" pointer, or an archived historical record — never two independently-maintained sources of the same claim.

**No duplicate PRDs.** A product gets exactly one Product Requirements Document (`SENTINEL_PRODUCT_REQUIREMENTS_DOCUMENT.md` for the platform, one per product going forward). Persona/workflow detail and screen-level UX mapping are *layers underneath* the PRD, not competing PRDs — state the layering explicitly in each document's header, as recommended for the Requirements family above.

**No duplicate architecture specifications.** Before writing a new architecture document, search for existing documents on the same subsystem (by grepping the subsystem name, not just checking the target folder — this plan found duplicates split across `docs/architecture/` and `docs/platform/`). If one exists, update it in place. A new "FINAL," "FORMAL," "v2," or "COMPREHENSIVE" sibling document is presumptively a mistake — this repo's history shows that pattern (`PHASE_2_UI_UX_REQUIREMENTS.md` → `_FORMAL.md`, `SENTINEL_ENGINE_SERVICE_ARCHITECTURE.md` vs. `SENTINEL_INTELLIGENCE_ENGINE_ARCHITECTURE.md`) reliably produces an undetected duplicate rather than a clean replacement.

**ADR required for structural changes.** Any change to package structure, ownership boundaries, ledger/ownership strategy, identity/access model, or platform hierarchy requires a new ADR — not a design document, not an implementation plan. If a document not in `docs/decisions/` is found making a binding structural call (as `AARA_TRADING_INTELLIGENCE_MVP_SCOPE_DECISION.md` was), it should be relocated into the ADR series, per the Phase 2 migration step above.

**Frozen documents require explicit amendment.** A frozen document is never silently edited. It is amended only by:
1. A dated addendum document that references the original and states exactly what changed and why (the `PHASE_2A_ARCHITECTURE_FREEZE_ADDENDUM.md` model), or
2. A narrowly-scoped ADR that names the specific files and specific change being permitted (the `ADR-006` model).

Both mechanisms must update the single authoritative freeze registry (`docs/architecture/FREEZE_STATUS.md`, post-Phase-2-merge) so the registry never drifts out of sync with what's actually frozen — the root cause of this plan's largest finding (the FREEZE_STATUS/INDEX disagreement) was exactly this kind of drift.
