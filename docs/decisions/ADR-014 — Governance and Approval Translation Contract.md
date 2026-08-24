# ADR-014 — Governance and Approval Translation Contract

**Status:** Accepted
**Date:** 2026-08-12
**Decision Type:** Architecture / Contract
**Supersedes:** None
**Related ADRs:** ADR-002, ADR-009, ADR-011, ADR-012, ADR-013

---

## 1. Context

The Sentinel Engine Phase-1 decision lifecycle defines the canonical flow:

Decision → Evidence → Governance Evaluation → Approval → Ledger Event → Projection → Query

The Sentinel Engine already contains the GovernanceService implementation required
for Governance Evaluation and Approval, including:

- `GovernanceService.evaluate_policy()`
- `GovernanceService.record_approval()`

These services are already implemented and tested inside `sentinel_engine/`.

The current Phase-1A `bot/` decision path has been authorized, through ADR-009,
to perform a narrowly scoped Evidence integration after the decision write.

No existing ADR authorizes the `bot/` path to invoke Governance Evaluation or
Approval.

Before any such wiring can be considered, the translation from a real Phase-1A
decision into the inputs required by GovernanceService must be defined as an
explicit architectural contract.

This ADR establishes that translation contract only.

It does not authorize any change to `bot/`.

---

## 2. Problem

GovernanceService requires domain-level inputs that are not currently defined
as a bot-side translation contract.

In particular, the architecture must explicitly establish:

1. how a Phase-1A decision identifies the policy being evaluated; and
2. how an Approval record represents an autonomous Phase-1A decision without
   incorrectly implying that a human approved the decision.

These semantics must not be invented inside a future `bot/` integration.

ADR-012 established the precedent that translation from bot/model data into
Sentinel Engine domain objects should be defined independently as a pure adapter
contract before production wiring is authorized.

---

## 3. Decision

Establish a dedicated, bot-independent Governance/Approval translation adapter:

    sentinel_engine/adapters/governance_adapter.py

The adapter shall contain only pure translation logic between existing
Phase-1A decision data and the existing Sentinel Engine GovernanceService input
contracts.

The adapter shall not:

- import from `bot/`;
- modify `GovernanceService`;
- modify `EvidenceService`;
- modify `DecisionService`;
- modify `LedgerRepository`;
- modify `ProjectionRepository`;
- invoke any `GovernanceService` method (`evaluate_policy`,
  `record_approval`, or any other);
- create or modify composition infrastructure;
- persist data;
- execute trades or orders;
- perform network I/O;
- make policy decisions itself.

The adapter is a translation boundary, not a governance engine. It produces
plain data and existing Sentinel Engine domain objects/inputs for a future
caller to pass to `GovernanceService`; it never calls `GovernanceService`
itself, mirroring the same caller/adapter separation ADR-012 established for
`to_evidence_records()`.

This ADR follows ADR-012's decision-identity **principle**, not its exact
adapter signature. ADR-012's evidence adapter (`to_evidence_records()`)
does not accept `decision_id` as an input, because the `Evidence`
dataclass it produces has no `decision_id` field -- identity is associated
separately, by the caller, via
`EvidenceService.associate_evidence(decision_id, evidence)`. By contrast,
the governance adapter established here necessarily accepts an
already-existing `decision_id` as plain input, because `Approval` is a
dataclass that requires `decision_id: str` directly on the object itself
(`sentinel_engine/governance/approval.py`) -- there is no equivalent
after-the-fact association mechanism for `Approval`. This difference in
signature is a consequence of the differing target domain objects
(`Evidence` vs. `Approval`), not a departure from ADR-012. In both cases
the architectural principle is identical: the adapter must never generate,
invent, mutate, derive from `bot/` infrastructure, or otherwise obtain the
decision identity itself -- the caller supplies it as plain data, and the
adapter preserves it exactly in its output.

### Input Data Shape

The adapter's input domain is the existing plain decision data already
produced by the current Phase-1A decision-write path -- the same
`decision_row` established by ADR-009 and consumed by ADR-012's evidence
adapter (e.g. `decision_row["decision_id"]`, `decision_row["model_outputs"]`)
-- available at the caller boundary. This ADR does not define a new
decision schema, and does not introduce new fields onto `decision_row` or
any other decision data structure.

