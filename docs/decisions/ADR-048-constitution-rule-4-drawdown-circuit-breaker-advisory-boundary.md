# ADR-048 — Constitution Rule 4 — Portfolio Drawdown Circuit Breaker Advisory Boundary (Phase-1A)

**Status:** Accepted
**Date Proposed:** 2026-08-24
**Decision Type:** Architecture / Governance — Behavioral Ratification
**Related ADRs:** ADR-002, ADR-010, ADR-047

---

## Context

`bot/trust_ledger/constitution.py`'s Rule 4 ("Portfolio Drawdown Circuit Breaker") is existing, shipped, ADR-002-protected Phase-1A behavior, structurally analogous to Rule 1 (ratified by ADR-047). A read-only evidence gate re-verified this behavior directly against the live implementation and its tests: the drawdown state Rule 4 evaluates is read from a single `RiskManager` attribute, with no method call and no assignment anywhere in the rule's code path; the sole call site of `constitution.check_and_log()` (`bot/_main_trust_decisions.py`) runs after the decision write, with its return value discarded; and three dedicated tests (`tests/phase1a/test_constitution.py`) exercise the no-drawdown, warning, and critical branches.

`ADR-010` (Accepted — FRED Macro Failure Handling) independently states, in its own analysis of Phase 1A's control landscape: *"every other blocking control (`RiskManager.halted`/daily-loss/portfolio-drawdown) is reactive, triggered only after a realized loss; Constitution Rules 1 and 4 are advisory-only in Phase 1A and block nothing."* This is corroborating evidence, from an already-Accepted ADR written independently of this one, for the exact advisory-only characterization ratified below.

The evidence gate also established a distinction that must not be lost: Rule 4's drawdown computation reads `RiskManager.portfolio_high` directly and compares it against locally-defined threshold constants inside `constitution.py`. This is **independent** of `RiskManager.approve_buy()`'s own blocking drawdown check (`check_portfolio_drawdown()`), which uses a separately configured, live-adjustable threshold. These are two distinct computations, not the same check observed twice, and this ADR does not conflate them.

This ADR is a deliberate ratification of the currently verified Phase-1A behavior. It recognizes and deliberately stabilizes an existing implementation invariant. It does not introduce a new runtime design, and it does not claim this behavior was previously ratified in full by any prior document.

---

## Decision

The following three-part behavioral contract is ratified as an architectural invariant:

### 1. Observation, Not Ownership

Constitution Rule 4 observes portfolio-drawdown-relevant risk state without mutating that state, underlying `RiskManager` enforcement state, or authoritative write paths.

The source, representation, and specific threshold values of that state remain implementation details unless separately ratified. This ADR does not claim that `RiskManager` owns all risk state in the system.

### 2. Advisory-Only Escalation, Unscoped by Action

When Rule 4's evaluated drawdown condition is elevated or critical, Rule 4 produces an advisory-only Constitution escalation, regardless of the decision's action. Unlike Rule 1 (ADR-047), this invariant is not limited to `BUY` — Rule 4 evaluates identically for every decision action.

### 3. No Independent Veto

Rule 4 does not independently veto or block execution, for any decision action or drawdown condition.

The real, independent drawdown-based execution block remains `RiskManager.approve_buy()`'s own call to `check_portfolio_drawdown()`. That check uses a separately configured, live-adjustable threshold and is not the same computation Rule 4 performs. This ADR does not imply that Rule 4 and `approve_buy()`'s drawdown check share thresholds, mechanism, or computation.

---

## Verified Scope

- This contract covers Rule 4 ("Portfolio Drawdown Circuit Breaker") only.
- Rule 4's predicate applies to every decision action — this ADR does not narrow or characterize that scope beyond what is already implemented.
- This contract does not characterize or ratify Constitution Rules 1, 2, 3, 5, or 6. Rule 1 is separately governed by ADR-047; none of Rules 2, 3, 5, or 6 are addressed here.

---

## Explicit Non-Goals / Non-Claims

This ADR does not:

