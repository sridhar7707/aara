# ADR-067 — Sentinel Causal Decision Lifecycle Boundary

**Status:** Accepted — authorizes exactly the architecture in §3 (pre-gate
causal `Decision` creation via G-A, one shared Sentinel composition pair, and
the two function-scoped ADR-002 exceptions in §13), the narrow supersession
of the three composition clauses in §12, and nothing else. See `## Acceptance`.
Per ADR-058 D2, full authoritative status is met when this file is tracked on
the default branch with `Status: Accepted` and landed under the repository's
applicable write/merge controls — carried by the commit that lands this
acceptance (recorded in the Status Log). **Acceptance authorizes the
architecture, not an implementation** — the causal lifecycle code is a
separate subsequent batch (SPRINT-1.3), subject to every constraint in §13
through §17.
**Date Proposed:** 2026-09-08
**Date Accepted:** 2026-09-04
**Decision Type:** Architecture / Governance — Causal Lifecycle Boundary + narrow ADR-002 exception + narrow supersession of three composition clauses
**Related ADRs:** ADR-001, ADR-002, ADR-004, ADR-009, ADR-011, ADR-012, ADR-013, ADR-014, ADR-020, ADR-043, ADR-045, ADR-047, ADR-048, ADR-049, ADR-050, ADR-058, ADR-065, ADR-066

---

## 1. Context

SPRINT-1.1 (read-only trace, verified again against HEAD `61eabbb` for this
ADR) established that **there is no causal Sentinel decision lifecycle in
production**:

- `bot/strategy/ensemble.py::ensemble_signal()` → `action_to_int()` produces
  an `int` action (`1` = BUY candidate). No Sentinel `Decision` is formed.
- `DecisionService.create_decision()` — **zero production callers**
  (`sentinel_engine/services/decision_service.py:28`; only the facade
  passthrough, a UI comment, and the ADR-043 one-shot diagnostic script
  `scripts/project_one_trust_ledger_decision.py` reference it).
- `decision_adapter.to_decision()` — **zero production callers**.
- `GovernanceService.record_approval()` / `register_policy()` — **zero
  production callers**.
- `GovernanceService.evaluate_policy()` — **one** production caller,
  `bot/_main_trust_decisions.py:95` inside `record_decision_safe()`, run
  **after** `write_decision_event()`; its `bool` result is **discarded**;
  the `policy_id` is always unregistered (ADR-045 §3 item 3).
- `decision_id` is minted inside
  `bot/trust_ledger/decisions.py::write_decision_event()` via
  `bot/trust_ledger/ids.py::new_decision_id(asset)` (`decisions.py:140`),
  called only from `EntryDecisionRecorder.reject()` /
  `.record_executed()` / `.record_order_not_filled()` — i.e. **at gate
  rejection or post-fill**, never before the gate sequence.
- `EntryDecisionRecorder.__init__()` (`bot/_main_trust_decisions.py:111`)
  runs **before** any gate and already computes `model_outputs`,
  `final_confidence`, `market_context`, and holds `candidate_event_id`,
  `deployment_manifest_id`, `symbol`, `trust_conn` — but no `decision_id`
  and no Sentinel `Decision`.
- `EntryContext` (`bot/_main_cycle.py:46-78`) carries no Sentinel
  `decision_id`.
- `RiskManager.approve_buy()` (`bot/_main_cycle.py:321`) is the **sole
  execution-blocking gate** and consumes **zero** Sentinel input.
  `PaperExecutor` (via `bot/execution/factory.py`) is the sole execution
  authority. Both are unmodified by ADR-065.
- ADR-065 execution-outcome reporting
  (`bot/_main_cycle.py::_report_execution_outcome_safe()` →
  `DecisionService.record_execution()` via
  `sentinel_engine/composition/execution.py`) is **post-hoc** and correlates
  by `_latest_decision_id_for_report()` — a read-only
  `SELECT … ORDER BY sequence_number DESC LIMIT 1` against the legacy
  `decision_events` table (ADR-065 §6.1).
- `sentinel_engine/composition/{evidence,governance,execution}.py` each
  construct a **separate** temporary in-memory
  `_TemporaryLedgerStore` + `_TemporaryProjectionRepository` +
  `LedgerRepository` pair and expose one `get_*_service()` accessor.
  Because `DecisionService.create_decision()` is never called on any of
  those pairs, `ProjectionRepository.get(decision_id)` always returns `None`
  and `advance_status()` (`sentinel_engine/repositories/projection_repository.py`)
  **no-ops** on every call. No `DecisionProjection` object exists in
  production, so nothing can walk
  `DECISION_CREATED → EVIDENCE_ATTACHED → GOVERNANCE_EVALUATED → DECISION_EXECUTED`.

ADR-066 (Accepted) ratified `DecisionAction` / `Horizon` / `EvidencePolarity`
and the optional `Decision`/`Evidence` fields as **inert representation
only**, and its §6 lists "pre-execution decision creation" and "the
Decision → Recommendation → Approval → Execution lifecycle" as **not
authorized by ADR-066**. ADR-065 §3.2 lists the pre-gate decision/read
boundary as **deferred**. This ADR is the separate authority both point to.

## 2. Problem

