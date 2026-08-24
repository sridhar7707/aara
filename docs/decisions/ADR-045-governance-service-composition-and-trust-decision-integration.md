# ADR-045 — GovernanceService Composition Wiring and Trust-Decision Governance/Approval Integration

**Status:** Accepted
**Date Proposed:** 2026-08-24
**Date Revised:** 2026-08-24
**Decision Type:** Architecture / Governance
**Related ADRs:** ADR-002, ADR-004, ADR-009, ADR-012, ADR-013, ADR-014

---

## 1. Context

ADR-014 establishes the Sentinel Engine Phase-1 canonical lifecycle:

```text
Decision → Evidence → Governance Evaluation → Approval → Ledger Event → Projection → Query
```

Of this chain, only "Decision" (the Trust Ledger write) and "Evidence" (ADR-009 +
ADR-012 + ADR-013) currently reach `bot/`. `GovernanceService.evaluate_policy()`
and `GovernanceService.record_approval()` are already implemented and tested
(`sentinel_engine/services/governance_service.py`), and the pure translation
boundary from a Phase-1A `decision_row` into `GovernanceService`'s input
contracts already exists and is tested: `to_policy_id()` and `to_approval()`
in `sentinel_engine/adapters/governance_adapter.py` (ADR-014, Accepted,
implemented, confirmed by direct inspection). Neither function is called from
anywhere today — a read-only inspection of `bot/_main_trust_decisions.py`
confirms zero references to `governance_adapter` or `GovernanceService`, and
`GovernanceService` has no composition boundary anywhere in `sentinel_engine/`
(only `EvidenceService` does, per ADR-013's `sentinel_engine/composition/evidence.py`).

ADR-014 §19 ("Future Work Requiring Separate Authorization") names exactly
this gap and states plainly that composition of `GovernanceService`, reuse of
ledger/projection infrastructure for it, and a narrow `bot/` integration "must
not be inferred from acceptance of [ADR-014]" and require a separate ADR. This
document is that separate ADR.

ADR-014 §8 additionally forbids "reuse of the existing Evidence composition
module (`sentinel_engine/composition/evidence.py`) for `GovernanceService`."
Any composition boundary this ADR authorizes must therefore be a **new,
independent** module — not an extension of ADR-013's.

This ADR follows the same sequencing precedent ADR-012 → ADR-009 and
ADR-014-adapter → (this ADR) already established in this repository:
translation contract first, production wiring decision second.

**Revision note (2026-08-24, revision 1):** this ADR's original draft raised
two open questions (§5, §6) rather than deciding them. Both have since been
resolved by architecture-owner review; that revision recorded those
resolutions while this ADR remained **Proposed**, not Accepted.

**Revision note (2026-08-24, revision 2):** an architecture-only
contradiction scan against ADR-002/004/009/012/013/014 found one legitimate
blocking governance gap: this ADR modifies an ADR-002-protected file
(`bot/_main_trust_decisions.py`) without independently establishing its own
ADR-002 exception, instead of relying on — and explicitly not assuming,
reusing, extending, or inheriting — ADR-009's existing, narrower exception.
§12 ("Relationship to ADR-002 / Narrow Protection Exception") and §13
("Rollback") were added to close this gap. This ADR remains **Proposed**;
this revision does not accept it.

---

## 2. Decision

### 2.0 Authorization Sequence

This ADR is one link in an explicit, ordered governance chain. It authorizes
only the second link below; each subsequent link requires its own separate,
future governance decision and must not be inferred from this ADR's
acceptance:

```text
ADR-014
  ↓
ADR-045 governance composition/evaluation
  ↓
separate Phase-1A Policy registration decision
  ↓
future authorization for Approval recording
  ↓
any future execution authorization
```

Authorize two additive changes, together constituting the trust-decision
governance-evaluation integration:

### 2.1 New composition boundary

```text
sentinel_engine/composition/governance.py
```

Structurally identical in minimalism to ADR-013's `evidence.py`, but a
**separate, dedicated instance** — not a reuse, import, or extension of
`sentinel_engine/composition/evidence.py`'s repositories or singleton. The
module shall:

1. construct exactly one temporary in-memory `LedgerStore` implementation
   (state: `List[Event]`; behavior: `append`, `read_all` — same minimal
   shape as ADR-013 §4.1, satisfying only the existing abstract contract);
2. construct exactly one temporary in-memory `ProjectionRepository`
   implementation (state: `Dict[str, DecisionProjection]`; behavior: `get`,
   `save`, inheriting `advance_status()` unchanged — same minimal shape as
   ADR-013 §4.2);
3. construct exactly one `LedgerRepository` wrapping the former;
4. construct exactly one process-scoped `GovernanceService` instance from
   the two repositories;
5. expose that instance through a single composition accessor,
   `get_governance_service()`, mirroring `get_evidence_service()`'s shape;
6. be consumed by `bot/_main_trust_decisions.py` only for the integration
   authorized in §2.2 below.

Rationale for a dedicated pair rather than reuse: ADR-014 §8 already forbids
reusing `composition/evidence.py`'s instances for `GovernanceService`, and a
shared `LedgerRepository`/`ProjectionRepository` across two independently
governed services would blur which ADR governs which slice of ledger state.
This mirrors the precedent ADR-043 already set (a third, separately governed
temporary repository pair, distinct from ADR-013's) — a fourth here is
consistent with, not a departure from, that pattern.

### 2.2 Bot-side integration (evaluation only)

In `bot/_main_trust_decisions.py::record_decision_safe()`, after the existing
ADR-009 evidence-integration block (current lines ~78-81) and using only the
already-available `decision_row`, add one additional, independently
exception-isolated block:

```text
policy_id = to_policy_id(decision_row)
get_governance_service().evaluate_policy(decision_row["decision_id"], policy_id)
```

This is the entire authorized bot-side change. **`evaluate_policy()`'s return
value is not converted into an `Approval`, is not persisted as a governance
verdict, and is not passed to `to_approval()` or `record_approval()` by
anything this ADR authorizes.** Its only authorized effect is the
`GOVERNANCE_EVALUATED` ledger event and (no-op, since the temporary
`ProjectionRepository` is never seeded — §3 item 11) projection advance that
`GovernanceService.evaluate_policy()` already performs internally, exactly
mirroring ADR-013 §13's precedent for the Evidence path's currently-inert
`advance_status()` call.

`to_approval()` and `GovernanceService.record_approval()` are **not called**
by any code this ADR authorizes. See §6 for why: with no Phase-1A `Policy`
registered, `policy_id` is always unregistered, and an unregistered policy
must not produce an `Approval` record of any `ApprovalStatus` — neither
`APPROVED` nor `REJECTED`. Authorizing `record_approval()` is deferred to a
future ADR, after Policy registration (§6, §11, §2.0).

---

## 3. Explicit Non-Authorization

This ADR does **not** authorize:

1. Any change to `bot/strategy/`, `bot/risk/`, execution/order-fill behavior,
   or BUY/SELL/HOLD/REJECT decision logic — identical restriction to ADR-009.
2. Any second `bot/` file change beyond `bot/_main_trust_decisions.py`.
3. **Registration of an actual Phase-1A `Policy`.** No `Policy` is
   registered by this ADR or its implementation. `policy_id` values this
   integration produces are therefore always unregistered against
   `GovernanceService` (ADR-014 §4). Registering a Policy is separate,
   future governance work — see §6 and the Authorization Sequence in §2.0.
4. **`GovernanceService.record_approval()`, for any `policy_id`, registered
   or unregistered.** This ADR authorizes only the composition boundary
   (§2.1) and the `evaluate_policy()` call (§2.2). No code this ADR
   authorizes constructs an `Approval`, calls `to_approval()`, or calls
   `record_approval()`. See §6.
5. **Treating an unregistered `policy_id` as `ApprovalStatus.REJECTED`, or
   as any other `ApprovalStatus` value.** An unregistered policy means no
   meaningful governance evaluation occurred; it must not be represented as
   a governance verdict of any kind, in any record, log, or future
   projection. See §6 for the full distinction between an unregistered
   policy and a registered policy that evaluates to `REJECTED`.
6. **Inventing a new `ApprovalStatus` value** (e.g., an "UNEVALUATED" or
   "NOT_APPLICABLE" status) to represent the unregistered-policy case.
   `ApprovalStatus` remains exactly `{APPROVED, REJECTED}`, unmodified —
   the unregistered case is handled by *not creating an Approval record*,
   not by adding a third status value.
7. Reuse of `sentinel_engine/composition/evidence.py`'s singleton or
   temporary repositories for `GovernanceService` — forbidden directly by
   ADR-014 §8.
8. Any production `LedgerStore`/`ProjectionRepository` backend, or any
   ADR-004 Option A/B/C selection.
9. Any change to `applications/*/bootstrap.py`.
10. Any modification to `GovernanceService`, `Approval`, `ApprovalStatus`,
    `Policy`, `governance_adapter.py`, or any other existing Sentinel Engine
    contract.
11. Decision creation or projection seeding — the new temporary
    `ProjectionRepository` shall not be seeded, mirroring ADR-013 §13
    exactly. `evaluate_policy()`'s `advance_status()` call will therefore
    normally no-op (`get()` returns `None`), the same intentional,
    non-"fixed" behavior ADR-013 §13 establishes for the Evidence path.
12. Any dashboard, UI, scheduler, or `.github/workflows/*` change.
13. Any change to `dashboard/components/pending_approvals.py` or the
    `database/` approval mechanism — ADR-014 §10 already establishes these
    as structurally unrelated and untouched.

---

## 4. Failure Isolation and Ordering

Identical guarantee to ADR-009, extended to this second integration:

- The governance-evaluation block executes only after `write_decision_event()`
  has returned, and only after the (already exception-isolated) evidence
  block has run to completion or failed — the two blocks are sequential and
  independently isolated, so a governance-evaluation failure can never affect
  the evidence integration's outcome or vice versa.
- The entire block (`to_policy_id`, `evaluate_policy`) is wrapped in its own
  `try/except`, logging a warning on any failure (same pattern as the
  existing `constitution.check_and_log` and evidence-integration blocks at
  this call site).
- A failure anywhere in this block can never fail, delay, retry, or roll back
  the decision write, and can never alter the already-committed BUY/SELL/
  HOLD/REJECT outcome.
- No second `write_decision_event()` call path is created;
  `scripts/verify_single_write_path.py` must continue to pass unchanged.
- `to_approval()` and `record_approval()` are not part of this block — they
  are not called by any code this ADR authorizes (§2.2, §3 item 4).

---

## 5. Autonomous Provenance — Resolved

**Resolved by architecture-owner review (2026-08-24).** The canonical
`approved_by` literal for autonomous Phase-1A decisions is:

```text
"phase1a-autonomous-engine"
```

This satisfies all five constraints ADR-014 §5 places on any future value:
deterministic; non-personal; does not impersonate a human role; does not
reuse or conflict with the existing Sentinel Engine human-role values
enforced by `governance_adapter.py`'s `_HUMAN_ROLE_APPROVED_BY_VALUES` guard
(`"risk_officer"`, `"cro"`); does not assume the unrelated `database/`-side
`"system"` convention transfers.

**This resolves ADR-014 §5's deliberately deferred literal-value question.**
ADR-014 fixed the *constraints* an autonomous `approved_by` value must
satisfy but explicitly declined to select the literal itself, reserving that
for "implementation review or a later governance decision." This ADR is that
later governance decision, for this one field.

**This literal is fixed for future use, not consumed today.** Per §2.2 and
§3 item 4, no code this ADR authorizes calls `to_approval()` or
`record_approval()`, so `"phase1a-autonomous-engine"` is not yet passed to
any `Approval` construction by anything this ADR implements. It is recorded
here so that the future ADR authorizing `record_approval()` (post-Policy-
registration, per §6 and §2.0) has a settled, already-reviewed value to use
rather than re-deriving it.

---

## 6. Unregistered Policy vs. Registered-and-Rejected — Resolved

**Resolved by architecture-owner review (2026-08-24).** This ADR draws an
explicit, permanent distinction between two states that must never be
conflated:

- **Unregistered policy** — `GovernanceService.get_policy(policy_id)`
  returns `None` because no Policy with that `policy_id` was ever
  registered. `is_policy_enabled()` returns `False` in this case purely as
  an implementation default for "nothing to evaluate," not as a governance
  verdict. **No meaningful governance policy evaluation occurred.** This is
  the state every `policy_id` this integration produces will be in, for as
  long as no Phase-1A `Policy` is registered (§3 item 3) — which is to say,
  for the entire scope this ADR authorizes.
- **Registered policy that evaluates to `REJECTED`** — a real `Policy` was
  registered (separate future governance, per §2.0's Authorization
  Sequence), `GovernanceService.evaluate_policy()` ran a real evaluation
  against it, and the decision failed that policy. This is a meaningful
  governance verdict, appropriately represented by `ApprovalStatus.REJECTED`
  on a real `Approval` record.

**Rule: an unregistered policy MUST NOT produce an `Approval` record of any
`ApprovalStatus`** — not `REJECTED`, not `APPROVED`, and not a new, invented
status (§3 items 5-6). Recording `REJECTED` for an unregistered policy would
misrepresent "no evaluation occurred" as "evaluation occurred and failed" —
a materially false governance signal, no different in kind from ADR-014
§5's core concern that autonomous provenance must never be represented as
fictitious human approval.

**Consequence for this ADR's scope:** because no Policy is registered under
this ADR, and Policy registration is explicitly out of scope (§3 item 3),
`record_approval()` has no correct value to record for the current
Phase-1A path — there is no registered-and-evaluated verdict to represent.
Rather than record a false one, this ADR does not authorize
`record_approval()` at all (§2.2, §3 item 4). `evaluate_policy()` remains
authorized because it only ever produces the honest, already-accurate
`GOVERNANCE_EVALUATED` audit event ("evaluation was attempted against this
policy_id, which was unregistered") — it makes no claim about a verdict.

Authorizing `record_approval()` for the Phase-1A path requires, at minimum,
a real Phase-1A `Policy` to be separately governed and registered first, per
the Authorization Sequence in §2.0.

---

## 7. Relationship to ADR-004

Identical posture to ADR-013 §10 and ADR-009's "ADR-004 Boundary": this ADR
authorizes only a temporary, non-production, non-durable composition point.
It does not select ADR-004 Option A, B, or C, does not establish the
temporary repositories as production architecture, and does not accelerate
ADR-004's resolution. ADR-004 remains fully deferred and unchanged.

## 8. Relationship to ADR-009

This ADR does not modify, extend, or supersede ADR-009. ADR-009's existing
Evidence integration in `record_decision_safe()` remains governed by its own
scope. This ADR adds a second, independent, similarly-isolated block to the
same function, following the same failure-isolation and ordering discipline
ADR-009 established, but does not touch the evidence block itself.

## 9. Relationship to ADR-012

Unaffected. `evidence_adapter.py` and its contract are not touched.

## 10. Relationship to ADR-013

ADR-013 remains fully in force and unmodified. This ADR does not reuse,
extend, or draw from `sentinel_engine/composition/evidence.py` — see §2.1's
rationale. The two composition boundaries (`evidence.py`, `governance.py`)
are independent, mirroring ADR-013 §7's own statement that its module "shall
not become a general-purpose Sentinel composition root."

## 11. Relationship to ADR-014

This ADR is exactly the "separate ADR" that ADR-014 §15, §17, and §19
anticipate and require. It does not modify `governance_adapter.py` or its
contract; it only authorizes a caller for the already-accepted, already-
implemented, currently-inert translation functions. ADR-014's explicit
non-authorizations (no Policy registration, no `bot/` change, no composition
change) are inherited here verbatim except for the two narrow additions this
ADR itself proposes (composition boundary, bot call site) — nothing else
ADR-014 deferred is reopened.

**ADR-014 §5 resolution:** this ADR resolves ADR-014 §5's deferred
autonomous `approved_by` literal as `"phase1a-autonomous-engine"` (§5
above). **ADR-014 §4's deferral of Policy registration remains fully in
force and is *not* resolved here** — this ADR explicitly keeps Policy
registration as separate, future governance (§3 item 3, §6, §2.0), and
explicitly withholds authorization of `record_approval()` until that future
governance step occurs.

See §12 below for the separate ADR-002 exception this ADR independently
requests to make the `bot/`-side change in §2.2 possible — ADR-014 itself
authorizes no `bot/` change and grants no ADR-002 exception (ADR-014 §11
invariant 8), so it has no bearing on that question.

---

## 12. Relationship to ADR-002 / Narrow Protection Exception

### 12.1 Protected File and the Existing ADR-009 Exception

`bot/_main_trust_decisions.py` is protected by ADR-002: *"no moves, no
import changes, no refactors, no file changes of any kind"* absent a
dedicated superseding ADR. ADR-009 already lifted this protection — but
**narrowly and exhaustively**, for exactly one file, one function, and one
additive call: its own Evidence integration in `record_decision_safe()`.
ADR-009 states this limit in its own text: *"No other line, function,
class, or file in `bot/` is authorized to change under this ADR."*

**ADR-045 does not assume, reuse, extend, or inherit ADR-009's exception.**
ADR-009's exception covers only the Evidence-integration call it explicitly
names; it grants no authority for any other addition to this file,
including the Governance-evaluation call §2.2 proposes. ADR-045 therefore
requests, and independently justifies below, its own separate, narrowly
scoped exception to ADR-002 — following the same mechanism ADR-009 used,
not building on it.

### 12.2 Scope of This ADR's Requested Exception

**Protected file:** `bot/_main_trust_decisions.py`

**Protected function:** `record_decision_safe()`

**Authorized change:** after the existing ADR-009 Evidence-integration block
runs to completion or fails (it is independently exception-isolated), add
exactly one additional, independently exception-isolated block consisting of
the two-line call sequence already described in §2.2:

```text
policy_id = to_policy_id(decision_row)
get_governance_service().evaluate_policy(decision_row["decision_id"], policy_id)
```

**No other line, function, class, or file in `bot/` is authorized to change
under this ADR** — mirroring ADR-009's own exhaustive restriction, restated
here independently rather than inherited.

**No other `bot/` file is authorized.** Only `bot/_main_trust_decisions.py`
is in scope; no second file may change under this ADR (restates §3 item 2 in
ADR-002 terms).

**No other function, class, control flow, strategy, risk, execution,
scheduler, order, or persistence change is authorized.** This restates §3
item 1 explicitly in ADR-002 terms: `bot/strategy/`, `bot/risk/`,
execution/order-fill behavior, BUY/SELL/HOLD/REJECT decision logic, and any
control flow inside `record_decision_safe()` other than the one additive
block above are all out of scope.

**The existing ADR-009 Evidence call must remain unchanged.** The authorized
Governance-evaluation block is purely additive, placed after the Evidence
block; it does not read, modify, reorder, wrap, or otherwise touch the
Evidence block's existing code, its `try/except`, or its call arguments.

**ADR-045 does not supersede or amend ADR-009**, except insofar as this
section independently authorizes a separate, second additive call in the
same function. ADR-009 is otherwise untouched, unmodified, and remains the
sole governing authority for the Evidence integration.

**Dependency direction:** the authorized call, like ADR-009's, is
one-directional — `bot → sentinel_engine`. Nothing in this ADR's scope
authorizes any `sentinel_engine → bot` import or call, in either direction —
consistent with ADR-001 and every prior ADR in this chain.

### 12.3 Why the Change Is Isolated

- It is a single, additive two-line block, not a modification of existing
  code.
- It is independently exception-isolated in its own `try/except` (§4),
  separate from the Evidence block's `try/except` — a failure in one cannot
  propagate to or mask a failure in the other.
- It reads only `decision_row`, already available at this point in the
  function (post-`write_decision_event()`), inventing no new state, no new
  identifier, and no new control-flow branch.
- It writes nothing back into `decision_row`, the decision write, the
  risk/execution path, or any variable consumed by code after this point in
  the function.

No refactor, rename, reordering of existing statements, or unrelated
modification of any kind is authorized alongside this change.

### 12.4 ADR-002 "Lifting This Protection" Checklist

Addressed explicitly, per ADR-002's own six-item checklist:

1. **Specific module named, with risk tier/coupling restated.** The specific
   module is `bot/_main_trust_decisions.py::record_decision_safe()` — the
   same single chokepoint ADR-009 already identified as the production write
   path for every BUY/SELL/HOLD/REJECT decision (`write_decision_event()`'s
   sole caller, per `scripts/verify_single_write_path.py`). No new module or
   file is touched; this is an addition to an already-audited function, not
   a new coupling.
2. **Isolated branch or worktree.** Any implementation of this ADR must
   occur in an isolated branch or worktree, not directly on `main`,
   identical to ADR-009's requirement. This ADR does not authorize
   direct-to-`main` implementation.
3. **All workflow YAML files referencing the moved paths updated in the same
   change.** Not applicable in the "moved paths" sense — no file is moved,
   and no workflow YAML references `bot/_main_trust_decisions.py` by path.
   No `.github/workflows/*.yml` change is authorized or required (§3 item
   12).
4. **Full test suite passes before and after.** Both `sentinel_engine/tests`
   and the bot-side `tests/` suite (baseline ~1200+ tests per ADR-002, 1274
   passed most recently per ADR-006) must pass unchanged before and after,
   identical to ADR-009's Validation Gate.
5. **Rollback plan stated before implementation starts.** See the dedicated
   §13 Rollback section below — written now, as part of this proposal, not
   reconstructed after implementation.
6. **Both documented entry points verified.** See §12.5 and §12.6 below.

### 12.5 CLI Entry-Point Applicability

**Applicable — must be verified.** ADR-002's own context establishes the CLI
path (`trade.yml` → `python bot/main.py --mode paper --loop`) as one of
exactly two entry points reaching `record_decision_safe()`. Because this
ADR's authorized change lives inside `record_decision_safe()` itself, every
call path that reaches that function — including the CLI path — reaches the
new Governance-evaluation block. This must be exercised in testing,
identical to ADR-009's own Validation Gate requirement.

### 12.6 Scheduler/HTTP Entry-Point Applicability

**Applicable — must be verified. Not omitted.** ADR-002's context (restated
and relied upon by ADR-009's Validation Gate) documents a second,
independent entry point: `watchdog.yml` → `dashboard/http_endpoints.py`
`GET /run/cron` → `scheduler/trading_job.py` → `bot.main.run()`, which also
reaches `record_decision_safe()`. Because the authorized change is inside
the same shared function as the Evidence integration, this entry point is
exactly as applicable to ADR-045 as it was to ADR-009, for the same reason:
both entry points converge on the one chokepoint this ADR touches.
Repository evidence for this conclusion is ADR-002's own two-entry-point
finding and `scripts/verify_single_write_path.py`'s existing
single-write-path guarantee, both already cited by ADR-009. This ADR does
not introduce, modify, or depend on any new entry point beyond these two
already-documented ones.

---

## 13. Rollback

Reverting this ADR's effect, if implemented, requires only:

1. **Remove the ADR-045 Governance Evaluation call block** (the two-line
   `to_policy_id()` / `evaluate_policy()` sequence) from
   `bot/_main_trust_decisions.py::record_decision_safe()`, restoring the
   function to its exact pre-ADR-045 state — i.e., ADR-009's Evidence
   integration, unmodified, with nothing after it.
2. **Remove the ADR-045 governance composition boundary** — delete
   `sentinel_engine/composition/governance.py` in its entirety (the
   dedicated temporary `LedgerStore`, `ProjectionRepository`,
   `LedgerRepository`, `GovernanceService` instance, and
   `get_governance_service()` accessor).
3. **Remove its tests**, if created under this ADR (e.g., any
   `test_composition_governance.py`-equivalent under `sentinel_engine/tests`
   and the `bot/`-side governance-evaluation tests under `tests/phase1a/`).
4. **The ADR-009 Evidence integration remains intact.** Because the
   authorized change is strictly additive and placed after the Evidence
   block without touching it (§12.2, §12.3), reverting steps 1-3 above has
   zero effect on Evidence integration, `to_evidence_records()`,
   `EvidenceService`, or `sentinel_engine/composition/evidence.py`.
5. **No Policy cleanup is required** — ADR-045 does not register a Policy
   (§3 item 3); there is no `Policy` object, registry entry, or
   configuration to remove.
6. **No persistence or database migration rollback is required** — the
   temporary repositories are process-local, in-memory, and non-durable
   (§2.1); no schema, migration, or database file is touched by this ADR.
7. **No production ledger/projection backend rollback is required** — no
   ADR-004 option is selected and no production backend is introduced (§7,
   §3 item 8); there is nothing at that layer to roll back.

Rollback is therefore a single-commit revert with no secondary cleanup,
identical in character to ADR-009's own Rollback section.

---

## 14. Testing Requirements

Mirroring ADR-009's and ADR-013's validation gates:

- `record_decision_safe()` still writes the decision event and returns
  normally when the governance-evaluation block raises at any point.
- `evaluate_policy()` is invoked with `decision_row["decision_id"]`
  verbatim — the identical identifier used by the evidence-integration
  block.
- **`GovernanceService.record_approval()` and `governance_adapter.to_approval()`
  are never invoked by `record_decision_safe()` or any code this ADR
  authorizes** — a dedicated test must assert zero calls to
  `record_approval()` across a full `record_decision_safe()` invocation,
  including the unregistered-`policy_id` case.
- No `to_policy_id` or `evaluate_policy` call occurs before
  `write_decision_event()` returns.
- The governance-evaluation block's failure does not affect the evidence
  block's outcome, and vice versa (independent isolation).
- Composition lifetime: repeated access through `get_governance_service()`
  returns the same instance within a process (mirrors
  `test_composition_evidence.py`'s existing pattern).
- The new temporary `LedgerStore`/`ProjectionRepository` pair: same
  construction/behavior tests as ADR-013 §18.
- Import boundary: extend `test_package_imports.py`'s coverage to include
  `sentinel_engine.composition.governance`, and confirm the whole-package
  AST forbidden-import scan already covers it.
- `scripts/verify_single_write_path.py` re-run and still passing.
- Both of ADR-002's documented entry points verified — the CLI path
  (`trade.yml` → `python bot/main.py --mode paper --loop`) and the
  scheduler/HTTP path (`watchdog.yml` → `dashboard/http_endpoints.py`
  `GET /run/cron` → `scheduler/trading_job.py` → `bot.main.run()`) — both
  reach `record_decision_safe()` and must both be exercised, not just one
  (§12.5, §12.6).
- Full `sentinel_engine/tests` and `tests/` suites, both before and after.

---

## 15. Acceptance Criteria

Both open questions this draft originally raised (§5, §6) have been resolved
by architecture-owner review, as recorded in §5 and §6 above. This ADR may
be considered **Accepted** only when the architecture owner additionally
confirms, in writing, that the resulting implementation plan preserves all
of the following:

- `approved_by` for any future autonomous `Approval` is exactly
  `"phase1a-autonomous-engine"` (§5) — no alternative literal is
  substituted without a further governance decision.
- No `Approval` record, of any `ApprovalStatus`, is ever created for an
  unregistered `policy_id` (§6, §3 items 5-6).
- `GovernanceService.record_approval()` is not invoked by any code this ADR
  authorizes (§2.2, §3 item 4) — only `evaluate_policy()` is authorized.
- No Phase-1A `Policy` is registered by this ADR or its implementation
  (§3 item 3) — Policy registration remains a separate, future governance
  decision, per the Authorization Sequence in §2.0.
- No new `ApprovalStatus` value is invented to represent the
  unregistered-policy case (§3 item 6); `ApprovalStatus` remains exactly
  `{APPROVED, REJECTED}`, unmodified.
- `GovernanceService`, `Approval`, and `Policy` remain unmodified (§3
  item 10).
- `bot/_main_trust_decisions.py` gains only the two-statement
  Governance-evaluation block described in §2.2 — the
  `to_policy_id(decision_row)` translation followed by the
  `evaluate_policy()` call — with no `to_approval()` or `record_approval()`
  call added there.
- No item elsewhere in §3 is violated by the resulting implementation plan.
- **The ADR-002 exception this ADR requests is explicitly documented** (§12)
  — not assumed, reused, extended, or inherited from ADR-009's existing,
  narrower exception.
- **The exact protected file and function are identified**:
  `bot/_main_trust_decisions.py::record_decision_safe()` (§12.2), and no
  other `bot/` file, function, class, or control-flow path is authorized.
- **ADR-002's "Lifting This Protection" checklist is addressed item-by-item**
  (§12.4), including the isolated-branch/worktree requirement and a rollback
  plan stated in advance.
- **CLI and scheduler/HTTP entry-point applicability is documented** (§12.5,
  §12.6) — both are applicable and both must be exercised; neither is
  silently omitted.
- **Rollback is defined** (§13) and covers removing the Governance-evaluation
  call block, the governance composition boundary, and its tests, while
  leaving ADR-009's Evidence integration untouched.
- **ADR-009's Evidence integration remains isolated and unchanged** — the
  Governance-evaluation block is strictly additive, placed after it, and
  does not read, modify, reorder, or wrap the Evidence block's existing
  code (§12.2, §12.3, §13 item 4).

**This ADR's status remains Proposed until the architecture owner records
explicit, separate acceptance.** Resolving §5, §6, and §12 in this and the
prior revision does not by itself change this ADR's status to Accepted, and
no implementation is authorized while it remains Proposed.

---

## 16. Decision Statement

> **Authorize a new, dedicated, temporary `GovernanceService` composition
> boundary at `sentinel_engine/composition/governance.py` (independent of
> ADR-013's `evidence.py`), and one additive, failure-isolated call in
> `bot/_main_trust_decisions.py::record_decision_safe()` that translates the
> existing `decision_row` through the already-accepted `governance_adapter.py`
> and invokes `GovernanceService.evaluate_policy()` only.**
>
> **`GovernanceService.record_approval()` is explicitly NOT authorized by
> this ADR.** No Phase-1A `Policy` is registered by this ADR, and an
> unregistered `policy_id` must never produce an `Approval` record of any
> `ApprovalStatus` (§6). Authorizing `record_approval()` for the Phase-1A
> path requires a separately governed and registered Phase-1A `Policy`
> first, per the Authorization Sequence in §2.0.
>
> **The autonomous `approved_by` literal is resolved as
> `"phase1a-autonomous-engine"` (§5)**, for use by that future
> `record_approval()` authorization — it is not consumed by anything this
> ADR itself authorizes.
>
> **This ADR does not register a Phase-1A `Policy`, does not select an
> ADR-004 option, does not seed or create decision projections, and does
> not invent a new `ApprovalStatus` value. This ADR remains Proposed, not
> Accepted, and authorizes no implementation.**
>
> **This ADR independently requests its own narrow, separate ADR-002
> exception (§12) for the one additive Governance-evaluation call in
> `bot/_main_trust_decisions.py::record_decision_safe()` described above.
> It does not assume, reuse, extend, or inherit ADR-009's existing
> exception, which remains limited to ADR-009's own Evidence integration.
> ADR-009's Evidence integration is untouched and must remain unchanged
> (§12.2). Rollback is defined in §13.**

---

## 17. Status

**Accepted — 2026-08-24.**

**ADR-045 was formally accepted by the architecture owner on 2026-08-24.**

**Acceptance authorizes ONLY the exact scope defined in §2.1, §2.2, and
§12.2** — the new `sentinel_engine/composition/governance.py` composition
boundary (§2.1), the one additive two-statement Governance-evaluation block
in `bot/_main_trust_decisions.py::record_decision_safe()` (§2.2), and that
same change as independently scoped under the ADR-002 exception this ADR
requests (§12.2). No other section expands this authorized scope.

**Acceptance does NOT authorize any of the explicit non-authorizations
listed in §3** — including, without limitation, `record_approval()`,
`to_approval()`, Phase-1A Policy registration, any second `bot/` file or
control-flow change, reuse of ADR-013's `evidence.py` composition, any
ADR-004 Option A/B/C selection or production backend, any change to
`applications/*/bootstrap.py`, any modification to `GovernanceService`,
`Approval`, `ApprovalStatus`, `Policy`, or `governance_adapter.py`, decision
creation or projection seeding, or any `dashboard/`/`scheduler/`/workflow/
`database/` change. All of §3 remains fully in force, unchanged by
acceptance.

**Implementation must occur in an isolated branch or worktree**, not
directly on `main`, as required by §12.4 item 2.

**No implementation has occurred as part of this acceptance action.** This
acceptance is a governance decision only: it does not itself create
`sentinel_engine/composition/governance.py`, does not modify
`bot/_main_trust_decisions.py`, does not add tests, and does not touch any
production code. Implementation remains a separate, subsequent step, subject
to every constraint recorded in §2 through §14.

Sections 5 and 6's open questions were resolved by architecture-owner review
(2026-08-24): the autonomous `approved_by` literal is
`"phase1a-autonomous-engine"`, and `record_approval()` is withheld from
authorization until a Phase-1A `Policy` is separately registered. A
subsequent architecture-only contradiction scan against
ADR-002/004/009/012/013/014 found one legitimate blocking governance gap —
this ADR modified an ADR-002-protected file without independently
establishing its own ADR-002 exception — which §12 and §13 closed. A final
acceptance-readiness review against all 16 consistency checks in this ADR's
governance history returned ACCEPTABLE, and this ADR was accepted on that
basis.

This ADR was originally produced by a read-only governance audit of
ADR-009, ADR-012, ADR-013, and ADR-014 against their current implementation,
at the architecture owner's request, to identify and draft the next
governance step those four ADRs point to but do not themselves authorize; it
was then revised twice prior to acceptance, at the architecture owner's
direction: first to resolve its two open questions (§5, §6), then to
independently establish its own ADR-002 exception (§12) and rollback plan
(§13) rather than relying on ADR-009's narrower one — before being formally
accepted as recorded above.
