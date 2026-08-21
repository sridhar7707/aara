# ADR-043 — Temporary Trust Ledger Decision Lineage Projection

**Status:** Accepted
**Date Proposed:** 2026-08-21
**Date Accepted:** 2026-08-21
**Decision Type:** Architecture / Governance — Narrow, Temporary, Non-Permanent Exception
**Related ADRs:** ADR-001, ADR-002, ADR-004, ADR-009, ADR-012, ADR-013, ADR-016

**Numbering note:** Drafted and reviewed under the working name "ADR-017"; assigned ADR-043 at creation because ADR-017 through ADR-042 were already in use in `docs/decisions/`.

---

## 1. Context

Prior read-only governance audits established: (a) `bot/` never calls
`DecisionService.create_decision()` for any real production decision
(verified by exhaustive grep — zero hits under `bot/`); (b) real Trust
Ledger decisions (e.g. `DEC-20260817T142218-SLB-c73eb686`,
`data/trust_ledger.db`) therefore never produce a `DecisionProjection`,
so `DecisionQuery.get_decision_timeline()` returns `None` for every real
decision regardless of how much real data exists one layer below it; (c)
ADR-004 remains **Deferred**, authoritative, and unresolved; (d) ADR-013
established that a narrow, dedicated exception ADR can authorize
ledger-adjacent infrastructure without amending or resolving ADR-004,
but explicitly declined to authorize either projection creation or
direct reads of `data/trust_ledger.db`, reserving both for "separate
governance" (ADR-013 §13, §15); (e) ADR-016 attempted a structurally
similar exception for a different dataset and remains **Proposed —
Implementation Deferred**, non-binding, but is the closest prior
reasoning on this exact boundary.

This ADR is written as that "separate governance."

## 2. Decision

Authorize a narrow, temporary, standalone, read-only consumer that
proves real Decision Center lineage for exactly one explicitly named
`decision_id` from the existing Trust Ledger, without amending ADR-004,
without selecting ADR-004 Option A, B, or C, and without any write path
back into the Trust Ledger.

**Architecture-Owner Acceptance (2026-08-21):** Accepted. The
architecture owner explicitly accepts the interpretation, presented as
unresolved in Section 6, that this narrowly scoped mechanism is a
legally distinguishable temporary exception and does **not** constitute
selection or implementation of ADR-004 Option A, B, or C. ADR-004
remains unchanged, unresolved, and fully governing for the permanent
ledger-ownership decision. Acceptance authorizes only the exact scope
already defined in this ADR: exactly one named `decision_id`; exactly
one manual invocation; read-only Trust Ledger access; exactly one
in-memory `DecisionProjection`; no persistence; no scheduler; no UI; no
reuse of ADR-013's composition; no protected-path changes; no
Five-Metric calculation; no governance/risk/approval translation; no
ADR-004 amendment or Option A/B/C selection. This acceptance does not
itself authorize implementation — no implementation code is created or
modified by this acceptance.

## 3. Scope

In scope: reading the already-committed row from `data/trust_ledger.db`
(`decision_events`, and `model_outputs` via the already-Accepted
`evidence_adapter.to_evidence_records()` path) for exactly one named
`decision_id`; translating it through existing, unmodified
`sentinel_engine` contracts; producing one `DecisionProjection` for that
named decision via a dedicated, temporary repository pair distinct from
ADR-013's.

Out of scope: everything not named in Section 4.

## 4. Explicit Authorization

This ADR authorizes:

1. A new, standalone script/module, located outside `bot/`,
   `dashboard/`, `scheduler/`, `.github/workflows/`, `database/`,
   top-level `ledger/`, and outside `applications/*/bootstrap.py` — its
   exact location is an implementation detail for the architecture
   owner, not fixed by this ADR, but it must be a new location, not a
   modification of any existing composition boundary (including
   `sentinel_engine/composition/evidence.py`).
2. Opening `data/trust_ledger.db` in a read-only connection mode
   (verified feasible and zero-risk in the audits preceding this ADR).
3. Reading the `decision_events` row for exactly one explicitly named
   `decision_id` — not a query, filter, scan, list, or "all recent
   decisions" mechanism. Any need to examine a second decision requires
   its own, separate architecture-owner approval, not an expansion of
   this authorization.
4. Reading the `model_outputs` JSON column of that named row and
   passing it, unmodified, to the already-Accepted, already-tested
   `sentinel_engine.adapters.evidence_adapter.to_evidence_records()`.
