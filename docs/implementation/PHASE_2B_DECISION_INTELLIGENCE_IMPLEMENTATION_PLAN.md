# AARA Phase 2B — Decision Intelligence Implementation Plan

**Status:** Planning only. No code created or modified — confirmed via
`git status` before and after this document was written. This plan does
not authorize implementation of any phase below; any change touching an
[ADR-002](../decisions/ADR-002-bot-runtime-protection.md) protected path
still requires its own ADR, per the precedent set by
[ADR-006](../decisions/ADR-006-confidence-integrity-phase1-exception.md).

---

## 1. Purpose

Phase 2A closed with a governance freeze: protected execution paths
(`bot/`, `dashboard/`, `scheduler/`, `database/`, `ledger/`, and all
workflow YAMLs) are locked under ADR-002, and the Trading Constitution's
rules are enforced and logged at every decision point.

Phase 2B's objective is to build **decision intelligence** on top of that
frozen foundation — the capability to score a decision, aggregate the
evidence behind it, reason about confidence, and generate a
human-readable explanation — without introducing any new path to
autonomous execution. Phase 2B adds *reasoning about* decisions; it does
not change *how* decisions get executed, and it does not touch the Risk
Governor's authority.

Human-governed decision making is preserved throughout: every artifact
Phase 2B produces is intelligence for a human reviewer (or a future,
separately-approved Decision Center), never a standalone trigger for
capital movement.

## 2. Architecture Boundary

**Allowed in Phase 2B:**

- `bot/decision_engine/` new package creation
- decision scoring
- evidence aggregation
- confidence reasoning
- explanation generation
- decision lifecycle modeling
- tests

**Not allowed in Phase 2B:**

- automatic trade execution
- broker order changes
- changing Risk Governor behavior
- modifying ledger schemas unless separately approved
- modifying bot execution flow
- changing existing strategy behavior

## 3. Decision Intelligence Architecture

All new code lives under `bot/decision_engine/`, a new, isolated package.
**No files listed below are created in this phase's planning commit** —
this section defines the target shape for the implementation phases that
follow, each under its own future approval.

Expected future modules:

- **`decision_engine.py`** — orchestrates decision evaluation.
- **`decision_state.py`** — `DecisionState` lifecycle model.
- **`evidence.py`** — evidence collection and normalization.
- **`confidence.py`** — confidence calculation and calibration.
- **`explanation.py`** — human-readable reasoning generation.
- **`decision_context.py`** — immutable context passed into evaluation.

## 4. Data Flow

```
Market Data
      |
      v
Existing Strategy Signals
      |
      v
Decision Engine
      |
      +--> Evidence
      +--> Confidence
      +--> Explanation
      |
      v
Human Review / Decision Center
```

The Decision Engine produces recommendations and intelligence. It does
not execute trades. Existing strategy signals (`bot/strategy/`) are a
read-only input to the Decision Engine, not a component it modifies.

## 5. Testing Strategy

Unit tests are written and passing before any integration work begins.

**Required test layers**, under `tests/decision_engine/`:

- decision state transitions
- confidence calculation
- evidence aggregation
- explanation consistency
- deterministic behavior

Integration tests — wiring the Decision Engine to real, live strategy
output — come later, once the unit layer above is stable, and are scoped
separately from Phase 2B.1/2B.2.

## 6. ADR Compliance

Phase 2B starts with **additive isolation**: a new package with no
imports into protected paths, so it can proceed without requiring an
ADR-002 exception of its own.

- **[ADR-002](../decisions/ADR-002-bot-runtime-protection.md)** — protected
  paths (`bot/` outside the new `bot/decision_engine/` package,
  `dashboard/`, `scheduler/`, `database/`, `ledger/`,
  `.github/workflows/*.yml`) remain frozen. Phase 2B claims no exception
  to this ADR.
- **Phase 0 ledger freeze** — `ledger/` schema and tables are not
  modified by Phase 2B. Any future need to write Decision Engine output
  to the Trust Ledger requires its own, separately-approved schema
  change, following the same additive-only precedent ADR-006 already
  established for Confidence Integrity Phase 1.
- **Phase 1 confidence integrity foundation** — Phase 2B's `confidence.py`
  module consumes the confidence calculation and Shadow Mode read-only
  pattern already specified by the Confidence Integrity Implementation
  Plan; it does not redefine or fork that calculation.

## 7. Implementation Sequence

**Phase 2B.1** — Create isolated `decision_engine` package.

**Phase 2B.2** — Add unit tests.

**Phase 2B.3** — Connect read-only data sources.

**Phase 2B.4** — Expose decision intelligence to UI.

**Phase 2B.5** — Evaluate production readiness.

**Constraints, all phases:**

- Do not touch `bot/main.py`
- Do not touch `ledger/`
- Do not touch `scheduler/`
- Do not touch `.github/workflows/`
- Do not touch broker execution code
