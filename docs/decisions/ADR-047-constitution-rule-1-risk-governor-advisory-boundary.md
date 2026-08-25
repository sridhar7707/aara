# ADR-047 — Constitution Rule 1 — Risk-Governor Advisory Boundary (Phase-1A)

**Status:** Accepted
**Date Proposed:** 2026-08-24
**Decision Type:** Architecture / Governance — Behavioral Ratification
**Related ADRs:** ADR-002, ADR-010

---

## Context

`bot/trust_ledger/constitution.py`'s Rule 1 ("Risk Governor Authority") is existing, shipped, ADR-002-protected Phase-1A behavior. A read-only governance audit found no Accepted ADR and no authoritative Tier-3 document addressing the relationship between Constitution and risk state in any form — the behavior exists only as implementation, with no binding governance record.

A subsequent, independently-run evidence gate re-verified this behavior directly against the live implementation and its tests: the risk state Rule 1 consumes is produced through calls confirmed non-mutating; the sole call site of `constitution.check_and_log()` (`bot/_main_trust_decisions.py`) runs after the decision write and after the real BUY-blocking risk gate has already executed, and its return value is discarded; and a dedicated regression test (`tests/phase1a/test_constitution.py::test_rule_1_does_not_mutate_risk_manager_state`) already guards the read-only property at the test level.

Separately, `ADR-010` (Accepted — FRED Macro Failure Handling) independently states, in its own analysis of Phase 1A's control landscape: *"every other blocking control (`RiskManager.halted`/daily-loss/portfolio-drawdown) is reactive, triggered only after a realized loss; Constitution Rules 1 and 4 are advisory-only in Phase 1A and block nothing."* This is corroborating evidence, from an already-Accepted ADR written independently of this one, for the exact advisory-only characterization ratified below.

This ADR is a deliberate ratification of the currently verified Phase-1A behavior. It recognizes and deliberately stabilizes an existing implementation invariant. It does not introduce a new runtime design, and it does not claim this behavior was previously ratified by any prior document.

---

## Decision

The following three-part behavioral contract is ratified as an architectural invariant:

### 1. Observation, Not Ownership

Constitution Rule 1 observes the risk-governor state relevant to its evaluation without mutating that state, underlying risk-management enforcement state, or authoritative write paths.

The source and representation of that state remain implementation details unless separately ratified. This ADR does not claim that `RiskManager` owns all risk state in the system.

### 2. Advisory-Only Escalation

For a qualifying new BUY decision, when the consumed risk state indicates an elevated or critical condition, Rule 1 produces an advisory-only Constitution escalation.

`WARNING`/`DEFENSIVE` may be mentioned only as the current implementation representation of that condition. Those labels are not frozen as architectural vocabulary.

### 3. No Independent Veto

Rule 1 does not independently veto or block execution for the BUY condition it evaluates.

The existing execution-blocking BUY gate remains `RiskManager.approve_buy()`, exercised prior to and independently of Constitution.

---

## Verified Scope

- The executable Rule 1 predicate is literal `action == "BUY"`.
- `INCREASE_SIZE` is **not** included in this architectural contract — it appears only in a test docstring, not in the executable predicate, and is explicitly excluded.
- This contract is not broadened to any action other than `BUY`.
- This contract does not characterize or ratify Constitution Rules 2–6.

---

## Explicit Non-Goals / Non-Claims

This ADR does not:

1. Freeze `_read_only_governor_state()`, or any other implementation function or class name, as an architectural symbol.
2. Freeze `WARNING`/`DEFENSIVE` as an API or architectural vocabulary.
3. Adopt, revive, or depend on `sentinel_engine`'s archived `RiskGovernorState` concept.
4. Ratify `docs/architecture/TRADING_CONSTITUTION.md`'s broader "No automatic execution" statement as live, currently-enforced Phase-1A behavior.
5. Characterize Constitution Rules 2–6 in any way.
6. Establish a general, cross-product Risk Governor architecture.
7. Authorize any code, schema, test, or configuration change.
8. Create an ADR-002 exception — no code change is authorized, so none is needed.
9. Resolve Q1 (Bot → Sentinel decision lineage) or Q2 (Audit Trail derived views).
10. Modify `DOCUMENT_INDEX.md`, `DOCUMENT_GOVERNANCE_MATRIX.md`, `AARA_ARCHITECTURE_AUTHORITY.md`, or any `docs/architecture/*` file.
11. Claim this behavior was previously ratified by any prior document — it was not; this is the first binding record of it.

---

## Relationship to ADR-002

`bot/trust_ledger/constitution.py` remains protected by ADR-002. This ADR authorizes no code, schema, or configuration change of any kind and therefore does not require, invoke, or constitute an ADR-002 exception. All ADR-002 protections remain exactly as they are, unchanged.

---

## Relationship to ADR-010

ADR-010 (Accepted) independently characterizes Constitution Rules 1 and 4 as "advisory-only in Phase 1A" and states they "block nothing," as part of its own analysis of Phase 1A's blocking-vs-reactive control landscape. This ADR is consistent with, and corroborated by, that characterization for Rule 1 specifically. This ADR does not modify, amend, or depend on ADR-010's own subject matter (FRED/macro failure handling); it cites ADR-010 only as independent supporting evidence for the invariant ratified here.

---

## Evidence

- `bot/trust_ledger/constitution.py` — Rule 1 predicate (`_rule_risk_governor_authority`), risk-state derivation (`_read_only_governor_state`), and the module's own docstring explaining its deliberate avoidance of mutating risk-check methods.
- `bot/risk/risk_manager.py` — `check_portfolio_drawdown()`, `check_daily_loss_warning()`, `check_weekly_loss()` (the three methods Rule 1 actually consumes, verified non-mutating), contrasted with `check_daily_loss()` (mutating, deliberately not used by Rule 1).
- `bot/_main_cycle.py` — the actual, independent BUY-blocking risk gate (`risk.approve_buy()`), which runs before any order is placed and has no dependency on or interaction with Constitution.
- `bot/_main_trust_decisions.py` — the sole call site of `constitution.check_and_log()`, called after the decision write, with its return value discarded.
- `tests/phase1a/test_constitution.py` — `test_rule_1_passes_when_risk_normal`, `test_rule_1_escalates_buy_when_defensive`, `test_rule_1_does_not_escalate_sell_when_defensive`, and `test_rule_1_does_not_mutate_risk_manager_state` (a dedicated regression guard for the read-only property).
- `ADR-002` — establishes the protected-file boundary this ADR does not exercise an exception against.
- `ADR-010` — independent corroborating characterization of Rule 1 as advisory-only and blocking nothing.

---

## Decision Character

This is a behavioral ratification, not a new runtime design. It recognizes and deliberately stabilizes an existing implementation invariant that was previously undocumented at any binding governance tier. No implementation change is authorized or required by this ADR; current implementation already satisfies §Decision in full.

---

## Consequences

**Positive:**
- Closes a previously undocumented governance gap with a precise, citable record.
- Any future change to this specific behavioral property — not merely to the file, which ADR-002 already protects generically — now requires its own governance action.
- Zero implementation risk: no code is authorized, moved, or changed by this ADR.

**Negative / Limitation:**
- Does not extend protection or clarity to Constitution Rules 2–6, or to any action type beyond `BUY`.
- Does not establish a general "Risk Governor" architectural concept for `sentinel_engine/` or any other product surface.
- Leaves `TRADING_CONSTITUTION.md`'s broader "no automatic execution" claim exactly as unresolved (Tier-4, non-binding) as before this ADR.

---

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-08-24
**Accepted By:** Architecture Owner