For the existing post-hoc Sentinel annotations to become a coherent,
auditable lifecycle, a Sentinel `Decision` with a **stable identity must be
created before the consequential gate**, and **that same identity must flow
through** the Trust Ledger write, evidence association, governance
evaluation, execution, and outcome — so one `DecisionProjection` walks the
lifecycle. Today the identity is minted last, in three disconnected in-memory
ledgers, and no `Decision` is ever created.

Nothing in the currently-Accepted ADR set authorizes: creating a Sentinel
`Decision` in production, calling `create_decision()`, ordering it before the
gate sequence, or sharing one composition pair across the lifecycle services
(ADR-013 §7, ADR-014 §8, and ADR-045 §2.1 each require a *dedicated,
non-shared* pair). This ADR grants exactly that, and nothing more.

## 3. Decision

Authorize three tightly-scoped changes, and only these:

### 3.A — Pre-gate causal `Decision` creation (bot side)

In **`bot/_main_trust_decisions.py::EntryDecisionRecorder.__init__()`**
— which already runs before every entry gate — additively:

1. Generate one `decision_id` by calling the existing
   `bot/trust_ledger/ids.py::new_decision_id(symbol)` (reused verbatim; no
   new generator, no new prefix, no new identifier scheme). Store it on the
   recorder instance.
2. Construct one `sentinel_engine.domain.decision.Decision` with
   `action = "BUY"` (the existing entry candidate; §6), `decision_id` = the
   value from step 1, `confidence` = the already-computed `final_confidence`,
   `symbol`, a `timestamp`, and `evidence_reference` / `risk_reference` set
   from data already present on the recorder (e.g. `candidate_event_id`; a
   fixed non-empty placeholder such as `"pending"` where no better value
   exists pre-gate). **No new identifier** is minted for these reference
   fields.
3. Call `get_decision_service().create_decision(decision)` (the shared
   accessor from §3.C) exactly once. This emits `DECISION_CREATED` and seeds
   one `DecisionProjection(status=DECISION_CREATED)` on the shared pair.
4. The entire block (steps 1-3, except the `decision_id` string itself,
   which is retained regardless) is wrapped in its own `try/except`,
   logging a warning on any failure, identical in discipline to the
   existing evidence/governance blocks in `record_decision_safe()` and to
   ADR-009 §4 / ADR-045 §4. **A failure here never blocks, delays, retries,
   or alters the gate sequence, `risk.approve_buy()`, `client.buy()`, or the
   Trust Ledger write.**

In **`EntryDecisionRecorder.reject()` / `.record_executed()` /
`.record_order_not_filled()`** and the module-level
**`record_decision_safe()`**: thread `self.decision_id` through to
`write_decision_event()` (§3.B) so the Trust Ledger row is keyed by the same
string. The existing `associate_evidence(decision_row["decision_id"], …)` and
`evaluate_policy(decision_row["decision_id"], …)` calls then key off the
identical value with no further change.

No other `bot/` file, function, or behavior changes. `bot/main.py`,
`EntryContext`, `_handle_entry()`'s gate sequence, `RiskManager`,
`PaperExecutor`, `AlpacaClient`, `bot/execution/factory.py`, and the exit
paths (`record_exit_decision_safe`, `ExitDecisionRecorder`) are **not
touched**.

### 3.B — `write_decision_event()` caller-supplied id (bot side)

In **`bot/trust_ledger/decisions.py::write_decision_event()`**: add one
additive optional parameter `decision_id: str | None = None`, and change the
row literal from `"decision_id": new_decision_id(asset)` to
`"decision_id": decision_id or new_decision_id(asset)`. When no id is
supplied — every current caller, including all exit paths — behavior is
**byte-for-byte identical** to today. No other change to this function or
file. `scripts/verify_single_write_path.py` must continue to pass unchanged
(this creates no new caller of `write_decision_event()`).

### 3.C — One shared Sentinel composition pair (sentinel_engine internal)

Establish a single process-scoped
`LedgerStore` + `ProjectionRepository` + `LedgerRepository` pair, shared by
`DecisionService`, `EvidenceService`, and `GovernanceService` for the causal
lifecycle, plus the `DecisionService` already used by ADR-065 execution
reporting. Concretely (implementation may refine, staying within these
bounds):

- Add one new module, e.g.
  `sentinel_engine/composition/decision_lifecycle.py`, that constructs
  exactly one `_TemporaryLedgerStore` (state `List[Event]`; `append`,
  `read_all`), one `_TemporaryProjectionRepository` (state
  `Dict[str, DecisionProjection]`; `get`, `save`; inheriting
  `advance_status()`), one `LedgerRepository`, and from them one
  `DecisionService`, one `EvidenceService`, one `GovernanceService`.
- Expose accessors: `get_decision_service()`, `get_evidence_service()`,
  `get_governance_service()`. To keep the bot-side call sites and their
  import lines unchanged, `sentinel_engine/composition/evidence.py`,
  `…/governance.py`, and `…/execution.py` are re-pointed so their existing
  accessors (`get_evidence_service()`, `get_governance_service()`,
  `get_decision_service_for_execution_reporting()`) return services built on
  this one shared pair rather than each constructing its own — a
  `sentinel_engine`-internal refactor with **no change to any bot import
  line or accessor name**. (If the architecture owner prefers the bot call
  sites to import the new module directly, that is a permissible
  alternative but widens the §4 exception to those import lines; the
  no-import-change form is preferred.)
