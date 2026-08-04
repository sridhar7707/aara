# AARA Trading Intelligence Implementation Roadmap

**Status:** Future execution roadmap — documentation only. No code was written,
no directory was created, no protected path was touched. This document contains
no task that implies immediate execution — every future step is stated as a
future planned phase, a candidate implementation sequence, or something that
requires approval before execution.

**Respects:** ADR-002 (`bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`
remain frozen until a future ADR explicitly lifts restrictions) and ADR-004
(ledger ownership, storage adapters, and bot integration adapters remain
deferred until Phase 1A's 30-day validation window completes — as of this
document, roughly 7 of 30 days have elapsed).

**Builds on:** `AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`,
`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`,
`TRADING_INTELLIGENCE_EVENT_MODEL.md`,
`TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md`, ADR-002, ADR-004.

---

## 1. Can Document Now

Architecture direction, future application boundaries, future interfaces, and
future migration sequence — describable today without touching any protected
path or writing any code.

- **Future application boundary concept** — `applications/trading_intelligence/`
  as a target namespace, per `CODEBASE_MIGRATION_MATRIX.md`/ADR-001. Its intended
  purpose (housing signal generation, execution, capital, risk, orchestration
  once moved) is already documented in
  `AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` Section 6. This roadmap
  does not add a new boundary definition beyond what already exists.
- **Future internal service concepts** — the shape of services Trading
  Intelligence would eventually expose internally (a signal/screening service, a
  decision-orchestration service, an execution service), conceptually parallel to
  `sentinel_engine`'s existing `DecisionService`/`EvidenceService`/
  `GovernanceService` pattern. Naming this pattern is documentation; building it
  is not part of this roadmap.
- **Future read-only adapter interfaces** — `TRADING_INTELLIGENCE_EVENT_MODEL.md`
  Section 6 already named four future adapters (candidate, risk, execution,
  outcome) beyond the existing `decision_adapter`. Describing their conceptual
  input/output shape (bot-side data in, `sentinel_engine` contract out) is
  documentable now; their concrete field-level design remains open per that
  document's own "explicitly left open" list.
- **Future UI-to-data connection sequence** — `AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`
  Section 4 already classifies each screen's data readiness (available today /
  available later / mock-future). Describing a candidate order in which screens
  could connect to real vs. adapter-mediated data is documentable now (Section 4
  below); actually connecting anything is not.
- **Candidate migration sequence** — an ordering of future steps (Section 4
  below), explicitly not an execution schedule.

## 2. Requires Future ADR Approval

None of the following is authorized by this document. Each requires a dedicated,
scoped ADR before any execution begins, per ADR-002's "Lifting This Protection"
checklist (named modules, isolated branch/worktree, workflow updates in the same
change, full regression pass, stated rollback plan, both known trading-trigger
paths verified):

- Any `bot/` extraction (moving `bot/strategy/`, `bot/capital/`, `bot/risk/`,
  `bot/execution/`, `bot/trust_ledger/`, or any `bot/` submodule into
  `applications/trading_intelligence/` or anywhere else).
- Any `dashboard/` change (per `DASHBOARD_DEPENDENCY_REDUCTION_PLAN.md`'s three
  undecided options — facade, Sentinel-projection-backed, or deferred).
- Any `.github/workflows/*.yml` change (required in lockstep with any `bot/`
  path change, per ADR-002).
- Execution migration (`bot/execution/` — the highest-risk single area per
  `BOT_EXTRACTION_CANDIDATES.md`, requiring its own dedicated, isolated
  migration, not a bundled step with anything else in this roadmap).
- Ledger ownership changes (selecting Option A, B, or C from
  `TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md` — remains
  unselected).

## 3. Blocked by Phase 1A Validation

Per ADR-004, the following cannot be scheduled — not merely "requires an ADR,"
but explicitly gated on Phase 1A's 30-day live-validation window completing
first, plus ADR-004's other criteria (event-model open questions resolved, a
dry run against real `trust_ledger` data, a written rollback plan, clarity on a
second product's timeline):

- Production integration of any adapter against real `bot/trust_ledger` data.
- Any storage decision for `sentinel_engine/ledger/`'s `LedgerStore` backend.
- Any runtime migration touching the live trading path (either the CLI entry
  point via `trade.yml`, or the `scheduler`-mediated HTTP entry point via
  `watchdog.yml` → `/run/cron` — both must be considered, per ADR-002's
  two-entry-point finding).

## 4. Candidate Implementation Sequence

**A future planned phase ordering — not an execution schedule.** Every item
below requires approval before execution, and several are additionally blocked
by Phase 1A per Section 3.

1. **Future planned phase:** Define `applications/trading_intelligence/`
   package boundary in detail (module layout, what moves where). *Requires
   approval before execution* — needs its own ADR per Section 2.
2. **Future planned phase:** Design internal service interfaces (candidate
   sequence: signal/screening service, then decision-orchestration service, then
   execution service — mirroring the order `sentinel_engine`'s own services were
   built in). *Requires approval before execution.*
3. **Future planned phase:** Design the four remaining adapters (candidate,
   risk, execution, outcome) at the field level, resolving
   `TRADING_INTELLIGENCE_EVENT_MODEL.md`'s open questions first. *Requires
   approval before execution*, and any step that touches real `bot/trust_ledger`
   data is additionally *blocked by Phase 1A validation* (Section 3).
4. **Future planned phase:** Plan which UI screens connect to which data source
   first, using `AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`'s readiness
   tiers as the starting point (e.g., screens already classified "available
   today" would not need to wait on adapter work; screens classified
   "mock/future" would). *Requires approval before execution.*
5. **Future planned phase:** Plan `dashboard/` dependency reduction execution,
   selecting among `DASHBOARD_DEPENDENCY_REDUCTION_PLAN.md`'s three options.
   *Requires approval before execution* — ADR-002 applies directly.
6. **Future planned phase:** Plan execution-path integration (`bot/execution/`).
   *Requires approval before execution*, ordered last given it carries the
   highest risk of any item in this sequence.

No item above is authorized to begin by this document. This section documents a
candidate order only.

---

## Summary

This roadmap adds no new architectural decisions beyond what
`AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`,
`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`, ADR-002, and ADR-004 already
established. It exists to give future execution a documented order to reference,
without pre-authorizing any of it.