1. Freeze the specific drawdown threshold values used by Rule 4, or any other numeric constant, as architectural vocabulary.
2. Freeze any state label, helper/function name, or internal representation used to compute or express Rule 4's drawdown condition.
3. Claim or imply that Rule 4's drawdown computation shares a threshold, mechanism, or computation with `RiskManager.approve_buy()`'s own blocking drawdown check.
4. Characterize Constitution Rules 1, 2, 3, 5, or 6 in any way. Rule 1 remains governed exclusively by ADR-047.
5. Establish a general, cross-product Risk Governor architecture.
6. Authorize any code, schema, test, or configuration change.
7. Create an ADR-002 exception — no code change is authorized, so none is needed.
8. Alter, amend, or reinterpret ADR-010. This ADR is consistent with, and corroborated by, ADR-010's own characterization of Rule 4, but does not modify ADR-010's text, status, or subject matter (FRED/macro failure handling).
9. Alter, amend, or reinterpret ADR-047.
10. Modify `DOCUMENT_INDEX.md`, `DOCUMENT_GOVERNANCE_MATRIX.md`, `AARA_ARCHITECTURE_AUTHORITY.md`, or any `docs/architecture/*` file.
11. Claim this behavior was previously ratified in full by any prior document — ADR-010 corroborates the advisory-only characterization as scene-setting context within a different ADR's subject matter; this is the first dedicated, binding record of Rule 4's own boundary.

---

## Relationship to ADR-010

ADR-010 (Accepted) independently characterizes Constitution Rules 1 and 4 as "advisory-only in Phase 1A" and states they "block nothing," as part of its own analysis of Phase 1A's blocking-vs-reactive control landscape. This ADR is consistent with, and corroborated by, that characterization for Rule 4 specifically. This ADR does not modify, amend, or depend on ADR-010's own subject matter; it cites ADR-010 only as independent supporting evidence for the invariant ratified here.

---

## Evidence

- `bot/trust_ledger/constitution.py` — Rule 4 predicate (`_rule_drawdown_circuit_breaker`), which reads `risk.portfolio_high` via plain attribute access (no method call) and compares it against locally-defined threshold constants.
- `bot/risk/risk_manager.py` — `update_portfolio_high()` (the only method that ever sets `portfolio_high`, never called by Rule 4) and `approve_buy()` (which calls `check_portfolio_drawdown()` — the separate, real blocking drawdown check, using a distinct, live-adjustable threshold).
- `bot/_main_cycle.py` — the real BUY-blocking risk gate (`risk.approve_buy()`), independent of and unaffected by Constitution.
- `bot/_main_trust_decisions.py` — the sole call site of `constitution.check_and_log()`, called after the decision write, with its return value discarded.
- `tests/phase1a/test_constitution.py` — `test_rule_4_passes_with_no_drawdown`, `test_rule_4_escalates_at_warning_drawdown`, `test_rule_4_escalates_at_critical_drawdown`.
- `ADR-002` — establishes the protected-file boundary this ADR does not exercise an exception against.
- `ADR-010` — independent corroborating characterization of Rule 4 as advisory-only and blocking nothing.
- `ADR-047` — the structurally analogous ratification for Rule 1, followed here for Rule 4 without characterizing Rule 1 itself.

---

## Consequences

**Positive:**
- Closes a previously undocumented governance gap for Rule 4 with a precise, citable record, mirroring ADR-047's treatment of Rule 1.
- Explicitly documents the independence between Rule 4's advisory computation and `approve_buy()`'s real blocking drawdown check, preventing a future reader from conflating the two.
- Zero implementation risk: no code is authorized, moved, or changed by this ADR.

**Negative / Limitation:**
- Does not extend protection or clarity to Constitution Rules 1, 2, 3, 5, or 6.
- Does not establish a general "Risk Governor" or drawdown-monitoring architecture for `sentinel_engine/` or any other product surface.
- Leaves the specific threshold values, and the question of whether Rule 4's and `approve_buy()`'s drawdown checks should ever be reconciled into one computation, entirely open for separate future governance.

---

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-08-24
**Accepted By:** Architecture Owner
