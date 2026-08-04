# Trading Intelligence Application Architecture

**Status:** Internal architecture design — Phase 2C. Documentation only. No code
was created or modified — `applications/trading_intelligence/`'s existing
skeleton (created in the Phase 1 implementation milestone) was reviewed
read-only, not changed. `sentinel_engine/`, `bot/`, `dashboard/`, `scheduler/`,
`.github/workflows/`, `database/`, `ledger/` untouched, confirmed via `git
status` before and after.

**Authority:** ADR-001, ADR-002, ADR-004, `TRADING_INTELLIGENCE_BOUNDARY.md`,
`TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md`,
`AARA_TRADING_INTELLIGENCE_IMPLEMENTATION_ROADMAP.md`.

---

## 1. Application Responsibilities

| Responsibility | Concern | Where (per Section 2's resolution) |
|---|---|---|
| Presentation boundary | UI-facing screens (Morning Brief, Decision Center, etc. — per `AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`) | **Not represented in the existing skeleton at all.** No `ui/`/`presentation/` subpackage exists under `applications/trading_intelligence/`. Flagged as a real gap, not silently assumed — see Section 6. |
| Query/read boundary | Reading Sentinel Engine data (Decision/Evidence/Governance/Risk contracts, per `TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md`) | `services/` — resolved in Section 2 |
| Domain services | Internal Trading Intelligence logic (signal/screening, decision-orchestration, execution — per the implementation roadmap) | `services/` |
| Adapters | Write-direction translation: `bot/`-shaped data → `sentinel_engine` contracts (candidate/risk/execution/outcome, per `TRADING_INTELLIGENCE_EVENT_MODEL.md` Section 6) | `adapters/` — unchanged from the existing skeleton's README |
| Projections | Trading-Intelligence-specific read models — see Section 4 for why these differ from Sentinel's own `DecisionProjection` | `projections/` |
| Contracts | Trading-Intelligence-specific data contracts | `contracts/` |

## 2. Resolve Package Placement

**Option A** (`contracts/`, `adapters/`, `projections/`, `services/`) is the
structure already created in the Phase 1 implementation milestone.

**Evaluated against existing AARA architecture principles, not preference:**

- **Option A** — matches `sentinel_engine/`'s own naming convention almost
  directly (`projections`, `services`, `adapters` are the same words
  `sentinel_engine` uses for the same kinds of concerns). This consistency was
  the deciding factor when the skeleton was originally created, and remains the
  strongest principle available: `sentinel_engine` was explicitly built as the
  shared pattern other AARA products should follow (ADR-001's own reasoning:
  "cleaner isolation for multiple future products... consuming one shared
  engine"). A second product using the same capability-based naming as the
  engine it depends on is a real, existing architectural principle, not a
  stylistic preference.
- **Option B** (`readers/` replacing `adapters/`) — rejected. It silently drops
  the write-direction adapter concept (candidate/risk/execution/outcome
  translation, already named in `TRADING_INTELLIGENCE_EVENT_MODEL.md`) without
  providing a replacement location for it. A "readers/" folder solves the gap
  identified in `TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md` Section 1, but
  only by creating a different, equally real gap on the write side.
- **Option C** (`domain/`, `application/`, `infrastructure/`) — rejected. This
  is a generic layered-architecture pattern, but nothing else in this
  codebase uses it — not `sentinel_engine/` (capability-based: `domain/`,
  `events/`, `evidence/`, `governance/`, `ledger/`, `projections/`,
  `repositories/`, `services/`, `adapters/`), not `bot/` (also
  capability-based: `strategy/`, `execution/`, `capital/`, `risk/`,
  `trust_ledger/`). Introducing a third naming paradigm found nowhere else in
  the repository breaks the one consistency principle Option A upholds, for no
  documented architectural gain.

**Conclusion: Option A is correct and already exists — this document does not
create or change it.**

**Resolving the reader-placement gap within Option A** (the open question left
by `TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md` Section 1): a "reader" is a
narrowly-scoped read-only service. `sentinel_engine`'s own service layer already
mixes read and write concerns within single service classes (e.g.
`GovernanceService` has both `get_policy()` and `register_policy()`) — Trading
Intelligence's `services/` can hold both domain services and read/query
services (readers) the same way, with finer-grained internal organization
(e.g. a future `services/readers/` grouping) left as a naming detail, not a
top-level structural question. This does not require, and this document does
not propose, any change to the four existing top-level subpackages.

## 3. Dependency Direction

Unchanged, restated for completeness:

```
sentinel_engine
        |
        v
trading_intelligence
```

Never:

```
trading_intelligence
        |
        v
bot/
```

Already enforced today, not just documented — `applications/trading_intelligence/tests/test_package_imports.py`'s
AST-based check asserts no file under the package imports `bot`, `dashboard`, or
`scheduler`, and it currently passes because no such import exists (the package
has no implementation yet at all).

## 4. Future Read Flow

```
Sentinel Projection (DecisionProjection, sentinel_engine)
        |
        v
Reader Contract (services/, per Section 2 — e.g. TradingIntelligenceDecisionReader)
        |
        v
Trading Intelligence Projection (projections/ — UI-shaped, product-specific)
        |
        v
UI (presentation boundary — not yet represented, Section 1/6)
```

**Why a second projection layer exists at all:** per Section 5's ownership
split, "user-facing interpretation" belongs to Trading Intelligence, not
Sentinel Engine. Sentinel's `DecisionProjection` is a governance/audit-shaped
read model; Trading Intelligence's own `projections/` would hold whatever
UI-shaped reformatting or enrichment (e.g. combining Sentinel's decision data
with local portfolio context) the presentation layer actually needs. This is
why `applications/trading_intelligence/projections/` isn't redundant with
`sentinel_engine/projections/` — they serve different consumers.

## 5. Ownership

Unchanged from `TRADING_INTELLIGENCE_BOUNDARY.md`, restated for this document's
context:

**Sentinel owns:**
- Intelligence contracts (`Decision`, `Event`/`EventType`)
- Governance (`Policy`, `Approval`)
- Evidence (`Evidence`)
- Decisions (`DecisionProjection`)

**Trading Intelligence owns:**
- Product views (the second projection layer, Section 4)
- Workflows (internal domain services, Section 1)
- User-facing interpretation (presentation boundary, once it exists)

## 6. Unresolved Decisions

Carried forward, not resolved by this document:

- **Evidence cardinality** — `Decision.evidence_reference` (singular) vs.
  `EvidenceService.get_evidence_for_decision()` (list) — per
  `TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md` Section 2, still open.
- **Risk contract** — no `RiskEvaluation` dataclass exists in `sentinel_engine`;
  a shape was proposed (not implemented) in
  `TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md` Section 3.
- **Ledger backend** — Option A/B/C from
  `TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md`, deferred per
  ADR-004 until Phase 1A validation completes.
- **UI integration** — this document surfaced a new specific gap: no
  presentation/UI subpackage exists anywhere in
  `applications/trading_intelligence/` today (Section 1). Where and how the six
  screens from `AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` eventually attach
  to this structure is not decided here.

---

## Constraints Confirmed

No file under `applications/trading_intelligence/` or `sentinel_engine/` was
created or modified. Options B and C were evaluated and rejected with stated
architectural reasoning (Section 2), not chosen or dismissed by preference.
