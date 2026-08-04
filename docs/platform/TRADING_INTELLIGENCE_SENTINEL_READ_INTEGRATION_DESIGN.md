# Trading Intelligence ↔ Sentinel Engine Read Integration Design

**Status:** Design — Phase 3B. Documentation only. No code was created or
modified. `sentinel_engine/`, `applications/trading_intelligence/`, `bot/`,
`dashboard/`, `scheduler/`, `.github/workflows/`, `database/`, `ledger/`
untouched, confirmed via `git status` before and after.

**Authority:** ADR-001, ADR-002, ADR-004, `TRADING_INTELLIGENCE_BOUNDARY.md`,
`TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md`,
`TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md`,
`AARA_TRADING_INTELLIGENCE_IMPLEMENTATION_ROADMAP.md`.

**Naming note to avoid confusion:** this document's Options A-D (Section 2) are
about *how Trading Intelligence reads from Sentinel Engine* — a different, later
decision from ADR-004's own Option A/B/C, which is about *which system owns the
ledger*. The two are orthogonal. This document does not touch ADR-004's
decision.

---

## 1. Current State

- **`sentinel_engine.domain.decision.Decision`** — frozen dataclass:
  `decision_id`, `symbol`, `action`, `timestamp`, `confidence`,
  `evidence_reference`, `risk_reference`.
- **`DecisionProjection`** — the read-model layer: `Decision`'s fields plus
  `status`, `updated_at`.
- **`ProjectionRepository(ABC)`** — abstract `save`/`get`. No backend
  implementation exists anywhere in the codebase.
- **`LedgerStore(ABC)`** — abstract `append`/`read_all`. No backend
  implementation exists anywhere in the codebase.
- **Current absence of backend wiring:** all 82 `sentinel_engine` tests run
  against in-memory fakes. Zero real data flows through `sentinel_engine`
  today, in either direction.
- **Also relevant:** `applications/trading_intelligence/` now has
  `DecisionContract`, `DecisionView`, and `DecisionQueryService` with an
  abstract `DecisionSource` (built in the prior milestone). `DecisionSource`
  has no concrete implementation — nothing wires it to `sentinel_engine` yet.
  This document is about designing that missing concrete implementation, not
  building it.

## 2. Integration Options

### Option A: Trading Intelligence directly consumes `ProjectionRepository`

A concrete `DecisionSource` implementation wraps a `ProjectionRepository`
instance directly, calling `.get(decision_id)` and converting the returned
`DecisionProjection` into a `DecisionContract`.

- **Benefits:** requires zero new `sentinel_engine` code — `ProjectionRepository`
  already has the exact right shape. Smallest possible integration surface.
- **Risks:** couples Trading Intelligence's `DecisionSource` implementation to
  `sentinel_engine`'s internal repository API — if that abstraction's shape
  changes, this adapter changes too.
- **Dependency impact:** direct in-process import, `trading_intelligence ->
  sentinel_engine`, matching the already-established allowed direction exactly.
- **Rollback difficulty:** low — reverting means deleting/replacing one adapter
  class; `DecisionQueryService`/`DecisionContract`/`DecisionView` are
  unaffected either way.
- **Compatibility with ADR-004:** the design itself is compatible — it doesn't
  presuppose any particular backend, since `ProjectionRepository` is already
  backend-agnostic by construction (ADR-001). It's only unusable *with real
  data* until ADR-004's backend decision is made — but the same is true of
  every option below.

### Option B: Sentinel exposes a read service/API consumed by Trading Intelligence

A new `sentinel_engine`-side read-service layer (in-process service class, or a
network API) sits between `ProjectionRepository` and any consumer, including
Trading Intelligence.

- **Benefits:** decouples consumers from `sentinel_engine`'s internal
  repository details; a single interface could later serve Wealth Intelligence
  too, matching the platform's "one engine, many products" model.
- **Risks:** requires building a new component that doesn't exist today; if
  implemented as a network API, adds latency/availability concerns not present
  in an in-process call.
- **Dependency impact:** still one-way, but through a narrower, purpose-built
  interface — better isolation, at the cost of new `sentinel_engine` code.
- **Rollback difficulty:** medium — a new `sentinel_engine`-side component
  needs to exist and be reverted too, not just a Trading-Intelligence-side
  adapter.
- **Compatibility with ADR-004:** ambiguous. A pure in-process read-API
  wrapping the already-existing `ProjectionRepository` (no new storage
  decision) arguably doesn't touch what ADR-004 defers — but this is a
  judgment call, not a clear yes, since ADR-004's exact scope wasn't written
  with this option in mind.

### Option C: Sentinel exports immutable snapshots consumed by Trading Intelligence

Periodic export of `DecisionProjection` data (e.g. to files) that Trading
Intelligence reads independently, with no live coupling.

- **Benefits:** maximum decoupling — no runtime dependency between the two
  systems; easiest option to reason about for an audit-style, air-gapped read
  pattern.
- **Risks:** staleness (only as fresh as the last export); requires building
  export *and* import tooling, neither of which exists — the most new
  infrastructure of the four options.
- **Dependency impact:** weakest coupling of the four; Trading Intelligence
  might not even need `sentinel_engine` as a runtime import, only its contract
  shapes for deserialization.
- **Rollback difficulty:** very low — snapshots are just files; stopping the
  export job has no ripple effect.