The exact field-to-field mapping from existing `decision_row` fields to
the adapter's outputs (including the `policy_id` mapping in Section 4)
cannot be stated precisely from current repository evidence and is
therefore not enumerated here. It remains an implementation-level detail,
strictly constrained to fields that already exist on `decision_row` --
implementation is not authorized to invent new decision-row fields or a
new decision schema to satisfy this contract.

---

## 4. Policy Identity Contract

This ADR defines only a deterministic mapping from an existing Phase-1A
decision to a `policy_id` string. It does not define, authorize, or imply
the existence of any operational governance policy.

The mapping shall:

- be deterministic;
- be derived only from existing decision data;
- not generate a policy dynamically;
- not consult external services;
- not introduce a new policy registry;
- not infer policy identity from presentation/UI data.

The resulting `policy_id` is an identifier only. It does not, by itself,
make governance evaluation operational.

This ADR does NOT authorize registration of a Phase-1A `Policy` with
GovernanceService. As of this writing, no Phase-1A `Policy` exists anywhere
in the repository -- every existing `Policy` construction is test or
illustrative-seed data. `GovernanceService.evaluate_policy()` treats an
unregistered `policy_id` identically to a registered-but-disabled policy;
this ADR's `policy_id` mapping therefore does not, by itself, cause
`evaluate_policy()` to evaluate anything meaningful.

Registration of an actual Phase-1A `Policy` -- deciding what governance rule
the policy represents, and its `name`, `description`, and `enabled` state --
is separate, unauthorized future governance work.

The adapter shall not itself evaluate whether the decision satisfies any
policy. That responsibility remains exclusively with GovernanceService.

---

## 5. Approval Semantics

The existing Phase-1A trading path is not a human approval workflow.

This ADR distinguishes two concepts that `Approval` carries as separate
fields, not one:

- **Governance verdict** -- `ApprovalStatus`, which has exactly two values,
  `APPROVED` and `REJECTED`. It represents the outcome of the governance
  check only. There is no third `ApprovalStatus` value for "autonomous" or
  "system" decisions, and this ADR does not introduce one.
- **Actor/provenance** -- `approved_by`, a free-text `str` field on
  `Approval`. This is the only field capable of representing who or what
  produced the verdict.

`ApprovalStatus` shall NOT be used, extended, or repurposed to represent
provenance. Provenance is carried exclusively by `approved_by`.

The adapter shall not represent an autonomous engine decision as having been
manually approved by a human when no such human approval occurred. A
Governance Evaluation event shall not, by itself, be interpreted as evidence
of human approval.

**This ADR does NOT fix the literal `approved_by` value for autonomous
Phase-1A decisions.** Repository evidence shows every existing Sentinel
Engine `Approval` construction uses a human-role value (`"risk_officer"`,
`"cro"`); no existing Sentinel Engine autonomous/machine provenance value
exists to reuse. A separate, structurally unrelated, and currently dormant
mechanism (`database/services/decision_service.py`) uses the literal string
`"system"` for its own autonomous-approval concept -- that convention
belongs to a different domain model and must not be assumed to transfer to
Sentinel Engine merely because the same literal string could be reused.

Any future implementation value for autonomous `approved_by` must:

- be deterministic;
- be non-personal;
- not impersonate a human role;
- not reuse or conflict with existing Sentinel Engine human-role semantics
  (e.g. `"risk_officer"`, `"cro"`);
- not assume that the separate `database/` `"system"` convention transfers
  to Sentinel Engine.

Selecting the literal value is deferred to explicit implementation review,
or to a later governance decision if the architecture owner determines one
is warranted. This ADR does not authorize a new autonomous approval policy
or change the meaning of execution authorization.

---

## 6. Domain Ownership

The adapter translates data into the existing Sentinel Engine domain contracts.

It does not define new GovernanceService behavior.

The following remain authoritative:

