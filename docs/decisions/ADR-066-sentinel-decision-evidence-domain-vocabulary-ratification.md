# ADR-066 — Sentinel Engine Decision / Evidence Domain-Vocabulary and Optional-Field Ratification (Inert Representation Only)

**Status:** Accepted — scope limited to the inert domain representation /
vocabulary and the one adapter contract narrowing described in §3 (see
`## Acceptance`). Per ADR-058 D2, full authoritative status additionally
requires this file to be tracked/landed on the default branch; that has not
yet occurred as of this acceptance act — the ADR remains untracked pending a
separate LAND batch. The acceptance decision recorded in `## Acceptance` is
the Architecture Owner act itself, distinct from and prior to that landing
step.
**Date Proposed:** 2026-09-08
**Date Accepted:** 2026-09-04
**Decision Type:** Architecture / Governance — Domain-Vocabulary Ratification (no runtime behavior change beyond one adapter contract narrowing, §8)
**Related ADRs:** ADR-001, ADR-009, ADR-011, ADR-012, ADR-013, ADR-014, ADR-020, ADR-045, ADR-050, ADR-058, ADR-065

---

## 1. Context

A batch of additive changes to `sentinel_engine/` domain contracts and their
receiving-side adapter currently sits uncommitted in the working tree
(referred to here as "Batch 2/3"). A read-only governance audit (Batch
4E-STATUS) established:

- **No Accepted ADR authorizes these changes.** ADR-001 names the
  `Decision`/`Evidence` contracts as existing but does not govern their field
  evolution or freeze them. ADR-009/012/013/014 govern the Evidence/Governance
  **bot integration**, not the domain vocabulary. ADR-047/048/049/050/051 cite
  the same source document these changes cite but each explicitly authorizes
  **zero** code/test/schema change and governs only
  `bot/trust_ledger/constitution.py` advisory boundaries.
- **The only stated basis in the code itself is
  `docs/architecture/SENTINEL_ENGINE_PAPER_TRADING_BEHAVIORAL_CONTRACT_P0.md`**,
  which is non-binding: `docs/architecture/*` is gitignored / Tier-4 per ADR-044
  and ADR-011, and that file's own header states it *"does not create, amend, or
  supersede any ADR."* It cannot be an authorization source.
- The changes are **technically sound, additive, and cross no boundary into
  approval or execution authority** — but they are governance-unresolved, and
  one of them (§8) narrows an existing contract.

This ADR is a deliberate, narrow ratification of that existing, verified
representation-level work, following the precedent ADR-050 set for Constitution
Rule 5: *recognize and stabilize an existing implementation invariant, without
claiming it was previously ratified and without introducing new runtime
design.* It differs from ADR-050 in one respect it states openly: §8 ratifies a
small, real contract narrowing, not a pure no-op.

## 2. Problem

The Sentinel Engine domain layer needs a settled, citable vocabulary for:
the action a `Decision` proposes; a `Decision`'s investment horizon; whether a
piece of `Evidence` supports or contradicts its `Decision`; and a handful of
optional decision-context fields (allocation figures, an uncertainty attribute,
free-text thesis/counterfactual). That vocabulary already exists in code but
rests entirely on a non-binding document. Absent a ratifying ADR it cannot be
landed under ADR-058 D2, and any future work referencing it inherits the same
gap.

Separately, `sentinel_engine/adapters/decision_adapter.py::to_decision()` now
validates `action` against the fixed vocabulary rather than accepting any
non-empty string. That is a real, if narrow, change to an existing contract and
needs an explicit decision of record.

## 3. Decision