- Ownership: the new module owns the pair; module-level construction; no
  DI framework, no service locator, no global mutable re-assignment.
- Lifecycle: process-scoped. Repeated access returns the same instances
  within a process. Separate OS processes (CLI vs scheduler/HTTP) have
  separate state — the same non-durable, process-local limitation ADR-013
  §14 / ADR-045 already accept.
- Import direction: `bot → sentinel_engine` only (unchanged). The new
  module imports only `sentinel_engine.{events,ledger,projections,
  repositories,services}` — the same set the three existing composition
  modules already import; services do not import composition, so no
  circular import is introduced.
- Persistence: none. Still ADR-004-deferred; this is not the production
  Sentinel repository architecture and does not select an ADR-004 option.

This is a **migration point**, exactly as ADR-013 §16 anticipates: when the
production ledger/projection backend and composition architecture are
separately governed, this temporary shared wiring is replaced or migrated.

## 4. Causal definition

**Causal**, for this ADR, means precisely:

1. the Sentinel `Decision` is **created before** the consequential gate
   (`risk.approve_buy()`) and before `client.buy()`; and
2. the **same `decision_id`** flows through the Trust Ledger decision event,
   evidence association, governance evaluation, execution reporting, and the
   single `DecisionProjection` — one identity, one projection, one lifecycle.

**Causal does NOT mean**, and this ADR does not create: Sentinel gating,
blocking, or vetoing execution; a required Sentinel approval; any
`RiskManager` consultation of Sentinel state; any change to what can stop a
trade. `RiskManager.approve_buy()` remains the sole execution-blocking
authority, unmodified, consuming zero Sentinel input. The pre-gate `Decision`
is **causally ordered, not causally gating**.

## 5. Identity design

| Identifier | Generator | Generation point | Exists pre-gate? |
|---|---|---|---|
| `candidate_event_id` | `ids.py::new_candidate_event_id` (existing) | earlier in cycle | yes (unchanged) |
| `decision_id` | `ids.py::new_decision_id(symbol)` (**reused verbatim**) | **`EntryDecisionRecorder.__init__()`**, before any gate | **yes (new)** |
| Trust Ledger `decision_events.decision_id` | — | `write_decision_event()` now **accepts** the pre-generated value (§3.B); falls back to `new_decision_id(asset)` only when none supplied | — |
| Sentinel `Event.event_id` | `uuid.uuid4()` inside each service (unchanged) | at each event emission | n/a |
| `order_id` / `trade_id` | Alpaca / `log_trade()` (unchanged) | at/after execution | no |

**One identity space.** The `decision_id` string generated in
`EntryDecisionRecorder.__init__()` is the single correlation key for the
Trust Ledger row, evidence, governance evaluation, execution outcome, and the
projection. **No second identifier is introduced** — consistent with ADR-009
§Identity ("No new correlation identifier is introduced"). `new_decision_id()`
is reused unchanged; `write_decision_event()` gains only an optional
pass-through parameter.

Rejection / failure behavior:

- **Early gate rejection (Gates 0-8e):** `recorder.reject()` writes the
  `decision_events` row with `event_type="QUALIFIED_REJECTION"` keyed by the
  same `decision_id`; evidence + governance evaluation run post-write as
  today. The projection legitimately terminates at whatever stage it
  reached (`DECISION_CREATED` / `EVIDENCE_ATTACHED` / `GOVERNANCE_EVALUATED`).
  No new state/event member is added for "rejected at gate" (§8).
- **`RiskManager` rejection (Gate 8f):** unchanged — `recorder.reject()` +
  ADR-065's existing `_report_execution_outcome_safe(outcome="REJECTED")`
  advances the (now-seeded) projection to `DECISION_EXECUTED` with
  `outcome=REJECTED` in the payload, per ADR-065 §3.1.
- **`PaperExecutor` / fill failure:** unchanged — ADR-065's existing
  `outcome="FAILED"` path, now against a seeded projection.
- **Sentinel `create_decision()` failure:** caught and logged; the
  `decision_id` string is still retained and still threaded to
  `write_decision_event()`; downstream Sentinel calls behave exactly as
  today (projection absent ⇒ `advance_status()` no-ops). The trade proceeds
  unaffected.
- **Absence (block skipped entirely):** `write_decision_event()` receives no
  `decision_id`, falls back to `new_decision_id(asset)` — **byte-for-byte
  current behavior.**

## 6. Decision semantics

The pre-gate `Decision` uses `action = DecisionAction.BUY.value` (`"BUY"`).
This is the correct representation of the existing `bot/_main_cycle.py`
entry candidate: `bot/main.py` reaches `_handle_entry()` only when
`action == 1` (BUY) after `check_signal_gate()` and regime checks.

Explicitly **not** implemented or represented by this ADR:

- `BUY_MORE`, `HOLD`, `SELL`, `WAIT` — no code path creates a `Decision`
  with these actions; the entry path is BUY-only.
- `REJECT` — **not** a `DecisionAction` (ADR-066 excludes it, unchanged
  here). A gate/risk/fill rejection is an **outcome/event**
  (`QUALIFIED_REJECTION` on the Trust Ledger row; `outcome=REJECTED/FAILED`
  in the ADR-065 payload), never an action value and never a reason to
  withhold `create_decision()`.