- `Policy` semantics remain owned by the Sentinel Engine governance domain.
- `Approval` semantics remain owned by the Sentinel Engine governance domain.
- Governance evaluation remains owned by `GovernanceService`.
- Approval recording remains owned by `GovernanceService`.
- Ledger event creation remains owned by the existing ledger infrastructure.
- Projection behavior remains owned by the existing projection infrastructure.

The adapter must not duplicate any of those responsibilities.

---

## 7. Dependency Direction

The dependency direction established by this ADR is:

    Phase-1A decision data
             ↓
    governance_adapter
             ↓
    existing Sentinel Engine domain contracts
             ↓
    GovernanceService

The adapter must remain independent of the `bot/` package.

Future callers may supply the required plain decision data without making the
adapter aware of where that data originated.

---

## 8. Composition Boundary

This ADR does not authorize creation or modification of a GovernanceService
composition boundary.

In particular, it does not authorize:

- a new GovernanceService singleton;
- a new LedgerRepository;
- a new ProjectionRepository;
- a new LedgerStore;
- a second in-memory ledger;
- a new production persistence mechanism;
- reuse of the existing Evidence composition module
  (`sentinel_engine/composition/evidence.py`) for GovernanceService.

Composition and service wiring are intentionally deferred to a separate
governance decision.

This prevents the translation contract from prematurely deciding how
GovernanceService will be composed or persisted.

---

## 9. Decision Creation Boundary

This ADR does not authorize `DecisionService.create_decision()` for the
Phase-1A `bot/` path.

No DecisionProjection seeding, decision creation, or projection lifecycle
change is introduced by this contract.

Any future authorization to create Sentinel Engine decisions from `bot/` must
be addressed by a separate architectural decision.

---

## 10. Existing Approval Mechanisms

This ADR does not modify or replace the existing approval mechanism in:

- `database/`
- `dashboard/components/pending_approvals.py`

That mechanism is:

- structurally separate from Sentinel Engine -- it operates on an integer
  `decision_id` against the `decision_log` table via
  `database/services/decision_service.py`, not on the `Approval`/
  `ApprovalStatus` dataclasses defined in `sentinel_engine/governance/`;
- currently dormant -- per `dashboard/components/pending_approvals.py`'s own
  documentation, the per-trade approval workflow it served was fully retired
  for Phase 1A and no longer writes to `decision_log`;
- sharing no types, imports, or decision-identity space with the Sentinel
  Engine `GovernanceService`/`Approval` contract.

