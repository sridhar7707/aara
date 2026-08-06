# ADR-001: Sentinel Engine Package Structure

**Status:** Accepted
**Date:** 2026-08-04

## Context

Two committed documents describe conflicting shapes for the Sentinel Intelligence Engine:

- `docs/implementation/CODEBASE_MIGRATION_MATRIX.md` — `sentinel/` extracts into a new,
  separate top-level `sentinel_engine/` package (domain, events, evidence, governance,
  ledger, projections, repositories, services, adapters). `bot/` moves into a new
  top-level `applications/trading_intelligence/`.
- `docs/platform/SENTINEL_ENGINE_BOUNDARY_AND_API_CONTRACTS.md` — `sentinel/` becomes the
  engine in place, reorganized internally (`sentinel/core/`, `sentinel/reasoning/`,
  `sentinel/memory/`, ...) with a five-verb capability API
  (`analyze`/`explain`/`remember`/`evaluate`/`recommend`). `bot/` nests inside it as
  `sentinel/modules/market_intelligence/`.

Both were added in the same commit (`6d3e59b`) with no supersession marker between them.

Since that commit, `sentinel_engine/` has been built out following the
`CODEBASE_MIGRATION_MATRIX.md` model: `Decision`, `Event`, `EventType`, `Evidence`,
`Policy`, `Approval` contracts; `LedgerStore` and `ProjectionRepository` abstractions;
`DecisionService`, `EvidenceService`, `GovernanceService`; a `SentinelEngine` facade; a
`decision_adapter` boundary. 108 tests pass under `sentinel_engine/tests/`.

## Decision

`CODEBASE_MIGRATION_MATRIX.md` is the package-structure authority for the Sentinel
Intelligence Engine: a separate `sentinel_engine/` package, extracted from `sentinel/`,
independent of `bot/`, `dashboard/`, and `database/`.

`SENTINEL_ENGINE_BOUNDARY_AND_API_CONTRACTS.md` is reinterpreted, not discarded: its
five-verb model (`analyze`/`explain`/`remember`/`evaluate`/`recommend`) describes
capabilities that products call on the engine, not the engine's internal package layout.
Those verbs may later be implemented as a thin API surface on top of
`sentinel_engine`'s services — they do not override its module structure.

`CLAUDE_AARA_MIGRATION.md`'s "the product is a wealth intelligence system, not a trading
bot" is clarified by the same evidence: `CODEBASE_MIGRATION_MATRIX.md` explicitly splits
the platform into "Aara Trading Intelligence (Product #1)" and "Aara Wealth Intelligence
(Product #2)" sharing one engine. Trading is scoped out of Product #2's MVP, not out of
the platform. Product #1 has not yet had its own architecture document written.

## Consequences

- Continue extracting Sentinel capability into `sentinel_engine/` per
  `CODEBASE_MIGRATION_MATRIX.md`'s Phase 2 order (events, ledger, evidence, governance,
  projections, reasoning — see `docs/implementation/SENTINEL_EXTRACTION_PLAN.md`).
- `bot/`, `dashboard/`, `database/` are not touched by this decision; their eventual move
  into `applications/trading_intelligence/` is a separate, later migration phase.
- Any future document proposing a different `sentinel_engine/` package shape must address
  this ADR, not silently coexist with it.

## Rejected Alternative

Reorganize `sentinel/` in place per `SENTINEL_ENGINE_BOUNDARY_AND_API_CONTRACTS.md`,
discarding the `sentinel_engine/` package. Rejected because it would discard 8 phases of
already-built, tested code with no functional gain, and because
`CODEBASE_MIGRATION_MATRIX.md`'s separate-package model gives cleaner isolation for
multiple future products (Trading Intelligence, Wealth Intelligence, CFO Intelligence)
consuming one shared engine.
