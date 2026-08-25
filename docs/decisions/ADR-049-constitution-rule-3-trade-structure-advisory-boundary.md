# ADR-049 — Constitution Rule 3 — Trade Structure Requirement Advisory Boundary (Phase-1A)

**Status:** Accepted
**Date Proposed:** 2026-08-24
**Decision Type:** Architecture / Governance — Behavioral Ratification
**Related ADRs:** ADR-002, ADR-047, ADR-048

---

## Context

`bot/trust_ledger/constitution.py`'s Rule 3 ("Trade Structure Requirement") is existing, shipped, ADR-002-protected Phase-1A behavior, structurally analogous to Rule 1 (ADR-047) and Rule 4 (ADR-048). A read-only evidence gate re-verified this behavior directly against the live implementation and its tests: Rule 3's function signature takes only the already-written decision record — no database connection, no `RiskManager` reference, and no external I/O of any kind — making it a pure function with no mutation surface whatsoever, the strongest read-only guarantee of any Constitution rule audited this session. The sole call site of `constitution.check_and_log()` (`bot/_main_trust_decisions.py`) runs after the decision write, with its return value discarded — identical ordering and discard behavior already verified for Rules 1 and 4. Five dedicated tests (`tests/phase1a/test_constitution.py`) exercise every branch of the predicate: missing-fields escalation, all-fields-present pass, `REJECT` inapplicability (the same shared non-`BUY`/`SELL` code path also covers `HOLD`, though no dedicated `HOLD` test exists), `SELL`'s exemption from the structural-completeness requirement, and `SELL`'s continued subjection to the confidence floor.

No Accepted ADR was found governing Rule 3, its consumed fields, or its threshold, in the evidence gate's search of `docs/decisions/`.

This ADR is a deliberate ratification of the currently verified Phase-1A behavior. It recognizes and deliberately stabilizes an existing implementation invariant. It does not introduce a new runtime design, and it does not claim this behavior was previously ratified by any prior document.

---

## Decision

The following three-part behavioral contract is ratified as an architectural invariant:

### 1. Observation, Not Ownership

Constitution Rule 3 observes structural-completeness and confidence state already present on the written decision record, without mutating that record, any risk-management state, or any authoritative write path.

The specific fields consumed, their count, and the confidence threshold used remain implementation details unless separately ratified. This ADR does not claim that any component owns the decision record's structure beyond what is already established by the decision write itself.

### 2. Advisory-Only Escalation, Scoped by Action

For `BUY`/`SELL` decisions, when Rule 3's structural-completeness or confidence-floor evaluation fails, Rule 3 produces an advisory-only Constitution escalation. `SELL` decisions are held only to the confidence-floor portion of this evaluation, not the structural-completeness portion — this action-based distinction is itself part of the ratified invariant, not an implementation detail.

### 3. No Independent Veto

Rule 3 does not independently veto or block execution, for any decision action or evaluation outcome.

---

## Verified Scope

- This contract covers Rule 3 ("Trade Structure Requirement") only.
- Rule 3 applies to `BUY`/`SELL` decisions; `HOLD`/`REJECT` decisions are not evaluated by this rule.
- This contract does not characterize or ratify Constitution Rules 1, 2, 4, 5, or 6. Rule 1 is separately governed by ADR-047 and Rule 4 by ADR-048; none of Rules 2, 5, or 6 are addressed here.

---

## Explicit Non-Goals / Non-Claims

This ADR does not:

1. Freeze the specific field names Rule 3 currently checks, their count, or the confidence threshold value, as architectural vocabulary.
2. Freeze any helper/function name or internal representation used to compute Rule 3's result.
3. Characterize Constitution Rules 1, 2, 4, 5, or 6 in any way. Rules 1 and 4 remain governed exclusively by ADR-047 and ADR-048 respectively.
4. Claim or imply that `docs/architecture/TRADING_CONSTITUTION.md`'s broader "no automatic execution" statement is live, currently-enforced Phase-1A behavior. This ADR ratifies only the one narrow, verified behavior described above.
5. Establish a general, cross-product structural-review or trade-thesis architecture.
6. Authorize any code, schema, test, or configuration change.
7. Create an ADR-002 exception — no code change is authorized, so none is needed.
8. Alter, amend, or reinterpret ADR-047 or ADR-048.
9. Modify `DOCUMENT_INDEX.md`, `DOCUMENT_GOVERNANCE_MATRIX.md`, `AARA_ARCHITECTURE_AUTHORITY.md`, or any `docs/architecture/*` file.
10. Claim this behavior was previously ratified by any prior document — this is the first dedicated, binding record of Rule 3's own boundary.

---

## Evidence

- `bot/trust_ledger/constitution.py` — Rule 3 predicate (`_rule_trade_structure`), which takes only `decision_row: dict` as input, with no database connection and no `RiskManager` reference in its signature.
- `bot/_main_trust_decisions.py` — the sole call site of `constitution.check_and_log()`, called after the decision write, with its return value discarded.
- `tests/phase1a/test_constitution.py` — `test_rule_3_escalates_when_thesis_fields_missing`, `test_rule_3_passes_when_all_fields_present`, `test_rule_3_not_applicable_to_hold_or_reject` (exercises `REJECT` only; `HOLD` shares the identical code branch but has no dedicated test), `test_rule_3_sell_does_not_require_a_fresh_thesis`, `test_rule_3_sell_still_escalates_below_confidence_floor` — full branch coverage of the predicate.
- `ADR-002` — establishes the protected-file boundary this ADR does not exercise an exception against.
- `ADR-047`, `ADR-048` — the structurally analogous ratifications for Rules 1 and 4, followed here for Rule 3 without characterizing either rule's own substance.

---

## Consequences

**Positive:**
- Closes a previously undocumented governance gap for Rule 3 with a precise, citable record, mirroring ADR-047's and ADR-048's treatment of Rules 1 and 4.
- Zero implementation risk: no code is authorized, moved, or changed by this ADR.

**Negative / Limitation:**
- Does not extend protection or clarity to Constitution Rules 1, 2, 4, 5, or 6.
- Leaves the specific field set, field count, and confidence threshold entirely open for separate future governance or silent implementation evolution.

---

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-08-24
**Accepted By:** Architecture Owner