The literal string `"system"` already has a documented meaning in that
mechanism (`decision_service.py::approve_decision()`: "autonomous mode, all
gates passed"). That meaning does not transfer to Sentinel Engine merely
because the same literal string could be reused for `Approval.approved_by`
-- see Section 5.

The Sentinel Engine Approval contract established here must not be
interpreted as a replacement, migration, or extension of the existing
dashboard approval workflow.

---

## 11. Explicit Non-Goals

This ADR does not authorize:

- any modification to `bot/`;
- any ADR-002 exception;
- GovernanceService implementation changes;
- EvidenceService changes;
- DecisionService changes;
- LedgerRepository changes;
- ProjectionRepository changes;
- LedgerStore changes;
- production persistence;
- dashboard changes;
- database changes;
- execution/order changes;
- risk-policy changes;
- human approval workflow changes;
- autonomous execution authorization changes;
- continuous learning;
- feedback loops;
- DecisionService.create_decision() from `bot/`;
- Evidence consumers;
- production ledger backend selection under ADR-004.

---

## 12. Implementation Scope

If this ADR is accepted, implementation is limited to:

1. creation of the Governance/Approval translation adapter;
2. tests proving its deterministic translation behavior;
3. tests proving that no bot, persistence, composition, execution, or
   governance-service behavior is introduced.

No existing production file is authorized to change under this ADR.

In particular, this ADR does not authorize modification of:

    bot/_main_trust_decisions.py

Any future wiring of this contract into `bot/` requires a separate ADR.

---

## 13. Required Tests

Acceptance tests for the adapter shall establish:

### A. Deterministic policy translation

Given the same Phase-1A decision data, the adapter produces the same
`policy_id`.

### B. Explicit autonomous provenance

An autonomous Phase-1A decision produces an Approval representation that does
not claim or imply approval by a human actor.

### C. Decision identity preservation

The decision identity supplied to the Governance/Approval domain objects is
the exact source decision identity.

### D. Pure translation

The adapter performs no persistence, network I/O, service invocation, or
composition.

### E. Existing approval isolation

The adapter has no dependency on the existing `database/` or dashboard
approval workflow.

---

## 14. Architectural Invariants

The following invariants are established:

1. Translation is separate from governance evaluation.
2. Governance evaluation is separate from human approval.
3. Autonomous provenance must never be represented as fictitious human approval.
4. The adapter is independent of `bot/`.
5. The adapter does not create Sentinel Engine decisions.
6. The adapter does not establish persistence or composition.
7. Existing dashboard/database approval remains independent.
8. No ADR-002 exception is created by this ADR.
9. No production `bot/` wiring is authorized by this ADR.

---

## 15. Relationship to ADR-009

ADR-009 authorized the existing Evidence integration in
`record_decision_safe()`.

This ADR does not modify, extend, or supersede ADR-009.

ADR-009's existing Evidence integration remains governed by its own scope and
validation requirements.

Any future Governance/Approval wiring into the same bot decision path requires
a separate ADR.

---

## 16. Relationship to ADR-012

ADR-012 established the precedent for defining a translation contract separately
from production wiring.

This ADR follows the same architectural sequencing:

    translation contract
          ↓
    acceptance/validation
          ↓
    separate production wiring decision

ADR-012 itself is not modified.

---

## 17. Relationship to ADR-013

ADR-013 remains fully in force.

This ADR does not authorize any GovernanceService consumer or composition
extension.

Any future production wiring must explicitly address ADR-013's existing
restrictions in a separate ADR.

---

## 18. Acceptance Criteria

This ADR may be considered implemented only when:

- `sentinel_engine/adapters/governance_adapter.py` exists;
- the policy identity mapping is explicit and deterministic;
- the autonomous Approval provenance *concept* is explicitly defined, and
  the five constraints on any future `approved_by` literal set out in
  Section 5 are explicit and independently testable -- **without** Section
  5's deliberately deferred literal `approved_by` value being fixed by
  this ADR; selecting that literal remains deferred to implementation
  review or a later governance decision, exactly as Section 5 states, and
  is NOT a condition of this ADR's acceptance;
- adapter tests cover the required invariants;
- no `bot/` production file is modified;
- no existing Sentinel Engine service or repository is modified;
- no composition infrastructure is modified;
- no dashboard/database approval mechanism is modified;
- the full relevant test suite passes.

---

## 19. Future Work Requiring Separate Authorization

A future ADR may, independently, authorize:

- composition of GovernanceService with the existing Sentinel Engine runtime;
- reuse of existing ledger/projection infrastructure;
- a narrow `bot/_main_trust_decisions.py` integration;
- Governance Evaluation/Approval invocation from `record_decision_safe()`.

Such work must not be inferred from acceptance of this ADR.

---

## 20. Status

**Accepted — 2026-08-12.**

This ADR is accepted as written, including the Section 3 (Decision) and
Section 18 (Acceptance Criteria) clarifications made during architecture-owner
review: the ADR-012 principle-vs-mechanism distinction and Input Data Shape
statement in Section 3, and the Section 5/Section 18 provenance-deferral
consistency clarification in Section 18.

Acceptance of this ADR authorizes only what Section 12 (Implementation
Scope) permits: creation of `sentinel_engine/adapters/governance_adapter.py`
and its tests. It does not authorize Policy registration (Section 4), any
`GovernanceService` invocation (Section 3), any `bot/` change (Sections 1,
11, 12), any composition change (Section 8), `DecisionService.create_decision()`
(Section 9), or any dashboard/database change (Section 10). All Explicit
Non-Goals (Section 11) and Architectural Invariants (Section 14) remain in
force unchanged. The literal autonomous `approved_by` value remains
deferred per Section 5.