5. Constructing a `Decision` via
   `sentinel_engine.adapters.decision_adapter.to_decision()` for the
   named row, using `decision_events.decision_id`, `.asset` (as
   `symbol`), `.action`, `.timestamp`, `.final_confidence` (as
   `confidence`), and placeholder string values for
   `evidence_reference`/`risk_reference` — **REQUIRED IMPLEMENTATION
   PREREQUISITE, not resolved by this ADR**: `Decision.evidence_reference`/
   `risk_reference` are opaque, non-empty strings with no defined
   real-Trust-Ledger construction rule anywhere in the codebase;
   existing precedent (`applications/trading_intelligence/bootstrap.py`'s
   seed decisions) uses arbitrary illustrative literals for these same
   fields, and these fields are independently documented elsewhere as
   deprecated-but-present. Using a deterministic placeholder (e.g. the
   row's own `candidate_event_id`) is consistent with existing precedent
   but is noted here as a real gap, not silently designed around.
6. Constructing one dedicated, new temporary `LedgerStore` and one
   dedicated, new temporary `ProjectionRepository` implementation pair,
   satisfying only the existing abstract contracts (`append`/`read_all`;
   `get`/`save`, inheriting `advance_status()` unchanged) — structurally
   identical in minimalism to ADR-013's, but a separate instance, not a
   reuse or extension of ADR-013's composition boundary.
7. Calling `DecisionService.create_decision()` exactly once per named
   `decision_id`, against the dedicated repositories from item 6.
8. Calling `EvidenceService.associate_evidence()` for the evidence
   records produced in item 4, against the same dedicated repositories.
9. Manual, on-demand, single-invocation execution only — not a
   scheduled job, not a loop, not triggered by any existing CI/CD
   workflow.

## 5. Explicit Non-Authorization

This ADR does **not** authorize:

- Any write, of any kind, to `data/trust_ledger.db`, `ledger/schema.sql`,
  or any table therein.
- Any change to `bot/`, `dashboard/`, `scheduler/`,
  `.github/workflows/`, `database/`, or top-level `ledger/` — no file in
  any of these paths may change under this ADR.
- Any change to `applications/*/bootstrap.py`.
- Any change to `sentinel_engine/composition/evidence.py` or reuse of
  its singleton instances.
- Any modification to `Decision`, `DecisionProjection`, `DecisionState`,
  `DecisionService`, `LedgerRepository`, `ProjectionRepository`,
  `decision_adapter.py`, or `evidence_adapter.py` — all consumed exactly
  as they exist today.
- Adding any new `DecisionState` value — `decision_state.py`'s own
  docstring reserves this until "an actual service path transitions a
  decision into one of them" in a governed way; this ADR's mechanism
  does not create that governance.
- Reading, translating, or exposing `constitution_enforcement_events`,
  `risk_evaluation_events`, `approval_events`, `deployment_manifests`,
  `model_artifacts`, `model_training_runs`, or `risk_rulesets` — no
  `sentinel_engine` contract exists for any of these today (confirmed:
  `Approval` does not fit the real 6-row constitution shape, per
  ADR-016's own finding; no `RiskEvaluation` contract exists anywhere in
  `sentinel_engine`, per prior read-model analysis). Exposing these
  requires new domain/event-model decisions this ADR does not make.
- Computing, deriving, estimating, or approximating any of the
  **Frozen** Five-Metric Framework values (Decision Quality Score,
  Conviction Score, Evidence Strength, Model Agreement, Model
  Confidence — frozen per `docs/architecture/ARCHITECTURE_FREEZE_STATUS.md`,
  "Rule 1: Metrics are derived, not calculated in UI," "Rule 3: Scores
  are not predictions") from raw `model_outputs` or any other Trust
  Ledger data. `final_confidence` may be carried through as
  `Decision.confidence` exactly as it already is on the row — nothing
  beyond that.
- Any UI, screen, controller, or Decision Center wiring change.
- Any synchronization, reconciliation, drift-detection, or repeat-run
  mechanism against the previously-created `DecisionProjection`.
- Any bidirectional data flow of any kind.
- Any second or additional `decision_id` beyond the single one fixed at
  acceptance — this ADR authorizes exactly one named `decision_id` and
  prohibits processing any other; examining a different or additional
  decision requires its own, separate architecture-owner approval, not
  an expansion of this authorization.
- Selection of ADR-004 Option A, B, or C.
- Amendment of ADR-004.

## 6. Relationship to ADR-004

This ADR does not amend, supersede, or modify ADR-004 in any way.
ADR-004 remains the sole governing document for the permanent Trust
Ledger↔`sentinel_engine` ledger-ownership question. This ADR does not
select Option A, does not select Option B, does not select Option C.
Trust Ledger remains the sole source of truth for the one record this
ADR reads; the `DecisionProjection` record this ADR authorizes is a
derived representation, not a second authoritative ledger, and carries
no independent evidentiary weight beyond what the underlying Trust
Ledger row already establishes. Any future, permanent ledger-ownership
decision remains governed exclusively by ADR-004, on ADR-004's own
stated criteria and timeline.

**INTERPRETATION, stated explicitly rather than assumed:** whether this
ADR's mechanism constitutes "implementation" of an ADR-004 option within
the meaning of ADR-004 criterion 6 is not settled by any existing
document. This ADR's position is that it does not, because (a) it is
explicitly temporary, non-durable, and disclaimed as non-permanent,
mirroring ADR-013's accepted precedent; (b) it operates on the one
fixed, explicitly-named `decision_id` this ADR authorizes, not an
expanding set, rather than establishing any ongoing capability; (c)
ADR-004 criterion 3 itself contemplates "a tested dry run... against
real `trust_ledger` data" as a precondition to (not a component of)
making the permanent choice — this mechanism is offered as exactly that
dry run. **The architecture owner has reviewed and accepted this
position, per Section 2's Architecture-Owner Acceptance record.**

## 7. Relationship to ADR-013

This ADR follows ADR-013's structural pattern (narrow, temporary,
non-production, non-durable, explicit non-authorization list, explicit
disclaimer of ADR-004 selection) but is a **separate, independent**
exception, not an extension of ADR-013. It does not modify
`sentinel_engine/composition/evidence.py`, does not add a consumer to
ADR-013's `EvidenceService` singleton, and does not rely on ADR-013
having already authorized projection creation or direct database reads
— it authorizes both of those itself, explicitly, as ADR-013 itself
required ("separate governance"). ADR-013 remains unchanged, unmodified,
and fully in force.

## 8. Relationship to ADR-016

ADR-016 is **Proposed — Implementation Deferred**, not Accepted, and is
therefore not binding on this ADR. This ADR does not rely on ADR-016 for
authorization and does not extend it. This ADR's scope is narrower than
ADR-016's in one respect (it does not touch `constitution_enforcement_events`
or any Risk Governor data at all — Section 5 explicitly excludes this)
and broader in another (it authorizes actual read access and projection
creation, which ADR-016 explicitly declined to authorize even in draft
form). The architecture owner should weigh ADR-016's reasoning — that
"any reader... is exactly the kind of ledger-integration work ADR-004
gates" — as persuasive-but-non-binding prior analysis, not as a
controlling rule.