- **Compatibility with ADR-004:** highest of the four — doesn't require any
  particular backend to exist at all; could even be prototyped against an
  in-memory/test backend without touching the real ledger-ownership question.

### Option D: Trading Intelligence builds its own projection from Sentinel events

Trading Intelligence reads raw `Event`/`EventType` history via
`LedgerRepository.get_events()` and derives its own decision state, instead of
consuming `DecisionProjection`.

- **Benefits:** full control over Trading Intelligence's own read-model shape;
  could diverge from Sentinel's own projection logic if product needs differ.
- **Risks:** duplicates projection-building logic that already exists in
  `sentinel_engine.services.decision_service`, with a real risk of the two
  drifting out of sync; requires correctly interpreting raw event semantics
  rather than consuming an already-built projection — the highest-effort,
  highest-risk option.
- **Dependency impact:** broader read surface than the other three —
  `get_events()` returns the *entire* ledger, unfiltered (the same
  over-exposure concern already flagged in
  `TRADING_INTELLIGENCE_SENTINEL_READ_MODEL_ANALYSIS.md` Section 1).
- **Rollback difficulty:** medium-high — Trading Intelligence's own
  projection-building logic becomes real business logic to maintain.
- **Compatibility with ADR-004:** same fundamental blocker as Option A —
  needs a `LedgerStore` backend to exist for real event data.

## 3. Recommended Direction

**Option A.** Reasoning, not a decision to implement:

- Requires zero new `sentinel_engine` code, consistent with this session's
  running principle of not inventing infrastructure beyond what's needed.
- `ProjectionRepository` is already explicitly backend-agnostic (ADR-001) — so
  Option A doesn't lock Trading Intelligence into any particular backend
  choice, only into the stable, already-built, already-tested abstraction.
- Lowest rollback difficulty among the three options that actually deliver
  live data (C is lower, but requires building export infrastructure that
  doesn't exist).
- Fits the `DecisionSource(ABC)` pattern already built in the prior milestone
  exactly as designed — a concrete implementation (e.g.
  `SentinelProjectionDecisionSource`) would simply wrap a `ProjectionRepository`
  and implement `get_decision()`. No redesign of anything already shipped.

Option C remains worth keeping in mind as a lower-coupling alternative if
operational requirements (e.g. wanting Trading Intelligence to run
independently of `sentinel_engine`'s runtime) become important later — not
ruled out, just not recommended as the default.

**This is a recommendation, not an implementation. Nothing was built.**

## 4. Future Read Flow

```
Sentinel decision creation
   (sentinel_engine.services.DecisionService.create_decision)
        |
        v
Sentinel projection
   (ProjectionRepository.save() / .get() -> DecisionProjection)
        |
        v
Trading Intelligence read contract
   (a future concrete DecisionSource, e.g. SentinelProjectionDecisionSource,
    per Option A -- converts DecisionProjection -> DecisionContract)
        |
        v
DecisionQueryService
   (applications/trading_intelligence/services/decision_query_service.py --
    already built, already tested against a fake source)
        |
        v
UI
   (not yet built -- no presentation/UI subpackage exists, per
    TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md Section 6)
```

## 5. Ownership Boundaries

Unchanged from `TRADING_INTELLIGENCE_BOUNDARY.md`/`TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md`:

**Sentinel owns:** decisions, evidence, governance, audit concepts.

**Trading Intelligence owns:** investor presentation, workflows, user
experience, product-specific views.

## 6. Blockers

- **Ledger backend decision** — ADR-004's Option A/B/C, deferred until Phase 1A
  validation completes.
- **Risk contract** — no `RiskEvaluation` dataclass exists in `sentinel_engine`
  (per `TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md` Section 3); a
  `TradingIntelligenceRiskReader`-equivalent cannot be built until this exists.
- **Evidence cardinality** — `Decision.evidence_reference` (singular) vs.
  `EvidenceService.get_evidence_for_decision()` (list), still unresolved.
- **Authentication/authorization** — ADR-003 remains "Implementation Deferred";
  no mechanism exists to gate who can query any of this.
- **UI integration** — no presentation/UI subpackage exists in
  `applications/trading_intelligence/` today.

## 7. First Future Implementation Milestone

A concrete `SentinelProjectionDecisionSource` implementing `DecisionSource`
(Option A), tested against an in-memory `ProjectionRepository` fake — exactly
the pattern `sentinel_engine`'s own 82 tests and the prior
`DecisionQueryService` tests already use.

- **Read-only:** only calls `ProjectionRepository.get()`, never `.save()`.
- **Reversible:** one new class; deleting it removes the entire change.
- **No `bot/` changes:** doesn't touch, import, or depend on `bot/` in any way.
- **No `dashboard/` changes:** doesn't touch, import, or depend on `dashboard/`
  in any way.

**Worth noting explicitly:** because this milestone can be fully tested
against a fake `ProjectionRepository` (no real backend required), it doesn't
technically depend on ADR-004's Phase 1A gate the way a *production* Sentinel
backend would. That does not make it pre-authorized by this document — like
the prior implementation milestone, it would need its own explicit go-ahead
before any code is written.

---

## Constraints Confirmed

No file under `sentinel_engine/` or `applications/trading_intelligence/` was
created or modified. This document is design and recommendation only.
