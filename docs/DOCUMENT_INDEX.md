# Documentation Index

Quick-reference entry point for `docs/`. For full detail see `docs/DOCUMENT_GOVERNANCE_MATRIX.md` (complete 134-document inventory) and `docs/DOCUMENT_CONSOLIDATION_PLAN.md` (consolidation actions and migration phases). This file stays short on purpose — update it only when a canonical document changes, not when any document changes.

---

## 1. Documentation Hierarchy

When documents disagree, the higher tier wins:

1. **Code** — the real, tested implementation always wins over any doc.
2. **ADRs** (`docs/decisions/`) — binding once status is **Accepted**. A "Proposed" ADR is not yet authoritative.
3. **Frozen Architecture Documents** — anything in `docs/architecture/ARCHITECTURE_FREEZE_STATUS.md`'s registry, plus `docs/platform/PHASE_0_ARCHITECTURE_VALIDATION_REPORT.md`. Changeable only via a dated addendum or a narrowly-scoped ADR exception.
4. **Product Requirements Documents (PRDs)** — one per product/platform. Persona/screen-level docs are layers under a PRD, not competing PRDs.
5. **Architecture Specifications** — non-frozen architecture docs describing a subsystem.
6. **Implementation Plans** — sequencing only; never authoritative for a decision.
7. **Design Documents** — screen/component/UX design.
8. **Analysis Documents** — informational findings that feed decisions but don't make them.
9. **Historical Notes** — closed logs, superseded specs, completed working plans.

---

## 2. Canonical Documents by Area

| Area | Canonical Document(s) |
|---|---|
| Doc governance / freeze registry | `architecture/ARCHITECTURE_FREEZE_STATUS.md` |
| Platform & product doc authority | `platform/AARA_ARCHITECTURE_AUTHORITY.md` |
| Core domain/behavior architecture | `architecture/DECISION_INTELLIGENCE_ARCHITECTURE.md` |
| Data & event model | `architecture/SYSTEM_EVENT_MODEL_v1.2.md` |
| API / UI interface contracts | `architecture/API_REQUIREMENTS_v1.0.md`, `architecture/PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md` |
| Implementation guidance | `architecture/IMPLEMENTATION_HANDOFF.md` |
| Sentinel Engine (vision/entry point) | `platform/SENTINEL_INTELLIGENCE_ENGINE_ARCHITECTURE.md` |
| Sentinel Engine (live status log) | `implementation/SENTINEL_EXTRACTION_PLAN.md` |
| AARA Platform shell | `platform/AARA_PLATFORM_SHELL_ARCHITECTURE.md` |
| Trading Intelligence PRD | `products/AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` |
| Trading Intelligence Decision Center | `products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_CAPABILITY_MODEL.md` |
| Trading Intelligence ↔ Sentinel boundary | `platform/TRADING_INTELLIGENCE_BOUNDARY.md` |
| Confidence Integrity design | `architecture/DECISION_CONFIDENCE_INTEGRITY_DESIGN.md` |
| Wealth Intelligence PRD | `products/AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` *(flagged — describes capabilities not yet in shipped code; verify against `applications/wealth_intelligence/` before treating as current)* |
| Platform-wide PRD | `architecture/SENTINEL_PRODUCT_REQUIREMENTS_DOCUMENT.md` |
| Design system / UI tokens | `architecture/SENTINEL_DESIGN_SYSTEM_FINAL.md` |
| QA / acceptance testing | `architecture/QA_ACCEPTANCE_SPECIFICATION_v1.1.md` |
| Module migration mapping | `implementation/CODEBASE_MIGRATION_MATRIX.md` |
| Legacy bot feature tracking | `REQUIREMENTS.md` (root, auto-generated) |

If a document not listed here claims to be authoritative for one of these areas, treat the table above as correct and flag the conflict — don't assume the newer or longer document wins.

---

## 3. Key Folders

| Folder | Contents |
|---|---|
| `docs/decisions/` | ADRs — binding structural decisions |
| `docs/architecture/` | Frozen platform architecture, requirements, design system, confidence-integrity design chain |
| `docs/platform/` | AARA platform shell/identity/registration docs, Sentinel Engine architecture, Trading Intelligence platform-level docs |
| `docs/products/` | Product-level PRDs and design docs (Trading Intelligence, Wealth Intelligence) |
| `docs/design/` | Cross-platform UI/UX design principles |
| `docs/implementation/` | Roadmaps and phase/build plans (non-authoritative for decisions) |
| `docs/analysis/` | Read-only codebase and contract-gap findings |
| `docs/specs/` | Legacy feature build log — historical, superseded by `REQUIREMENTS.md` |
| `docs/` (root) | Legacy single-bot documentation (`ARCHITECTURE.md`, `DESIGN_SYSTEM.md`, `GOALS.md`, etc.) and repo-wide operations docs |

---

## 4. AI Assistant Reading Order

When asked to make a decision, design a feature, or answer "what's authoritative for X," read in this order and stop as soon as you have an answer:

1. **This file** (`docs/DOCUMENT_INDEX.md`) — check the Canonical Documents table first.
2. **Relevant ADR(s)** in `docs/decisions/` — check status is Accepted before treating as binding.
3. `docs/architecture/ARCHITECTURE_FREEZE_STATUS.md` — is the topic covered by a frozen document?
4. `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md` — is the topic covered by a platform/product doc-role ruling?
5. The area-specific canonical document from section 2 above.
6. `docs/DOCUMENT_GOVERNANCE_MATRIX.md` — only if you need full detail on a specific document (authority level, supersession, duplicate risk) not covered by this index.
7. `docs/DOCUMENT_CONSOLIDATION_PLAN.md` — only if doing documentation cleanup work, not for ordinary feature/decision questions.

Never treat a document's filename (`_FINAL`, `_FORMAL`, `_COMPREHENSIVE`) as a signal of authority — check this index and the freeze registry instead.

---

## 5. Rules for Adding New Documents

- **Check this index first.** If a canonical document already exists for the topic, update it in place — do not create a new sibling document.
- **Structural changes require an ADR**, not a design doc or implementation plan. Package structure, ownership boundaries, ledger strategy, identity/access model, and platform hierarchy all go in `docs/decisions/`.
- **Frozen documents are amended, never silently edited** — via a dated addendum (see `PHASE_2A_ARCHITECTURE_FREEZE_ADDENDUM.md`) or a narrowly-scoped ADR exception (see `ADR-006`).
- **One PRD per product.** Persona, screen, and capability detail live in separate documents that explicitly state which PRD they extend — they do not become alternate PRDs.
- **New documents must be registered**: add the file to `platform/AARA_ARCHITECTURE_AUTHORITY.md`'s document-roles table (or its successor) and, if it becomes canonical for an area, add it to section 2 of this index.
- **Place files by folder meaning, not convenience**: `docs/decisions/` for ADRs, `docs/architecture/` for frozen/platform-wide architecture, `docs/products/` for product-specific docs, `docs/implementation/` for sequencing plans, `docs/analysis/` for findings. A product doc has no business in `docs/architecture/`, and a decision doc has no business in `docs/products/`.
- **Historical or superseded documents move to an archive location** with a `> Superseded by: <path>` banner — they are not deleted and not left in the active tree unmarked.
