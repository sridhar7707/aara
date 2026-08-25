# ADR-051 — Constitution Rule 2 — Position Sizing Discipline Advisory Boundary (Phase-1A)

**Status:** Accepted
**Date Proposed:** 2026-08-24
**Decision Type:** Architecture / Governance — Behavioral Ratification
**Related ADRs:** ADR-002, ADR-047, ADR-048, ADR-049, ADR-050

---

## Context

`bot/trust_ledger/constitution.py`'s Rule 2 ("Position Sizing Discipline") is existing, shipped, ADR-002-protected Phase-1A behavior, structurally analogous to Rule 1 (ADR-047), Rule 4 (ADR-048), Rule 3 (ADR-049), and Rule 5 (ADR-050). A dedicated evidence-gate sequence re-verified this behavior directly against the live implementation, its tests, and its call site: Rule 2's only data source is a single, non-mutating `SELECT` over already-written decision and outcome records for the asset in question; the sole call site of `constitution.check_and_log()` (`bot/_main_trust_decisions.py`) runs after the decision write, with its return value discarded — identical ordering and discard behavior already verified for every other Constitution rule this session. Three dedicated tests now exercise every branch of the predicate.

Unlike Rules 1, 3, 4, and 5 — each of which has at least one code path capable of returning `ESCALATED` — **Rule 2, as currently implemented, has no such path.** Every branch of its predicate returns `PASS`/`execution_proceeded`. This ADR ratifies that fact precisely, rather than describing Rule 2 as "advisory-only escalation" in the sense the other four rules' ADRs use that phrase.

Rule 2's `PASS` reason text, for the branch reached when a prior closed trade on the asset lost money, references `bot/trust_ledger/risk.py::recommend_position_size()` and Risk Governor `WARNING`/`DEFENSIVE` states. A dedicated evidence gate (this session) traced that reference and found it technically accurate but capable of being misread: `recommend_position_size()` is called only from a separate function (`record_risk_evaluation()`, not Rule 2), computes a purely observational, non-enforced value logged for later comparison, and does not participate in the actual production position-sizing path (`bot/_main_cycle.py`'s Kelly-fraction-based computation, which has no dependency on Risk Governor classification). This is noted here as context only. **This ADR ratifies Rule 2's executable behavior, not its reason-string wording**, and does not propose correcting that wording.