## 9. Data/Lineage Boundary

Explicitly bounded: `decision_events` (core fields only: `decision_id`,
`asset`, `action`, `timestamp`, `final_confidence`) and `model_outputs`
(via the existing, unmodified `evidence_adapter.to_evidence_records()`,
which itself requires exactly the `xgboost`/`lstm`/`finbert` keys —
verified present in this shape in real production rows). No other table
or column is in scope. `portfolio_snapshot`, `market_context`,
`risk_checks`, `intent`, and `data_completeness` on `decision_events`
are **not** translated by this ADR — no existing `sentinel_engine`
contract has a field for any of them, and inventing one is a
domain/event-model decision this ADR does not make.

## 10. Repository/Composition Boundary

One new, dedicated composition point, entirely separate from
`sentinel_engine/composition/evidence.py`. It owns: one temporary
`LedgerStore` implementation (state: `List[Event]`; behavior: `append`,
`read_all`); one temporary `ProjectionRepository` implementation (state:
`Dict[str, DecisionProjection]`; behavior: `get`, `save`, inheriting
`advance_status()` unchanged); one `LedgerRepository` wrapping the
former; one `DecisionService` and one `EvidenceService` constructed
against these, for the lifetime of a single script invocation only. No
singleton, no process-persistent state, no reuse across invocations is
authorized.

## 11. Read-Only Safety Requirements

The database connection to `data/trust_ledger.db` must be opened in a
mode that makes write operations impossible at the connection level, not
merely unused by convention (demonstrated feasible:
`sqlite3.connect('file:...?mode=ro', uri=True)` in prior read-only
audits of this same file). No `INSERT`/`UPDATE`/`DELETE` statement may
appear anywhere in the authorized script. The script must not hold the
database connection open longer than the single read operation
requires.

## 12. Projection Creation Rules