Ratify the following **inert domain representation and vocabulary** as the
Sentinel Engine's settled Tier-2 decision of record. "Inert" here means: a
type or field that carries a value and nothing else — no evaluation, no
enforcement (except §8's boundary check), no lifecycle, no side effect, no
authority.

### 3.1 `DecisionAction` enum

`sentinel_engine/domain/decision_action.py` — exactly five members, no more:

```
BUY   BUY_MORE   HOLD   SELL   WAIT
```

Every value is a **recommendation label**, never an executable order. Nothing
in this module, in `DecisionService`, or anywhere this enum is used, calls an
executor, a broker client, or `RiskManager`.

### 3.2 `Horizon` enum

`sentinel_engine/domain/horizon.py` — exactly three members, no more:

```
TACTICAL   MEDIUM   LONG
```

An inert categorical label only. No expiry, no automatic re-evaluation, no
transition rule, no enforcement.

### 3.3 `EvidencePolarity` enum

`sentinel_engine/evidence/evidence_polarity.py` — exactly two members:

```
SUPPORTING   CONTRADICTING
```

A classification of a single existing `Evidence` record. It is **not** a
weighting, a score, a corroboration rule, or an input to any recommendation or
decision authority. It does not fork `Evidence` into subtypes.

### 3.4 Optional `Decision` fields

`sentinel_engine/domain/decision.py` — six additive fields, each
`Optional[...] = None`, each with no validation in the domain object (matching
this module's existing trusting-domain-object convention):

```
horizon                     Optional[str]
desired_allocation          Optional[float]
minimum_viable_allocation   Optional[float]
uncertainty                 Optional[float]
thesis                      Optional[str]
counterfactual              Optional[str]
```

Every existing caller that constructs a `Decision` without them keeps working
unchanged. See §5 for the precise, deliberately bounded meaning of each.

### 3.5 `Evidence.polarity`

`sentinel_engine/evidence/evidence.py` — one additive field,
`polarity: Optional[str] = None`, no domain-object validation, defaulting to
`None` so every existing caller is unaffected.

### 3.6 `DecisionService` optional-field payload passthrough

`sentinel_engine/services/decision_service.py::create_decision()` includes the
six §3.4 fields in the `DECISION_CREATED` event payload. This is a passthrough
of already-optional values into an existing event dict — no new behavior beyond
carrying the fields.

### 3.7 `EvidenceService` polarity payload passthrough

`sentinel_engine/services/evidence_service.py::associate_evidence()` includes
`polarity` in the `EVIDENCE_ATTACHED` event payload. Same character as §3.6.

### 3.8 `decision_adapter.to_decision()` vocabulary enforcement — CONTRACT NARROWING

`sentinel_engine/adapters/decision_adapter.py::to_decision()` now raises
`ValueError` when `action` is not one of the five `DecisionAction` values, in
addition to its existing "must be a non-empty string" check. It also validates
the six §3.4 optional fields **only when present** (non-empty `str` for
`horizon`/`thesis`/`counterfactual`; numeric for
`desired_allocation`/`minimum_viable_allocation`/`uncertainty`), and omits
absent ones so `Decision`'s own defaults apply — the adapter never invents a
value.

**This is a deliberate contract narrowing, ratified as intentional:**

- Before: `to_decision()` accepted **any** non-empty string as `action`.
- After: only `BUY`, `BUY_MORE`, `HOLD`, `SELL`, `WAIT` are accepted at this
  boundary. Values such as `"REJECT"` — previously accepted as an arbitrary
  string — are **intentionally no longer accepted by this adapter.**
- **`"REJECT"` is deliberately NOT added to `DecisionAction`.** A rejected
  trade or governance operation is an *outcome* of evaluating a decision, not a
  kind of investment action a decision proposes. Representing it as a
  `DecisionAction` value would conflate "what was recommended" with "what
  happened to the recommendation" — the same category error ADR-045 §6 and the
  ADR-065 `outcome`-field precedent already refuse elsewhere. Rejection
  belongs in an outcome/event representation (e.g. ADR-065's `DECISION_EXECUTED`
  payload `outcome` field, or the existing Trust Ledger
  `QUALIFIED_REJECTION` event type), not in this enum.
- This narrowing is confined to `sentinel_engine/adapters/decision_adapter.py`.
  The `Decision` domain object itself still does no `action` validation
  (§3.1 keeps the trusting-domain-object convention); enforcement lives only at
  the adapter boundary, exactly as ADR-012 established for the evidence adapter.
- No production caller of `to_decision()` exists today (confirmed by the Batch
  4E-STATUS audit and consistent with TRADING_INTELLIGENCE_BOUNDARY.md §3:
  *"Nothing in `bot/` constructs one today"*), so this narrowing has no live
  blast radius. It constrains only future callers, and does so intentionally.

## 4. Scope

**In scope — ratified by this ADR:** §3.1 through §3.8 exactly, and the unit
tests that directly exercise those types and fields (§9).

**Out of scope — not ratified, not authorized, not touched:** everything in §6,
plus `sentinel_engine/tests/test_recommendation_governance_lifecycle.py` (§9,
held for a future ADR), plus any other working-tree change not enumerated in
§3 (e.g. `docs/REQUIREMENTS.md`, `tests/req_snapshots/req_state.json`, and the
uncommitted one-line edit to `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`
remain separate concerns this ADR does not address).

## 5. Precise, Bounded Meaning of Each Optional Field

Ratified **only** as optional stored decision context. None of the following
implies an engine, evaluator, algorithm, or lifecycle:

- **`thesis`** — optional free-text string holding the recommendation's own
  stated reasoning, if a caller supplies one. This ADR does **not** ratify a
  thesis engine, a conviction engine, a thesis evaluator, automatic thesis
  invalidation, or any Stage-3 Thesis/Conviction capability. Nothing populates,
  reads, scores, or acts on this field. See §7 (ADR-011).
- **`counterfactual`** — optional free-text string holding a
  "would we open this today?" style note, if supplied. Same treatment as
  `thesis`: inert storage only, no evaluator, no automatic reassessment.
- **`uncertainty`** — optional numeric attribute, a bare float mirroring
  `confidence`'s existing representation. This ADR does **not** define a
  confidence/uncertainty formula, a calibration methodology, bounds enforcement,
  or a distributional model. It is a value slot, nothing more.
- **`desired_allocation`, `minimum_viable_allocation`** — optional numeric
  decision data. This ADR does **not** define or authorize any position-sizing
  algorithm, Kelly logic, allocation policy, or capital-pool interaction. They
  are value slots.
- **`horizon`** (the `Decision` field) — optional string, expected to carry a
  `Horizon` value when set. This ADR does **not** authorize horizon
  enforcement, expiration, automatic re-evaluation, horizon-change detection,
  or any lifecycle transition. Inert categorical value only.

## 6. Explicit Non-Goals / Authority Boundary

The types and fields ratified in §3 are **inert representation and vocabulary
only.** This ADR does **not** authorize, imply, prepare for, or partially
enable any of the following. Each remains governed elsewhere or explicitly
deferred:

- Causal Sentinel recommendation (a recommendation influencing what `bot/`
  does).
- Pre-execution Sentinel decision creation (`DecisionService.create_decision()`
  called before or during the `bot/` entry-gate sequence).
- The Decision → Recommendation → Approval → Execution causal lifecycle.
- `GovernanceService.register_policy()` for any operative Phase-1A policy.
- `GovernanceService.record_approval()` wiring into any production path.
- Operative `GovernanceService` approval of any kind.
- Any Sentinel authority over `RiskManager.approve_buy()`.
- Any change to `RiskManager`, `PaperExecutor`, `AlpacaClient`, or
  `bot/execution/factory.py`.
- Any `bot/` integration, import, or ADR-002 exception (none is created or
  needed — every §3 file is inside `sentinel_engine/`, outside ADR-002's
  protected scope).
- `EntryContext.decision_id`, any `bot/main.py` change, or any pre-Gate-8f
  Sentinel lookup (all held deferred by ADR-065 §3.2, unchanged here).
- Autonomous execution, automatic authority expansion, or live / Robinhood
  execution.
- Any position lifecycle, exit-decision intelligence, averaging-down logic,
  blank-slate reassessment, or `WAIT` scheduling.
- Special execution logic for `BUY_MORE` or `WAIT` — they are action labels
  only.
- Evidence weighting, causal inference, recommendation scoring, or any decision
  authority derived from `EvidencePolarity`.
- Any new `EventType` or `DecisionState` member (none is added).
- Any persistence, ledger backend, or ADR-004 Option A/B/C selection.

## 7. Relationship to Existing ADRs

### ADR-058
This ADR is subordinate to ADR-058 D1–D4. It is `Status: Proposed` and
non-authoritative until landed under D2. Authoring it records a proposal only
(D4).

### ADR-001
Every §3 change is additive to contracts ADR-001 already places inside
`sentinel_engine/`. No package structure, module path, or ownership boundary
changes. `sentinel_engine`'s zero-import-of-`bot` guarantee is preserved —
`decision_action.py`, `horizon.py`, and `evidence_polarity.py` import only from
the standard library, and `decision_adapter.py` continues to import no `bot`
type.

### ADR-011 — adjacency, not conflict
ADR-011 established that Stage-3 Thesis/Conviction and Stage-11/12 Investment
Memory are **not a Phase-1 implementation dependency**. This ADR ratifies
`thesis` and `counterfactual` **only as optional, inert, unread string fields
that default to `None`**. An empty value slot that nothing populates, reads,
evaluates, or acts on is **not an implementation of Stage-3 Thesis/Conviction**
and does not make it a dependency. No genuine conflict exists; this ADR does
not supersede, amend, reinterpret, or weaken ADR-011, and does not claim any
Stage-3 capability is now implemented.

### ADR-020 — adjacency, not conflict
ADR-020 ("Sell Intelligence", Accepted — **Implementation Deferred**) uses the
vocabulary `holding_horizon` for a future exit-decision-intelligence capability
it explicitly does not authorize. This ADR ratifies a `Horizon` enum and an
optional `horizon` field on `Decision` **as an inert categorical value only** —
no exit intelligence, no holding-period enforcement, no automatic
re-evaluation. This is vocabulary adjacency, not a conflict. This ADR does not
supersede, amend, or reinterpret ADR-020, and does not authorize any part of
the exit-decision intelligence ADR-020 defers.

### ADR-045 — prohibition unchanged
ADR-045 §3 prohibits operative Phase-1A `Policy` registration and
`GovernanceService.record_approval()` wiring in the production trust-decision
path. **This ADR does not alter, weaken, or create any exception to that
prohibition.** Nothing in §3 registers a policy, constructs an `Approval`,
calls `record_approval()`, or wires any governance evaluation into a production
path. `ApprovalStatus` is unmodified.

### ADR-050 — precedent followed
This ADR follows ADR-050's "recognize and stabilize an existing implementation
invariant" ratification pattern, and mirrors its explicit non-claims: it does
not claim prior ratification, does not freeze any specific string/constant as
architectural vocabulary beyond the enum member sets named in §3, and does not
establish a general cross-product architecture. Unlike ADR-050 it does ratify
one real contract narrowing (§8) rather than a pure no-op — stated openly here
rather than glossed.

### ADR-065 — separate governance
ADR-065 (Accepted, landed in commit `958751f`) governs **execution-outcome
reporting only** — `execution_adapter.py`, `composition/execution.py`,
`DecisionService.record_execution()`, `DecisionState.DECISION_EXECUTED`, and the
`bot/_main_cycle.py` report-half. ADR-065 **does not authorize any of the §3
domain-contract changes** in this ADR, and this ADR does not modify, extend, or
reinterpret ADR-065. ADR-065 §3.2's deferred list (EntryContext.decision_id,
pre-Gate-8f lookup, causal recommendation, etc.) remains deferred and is not
reopened here.

### ADR-009 / ADR-012 / ADR-013 / ADR-014
Untouched. The Evidence/Governance bot-integration paths those ADRs authorize
are not modified. `EvidencePolarity` and `Evidence.polarity` are additive to
the `Evidence` contract ADR-012 consumes, but ADR-012's `to_evidence_records()`
signature, behavior, and MODEL_OUTPUT shape are not changed by this ADR, and no
polarity value is introduced into that path.

## 8. Compatibility / Contract Impact

- **§3.1–3.7 (enums, optional fields, payload passthroughs):** backward
  compatible. Every new field defaults to `None`; every existing constructor
  call and event consumer keeps working unchanged. No `EventType`,
  `DecisionState`, or `ApprovalStatus` member added or changed.
- **§3.8 (`to_decision()` action enforcement):** a **contract narrowing**, as
  detailed in §3.8. Accepts strictly fewer `action` values than before.
  Blast radius today is zero (no production caller of `to_decision()` exists).
  Future callers must pass a `DecisionAction` value. This is intentional and is
  the one non-additive item in this ADR.
- No persistence, schema, migration, or ledger change.
- No `bot/`, `dashboard/`, `scheduler/`, `database/`, `ledger/`, or workflow
  change. No ADR-002 exception created or required.

## 9. Testing

**Ratified:** unit tests that directly exercise the §3 types and fields —
their construction, their defaults, their preservation through
`to_decision()` / `create_decision()` / `associate_evidence()`, and the §3.8
rejection of out-of-vocabulary `action` values. Specifically the working-tree
additions to `test_decision.py`, `test_decision_adapter.py`,
`test_decision_service.py` (only the optional-field and `DecisionAction`
vocabulary tests), `test_evidence.py`, `test_evidence_service.py`, and the new
`test_decision_action.py`, `test_horizon.py`, `test_evidence_polarity.py`.

**Explicitly NOT ratified and held for a future ADR:**
`sentinel_engine/tests/test_recommendation_governance_lifecycle.py`. That test
exercises a full Decision → Governance-evaluation → `record_approval()` pattern
with `Policy(enabled=True)` / `Approval(APPROVED)` fixtures. Although it is
test-only and wires nothing into production, it pre-figures the unresolved
causal recommendation/approval lifecycle (Batch 4D) and brushes ADR-045 §3's
prohibited operations. It is left in the working tree **unmodified and
undeleted**; it must be governed by the future causal-lifecycle ADR, not this
one.

This ADR authorizes no change to any existing test and no removal or weakening
of any test.

## 10. Deferred Work (requires separate governance)

- The causal Decision → Recommendation → Approval → Execution lifecycle
  (Batch 4D's open question).
- Any operative use of `DecisionAction`/`Horizon`/`uncertainty`/allocation
  fields — sizing algorithms, horizon lifecycle, thesis evaluation, calibration
  methodology, `BUY_MORE` blank-slate reassessment, `WAIT` scheduling.
- Operative `EvidencePolarity` use — weighting, scoring, corroboration rules.
- `test_recommendation_governance_lifecycle.py` ratification.
- Any `bot/` integration of any §3 type.
- Landing of the Batch 2/3 implementation itself — permitted only after this
  ADR is Accepted and landed under ADR-058 D2, at which point the
  implementation may be committed under this ADR's authority using
  blob-granular staging (mirroring ADR-065's landing discipline) to keep
  unrelated working-tree changes out.

## 11. Rollback

If this ADR is later superseded: a superseding ADR marks it
`Superseded by ADR-0NN`. If the §3 implementation has been landed under it,
rollback is deletion of `decision_action.py`, `horizon.py`,
`evidence_polarity.py`, and reversion of the additive fields/passthroughs and
the §3.8 adapter check — a single-commit revert with no schema, migration, or
persistence cleanup (nothing at that layer is touched). Because §3.8 has no
production caller, reverting it has no live blast radius.

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-09-04
**Accepted By:** Architecture Owner (explicit act performed directly in this
conversation — Batch 4E-ACCEPT — not inferred from the existing
implementation, from the Batch 4E-RATIFY draft, or from any other source)
**Accepting / landing commit:** — none yet. This acceptance act has not been
committed. Per ADR-058 D2, full authoritative status additionally requires
this document to be tracked on the default branch and landed under the
repository's applicable write/merge controls; that is a separate, subsequent
LAND batch, not part of this acceptance. No PR number or commit SHA is
asserted because none exists yet.

**Accepted scope — exactly, and only:** the inert domain representation and
vocabulary in §3.1–§3.7 (`DecisionAction`, `Horizon`, `EvidencePolarity`; the
six optional `Decision` fields; `Evidence.polarity`; the two service payload
passthroughs), together with the `decision_adapter.to_decision()` behavior in
§3.8 — including its **deliberate contract narrowing**: out-of-vocabulary
`action` values such as `"REJECT"` are intentionally rejected at that boundary,
and `"REJECT"` is **not** added to `DecisionAction` (rejection is an outcome,
not an investment action). The unit tests in §9 that directly exercise these
types and fields are ratified with them.

**Not authorized by this acceptance** — every item in §6 remains
non-authorized, restated here because acceptance does not expand it: causal
Sentinel recommendation; pre-execution decision creation; the
Decision → Recommendation → Approval → Execution lifecycle; `register_policy()`
/ `record_approval()` / operative `GovernanceService` approval; any Sentinel
authority over `RiskManager.approve_buy()`; any change to `RiskManager`,
`PaperExecutor`, or `AlpacaClient`; any `bot/` integration, import, or ADR-002
exception; `EntryContext.decision_id` or any pre-Gate-8f Sentinel lookup;
autonomous / automatic-expansion / live execution; any position lifecycle or
exit intelligence; special `BUY_MORE` / `WAIT` execution logic; evidence
weighting or scoring from polarity; any new `EventType` / `DecisionState` /
`ApprovalStatus` member; any persistence, ledger backend, or ADR-004 option.

This acceptance ratifies the ADR-066 text exactly as Batch 4E-RATIFY drafted
it. No section other than the header status/date lines and this `## Acceptance`
section (plus the Status Log entry below) was altered to perform the
acceptance. `sentinel_engine/tests/test_recommendation_governance_lifecycle.py`
remains excluded from ratification (§9) and untouched.

---

## 12. Status Log

**Proposed — 2026-09-08 (Batch 4E-RATIFY).** Drafted as an ADR-authoring-only
task following the Batch 4E-STATUS governance audit, which found the Batch 2/3
domain-contract work technically sound but unauthorized by any Accepted ADR and
resting solely on the non-binding
`docs/architecture/SENTINEL_ENGINE_PAPER_TRADING_BEHAVIORAL_CONTRACT_P0.md`. No
production code or test was modified in the course of producing this draft; no
existing ADR was modified; nothing was staged or committed.
`test_recommendation_governance_lifecycle.py` is deliberately excluded from
ratification (§9) and left untouched in the working tree.

**Accepted — 2026-09-04 (Batch 4E-ACCEPT).** The Architecture Owner explicitly
accepted this ADR, in exactly the form Batch 4E-RATIFY drafted it, through the
act recorded in `## Acceptance` above. `Status` now reads `Accepted`, scoped
exactly to §3 and excluding everything in §6. This acceptance was not inferred
from the pre-existing implementation, the draft, or any other source — it is a
direct, explicit act. Per ADR-058 D2, this document additionally requires
tracking/landing on the default branch before it is fully authoritative; that
is a separate LAND batch and has not occurred as of this entry, so ADR-058 D3
still applies until it lands. No production code or test was modified to
perform this acceptance; no other ADR was modified; nothing was staged or
committed. The date rollover during this conversation (system clock now
2026-09-08) does not change the `Date Accepted` the Architecture Owner
specified for this act (2026-09-04).
