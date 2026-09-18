# AARA Architecture Authority

**Purpose:** Which documents are authoritative when architecture docs disagree.

## Hierarchy

1. **Committed code** — highest authority. What's actually built and tested wins over
   any document.
2. **Committed architecture decision records** (`docs/decisions/ADR-*.md`) — explicit,
   dated resolutions of a specific conflict. Supersede any conflicting doc below.
3. **Committed architecture/migration docs** (tracked in git, e.g. everything directly
   under `docs/platform/`, `docs/implementation/`, top-level `CLAUDE_AARA_MIGRATION.md`)
   — intended design, in the absence of a conflicting ADR.
4. **`docs/architecture/*`** — gitignored (`.gitignore:44`). Local working drafts, not
   the project's controlled source of truth. Useful for ideas; not binding.

## Directory structure

```
docs/
├── decisions/
│   └── ADRs
│       (why decisions were made)
│
├── platform/
│   ├── architecture definitions
│   ├── system boundaries
│   └── migration strategy
│       (what architecture we follow)
│
├── analysis/
│   ├── runtime investigations
│   ├── dependency maps
│   └── findings
│       (what we discovered)
│
└── architecture/
    └── local exploratory drafts only
```

`docs/platform/` contains authoritative architecture boundary and migration
strategy documents — tracked in git, binding in the absence of a conflicting ADR
(hierarchy level 3 above). A document only belongs in `docs/architecture/` if it is
a local, exploratory draft not yet promoted to a decision; once a document starts
being used to make real calls (as `TRADING_INTELLIGENCE_BOUNDARY.md` and
`DASHBOARD_DEPENDENCY_REDUCTION_PLAN.md` did), it moves to `docs/platform/`.

## Current document roles

