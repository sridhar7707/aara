# ADR-050 — Constitution Rule 5 — Approval Escalation for First N Trades Advisory Boundary (Phase-1A)

**Status:** Accepted
**Date Proposed:** 2026-08-24
**Decision Type:** Architecture / Governance — Behavioral Ratification
**Related ADRs:** ADR-002, ADR-047, ADR-048, ADR-049

---

## Context

`bot/trust_ledger/constitution.py`'s Rule 5 ("Approval Escalation for First N Trades") is existing, shipped, ADR-002-protected Phase-1A behavior, structurally analogous to Rule 1 (ADR-047), Rule 4 (ADR-048), and Rule 3 (ADR-049). A read-only evidence gate re-verified this behavior directly against the live implementation and its tests: the trade-count state Rule 5 evaluates is read via `_executed_trade_count(conn)`, a single `SELECT COUNT(*)` query, with no mutation and no `RiskManager` reference anywhere in the function; the sole call site of `constitution.check_and_log()` (`bot/_main_trust_decisions.py`) runs after the decision write, with its return value discarded — identical ordering and discard behavior already verified for Rules 1, 3, and 4.

Four dedicated tests (`tests/phase1a/test_constitution.py`) now exercise every branch of the predicate: not-applicable for `HOLD` (the same shared non-`BUY`/`SELL` code path also covers `REJECT`, though no dedicated `REJECT` test exists), escalation below the trade-count threshold, escalation for the combined below-secondary-threshold-and-low-confidence condition, and pass once both thresholds are satisfied. The evidence gate confirmed no remaining gap in branch coverage.

No Accepted ADR was found governing Rule 5, its consumed state, or its thresholds, in the evidence gate's search of `docs/decisions/`.

This ADR is a deliberate ratification of the currently verified Phase-1A behavior. It recognizes and deliberately stabilizes an existing implementation invariant. It does not introduce a new runtime design, and it does not claim this behavior was previously ratified by any prior document.

---

## Decision

The following three-part behavioral contract is ratified as an architectural invariant:

### 1. Observation, Not Ownership

Constitution Rule 5 observes already-available trade-count and confidence state read-only, without mutating that state, any risk-management state, or any authoritative write path.

The specific thresholds, their count, and the manner in which trade count and confidence are computed remain implementation details unless separately ratified. This ADR does not claim that any component owns trade-count or confidence state beyond what is already established elsewhere.

### 2. Advisory-Only Escalation, Scoped by Action

For `BUY`/`SELL` decisions, Rule 5 may produce advisory-only Constitution escalation when its current approval-escalation evaluation indicates it. `HOLD`/`REJECT` decisions are outside this rule's scope and are not evaluated by it.

### 3. No Independent Veto

Rule 5 has no independent veto or execution-blocking authority, for any decision action or evaluation outcome.

---

## Verified Scope

- This contract covers Rule 5 ("Approval Escalation for First N Trades") only.
- Rule 5 applies to `BUY`/`SELL` decisions; `HOLD`/`REJECT` decisions are not evaluated by this rule.
- This contract does not characterize or ratify Constitution Rules 1, 2, 3, 4, or 6. Rule 1 is separately governed by ADR-047, Rule 4 by ADR-048, and Rule 3 by ADR-049; neither Rule 2 nor Rule 6 is addressed here.

---

## Explicit Non-Goals / Non-Claims

This ADR does not:

1. Freeze the current thresholds (twenty, fifty, and 0.65, as currently implemented), or any other numeric constant, as architectural vocabulary.
2. Freeze any constant name, helper/function name, or internal representation used to compute Rule 5's result.
3. Characterize Constitution Rules 1, 2, 3, 4, or 6 in any way. Rules 1, 3, and 4 remain governed exclusively by ADR-047, ADR-049, and ADR-048 respectively.
4. Claim or imply that `docs/architecture/TRADING_CONSTITUTION.md`'s broader "no automatic execution" statement is live, currently-enforced Phase-1A behavior. This ADR ratifies only the one narrow, verified behavior described above.
5. Establish a general, cross-product approval-escalation or evidence-threshold architecture.
6. Authorize any code, schema, test, or configuration change.
7. Create an ADR-002 exception — no code change is authorized, so none is needed.
8. Alter, amend, or reinterpret ADR-047, ADR-048, or ADR-049.
9. Modify `DOCUMENT_INDEX.md`, `DOCUMENT_GOVERNANCE_MATRIX.md`, `AARA_ARCHITECTURE_AUTHORITY.md`, or any `docs/architecture/*` file.
10. Claim this behavior was previously ratified by any prior document — this is the first dedicated, binding record of Rule 5's own boundary.

---

## Evidence

- `bot/trust_ledger/constitution.py` — Rule 5 predicate (`_rule_approval_escalation`) and its trade-count helper (`_executed_trade_count`), which performs a single, non-mutating `SELECT COUNT(*)` query and takes no `RiskManager` reference.
- `bot/_main_trust_decisions.py` — the sole call site of `constitution.check_and_log()`, called after the decision write, with its return value discarded.
- `tests/phase1a/test_constitution.py` — `test_rule_5_escalates_before_autonomy_threshold`, `test_rule_5_passes_after_autonomy_threshold_with_high_confidence`, `test_rule_5_escalates_between_thresholds_at_low_confidence`, `test_rule_5_not_applicable_to_hold_or_reject` (exercises `HOLD` only; `REJECT` shares the identical code branch but has no dedicated test) — full branch coverage of the predicate.
- `ADR-002` — establishes the protected-file boundary this ADR does not exercise an exception against.
- `ADR-047`, `ADR-048`, `ADR-049` — the structurally analogous ratifications for Rules 1, 4, and 3, followed here for Rule 5 without characterizing any of those rules' own substance.

---

## Consequences

**Positive:**
- Closes a previously undocumented governance gap for Rule 5 with a precise, citable record, mirroring ADR-047's, ADR-048's, and ADR-049's treatment of Rules 1, 4, and 3.
- Zero implementation risk: no code is authorized, moved, or changed by this ADR.

**Negative / Limitation:**
- Does not extend protection or clarity to Constitution Rules 1, 2, 3, 4, or 6.
- Leaves the specific thresholds and their computation entirely open for separate future governance or silent implementation evolution.

---

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-08-24
**Accepted By:** Architecture Owner