This ADR defines **no** confidence mathematics, sizing algorithm, thesis
evaluation, conviction model, horizon enforcement, or evidence weighting.
`confidence` is the existing `final_confidence` float, passed through
unchanged. The optional `Decision` fields (`horizon`, `thesis`, etc.) may be
left `None`; nothing populates or evaluates them.

## 7. Governance / authority boundary

Preserved exactly as today:

- `RiskManager.approve_buy()` — unchanged logic, signature, and call site;
  still the only code that can block a trade.
- Sentinel does not veto, override, or gate execution.
- `GovernanceService.record_approval()` — **still uncalled in production.**
- `GovernanceService.register_policy()` — **still uncalled in production.**
- `ApprovalStatus` — unchanged.
- Constitution rules incl. ADR-050's ladder — remain advisory, logged, non-
  blocking (ADR-047/048/049/050/051 unchanged).
- No autonomous authority expansion; no live/Robinhood execution; no
  Constitution-authority change.

`GovernanceService.evaluate_policy()` continues to run **evaluation only**,
now against the newly created `Decision`'s `decision_id`. Its `bool` result
**cannot and does not block execution** — it remains discarded at the call
site. This ADR does not authorize acting on that result, and does not
authorize `record_approval()` even for the now-existing `Decision`. Making
the Sentinel governance verdict consequential is a separate, future
Constitution-family decision, outside this ADR (see §14).

## 8. Lifecycle semantics

Intended projection walk on the shared pair, for a filled BUY:

```
create_decision()          → DECISION_CREATED   (projection seeded)
associate_evidence() ×3    → EVIDENCE_ATTACHED  (advance_status now advances)
evaluate_policy()          → GOVERNANCE_EVALUATED
record_execution(FILLED)   → DECISION_EXECUTED
```

For a `RiskManager` rejection: `… → GOVERNANCE_EVALUATED →`
`record_execution(REJECTED) → DECISION_EXECUTED` (outcome in payload).
For an early gate rejection: terminates at the stage reached; the Trust
Ledger `QUALIFIED_REJECTION` row is the authoritative negative record.

**No new `EventType`, `DecisionState`, or `ApprovalStatus` member is added.**
Repository evidence does not prove one is necessary: `DECISION_CREATED`,
`EVIDENCE_ATTACHED`, `GOVERNANCE_EVALUATED`, `DECISION_EXECUTED` already
exist (ADR-065 added the last), and ADR-065 §3.1's `outcome` payload field
already distinguishes FILLED/REJECTED/FAILED. ADR-066 explicitly does not
authorize new members, and this ADR does not either. If implementation
review finds a single terminal state genuinely cannot represent an
early-gate rejection honestly, that determination — and any member it
implies — is separate, future governance, **not** pre-authorized here.

Optional, authorized-only-if-necessary: implementation review MAY extend
ADR-065's `_report_execution_outcome_safe()` to also fire on early-gate
rejections with `outcome="REJECTED"` so every seeded projection reaches a
terminal `DECISION_EXECUTED` event. That is an ADR-065-path change; this ADR
authorizes it **only if** review shows it is required for lifecycle
coherence, and it does not rewrite ADR-065's text.

## 9. Failure / absence safety

The pre-gate Sentinel block is **advisory and failure-isolated**. It is
causally ordered (runs before the gates) but must never become an execution
blocker:

| Failure | Effect |
|---|---|
| `create_decision()` raises | caught, logged; `decision_id` retained; trade proceeds; downstream Sentinel calls no-op as today |
| `associate_evidence()` raises | unchanged from ADR-009 (already isolated) |
| `evaluate_policy()` raises | unchanged from ADR-045 (already isolated) |
| `record_execution()` raises | unchanged from ADR-065 (already isolated; never rolls back a trade) |
| projection `advance_status()` raises | caught by the enclosing block; logged; not propagated |
| whole pre-gate block skipped | `write_decision_event()` falls back to `new_decision_id()`; identical to current behavior |

Separation maintained: **causal identity** (`decision_id`) · **advisory
intelligence** (Decision/Evidence/Governance events) · **capital-safety
gate** (`RiskManager.approve_buy()`) · **execution** (`PaperExecutor`) ·
**audit/reporting** (Trust Ledger + `log_trade` + ADR-065). This ADR moves
only the first; it does not merge any two of them.

## 10. Test plan (to be written at implementation, not now)

1. A `Decision` is created (via `get_decision_service().create_decision()`)
   **before** Gate 8f (`risk.approve_buy()`) — asserted by call order.
2. A stable `decision_id` is generated in `EntryDecisionRecorder.__init__()`
   before any gate runs.
3. The **same** `decision_id` reaches `write_decision_event()`, the
   `decision_events` row, `associate_evidence()`, `evaluate_policy()`, and
   `record_execution()`.
4. `DecisionService`, `EvidenceService`, `GovernanceService`, and the
   execution-reporting `DecisionService` resolve to services sharing **one**
   `LedgerRepository` / `ProjectionRepository` pair within a process.