| Document | Role |
|---|---|
| `docs/implementation/CODEBASE_MIGRATION_MATRIX.md` | Authoritative: package/module migration mapping for `sentinel_engine/`, `applications/`, `dashboard/` splits. See [ADR-001](../decisions/ADR-001-sentinel-engine-structure.md). |
| `docs/implementation/SENTINEL_EXTRACTION_PLAN.md` | Authoritative: phase-by-phase execution log and next-steps for the `sentinel_engine/` extraction. |
| `docs/platform/SENTINEL_ENGINE_BOUNDARY_AND_API_CONTRACTS.md` | Reinterpreted as a **conceptual capability model** (the `analyze`/`explain`/`remember`/`evaluate`/`recommend` verbs products call), not the engine's package architecture. Its literal `sentinel/core/`, `sentinel/reasoning/` layout is superseded by ADR-001. |
| `CLAUDE_AARA_MIGRATION.md` | Migration strategy and naming/positioning rules (Aara / Sentinel Intelligence Engine / Aara Wealth Intelligence). Its "not a trading bot" framing is clarified by ADR-001: trading is scoped out of the Wealth Intelligence *product*, not the platform. |
| `docs/products/AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` | Authoritative for Product #2 (Aara Wealth Intelligence) only. Does not define Product #1 or the engine. |
| `docs/decisions/ADR-001-sentinel-engine-structure.md` | Authoritative: `sentinel_engine/` is a separate package extracted from `sentinel/`, per `CODEBASE_MIGRATION_MATRIX.md`'s model. |
| `docs/decisions/ADR-002-bot-runtime-protection.md` | Authoritative: protects `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`, `database/`, and top-level `ledger/` from any code change until a future ADR explicitly and narrowly lifts it. |
| `docs/decisions/ADR-003-aara-identity-and-product-access.md` | Authoritative requirement, implementation deferred: multi-product identity/role/entitlement model (Trading Intelligence User, Wealth Intelligence User, Platform Administrator). No auth/schema/UI work exists yet. |
| `docs/decisions/ADR-004-sentinel-ledger-ownership-strategy.md` | Authoritative: formally defers the ledger-ownership choice (Option A/B/C, see `TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md`) until Phase 1A validation completes and its decision criteria are met. ADR-002 protections unchanged. |
| `docs/decisions/ADR-007-aara-platform-hierarchy.md` | Authoritative: formalizes the `AARA Systems → Sentinel Intelligence Engine → Products` naming hierarchy. Sentinel Intelligence Engine is a permanent architectural layer — not deprecated, renamed, or replaced by AARA. |
| `docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md` | Authoritative: target ownership boundary between Trading Intelligence (Product #1) and `sentinel_engine/`. Promoted from `docs/architecture/` — see Directory Structure above. |
| `docs/platform/TRADING_INTELLIGENCE_EVENT_MODEL.md` | Authoritative: resolves the `DECISION_CREATED`/`DECISION_EXECUTED` split, rejected-candidate handling (two-stage), portfolio-scoped `RISK_EVALUATED` model, and BUY-only outcome lifecycle. |
| `docs/platform/TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md` | Authoritative comparison (no option chosen — see ADR-004): three ledger-ownership architectures with tradeoffs on migration risk, rollback, and Phase 1A impact. |
| `docs/analysis/TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md` | Authoritative findings: field-level comparison of `bot/trust_ledger` data against `Decision`/`Event`/`EventType` contracts — what maps directly, what requires an adapter, what's structurally mismatched (e.g., portfolio-scoped risk evaluation). |
| `docs/platform/DASHBOARD_DEPENDENCY_REDUCTION_PLAN.md` | Authoritative: documents `dashboard/`'s coupling to `bot`/`database`/`scheduler` and un-decided reduction options. Promoted from `docs/architecture/`. No option chosen yet. |
| `docs/analysis/BOT_RUNTIME_BASELINE.md`, `BOT_DEPENDENCY_MAP.md`, `BOT_EXTRACTION_CANDIDATES.md` | Authoritative findings (what was discovered, not a decision) — entry points, import coupling, per-module extraction risk. Includes the corrected finding that `scheduler/` is a second live trading-trigger path, not an unused/legacy module. |
| `docs/platform/SENTINEL_ENGINE_DOMAIN_VOCABULARY.md` | Reference vocabulary only (not authoritative): preserves Sentinel Engine domain terminology and unresolved concepts. Does not authorize implementation, migration, package movement, or architecture decisions. Conflicts and decisions remain governed by ADRs. |
| `docs/architecture/SENTINEL_ENGINE_PAPER_TRADING_BEHAVIORAL_CONTRACT_P0.md` | Non-binding working material (gitignored, per ADR-044): consolidates the Sentinel Engine's decision-formation capability into a paper-trading behavioral contract under the *current* Accepted governance model (ADR-047, ADR-048, ADR-049, ADR-050, `RiskManager.approve_buy()`). Introduces no new authority and is not Accepted; describes existing ratified behavior only. |
| `docs/architecture/*` (remaining files) | Gitignored working drafts (Phase 2A Gradio/mock-data decision-intelligence UI spec — a different "Phase 2A" than this migration's, see Terminology below). Not binding on `sentinel_engine/` or product-identity decisions. |
| `docs/platform/AARA_PLATFORM_ARCHITECTURE.md` | Long-term platform vision doc; its hierarchy diagram is the one ADR-007 cites as already-reconciled with this Authority doc (see ADR-007's Status Log). Aspirational product roster (CFO/Tax/Estate/Retirement) is not current scope until a PRD exists for each. |
| `docs/platform/AARA_PLATFORM_SHELL_ARCHITECTURE.md` | Authoritative for platform shell responsibilities — foundational, cited by `AARA_PLATFORM_USER_EXPERIENCE.md` and 3 other docs in this family. |
| `docs/products/AARA_PLATFORM_USER_EXPERIENCE.md` | Authoritative for platform shell UX and navigation, together with `AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md` (which explicitly extends its §2). |
| `docs/products/AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md` | Extends `AARA_PLATFORM_USER_EXPERIENCE.md` §2 — read as one continuous document with it, not a competing doc. |
| `docs/platform/AARA_NAVIGATION_MODEL_ARCHITECTURE.md` | Platform-level nav composition (Product > Workspace); shares an unresolved "visibility inheritance" question with the two Workspace Registration docs below — resolve once, reference from all three. |
| `docs/platform/AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md` | Refines, does not contradict, ADR-003's identity/access model. |
| `docs/platform/AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md` | Companion/prerequisite to Workspace Registration, one granularity level up. |
| `docs/platform/AARA_WORKSPACE_REGISTRATION_ARCHITECTURE.md` | Shares the open "visibility inheritance" question with Product Registration and Navigation Model above — same question, tracked in three places. |
| `docs/platform/AARA_WORKSPACE_ACTIVATION_ARCHITECTURE.md` | Analyzes the same missing "workspace entry resolver" gap as Workspace Entry Architecture below — read as one continuous document with it. |
| `docs/platform/AARA_WORKSPACE_ENTRY_ARCHITECTURE.md` | Names the missing workspace-entry-resolver component; Workspace Activation above adds the options analysis for the same gap. |
| `docs/platform/SENTINEL_INTELLIGENCE_ENGINE_ARCHITECTURE.md` | Broadest-scope vision-tier doc for the engine; best "start here" entry point, though its literal package layout is superseded by ADR-001 (see `SENTINEL_ENGINE_BOUNDARY_AND_API_CONTRACTS.md` row above). |
| `docs/platform/SENTINEL_ENGINE_SERVICE_ARCHITECTURE.md` | ~80% identical content to `SENTINEL_INTELLIGENCE_ENGINE_ARCHITECTURE.md`, written independently with no cross-references — merge candidate (see `docs/DOCUMENT_CONSOLIDATION_PLAN.md`); its unique API-contract and migration-map sections aren't covered elsewhere. |
| `docs/platform/SENTINEL_ENGINE_RUNTIME_FLOW.md` | Canonical for runtime lifecycle — the same content is independently restated in Service Architecture and Intelligence Engine Architecture; this should be the only copy. |
| `docs/platform/SENTINEL_ENGINE_GOVERNANCE_ARCHITECTURE.md` | Canonical for the governance layer (more depth than the master doc's summary section). |
| `docs/platform/SENTINEL_ENGINE_MEMORY_ARCHITECTURE.md` | Canonical for the memory layer — same pattern as Governance Architecture. |
| `docs/platform/SENTINEL_ENGINE_REASONING_ARCHITECTURE.md` | Canonical for the reasoning layer — same pattern. |
| `docs/platform/SENTINEL_ENGINE_EVENT_ARCHITECTURE.md` | Vision-tier event philosophy — distinct scope from the grounded `TRADING_INTELLIGENCE_EVENT_MODEL.md` (not a duplicate of it), but restates this family's master doc's event philosophy. |
| `docs/platform/SENTINEL_ENGINE_DEPLOYMENT_ARCHITECTURE.md` | Unique topic (deployment), no overlap found. |
| `docs/platform/SENTINEL_ENGINE_SECURITY_AND_PRIVACY_ARCHITECTURE.md` | Aspirational multi-tenant/multi-product security model. Distinct in scope from `docs/SECURITY.md`, which covers the concrete bot/dashboard system actually credentialed today. |
| `docs/platform/SENTINEL_ENGINE_AI_ORCHESTRATION_ARCHITECTURE.md` | Vision-tier; aspirational product roster (CFO/Tax/Estate/Retirement) not reflected in the real 2-product scope — needs review before being cited as current. |
| `docs/platform/SENTINEL_ENGINE_DATA_MODEL.md` | Vision-tier; verify its 8 domain objects against the real implemented `sentinel_engine/` contracts (ADR-066 etc.) before treating as authoritative. |
| `docs/platform/SENTINEL_ENGINE_PHASE1_DECISION_LIFECYCLE.md` | Only grounded, current-dated (2026-08-06) doc in this vision-tier set — an implementation contract against ADR-001's structure, not an implementation itself. |
| `docs/platform/PHASE_0_ARCHITECTURE_VALIDATION_REPORT.md` | Historical validation record for the `sentinel/` → `sentinel_engine/` archival (ADR-001, ADR-008) — a point-in-time snapshot, not a living document. |
| `docs/platform/TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md` | Package structure/dependency direction for `applications/trading_intelligence/`. |
| `docs/platform/TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md` | Cited as authority by 2 other docs in this family; contract design for read models against `sentinel_engine/` projections. |
| `docs/platform/TRADING_INTELLIGENCE_SENTINEL_READ_INTEGRATION_DESIGN.md` | Its recommended Option A is confirmed already implemented in `applications/trading_intelligence/adapters/sentinel_projection_decision_source.py`. Not the same decision as `TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md` above despite the near-identical name — that one is ownership, this one is read-path. |
| `docs/platform/WEALTH_INTELLIGENCE_BOUNDARY.md` | Records the Wealth Intelligence ↔ `sentinel_engine` ownership boundary, including relocations already completed and ratified (ADR-025). |
| `docs/products/AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` | Canonical PRD-tier document for Trading Intelligence (Product #1) — vision/scope/6-screen workspace anchor. |
| `docs/products/AARA_TRADING_INTELLIGENCE_MVP_SCOPE_DECISION.md` | Functions as a binding scope decision though filed among design docs — candidate for relocation into `docs/decisions/` as a numbered ADR (see `docs/DOCUMENT_CONSOLIDATION_PLAN.md`). |
| `docs/products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_CAPABILITY_MODEL.md` | Canonical rollup synthesizing the 5 capability-design docs below — deliberate layering, not duplication. |
| `docs/products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md` | Foundational screen design for the Decision Center — cited as authority by the other 4 capability-design docs. |
| `docs/products/AARA_TRADING_INTELLIGENCE_EVIDENCE_DESIGN.md` | One of the 5 capability-design docs synthesized by the Capability Model. |
| `docs/products/AARA_TRADING_INTELLIGENCE_GOVERNANCE_INTELLIGENCE_DESIGN.md` | Same; explicitly defers ADR-004 ledger ownership. |
| `docs/products/AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md` | Same; note the "Risk Intelligence" naming collision with the UI Specification doc's screen of the same name — a glossary/naming fix, not a merge. |
| `docs/products/AARA_TRADING_INTELLIGENCE_APPLICATION_COMPOSITION_DESIGN.md` | Composition/wiring detail; corrects two other docs found stale against real code. |
| `docs/products/AARA_TRADING_INTELLIGENCE_DEMO_RUNTIME_DESIGN.md` | Most recently written in this family; extends the Composition Design's gap list. |
| `docs/products/AARA_TRADING_INTELLIGENCE_MVP_EXPERIENCE_DESIGN.md` | Narrative/journey reference — MVP Scope Decision above is authoritative for the final scope; this doc restates it plus prose detail. |
| `docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` | Establishes the 6-screen Trading Intelligence structure every downstream design doc builds on. |
| `docs/products/AARA_TRADING_INTELLIGENCE_UI_IMPLEMENTATION_PLAN.md` | Frozen code-location decision (Option C), confirmed by real code in `applications/trading_intelligence/ui/`. |
| `docs/products/AARA_TRADING_INTELLIGENCE_UNITS_1_3_DATA_PROVISIONING_SCOPE_DECISION.md` | Scope decision for production data provisioning, Units 1–3. |
| `docs/products/AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` | Describes an aspirational product (Plaid aggregation, Wealth X-Ray/Map) with zero matching code — the shipped `applications/wealth_intelligence/` app is a minimal Decision-Center clone. Flagged for reconciliation, not authoritative as a current PRD until code catches up. |

*(Table expanded 2026-09-18 to individually name the ~38 `docs/platform/` and `docs/products/` files this table previously left unadjudicated — see `docs/DOCUMENT_CONSOLIDATION_PLAN.md` Phase 1.)*

## Product model (per CODEBASE_MIGRATION_MATRIX.md)

One shared Sentinel Intelligence Engine (`sentinel_engine/`), two products:

- **Product #1 — Aara Trading Intelligence**: medium-term investing intelligence,
  portfolio decisions, trade evaluation, risk management, paper trading validation,
  eventual broker integration. Not day trading, not auto-execution-as-identity, not
  market prediction as the product pitch. Architecture is defined across three
  documents rather than one consolidated file:
  `docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md` (ownership boundary),
  `TRADING_INTELLIGENCE_EVENT_MODEL.md` (event contract), and
  `TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md` (ledger options,
  decision deferred per ADR-004).
- **Product #2 — Aara Wealth Intelligence**: account aggregation, portfolio health,
  wealth X-Ray. Defined in `docs/products/AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`.
  Explicitly excludes trading/execution from its own MVP.

## Terminology

"Sentinel" is used for three different things in existing docs, which invites
ambiguity. Going forward:

- **Sentinel Intelligence Engine** — the platform layer (`sentinel_engine/`). Never
  "Sentinel" alone when precision matters.
- **Trading Intelligence** (Product #1) — a module/application consuming the engine.
  Never "Sentinel Trading Bot" — that phrasing anchors company identity to trading,
  which `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` and `CLAUDE_AARA_MIGRATION.md`
  both explicitly avoid.
- **Wealth Intelligence** (Product #2) — a second module/application consuming the
  same engine.

```
AARA Platform
  Sentinel Intelligence Engine
    Trading Intelligence Module
    Wealth Intelligence Module
    (future modules)
```

## Migration Status

**Date:** 2026-08-04

| Area | Status |
|---|---|
| Architecture reconciliation | COMPLETE |
| Runtime boundary analysis | COMPLETE |
| Production trading paths | PROTECTED (see ADR-002) |
| `sentinel_engine/` contracts (domain, events, evidence, governance, ledger, projections, repositories, services, adapters) | COMPLETE — 531 tests passing (was 82 at Phase 0 completion; count refreshed 2026-09-18, see `docs/TEST_STRATEGY.md`) |
| Phase 2A (Trading Intelligence boundary, event model, contract gap analysis, ledger integration options) | COMPLETE |
| Ledger ownership decision (Option A/B/C) | DEFERRED — see ADR-004, gated on Phase 1A completion |
| AARA identity/product-access model | REQUIREMENT RECORDED, IMPLEMENTATION DEFERRED — see ADR-003 |
| `applications/trading_intelligence/` + `applications/platform/` skeleton (contracts, projections, services, adapters, UI) | BUILT — not fed by `bot/`; one real, tested, one-way read dependency on `sentinel_engine/` via `adapters/sentinel_projection_decision_source.py`, not wired to a live backend (no concrete `ProjectionRepository` exists — see ADR-004) |
| Code extraction (`bot/` → `applications/trading_intelligence/`) | NOT STARTED — no `bot/` code moved, refactored, or import-changed (ADR-002 unchanged) |

**Next implementation phase:** Phase 3 — Product Development. Concrete ledger
storage adapters and bot integration adapters are explicitly **not** in Phase 3's
initial scope — per ADR-004, that work stays deferred until Phase 1A validation
completes and ADR-004's decision criteria are met. No `bot/`, `dashboard/`,
`scheduler/`, or workflow code has been moved, refactored, or had its imports
changed at any point in this process.

## Future Platform Capability Requirements

- AARA is a multi-product platform (Trading Intelligence, Wealth Intelligence, and
  future products sharing one Sentinel Intelligence Engine).
- Identity and product access is a future cross-platform capability — not specific
  to any one product.
- [ADR-003](../decisions/ADR-003-aara-identity-and-product-access.md) defines the
  requirement (roles, entitlements, workspace/capability separation).
- Implementation is intentionally deferred until product boundaries are finalized.
  No authentication, authorization, schema, or UI work exists yet for this
  requirement.

## Resolving future conflicts

A new document that conflicts with an existing authoritative doc does not silently
coexist with it. Write a new ADR under `docs/decisions/` that references both and states
which wins and why.