`DecisionService.create_decision()` may be called at most once per named
`decision_id` per script invocation. **REQUIRED IMPLEMENTATION
PREREQUISITE, not resolved by this ADR:** no existing contract enforces
idempotency — `ProjectionRepository.save()`'s existing implementations
unconditionally overwrite by `decision_id` key (verified in
`sentinel_engine/tests/test_decision_service.py` and the concrete
implementations inspected), and no test anywhere in the codebase
establishes duplicate-`decision_id` behavior for `create_decision()`.
Any implementation of this ADR must add its own guard (e.g. refuse to
re-process a `decision_id` already present in the temporary
`ProjectionRepository` within the same run) rather than relying on an
existing safety net that does not exist.

## 13. Prohibited Behaviors

Restated from Section 5 for emphasis, plus:

- No import of this mechanism's code by any other module, application,
  or test outside itself.
- No environment variable, feature flag, or configuration path that
  could cause this mechanism to run automatically, silently, or as a
  side effect of any other process.
- No documentation claiming Trust Ledger data is "verified" in the
  Decision Center sense — the projection this ADR creates carries no
  hash, no independent cryptographic commitment, and no
  audit-fingerprint claim.

## 14. Rollback / Removal

Deleting the authorized script/module and the `DecisionProjection`
record it produced (held only in its own temporary, process-local,
non-durable repository — nothing persists past the invocation) fully
reverts this ADR's effect. No schema change, no data migration, no
other file requires reverting. Trust Ledger itself is never written to,
so no Trust Ledger rollback is ever needed.

## 15. Expiration / Review

This authorization expires — and must be re-justified or formally
migrated — no later than whichever of the following occurs first: (a)
ADR-004's Option A/B/C choice is made (per ADR-004's own criteria); (b)
this mechanism's temporary repository implementations are proposed for
reuse by any second consumer (requires separate governance, per Section
5); or (c) 90 days from acceptance (i.e. no later than 2026-11-19),
whichever is sooner, consistent with ADR-013's "Primary Risk" concern
that temporary infrastructure becomes permanent through incremental
reuse.

## 16. Acceptance Criteria

This ADR may be considered accepted only when the architecture owner has
explicitly resolved, in writing, the interpretive question in Section 6
— this ADR does not resolve that question for them, only frames it. In
addition: exactly one named `decision_id` is fixed and explicit at
acceptance time; no item in Section 5 is violated by the accepted
implementation plan; the Section 12 idempotency prerequisite has an
implementation plan.

**Satisfied at acceptance (2026-08-21):** the architecture owner
resolved the Section 6 interpretive question as recorded in Section 2.
The named `decision_id` is not yet fixed as of acceptance — selecting it
is an implementation-time step, to be recorded when this ADR's
authorized mechanism is actually run, consistent with Section 2's
acceptance not itself authorizing implementation.

## 17. Consequences

**Positive:** proves or disproves, against exactly one real decision,
whether the existing `sentinel_engine` contracts (`decision_adapter`,
`evidence_adapter`, `DecisionService`, `ProjectionRepository`) are
sufficient for real data without waiting for ADR-004's full resolution;
produces exactly the "tested dry run against real `trust_ledger` data"
ADR-004 criterion 3 names as a prerequisite; keeps the exception
extremely narrow and fully reversible.

**Negative:** introduces a second, independent temporary repository
implementation pair (alongside ADR-013's), increasing the number of
non-durable in-memory Sentinel states a future reader must reconcile;
does not itself close any of the domain/event-model gaps (model
identity, governance verdict richness, Risk Governor state, hash, the
Five-Metric Framework) prior audits identified — this remains a narrow
proof of the smallest possible slice, not a step toward a complete
Decision Center.

**Primary Risk:** identical in kind to ADR-013's named risk — temporary
infrastructure becoming permanent through incremental reuse — with the
added dimension that this ADR, unlike ADR-013, touches the live
database file directly, however read-only, which is new ground no prior
ADR has crossed.

## 18. Open Questions

- Whether "Mock Decision Data" being explicitly listed as in-scope for
  Phase 2A in the **Frozen** `ARCHITECTURE_FREEZE_STATUS.md` creates a
  tension with this ADR's premise of bridging *real* data into the same
  product surface — not resolved by any document; the frozen document
  predates ADR-004 by five days and does not address ledger ownership at
  all, so whether it constrains this ADR is itself unresolved.
- Whether the placeholder `evidence_reference`/`risk_reference` values
  (Section 4, item 5) are acceptable to the architecture owner or
  require their own resolution before implementation begins.