5. The `DecisionProjection` advances `DECISION_CREATED → EVIDENCE_ATTACHED →
   GOVERNANCE_EVALUATED → DECISION_EXECUTED` for a filled BUY;
   `advance_status()` no longer no-ops for the live path.
6. `RiskManager.approve_buy()` receives byte-for-byte identical arguments.
7. `RiskManager` blocking behavior is unchanged (decline still returns
   `available_cash` and skips the buy).
8. A gate / risk / fill rejection is recorded as an outcome/event, never as
   `DecisionAction.REJECT`, and never by withholding `create_decision()`.
9. `client.buy()` still routes through the existing `PaperExecutor` via
   `bot/execution/factory.py`.
10. Execution failure (no fill / `client.buy()` returns `None`) remains a
    failure outcome.
11. A Sentinel reporting/creation failure does not roll back, retry, or
    alter an already-committed trade.
12. `GovernanceService.record_approval()` is **never** invoked across a full
    `_handle_entry()` — guard test.
13. `GovernanceService.register_policy()` is **never** invoked in the live
    path — guard test.
14. Both ADR-002 entry points exercise the new pre-gate path: CLI
    (`trade.yml` → `bot/main.py`) and scheduler/HTTP (`watchdog.yml` →
    `dashboard/http_endpoints.py` `GET /run/cron` → `scheduler/trading_job.py`
    → `bot.main.run()`).
15. `sentinel_engine/tests/test_package_imports.py` and
    `applications/trading_intelligence/tests/test_package_imports.py` pass
    unchanged (extended to cover the new composition module; no `bot`
    import in `sentinel_engine`).
16. Existing ADR-065 reporting tests
    (`tests/phase1a/test_execution_outcome_reporting.py`) pass unchanged;
    ADR-065's SQL-recency correlation still resolves (now to a genuinely
    pre-existing `Decision`'s id).
17. No second decision identity is introduced anywhere in the flow.
18. `scripts/verify_single_write_path.py` passes unchanged.
19. Absence safety: with the pre-gate block disabled/failing,
    `_handle_entry()` behavior is byte-for-byte identical to pre-ADR-067.
20. `sentinel_engine/tests/test_recommendation_governance_lifecycle.py`
    remains **out of scope** — untouched, still governed by a future
    causal-recommendation/approval ADR (§14).

## 11. Compatibility / contract impact

- `write_decision_event()` — additive optional parameter; every current
  caller unaffected; exit paths unaffected.
- `EntryDecisionRecorder` — additive instance state + one additive
  failure-isolated block in `__init__`; existing `reject()` /
  `record_executed()` / `record_order_not_filled()` gain a threaded
  argument, no behavior change.
- `record_decision_safe()` — additive optional `decision_id` parameter,
  forwarded to `write_decision_event()`; ADR-009/ADR-045's existing
  evidence/governance blocks unchanged.
- Composition consolidation — no bot import line or accessor name changes
  (preferred form); `sentinel_engine`-internal only; the three existing
  composition modules keep their public accessors.
- No schema, migration, persistence, `EventType`, `DecisionState`,
  `ApprovalStatus`, `RiskManager`, `PaperExecutor`, `AlpacaClient`,
  `bot/main.py`, `EntryContext`, `dashboard/`, `scheduler/`, `database/`,
  `ledger/`, or workflow change.

## 12. Narrow supersession of three composition clauses

This ADR narrowly supersedes the following, **only** for the causal Decision
lifecycle's shared composition pair, and states which wins and why (per
`AARA_ARCHITECTURE_AUTHORITY.md`'s conflict-resolution rule):