A separate evidence gate searched the repository for an authoritative source defining "FR-1.10a" (the requirement ID cited in `recommend_position_size()`'s docstring and elsewhere) and found none — only consistent, non-contradictory citations across implementation, schema, and one design document, with no originating requirements document located. This is stated here as a factual finding, not as a defect this ADR corrects. FR-1.10a is not ratified, defined, or relied upon by this ADR in any way.

No Accepted ADR was found governing Rule 2, its consumed data, `recommend_position_size()`, or Observation Mode, in the evidence gate's search of `docs/decisions/`.

This ADR is a deliberate ratification of the currently verified Phase-1A behavior. It recognizes and deliberately stabilizes an existing implementation invariant. It does not introduce a new runtime design, and it does not claim this behavior was previously ratified by any prior document.

---

## Decision

The following three-part behavioral contract is ratified as an architectural invariant:

### 1. Observation, Not Ownership

Constitution Rule 2 observes prior-trade-outcome information relevant to position-sizing discipline for `BUY` decisions.

It does not mutate the decision record, any risk-management state, or any authoritative execution path. The specific data read, its source, and the manner in which it is computed remain implementation details unless separately ratified.

### 2. No Escalation in Current Implementation

Under the currently verified implementation, Rule 2 has no code path that returns `ESCALATED`. All Rule 2 outcomes currently return `PASS`/`execution_proceeded`.

This is a statement of currently verified behavior, not a prohibition on Rule 2 ever gaining an escalation path in the future — any such change would require its own separate implementation and, consistent with the pattern established for Rules 1, 3, 4, and 5, its own governance treatment of what that escalation may and may not do.

### 3. No Independent Veto

Rule 2 has no independent authority to veto, block, alter, or otherwise affect execution, under any circumstance.

---

## Verified Scope

- This contract covers Rule 2 ("Position Sizing Discipline") only.
- Rule 2's qualifying decision action is `BUY`; other actions are outside its evaluated scope.
- This contract does not characterize or ratify Constitution Rules 1, 3, 4, 5, or 6. Rules 1, 4, 3, and 5 are separately governed by ADR-047, ADR-048, ADR-049, and ADR-050 respectively; Rule 6 is addressed by none of them and not by this ADR.

---

## Explicit Non-Goals / Non-Claims

This ADR does not ratify, freeze, or authorize:

1. `_rule_position_sizing_discipline`, `_last_closed_net_return`, or any other function/helper name, as an architectural symbol.
2. Any `decision_row` field name, table name, column name, or SQL structure.
3. The exact prior-return calculation or comparison logic.
4. `recommend_position_size()`, its formula, or its existence as a dependency of Rule 2 — Rule 2 does not call it.
5. FR-1.10a's wording, scope, or any authoritative status for it. Q6-E2 found no standalone document defining FR-1.10a; this ADR does not supply one, does not treat its absence as a defect to be fixed, and does not itself become that source.
6. "Observation Mode" as a separately ratified architectural contract.
7. `NORMAL`/`WARNING`/`DEFENSIVE` or any other Risk Governor classification label.
8. Kelly-fraction sizing or any other detail of the actual production position-sizing implementation.
9. Any numerical threshold.
10. Any specific reason-string wording, including Rule 2's own current reason text — the ratified invariant above is derived from Rule 2's executable behavior, not from that text.
11. Characterization of Constitution Rules 1, 3, 4, 5, or 6 in any way.
12. Any amendment, reopening, or reinterpretation of ADR-047, ADR-048, ADR-049, or ADR-050.
13. Any code, schema, test, configuration, index, or governance-document change.
14. An ADR-002 exception — no code change is authorized, so none is needed.
15. A claim that this behavior was previously ratified by any prior document — this is the first dedicated, binding record of Rule 2's own boundary.

---

## Evidence

**Executable behavior:**
- `bot/trust_ledger/constitution.py::_rule_position_sizing_discipline` — three return branches, all `PASS`/`execution_proceeded`; reads only `decision_row["action"]`, `decision_row["asset"]`, and `_last_closed_net_return(conn, asset)`, a single non-mutating `SELECT`. No `RiskManager` reference.

**Test evidence:**
- `tests/phase1a/test_constitution.py::test_rule_2_not_applicable_to_non_buy`, `test_rule_2_passes_when_no_prior_closed_loss`, `test_rule_2_passes_with_prior_closed_loss` — one test per predicate branch, each asserting only `check_result`/`action_taken`.

**Execution-order evidence:**
- `bot/_main_trust_decisions.py` — the sole call site of `constitution.check_and_log()`, called after the decision write, with its return value discarded.

**Contextual/reference evidence (not ratified):**
- Q6-E2's determination that no standalone document defining FR-1.10a exists in this repository.
- The traced production sizing path (`bot/_main_cycle.py`'s Kelly-fraction-based computation, independent of Risk Governor classification) — cited only as evidence that Rule 2 does not own, control, or enforce position sizing, not as a mechanism this ADR characterizes or authorizes.
- `ADR-002` — establishes the protected-file boundary this ADR does not exercise an exception against.
- `ADR-047`, `ADR-048`, `ADR-049`, `ADR-050` — structural precedent for this ADR's form only; none of their own substance is characterized or amended here.

---

## Consequences

**Positive:**
- Closes a previously undocumented governance gap for Rule 2 with a precise, citable record, mirroring ADR-047's, ADR-048's, ADR-049's, and ADR-050's treatment of Rules 1, 4, 3, and 5.
- Correctly distinguishes Rule 2's "always `PASS` today" behavior from the other four rules' "may escalate" behavior, avoiding an inaccurate generalization across rules.
- Zero implementation risk: no code is authorized, moved, or changed by this ADR.

**Negative / Limitation:**
- Does not extend protection or clarity to Constitution Rules 1, 3, 4, 5, or 6.
- Does not resolve the reason-text precision concern identified in evidence gathering, or FR-1.10a's undocumented provenance — both remain open, separately addressable questions this ADR deliberately does not decide.

---

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-08-24
**Accepted By:** Architecture Owner

---

## READY / NOT READY

**READY**

### Overreach Check

- No implementation names frozen — `_rule_position_sizing_discipline`/`_last_closed_net_return` appear only as Evidence citations, never inside the Decision section's normative text.
- No formulas frozen — `recommend_position_size()`'s formula is not stated anywhere in this document.
- No thresholds frozen — no numeric value appears in the Decision or Context sections.
- No FR-1.10a contract created — Non-Goals item 5 explicitly forecloses this; Context states the absence of a source as a finding, not a defect this ADR fixes.
- No Risk Governor architecture created — `NORMAL`/`WARNING`/`DEFENSIVE` are excluded by Non-Goals item 7 and never appear in the Decision section.
- No production sizing architecture created — Kelly-fraction sizing is excluded by Non-Goals item 8, cited only as Evidence that Rule 2 does not own sizing.
- No other Constitution rule characterized — Non-Goals items 11 and Verified Scope both explicitly exclude Rules 1, 3, 4, 5, and 6.
- No code change authorized — Non-Goals items 13-14 and Consequences' "Zero implementation risk" both confirm.