- **ADR-013 §7** ("[`composition/evidence.py`] shall not become a
  general-purpose Sentinel composition root… does not authorize
  construction of: `DecisionService`; `GovernanceService`; …") — superseded
  **only** to the extent that a **new, separate** module
  (`composition/decision_lifecycle.py`) may construct `DecisionService`,
  `EvidenceService`, and `GovernanceService` on one shared pair for this
  lifecycle. `composition/evidence.py`'s own scope is **not** reopened;
  ADR-013 §7 continues to govern that module.
- **ADR-014 §8** ("does not authorize… a second in-memory ledger… reuse of
  the existing Evidence composition module… for `GovernanceService`") —
  superseded **only** insofar as this ADR authorizes one shared ledger pair
  spanning the lifecycle services. ADR-014's translation-contract scope is
  otherwise untouched.
- **ADR-045 §2.1** ("a **separate, dedicated instance** — not a reuse,
  import, or extension… a shared `LedgerRepository`/`ProjectionRepository`
  across two independently governed services would blur which ADR governs
  which slice of ledger state") — superseded **only** for the causal
  lifecycle pair. The "blur" concern is addressed explicitly: **event
  content** remains governed by its originating ADR (evidence by
  ADR-009/012/013, governance evaluation by ADR-014/045, execution outcome
  by ADR-065); **this ADR governs only the shared pair's existence and the
  `DecisionProjection` lifecycle semantics** across those events.

**This ADR does not supersede ADR-013, ADR-014, or ADR-045 generally.** All
other provisions of all three — including ADR-045's prohibition on operative
`Policy` registration and `record_approval()` (§3 items 3-4), and ADR-013's
process-local / non-durable / ADR-004-deferred limitations — remain fully in
force. ADR-043's separate one-shot diagnostic pair
(`scripts/project_one_trust_ledger_decision.py`) is unaffected and not
consolidated.

## 13. ADR-002 exception scope

Narrow, function-scoped, following ADR-009's / ADR-045's / ADR-065's
template. Two protected files:

### `bot/trust_ledger/decisions.py`

- **Function:** `write_decision_event()` only.
- **Permitted:** add one additive optional parameter
  `decision_id: str | None = None`; use it in place of
  `new_decision_id(asset)` when supplied (`decision_id or new_decision_id(asset)`).
- **Prohibited:** any other change to this function or file; any change to
  `check_fingerprint()`, `build_intent()`, `build_data_completeness()`, or
  any other symbol here; any new caller of `write_decision_event()`; any
  change to the `decision_events` schema or to `ledger_svc.append_ledger_row`.

### `bot/_main_trust_decisions.py`

- **Symbols:** `EntryDecisionRecorder.__init__()`,
  `EntryDecisionRecorder.reject()`, `EntryDecisionRecorder.record_executed()`,
  `EntryDecisionRecorder.record_order_not_filled()`, and the module-level
  `record_decision_safe()` — these only.
- **Permitted:** in `__init__`, the additive failure-isolated
  `decision_id` generation + `Decision` construction + `create_decision()`
  call (§3.A steps 1-4); on the three recorder methods and
  `record_decision_safe()`, threading `self.decision_id` /
  a new optional `decision_id` parameter to `write_decision_event()`; the
  necessary new `import` of `get_decision_service()` and
  `sentinel_engine.domain.decision.Decision` (both outside `bot/`,
  `bot → sentinel_engine` direction, consistent with ADR-001 and the
  existing evidence/governance imports in this file).
- **Prohibited:** any change to `ExitLedgerContext`,
  `record_exit_decision_safe()`, `ExitDecisionRecorder`,
  `record_risk_evaluation_safe()`, `record_data_quality_safe()`, the
  existing ADR-009 evidence block, or the existing ADR-045 governance block;
  any change to gate logic, risk logic, execution, order-fill behavior, or
  control flow beyond the one additive `__init__` block and the threaded
  argument; any second `bot/` file; any `bot/main.py` / `EntryContext` /
  `_handle_entry()` gate-sequence change; any `sentinel_engine → bot`
  import.

**No `.github/workflows/*` change is authorized or required.** Both ADR-002
entry points must be exercised in testing (§10 item 14). Implementation must
occur in an isolated branch/worktree, not directly on `main`. The full
`sentinel_engine/tests` and `tests/` suites must pass before and after.

The `sentinel_engine/composition/` consolidation (§3.C) is **inside
`sentinel_engine/`, outside ADR-002's protected scope**, and requires no
ADR-002 exception — it is ordinary additive/refactor work in a package that
governs itself under ADR-001, constrained here only by §12.

## 14. Explicit non-goals

This ADR does **not** authorize, and any implementation claiming its
authority for the following is out of scope:

- Sentinel approval authority; `record_approval()`; `register_policy()`;
  operative `GovernanceService` approval; acting on the `evaluate_policy()`
  result.
- Any Sentinel veto, block, or override of `RiskManager.approve_buy()` or
  `client.buy()`.
- Any change to `RiskManager`, `PaperExecutor`, `AlpacaClient`,
  `bot/execution/factory.py`, or `bot/main.py` / `EntryContext` /
  `_handle_entry()`'s gate sequence.
- Live / Robinhood execution, autonomous execution, automatic authority
  expansion, or any Constitution-authority change.
- A new `Recommendation` class/service; a new "Risk Governor".
- `BUY_MORE` execution logic; `WAIT` scheduling; `SELL` / exit
  intelligence; position lifecycle.
- Thesis engine; conviction engine; confidence/calibration methodology;
  position-sizing algorithm; evidence weighting/scoring; horizon
  enforcement / expiry / re-evaluation.
- A new `EventType`, `DecisionState`, or `ApprovalStatus` member.
- Any ADR-004 persistence / ledger-backend selection.
- Any modification to `sentinel_engine/tests/test_recommendation_governance_lifecycle.py`.
- A broad `bot/` ↔ `sentinel_engine` coupling, or any ADR-002 exception
  beyond the two functions in §13.
- A second decision identity space.
- General supersession of ADR-013 / ADR-014 / ADR-045 (only the three
  clauses in §12, only for the shared lifecycle pair).
- A rewrite of ADR-065 (its `_report_execution_outcome_safe()` /
  `record_execution()` path stays as written; the optional early-gate
  extension in §8 is authorized only if implementation review proves it
  necessary).

## 15. Deferred work (separate future governance)

- Making the Sentinel governance verdict consequential (able to block or
  require approval) — a Constitution-family ADR (ADR-047/048/049/050
  lineage), not a wiring ADR.
- Operative `Policy` registration and `record_approval()` — a separate ADR
  after the above.
- `BUY_MORE` / `HOLD` / `SELL` / `WAIT` causal Decisions; exit-path
  Decisions.
- Replacing ADR-065's SQL-recency correlation with a threaded
  `EntryContext.decision_id` (ADR-065 §3.2's deferred read-half) — a
  cleanup, not required by this ADR.
- Production `LedgerStore` / `ProjectionRepository` backend and the final
  composition architecture — ADR-004.
- Landing `test_recommendation_governance_lifecycle.py`.
- Any confidence / sizing / thesis / horizon capability.

## 16. Implementation prerequisites

Before implementation may begin, all of the following must hold:

1. This ADR is **Accepted and landed** under ADR-058 D2 (tracked on the
   default branch, `Status: Accepted`, landed under applicable write/merge
   controls).
2. Implementation occurs in an isolated branch/worktree, not on `main`.
3. A rollback plan is recorded (see §17) before code changes start.
4. The §13 ADR-002 exception scope is followed exactly; any need to touch a
   third `bot/` file stops implementation and requires a scope amendment.
5. The full `sentinel_engine/tests` and `tests/` suites pass before and
   after; `scripts/verify_single_write_path.py` passes; both ADR-002 entry
   points are exercised.

## 17. Rollback

If implemented and later reverted:

1. Remove the additive `__init__` block and threaded `decision_id` argument
   from `bot/_main_trust_decisions.py` (restores `EntryDecisionRecorder` and
   `record_decision_safe()` exactly).
2. Remove the optional `decision_id` parameter from
   `write_decision_event()` (restores `bot/trust_ledger/decisions.py`
   exactly).
3. Re-point the three composition modules back to their own dedicated pairs
   and delete `composition/decision_lifecycle.py` and its tests.
4. Remove the ADR-067 tests.
5. No schema, migration, persistence, or ADR-004 rollback — none was
   touched. `RiskManager`, `PaperExecutor`, `AlpacaClient`, `bot/main.py`
   are untouched, so nothing to roll back there.

Single-commit revert, no secondary cleanup, identical in character to
ADR-009's / ADR-045's / ADR-065's rollback sections.

## 18. Relationship to existing ADRs

- **ADR-001** — preserved. `sentinel_engine` gains no `bot` import; the new
  composition module imports only the standard `sentinel_engine` internals;
  bot→sentinel_engine only, via existing + one new accessor.
- **ADR-002** — this ADR is the requested narrow exception (§13), following
  the ADR-009/045/065 template, function-scoped to two files.
- **ADR-004** — untouched; no production backend, no Option A/B/C selection;
  the shared pair is temporary, in-memory, process-local.
- **ADR-009 / ADR-012** — the evidence integration and adapter are unchanged;
  `associate_evidence()` now keys off a pre-existing `decision_id` and its
  `advance_status()` call now actually advances (a seeded projection
  exists), which is the intended effect, not a contract change.
- **ADR-011 / ADR-020** — adjacency only, no conflict. This ADR implements
  no Thesis/Conviction (ADR-011) and no exit/sell intelligence or
  `holding_horizon` capability (ADR-020); `thesis` / `horizon` fields stay
  inert `None`. Neither ADR is superseded or amended.
- **ADR-013 / ADR-014 / ADR-045** — narrowly superseded per §12 (three named
  clauses, shared lifecycle pair only); otherwise fully in force, including
  ADR-045 §3's `record_approval()` / `Policy`-registration prohibition,
  which this ADR **re-affirms** (§7, §14).
- **ADR-043** — its separate one-shot diagnostic pair is untouched and not
  consolidated.
- **ADR-047 / ADR-048 / ADR-049 / ADR-050 / ADR-051** — unchanged. The
  Constitution rules remain advisory and non-blocking. This ADR adds no
  new authority and makes no governance verdict consequential.
- **ADR-058** — this ADR is subordinate to D1-D4; Proposed and
  non-authoritative until landed.
- **ADR-065** — remains authoritative for execution-outcome reporting. Its
  `_report_execution_outcome_safe()` / `record_execution()` path and its
  SQL-recency correlation (§6.1) are **not rewritten**; the correlation now
  resolves to a genuinely pre-existing `Decision` identity. Any change to
  ADR-065's path (the optional early-gate extension in §8) is authorized
  only if implementation review proves it necessary, and does not amend
  ADR-065's text.
- **ADR-066** — **not amended.** It ratified `DecisionAction` /
  `Horizon` / `EvidencePolarity` and the optional fields as **inert
  representation**; this ADR is the separate authority that makes pre-gate
  `Decision` creation **causal**. `DecisionAction` remains exactly
  `{BUY, BUY_MORE, HOLD, SELL, WAIT}`; `REJECT` remains excluded; the entry
  path uses `BUY` only.

## 19. Acceptance

**Status:** Accepted
**Date Accepted:** 2026-09-04
**Accepted By:** Architecture Owner (explicit act performed directly in this
conversation — SPRINT-1.2 ACCEPT + LAND — not inferred from the SPRINT-1.2
draft, from any implementation, or from any other source)
**Accepting / landing commit:** the commit that flips this ADR's `Status` to
`Accepted` and adds this section (message "docs: accept and land ADR-067
causal decision lifecycle boundary"), on the default branch `main`, landed
under the repository's normal direct-to-`main` flow. That commit cannot
contain its own SHA; the SHA is recorded in the Status Log entry below (added
in the same commit as a forward reference is not possible — see the Status
Log). With that commit, ADR-058 D2's three conditions are met: tracked on
`main`, `Status: Accepted`, landed under applicable write/merge controls.

**Accepted scope — exactly, and only:**

1. Pre-gate causal Sentinel `Decision` creation via **G-A** (§3.A): one
   `decision_id` generated in `EntryDecisionRecorder.__init__()` by reusing
   `bot/trust_ledger/ids.py::new_decision_id(symbol)`; one `Decision` with
   `action="BUY"` created pre-gate on the shared composition; the **same**
   `decision_id` threaded to `write_decision_event()` and used by every
   downstream Sentinel call and the one `DecisionProjection`. **One identity
   space; no new identifier.**
2. One shared, process-scoped `LedgerStore` + `ProjectionRepository` +
   `LedgerRepository` pair (§3.C), used by the causal-lifecycle
   `DecisionService` / `EvidenceService` / `GovernanceService` and the
   ADR-065 execution-reporting `DecisionService`, via a new
   `sentinel_engine/composition/` module with **no bot import-line or
   accessor-name changes** (preferred form).
3. The two function-scoped ADR-002 exceptions in §13 — and only those:
   `bot/trust_ledger/decisions.py::write_decision_event()` (one additive
   optional `decision_id` parameter) and
   `bot/_main_trust_decisions.py` (`EntryDecisionRecorder.__init__` /
   `.reject()` / `.record_executed()` / `.record_order_not_filled()` and
   module-level `record_decision_safe()`).
4. The **narrow** supersession of ADR-013 §7, ADR-014 §8, and ADR-045 §2.1
   (§12) — only their "dedicated, non-shared instance" language, only for the
   causal lifecycle pair. All other provisions of those three ADRs, and
   ADR-045 §3's `record_approval()` / `Policy`-registration prohibition,
   remain fully in force.
5. Preservation, unchanged: `RiskManager.approve_buy()` as the sole
   execution-blocking gate consuming zero Sentinel input; `PaperExecutor` as
   the sole execution authority; ADR-045's approval restrictions; ADR-065's
   execution-outcome-reporting authority and its SQL-recency correlation
   path; ADR-066's inert `DecisionAction` vocabulary
   `{BUY, BUY_MORE, HOLD, SELL, WAIT}` with `REJECT` excluded.

**Not authorized by this acceptance** — restated because acceptance does not
expand §14: `record_approval()`; `register_policy()`; any Sentinel
veto/override/gating of `RiskManager.approve_buy()` or `client.buy()`; any
change to `RiskManager`, `PaperExecutor`, `AlpacaClient`,
`bot/execution/factory.py`, `bot/main.py`, `EntryContext`, or `_handle_entry()`'s
gate sequence; live execution; autonomous execution; automatic authority
expansion; a new `Recommendation` class; a "Risk Governor";
`BUY_MORE` / `WAIT` / `SELL` execution behavior; exit / sell intelligence;
position lifecycle; a thesis engine; a conviction engine;
confidence / calibration / position-sizing methodology; evidence
weighting / scoring; horizon enforcement / expiry / re-evaluation; a new
`EventType`, `DecisionState`, or `ApprovalStatus` member; any ADR-004
persistence / ledger-backend selection; a broad `bot` ↔ `sentinel_engine`
coupling or any ADR-002 exception beyond §13's two functions; a second
decision identity space; a general supersession of ADR-013 / ADR-014 /
ADR-045; a rewrite of ADR-065; or any modification to
`sentinel_engine/tests/test_recommendation_governance_lifecycle.py`.

This acceptance ratifies the ADR-067 text exactly as SPRINT-1.2 drafted it.
Only the header status/date lines, this `## Acceptance` section, and the
Status Log entry below were altered to perform the acceptance; no
substantive Context, Problem, Decision, or architecture section was changed.

---

## 20. Status Log

**Proposed — 2026-09-08 (SPRINT-1.2).** Drafted as a read-only-trace +
ADR-drafting-only task following SPRINT-1.1's causal-lifecycle trace.
Verified against HEAD `61eabbb`. No production code, test, or other ADR was
modified; no `docs/platform/` governance file was modified; nothing was
staged or committed; `test_recommendation_governance_lifecycle.py` was not
touched.

**Accepted + Landed — 2026-09-04 accepted / 2026-09-08 landed
(SPRINT-1.2 ACCEPT + LAND).** The Architecture Owner explicitly accepted this
ADR, in exactly the form SPRINT-1.2 drafted it, and it was landed in the same
commit ("docs: accept and land ADR-067 causal decision lifecycle boundary")
on the default branch `main`. With that commit ADR-058 D2's three conditions
are satisfied — tracked on `main`, `Status: Accepted`, landed under applicable
write/merge controls — and ADR-067 is authoritative; ADR-058 D3 no longer
applies. **This authorizes the architecture in §3 only; no causal-lifecycle
code was implemented in this batch.** Implementation is SPRINT-1.3, a separate
subsequent batch bound by §13–§17. No production code, test, or other ADR was
modified to perform this acceptance; no `docs/platform/` governance file, no
`docs/REQUIREMENTS.md`, no `tests/req_snapshots/req_state.json`, and no
`test_recommendation_governance_lifecycle.py` was touched; only ADR-067
changed. The date rollover during this conversation (system clock now
2026-09-08) does not change the `Date Accepted` the Architecture Owner
specified (2026-09-04); the landing commit is dated by git at commit time.
