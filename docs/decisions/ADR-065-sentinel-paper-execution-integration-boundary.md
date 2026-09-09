# ADR-065 — Narrow ADR-002 Exception: Sentinel-to-Paper-Execution Integration Boundary

**Status:** Accepted — scope limited to the reconciled, as-built
execution-outcome-reporting boundary (§3, §3.1, §4). See §3.2 for what
remains explicitly deferred and unauthorized, and see `## Acceptance` below
for the acceptance record. Per ADR-058 D2, full authoritative status
additionally requires this file to be tracked/landed on the default
branch — that has not yet occurred as of this act; see `## Acceptance`.
**Date Proposed:** 2026-09-04
**Date Reconciled:** 2026-09-04 (Batch 4D-RECONCILE — see §0)
**Date Accepted:** 2026-09-04 (Batch 4D-ACCEPT — see `## Acceptance`)
**Decision Type:** Architecture / Governance
**Related ADRs:** ADR-001, ADR-002, ADR-009, ADR-012, ADR-013, ADR-014, ADR-045, ADR-058

---

## 0. Reconciliation Note (Batch 4D-RECONCILE)

A governance audit (Batch 4D-STATUS) found that Batch 4C had already implemented
code in the working tree — `sentinel_engine/adapters/execution_adapter.py`,
`sentinel_engine/composition/execution.py`, `DecisionService.record_execution()`,
`DecisionState.DECISION_EXECUTED`, and a `bot/_main_cycle.py` integration —
while this ADR remained untracked and `Status: Proposed`. Per **ADR-058**
(Accepted, authoritative) **D3/D4**: an untracked document is non-authoritative
regardless of its status header, and authoring or implementing something
described in a Proposed document does not itself confer acceptance. That
finding stands; this revision does not change it.

This revision (Batch 4D-RECONCILE) does two things, and **only** these two:

1. **Narrows this ADR's text to describe exactly what Batch 4C built**,
   removing or explicitly marking as deferred everything the original draft
   described that was never implemented (principally: the `EntryContext.decision_id`
   field, the `bot/main.py` threading change, and the pre-Gate-8f read-half).
2. **Left `Status: Proposed` unchanged at the time of this reconciliation
   pass.** No architecture-owner acceptance act had occurred yet.
   Reconciling the text was a documentation correction, not an acceptance
   event, and was not read as one.

No production code, test, or other ADR was changed to produce this revision.

**Superseding note (Batch 4D-ACCEPT, same day):** an explicit Architecture
Owner acceptance act was subsequently performed against this reconciled
text, unchanged from what is described above. See `## Acceptance` and the
Status Log for that separate, later act. This paragraph is left intact as
the historical record of the reconciliation pass itself.

---

## 1. Context

Batch 4 (implementation) attempted to connect `sentinel_engine`'s decision/
recommendation capability directly to the existing `PaperExecutor`/
`RiskManager` by importing `bot.execution.base` and `bot.risk.risk_manager`
into a new `sentinel_engine/execution/` package. This failed
`sentinel_engine/tests/test_package_imports.py`
(`test_sentinel_engine_does_not_import_bot_dashboard_scheduler_ledger_database_or_applications`),
which enforces ADR-001's package-independence text. The same restriction
independently applies to `applications/trading_intelligence/` (its own
`test_package_imports.py`, and `docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md`
§7: *"Adapters are the only mechanism permitted to cross the boundary"*). All
Batch 4 code was reverted; see `sentinel_engine/domain/decision_state.py`'s
module docstring for the recorded finding.

Batch 4A (read-only architecture analysis) evaluated five boundary options
and selected **Option C — bot-side integration consumes Sentinel's decision/
recommendation capability** — the same direction already used, successfully
and repeatedly, by ADR-009 → ADR-012 → ADR-013 → ADR-014 → ADR-045 for
Evidence and Governance integration. That chain establishes a proven,
repeatable pattern: a pure translation adapter in `sentinel_engine/adapters/`
(zero `bot` import) plus one narrowly-scoped ADR-002 exception naming the
exact `bot/` file(s)/function(s) authorized to call it.

This ADR is the sixth application of that pattern, for the one capability
that chain has not yet reached: **paper execution**, and reporting its
outcome back to Sentinel.

Read-only tracing of the real execution path (performed for this ADR, not
assumed from Batch 4's or Batch 4A's prior naming of
`bot/_main_trust_decisions.py`) found that file is **not** where risk
approval or order placement actually happen. The real chokepoint is:

- **`bot/main.py`** (lines 385-399): the per-symbol cycle loop constructs
  `EntryContext` and calls `_handle_entry(con, client, risk, symbol, ctx)`.
- **`bot/_main_cycle.py::_handle_entry()`** (lines 78-320+): runs the entry
  gates, calls `risk.approve_buy(...)` (line 258) — the real,
  execution-blocking safety gate — then, only if approved, calls
  `client.buy(...)` (line 265) against whatever `Executor` `bot/execution/
  factory.py::get_executor()` selected (`PaperExecutor` today, per
  `EXECUTION_BACKEND=alpaca_paper`), waits for fill, and records the outcome
  via `EntryDecisionRecorder.record_executed()` and `log_trade()`.

`bot/_main_trust_decisions.py` defines `EntryDecisionRecorder` (used by
`_handle_entry()`) and holds the ADR-009/ADR-045 Evidence/Governance
integration inside a *different* function, `record_decision_safe()` — but it
does not itself call `risk.approve_buy()` or `client.buy()`. Naming it as the
execution integration point, as Batch 4 did, would have been incorrect; this
ADR corrects that.

**As-built note (§0):** the original draft, at this point, also proposed a
*read-half* — an optional Sentinel decision_id threaded from `bot/main.py`
into `EntryContext`, read back before Gate 8f. That half was never built.
Batch 4C implemented only the *report-half* described in §3/§4/§6 below,
using a correlation mechanism the original draft did not describe: a
direct, read-only SQL lookup against the existing `decision_events` table
(§6.1).

## 2. Problem

Sentinel Engine can form a Decision, attach Evidence, evaluate Governance,
and record an Approval (ADR-009/012/013/014/045) — but nothing today lets an
approved Sentinel recommendation reach the code that actually places a paper
order, and nothing reports the real execution outcome back into Sentinel's
ledger. `sentinel_engine`'s own independence boundary (ADR-001) and
`applications/trading_intelligence`'s equivalent boundary both correctly
forbid closing this gap by importing `bot.execution`/`bot.risk` from outside
`bot/`. Closing it requires `bot/` itself to be the caller — which requires
lifting ADR-002's freeze for the minimum necessary scope.

**As-built note:** this ADR, as reconciled, closes only the *report* half of
that gap — outcome reporting after execution completes. It does not close,
and does not claim to close, the *recommendation-reaches-execution* half; no
mechanism exists today, under this ADR or any other, by which a Sentinel
recommendation or approval influences `risk.approve_buy()` or `client.buy()`.

## 3. Decision

**Authorize, narrowly:**

1. A new, pure translation adapter, **`sentinel_engine/adapters/
   execution_adapter.py`** (zero `bot` import, mirrors `evidence_adapter.py`/
   `governance_adapter.py`'s existing shape exactly) that translates a plain
   execution-outcome dict into Sentinel Engine's existing event/domain
   contracts. **[IMPLEMENTED]**
2. One additive, failure-isolated integration in **`bot/_main_cycle.py::
   _handle_entry()`**: after `risk.approve_buy()` and `client.buy()` already
   run (unmodified), report the resulting outcome (fill, rejection, or
   order-fill failure) to Sentinel through the adapter in (1), correlated to
   the decision_id the existing Trust Ledger write already produced for this
   symbol/cycle via a read-only SQL lookup — see §6.1. **[IMPLEMENTED]**
3. The **minimum additive Sentinel-side lifecycle change** necessary to
   represent an execution outcome — see §3.1. No other Sentinel-engine
   production module is authorized to change. **[IMPLEMENTED]**

Nothing about `RiskManager`, `PaperExecutor`, `Executor`, `AlpacaClient`, or
the existing entry-gate sequence in `_handle_entry()` (Gates 0 through 8f) is
modified, reordered, or reduced in strictness by this ADR.

**Not authorized, not implemented (see §3.2):** the original draft's item 3 —
an additive change to `bot/main.py`'s `EntryContext(...)` construction
threading an optional Sentinel `decision_id` through, and a corresponding
pre-Gate-8f read of an approved Sentinel decision — was never built. It is
removed from this ADR's authorized/implemented scope, not merely left
unbuilt-but-still-authorized. Re-authorizing it requires revisiting this ADR
or a future one; it is not standing authorization today.

### 3.1 Minimum Necessary Lifecycle-Vocabulary Change — Implemented

`EventType.DECISION_EXECUTED` **already existed** in
`sentinel_engine/events/event_types.py` (added earlier, previously unused, no
producer). This ADR authorizes, and the implementation uses, that *existing*
value as the ledger event type for a reported execution outcome — no new
`EventType` member was required for the successful-fill case.

`DecisionState` (`sentinel_engine/domain/decision_state.py`) did **not**
previously include `DECISION_EXECUTED` — deliberately, per Batch 4's finding,
until a real producer existed. This ADR's implementation is that producer:
`DecisionState.DECISION_EXECUTED` is now a real, additive, terminal member,
confirmed present in `sentinel_engine/domain/decision_state.py`.

For the rejected/failed-execution case (RiskManager declines, or the fill
fails), no new `EventType` member was added. Instead, the existing
`DECISION_EXECUTED` event/state is reused for all three outcomes,
distinguished by an `outcome` field in the event payload — confirmed in
`sentinel_engine/adapters/execution_adapter.py::to_execution_outcome()`,
which validates `outcome` against exactly `{"FILLED", "REJECTED", "FAILED"}`
— plus the existing numeric/price fields on success. This mirrors ADR-045
§6's precedent of representing a distinction through payload data rather
than proliferating enum members.

### 3.2 Deferred / Not Implemented

The following are **not** authorized and **not** implemented by this ADR.
Nothing below may be treated as standing authorization; each requires its
own future governance:

1. `EntryContext.decision_id` (no such field exists on `EntryContext` in
   `bot/_main_cycle.py`).
2. Any change to `bot/main.py` for threading a decision_id into
   `EntryContext(...)` (that construction site is untouched).
3. Any pre-Gate-8f Sentinel decision lookup (no read occurs anywhere before
   `risk.approve_buy()` runs).
4. Any call to `SentinelEngine.get_decision_projection()` from `bot/`.
5. Any call to `SentinelEngine.get_approval()` from `bot/`.
6. Any causal pre-execution Sentinel recommendation reaching `_handle_entry()`.
7. Any Sentinel approval authority over execution — `RiskManager.approve_buy()`
   remains the sole execution-blocking gate, consuming zero Sentinel input.
8. Policy registration (`GovernanceService.register_policy()` for any
   Phase-1A policy).
9. `GovernanceService.record_approval()` / `to_approval()`.
10. Any change to `RiskManager.approve_buy()`'s logic, signature, or call
    sites.

Items 6-10 restate, for this ADR's own scope, the same boundary ADR-045 §3
already drew for the governance-evaluation integration — this ADR does not
loosen it.

## 4. Exact Files/Modules Authorized (As Built)

| File | Authorized change | Status |
|---|---|---|
| `sentinel_engine/adapters/execution_adapter.py` (new file) | Pure translation function `to_execution_outcome(execution: dict) -> dict`, zero `bot` import, validates required keys (`decision_id`, `symbol`, `action`, `side`, `outcome`, `is_paper`, `timestamp`) and optional keys (`notional`, `quantity`, `fill_price`, `order_id`, `reason`). | **Implemented** |
| `sentinel_engine/domain/decision_state.py` | One additive member: `DECISION_EXECUTED`. No removal or renaming of existing members. | **Implemented** |
| `sentinel_engine/services/decision_service.py` | One additive method: `record_execution(decision_id, payload) -> Optional[Event]`, idempotent per `decision_id` (returns `None` without appending a second event if a `DECISION_EXECUTED` event for that `decision_id` already exists), advances the projection via `ProjectionRepository.advance_status()` (no-ops if no projection was ever seeded, per the ADR-013/045 precedent). | **Implemented** |
| `sentinel_engine/composition/execution.py` (new file) | Dedicated temporary composition boundary (own `LedgerStore`/`ProjectionRepository` pair, per ADR-013/045's "never reuse another ADR's instance" convention), exposing `get_decision_service_for_execution_reporting() -> DecisionService`. | **Implemented** |
| `bot/_main_cycle.py::_handle_entry()` | One additive, failure-isolated block, `_report_execution_outcome_safe()`, called after `risk.approve_buy()`'s decline path and after `client.buy()`/fill-handling completes (success, no-fill, and submission-failure paths). Looks up the correlated `decision_id` via `_latest_decision_id_for_report()` (§6.1), builds the payload via `to_execution_outcome()`, and calls `record_execution()`. Wrapped in `try/except`, logs a warning on failure, never raises. | **Implemented** |
| `bot/main.py` (`EntryContext(...)` construction) | Threading an optional `decision_id` field through. | **Deferred — not implemented (§3.2)** |
| `bot/_main_cycle.py::EntryContext` | Additive dataclass field `decision_id: Optional[str] = None`. | **Deferred — not implemented (§3.2)** |
| Pre-Gate-8f read of an approved Sentinel decision | Read via `get_decision_projection()`/`get_approval()`. | **Deferred — not implemented (§3.2)** |

**No other file, function, class, or line in `bot/`, `dashboard/`,
`scheduler/`, `database/`, `ledger/`, or `applications/trading_intelligence/`
is authorized to change under this ADR.** `PaperExecutor`, `RiskManager`,
`Executor`, `AlpacaClient`, and `bot/execution/factory.py` are, and remain,
**not** modified — confirmed by inspection: no diff touches any of them.

## 5. Dependency Direction

Unchanged and one-directional, identical to ADR-009/012/013/014/045:
**`bot → sentinel_engine`, never `sentinel_engine → bot`.** The new adapter
has zero import of `bot`. Only `bot/_main_cycle.py` imports *into*
`sentinel_engine` (`sentinel_engine.adapters.execution_adapter`,
`sentinel_engine.composition.execution`) — `bot/main.py` was not modified
and imports nothing new. `applications/trading_intelligence` gains no new
relationship to `bot/` under this ADR — Option B (Batch 4A) remains
unauthorized and untouched.

## 6. Data/Control Flow (As Built)

```text
[existing, unmodified]
bot/main.py: per-symbol loop
  → EntryContext(...)                        [[UNCHANGED — no decision_id
                                                field; §3.2 item 1-2]]
  → bot/_main_cycle.py::_handle_entry(con, client, risk, symbol, ctx)
      → Gates 0-8e (unmodified)

[NO read-half exists — §3.2 items 3-5]

[existing, unmodified]
      → Gate 8f: risk.approve_buy(...)          [[UNCHANGED — the only real
                                                    execution-safety gate,
                                                    consumes zero Sentinel
                                                    input]]
      → client.buy(...)                          [[UNCHANGED — PaperExecutor
                                                    or Executor, unmodified]]
      → wait_for_fill / get_fill_price           [[UNCHANGED]]
      → recorder.record_executed(...) / log_trade(...) /
        recorder.record_order_not_filled(...)    [[UNCHANGED — this is also
                                                    where write_decision_event()
                                                    mints decision_id, via
                                                    EntryDecisionRecorder]]

[new, additive — report half, implemented]
      → _report_execution_outcome_safe(trust_conn, symbol, ledger_action,
        ledger_event_type, side=..., outcome=..., is_paper=..., ...)
      → _latest_decision_id_for_report(): read-only SQL —
        "SELECT decision_id FROM decision_events WHERE asset=? AND action=?
         AND event_type=? ORDER BY sequence_number DESC LIMIT 1"
        (§6.1) — silent no-op if trust_conn is None or no row is found
      → sentinel_engine/adapters/execution_adapter.py::to_execution_outcome():
        validates and shapes the payload (symbol, action, fill price or
        rejection reason, timestamp — NOT raw broker order IDs beyond the
        optional order_id field itself, retry counts, or wait_for_fill
        polling detail, per docs/platform/TRADING_INTELLIGENCE_EVENT_MODEL.md
        §5) into a DECISION_EXECUTED event
      → DecisionService.record_execution(decision_id, payload): appends to
        the dedicated composition/execution.py ledger, advances
        DecisionProjection to DecisionState.DECISION_EXECUTED
        (sentinel_engine-internal, no bot involvement; no-ops if no
        projection was ever seeded for decision_id, per the ADR-013/045
        precedent)
```

Sentinel Engine never calls `risk.approve_buy()`, `client.buy()`, or any
`bot/` code at any point in this flow. `bot/` calls into Sentinel Engine
exactly **once** per outcome — to report, after the gate sequence and
execution attempt have already completed. There is no read call.

### 6.1 Correlation Mechanism and Its Limitations

The as-built correlation mechanism is `bot/_main_cycle.py::
_latest_decision_id_for_report()`:

```text
SELECT decision_id FROM decision_events
WHERE asset=? AND action=? AND event_type=?
ORDER BY sequence_number DESC LIMIT 1
```

executed against `trust_conn` (the same connection `EntryDecisionRecorder`
already writes through), using the `(symbol, ledger_action, ledger_event_type)`
triple the calling code already knows (e.g. `("AAPL", "BUY", "EXECUTED")` or
`("AAPL", "REJECT", "QUALIFIED_REJECTION")`). This is a **read-only, best-effort,
most-recent-row lookup**, not a carried identifier — it is structurally
different from, and does not implement, the identifier-threading mechanism
(`EntryContext.decision_id`) the original draft described.

**Limitations relevant to future causal-lifecycle work** (see the separate,
unresolved Batch 4D causal-recommendation/approval analysis — not addressed
or advanced by this ADR):

- **Post-hoc only.** The row this query reads only exists because
  `EntryDecisionRecorder`'s `.reject()`/`.record_executed()`/
  `.record_order_not_filled()` already ran and already called
  `write_decision_event()` (which mints `decision_id` internally). This
  mechanism is therefore unusable for any pre-execution read — it depends on
  the very outcome it is reporting having already been written.
- **Identity by recency, not by reference.** The lookup finds the *most
  recent* matching row for the tuple, not a specific decision instance
  carried through the call stack. Under the current single-threaded,
  sequential per-symbol-per-cycle execution model this is unambiguous in
  practice, but it is not a structurally guaranteed one-to-one correlation
  the way a threaded identifier would be — a future concurrent or
  re-entrant execution model would need a different mechanism.
  QUALIFIED_REJECTION and EXECUTED
- **No forward utility for causal ordering.** Because the lookup only ever
  runs after the row it reads already exists, it cannot serve as the
  identity source for a pre-gate `Decision`/recommendation the way
  Batch 4D's causal-lifecycle analysis requires. That analysis's own
  finding — that `decision_id` generation must move from inside
  `write_decision_event()` to an earlier caller — is unaffected by, and not
  advanced by, this mechanism.

## 7. Existing Components Reused

- `RiskManager.approve_buy()` — unmodified, still the sole execution-blocking
  gate.
- `PaperExecutor` (via the `Executor` protocol and `bot/execution/factory.py`)
  — unmodified, still the paper order engine.
- The adapter pattern itself (`sentinel_engine/adapters/*`) and the ADR-002
  narrow-exception mechanism (ADR-006's template; ADR-009/045's exact
  structure) — both proven, reused verbatim in form.
- `EntryDecisionRecorder` / `log_trade()` — unmodified; this ADR's report-half
  runs alongside them, not instead of them, and depends on
  `EntryDecisionRecorder` having already written the correlated row (§6.1).

No new execution engine, no new risk gate, no new composition of
`RiskManager` or `PaperExecutor` is created.

**As-built note:** `SentinelEngine.get_decision_projection()`/`get_approval()`
are **not** exercised by the implemented scope — see §3.2.

## 8. Alternatives Rejected

Restates Batch 4A §4-8 findings, specific to why each was not chosen:

- **Option A** (`sentinel_engine → bot/execution`) — forbidden by ADR-001's
  literal text; would require amending a foundational package-structure
  ADR, not a narrow exception.
- **Option B** (`applications/trading_intelligence → bot/execution`) —
  forbidden by `TRADING_INTELLIGENCE_BOUNDARY.md` §7 and the package's own
  README dependency rules and enforced test; no ADR supports it and adopting
  it would contradict the deliberate duplication precedent
  (`alpaca_paper_orders_source.py`) that package already established for
  itself.
- **Option D** (dedicated service/process/API boundary) — no such boundary
  exists for decision-data exchange; the one existing HTTP endpoint
  (`GET /run/cron`) is a scheduling trigger, not a data-passing mechanism,
  and itself lives inside the ADR-002-protected set. Building one would be
  strictly more new architecture than reusing the proven adapter pattern.
- **Option E** (independent duplicate execution/risk primitive) — explicitly
  out of scope per Batch 4's and this ADR's own instructions; duplicating a
  capital-safety gate (`RiskManager`) is a materially different, worse risk
  than the read-only-data duplication precedent (`alpaca_paper_orders_source.py`)
  that motivated it — two independently-maintained risk gates can silently
  diverge.

## 9. Security/Safety Implications

- `RiskManager.approve_buy()` remains the only code that can block a trade;
  this ADR adds no second approval mechanism and no bypass path around it.
  There is no Sentinel-side "approved" recommendation consumed anywhere in
  the implemented scope — see §3.2 — so there is nothing that could skip or
  weaken Gate 8f or any earlier gate.
- The report-half is entirely additive and observational: absent a matching
  `decision_events` row (§6.1), it is a silent no-op, and existing behavior
  is unchanged.
- The report-half runs strictly after execution completes and is wrapped in
  its own `try/except`, isolated from the evidence/governance blocks and
  from the execution result itself (identical failure-isolation discipline
  to ADR-009 §4 / ADR-045 §4) — a Sentinel-reporting failure must never roll
  back, retry, or alter a real trade.
- No live/Robinhood execution, no autonomous authority escalation, and no
  Constitution-authority change is introduced or implied.

## 10. Test Requirements (As Built)

- `_handle_entry()` still executes gates, calls `risk.approve_buy()` and
  `client.buy()`, and returns normally when the report-half block raises at
  any point.
- A dedicated test asserts that when `trust_conn` is `None`, or no matching
  `decision_events` row exists, the report-half is a silent no-op and
  behavior is otherwise unaffected.
- A dedicated test asserts the report-half never runs before
  `client.buy()`/fill-handling (or the rejection/failure path) completes.
- A dedicated test asserts a report-half failure does not affect the
  already-committed trade, `EntryDecisionRecorder`, or `log_trade()`.
- `sentinel_engine/tests/test_package_imports.py`'s whole-package AST scan
  continues to pass unchanged, extended to cover
  `sentinel_engine.adapters.execution_adapter` and
  `sentinel_engine.composition.execution`.
- `DecisionState` tests updated additively: `DECISION_EXECUTED` becomes a
  valid `DecisionState` member; existing member-count assertions updated,
  not weakened elsewhere.
- `DecisionService.record_execution()` idempotency (a second call for the
  same `decision_id` returns `None` and does not append a second event or
  re-advance the projection) is covered.
- Both ADR-002 entry points (CLI `trade.yml` → `bot/main.py`; scheduler/HTTP
  `watchdog.yml` → `dashboard/http_endpoints.py` `GET /run/cron` →
  `scheduler/trading_job.py` → `bot.main.run()`) are exercised, since both
  reach `_handle_entry()`.
- Full `sentinel_engine/tests` and `tests/` suites pass before and after,
  0 regressions.

**Removed from this ADR's test requirements (as-built):** any test asserting
`ctx.decision_id=None` byte-for-byte-identical behavior — `EntryContext` has
no such field (§3.2).

## 11. Rollback Plan (As Built)

1. Remove the report-half block (`_report_execution_outcome_safe()` and its
   call sites) and `_latest_decision_id_for_report()` from
   `bot/_main_cycle.py::_handle_entry()`, restoring it to its exact
   pre-ADR-065 state.
2. Delete `sentinel_engine/adapters/execution_adapter.py` and its tests.
3. Delete `sentinel_engine/composition/execution.py` and its tests.
4. Remove `DecisionService.record_execution()` and its tests.
5. Remove the additive `DecisionState.DECISION_EXECUTED` member and its
   tests, restoring the prior member count.
6. No schema, migration, or persistent-storage rollback is required — all
   Sentinel Engine state affected remains the existing in-memory/temporary
   composition pattern already governing ADR-013/045.
7. `RiskManager`, `PaperExecutor`, `Executor`, `bot/execution/factory.py`,
   and `bot/main.py` are never touched, so no rollback is needed for any of
   them.

Rollback is a single-commit revert with no secondary cleanup, identical in
character to ADR-009's and ADR-045's Rollback sections.

## 12. Explicit Non-Goals

This ADR does **not** authorize, and any implementation claiming its
authority for the following is out of scope:

- Live or Robinhood execution of any kind.
- Autonomous live trading or any change to who/what may initiate a live
  order.
- A "Risk Governor" or any new independent veto/approval authority —
  Constitution Rules remain exactly as advisory as ADR-047/048/049/050/051
  already established.
- Any modification to `RiskManager.approve_buy()`'s logic, signature, or
  call sites.
- Any modification to `PaperExecutor`, `AlpacaClient`, `Executor`, or
  `bot/execution/factory.py`.
- A second, duplicate execution engine or duplicate risk-approval logic
  anywhere (Option E, rejected in §8).
- `applications/trading_intelligence` gaining any new relationship to
  `bot/` (Option B, rejected in §8).
- `sentinel_engine` gaining any import of `bot`, in any form (Option A,
  rejected in §8).
- General `bot/` extraction, refactor, or migration toward
  `applications/trading_intelligence` — that remains ADR-002's own
  reserved "Phase 2 extraction... requires its own ADR."
- Removal, weakening, or bypass of any existing package-import protection
  test.
- Any new execution architecture beyond the one-call (report only, §6)
  integration described in this ADR.
- Any change to Sentinel Engine's role as recommendation/intelligence
  infrastructure — see §13.
- Everything listed in §3.2.

## 13. Sentinel Engine's Role Is Unchanged

**Sentinel Engine** forms intelligence/recommendations and, under this ADR,
additionally *records* execution outcomes reported to it — it never becomes
an execution agent. **`bot/`** remains the execution application, remains
solely responsible for invoking `RiskManager`/`PaperExecutor`, and gains only
the ability to report what it already decided and did (§3.2: it does not
gain the ability to read a Sentinel recommendation — that half was not
built). **`PaperExecutor`** remains authoritative for paper order execution.
**`RiskManager`** remains the sole execution-blocking safety gate. Nothing in
this ADR inverts, blurs, or shares those roles.

## 14. Relationship to ADR-001

Fully preserved. `sentinel_engine`'s zero-import-of-`bot` guarantee is
unchanged; every new `sentinel_engine`-side file/change in §4 has no `bot`
import, verified by the existing AST scan (§10). This ADR only ever adds a
*caller* on the `bot` side, exactly as ADR-009/012/013/014/045 already did.

## 15. Relationship to ADR-002

This ADR is the requested narrow exception itself, following ADR-002's own
"Lifting This Protection" checklist:

1. **Specific modules named, with risk restated:** `bot/_main_cycle.py::
   _handle_entry()` only (the confirmed real risk/execution chokepoint — not
   `bot/_main_trust_decisions.py`, which Batch 4 and Batch 4A had not yet
   ruled out; see §1). `bot/main.py` is **not** in scope — it was not
   modified (§3.2).
2. **Isolated branch/worktree:** required for any implementation; not
   authorized directly on `main`.
3. **Workflow YAML files:** none reference these paths directly; no
   `.github/workflows/*.yml` change is authorized or required.
4. **Full test suite before/after:** required, per §10.
5. **Rollback plan stated in advance:** §11, written now.
6. **Both entry points verified:** §10 — CLI and scheduler/HTTP paths both
   converge on `_handle_entry()` and must both be exercised.

All other ADR-002 protections (`dashboard/`, `scheduler/` beyond the
already-existing HTTP-trigger relationship, `database/`, `ledger/`, and every
other `bot/` file, including `bot/main.py`) remain in force, unchanged.

## 16. Relationship to ADR-009 / ADR-012 / ADR-013 / ADR-014 / ADR-045

This ADR does not modify, extend, reuse, or depend on any of these five
ADRs' authorized code paths. It follows their *pattern* (pure adapter +
narrow ADR-002 exception + failure isolation + explicit non-authorization
list) as precedent, and it touches a different function
(`_handle_entry()`) than their shared chokepoint (`record_decision_safe()`
in `bot/_main_trust_decisions.py`) — the two integration points are
independent and do not interact. `sentinel_engine/composition/execution.py`
follows ADR-013/045's "dedicated pair per integration, never reused" rule —
it is its own, third/fourth independent temporary ledger, not a reuse of
`composition/evidence.py` or `composition/governance.py`.

## 17. Relationship to TRADING_INTELLIGENCE_BOUNDARY.md

Consistent with, and directly resolves (for the report-half only — see §2),
the gap that document names in its §6 ("Future Adapter Responsibilities"):
*"Execution adapter — would translate `bot/execution/` results into
`DECISION_EXECUTED`. Not designed, not implemented, requires future
ADR/design."* This ADR is that future ADR, for the execution-outcome-reporting
half. It respects §5's ("Events That Must NOT Cross The Boundary") payload
constraint — §6 above explicitly excludes raw broker order IDs beyond the
optional `order_id` field, retry counts, and polling detail from the
reported event. It does not modify `applications/trading_intelligence`'s
own boundary or grant it any new relationship to `bot/`; that document's
Dependency Rules table is unaffected.

## 18. Acceptance Criteria

This ADR may be considered **Accepted** only when the architecture owner
confirms, in writing, through the mechanism ADR-058 D2/D4 requires (tracked
on the default branch, `Status: Accepted`, landed under applicable write/merge
controls — an in-file "Accepted By" string alone is not sufficient), that the
**as-built** implementation described in §3/§4/§6 above satisfies all of the
following:

- The exact protected file/function is `bot/_main_cycle.py::_handle_entry()`
  only (§4, §15) — `bot/main.py` is not in scope, having not been modified.
- `risk.approve_buy()` and `client.buy()` remain byte-for-byte unmodified,
  unmoved, and un-reordered relative to the existing gate sequence.
- `RiskManager`, `PaperExecutor`, `Executor`, `AlpacaClient`, and
  `bot/execution/factory.py` are not modified.
- There is no read-half, no `EntryContext.decision_id`, and no pre-Gate-8f
  Sentinel lookup (§3.2) — confirmed absent from the as-built code, not
  merely unauthorized in text.
- The report-half cannot affect, delay, retry, or roll back an
  already-committed trade (§9), and is a silent no-op absent a correlated
  `decision_events` row (§6.1, §9).
- `DecisionState` gains exactly one additive member, `DECISION_EXECUTED`
  (§3.1) — no other member added, removed, or renamed.
- `DecisionService.record_execution()` is idempotent per `decision_id` (§4).
- No new `EventType` member is added for the rejected/failed case; outcome
  is represented via event payload data (§3.1).
- No live/Robinhood execution, autonomous escalation, Risk Governor,
  duplicate execution/risk engine, or `applications/trading_intelligence
  → bot` relationship is introduced (§12).
- Both CLI and scheduler/HTTP entry points are verified (§10, §15 item 6).
- Rollback (§11) is executable as a single-commit revert with the stated
  steps.
- Sentinel Engine's role remains recommendation/intelligence infrastructure
  only (§13).
- The correlation mechanism's limitations (§6.1) are acknowledged as
  limitations, not silently treated as solving the causal-recommendation
  question the separate, unresolved Batch 4D analysis addresses.

**Accepted (Batch 4D-ACCEPT).** The architecture owner has recorded explicit,
separate acceptance of exactly this reconciled scope — see `## Acceptance`
below. Per ADR-058 D2, this document's full authoritative status
additionally requires it to be tracked/landed on the default branch, which
has not yet occurred as of this acceptance act (no commit has been made);
until that lands, D3 continues to apply. The acceptance recorded here is the
architecture-owner decision itself, distinct from, and a prerequisite to,
the subsequent tracking/landing step.

---

## Decision Statement

> **Authorize a new pure translation adapter,
> `sentinel_engine/adapters/execution_adapter.py`, a dedicated composition
> boundary (`sentinel_engine/composition/execution.py`), an additive
> `DecisionService.record_execution()` method, and one additive,
> failure-isolated integration point in `bot/_main_cycle.py::_handle_entry()`
> that reports the real execution outcome (fill, rejection, or failure) back
> to Sentinel Engine, correlated by a read-only SQL lookup against the
> existing `decision_events` table, via one additive
> `DecisionState.DECISION_EXECUTED` member.**
>
> **This ADR does not modify `RiskManager`, `PaperExecutor`, `Executor`,
> `AlpacaClient`, `bot/execution/factory.py`, or `bot/main.py`. It does not
> authorize live or Robinhood execution, a Risk Governor, a duplicate
> execution/risk engine, or any `applications/trading_intelligence → bot` or
> `sentinel_engine → bot` relationship. It corrects Batch 4/4A's provisional
> naming of `bot/_main_trust_decisions.py` as the integration point — the
> real chokepoint, confirmed by direct tracing, is
> `bot/_main_cycle.py::_handle_entry()`.**
>
> **It does not authorize, and the implementation does not include, a
> pre-execution read of any Sentinel recommendation, an `EntryContext.decision_id`
> field, or any change to `bot/main.py` — those remain deferred, undecided,
> and un-implemented (§3.2).**
>
> **This ADR is Accepted, scoped exactly to the implemented items enumerated
> in §3/§3.1/§4 and explicitly excluding every item in §3.2. It authorizes
> no implementation beyond what already exists as of this acceptance act.**

---

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-09-04
**Accepted By:** Architecture Owner (explicit act performed directly in this
conversation — Batch 4D-ACCEPT — not inferred from implementation, from the
Batch 4D-RECONCILE text change, or from any other source)
**Accepting PR / commit:** — none yet. This acceptance act has not been
committed to the repository as of this record. Per ADR-058 D2, full
authoritative status additionally requires this document to be tracked on
the default branch and landed under the repository's applicable write/merge
controls; that step is separate from, and subsequent to, the acceptance
decision recorded here, and has not occurred yet. No PR number, commit SHA,
or other landing evidence is asserted because none exists at the time of
this record.

**Scope of this acceptance — exactly, and only:**

1. Post-execution Sentinel execution-outcome reporting from
   `bot/_main_cycle.py::_handle_entry()`.
2. `sentinel_engine/adapters/execution_adapter.py`.
3. `sentinel_engine/composition/execution.py`.
4. `DecisionService.record_execution()`.
5. `DecisionState.DECISION_EXECUTED`.
6. The FILLED / REJECTED / FAILED execution-outcome distinction.
7. Failure-isolated reporting (§9).
8. Idempotent execution-outcome recording (§4).
9. The `_latest_decision_id_for_report()` read-only SQL correlation
   mechanism and its stated limitations (§6.1).

**Explicitly NOT authorized by this acceptance** — restating §3.2 verbatim,
because this acceptance does not expand it: `EntryContext.decision_id`;
`bot/main.py` decision_id threading; any pre-Gate-8f Sentinel recommendation
lookup; `get_decision_projection()`; `get_approval()`; any causal
pre-execution Sentinel recommendation; any Sentinel approval authority over
`RiskManager.approve_buy()`; Policy registration; `record_approval()`; any
autonomous Sentinel execution authority; any change to `RiskManager`,
`PaperExecutor`, or `AlpacaClient`.

This acceptance ratifies the reconciled text exactly as Batch 4D-RECONCILE
left it. No wording in §3, §3.1, §4, §6, §6.1, §9, §10, §11, §13, §15, or
§18 was altered to perform this acceptance, beyond the status/header/closing
language changes recorded in this Status Log.

---

## Status Log

**Proposed — 2026-09-04.** Drafted per Batch 4B, a read-only governance-
artifact task following Batch 4A's boundary-option analysis. No
architecture-owner review has occurred. No production code, test, or other
ADR/document has been modified in the course of producing this draft.

**Governance-drift finding — 2026-09-04 (Batch 4D-STATUS).** Read-only audit
found Batch 4C had already implemented code in the working tree while this
ADR remained untracked and `Status: Proposed`, and that three code/test
docstrings incorrectly asserted "ADR-065 (Accepted)". Per ADR-058 D3/D4,
determined this ADR conferred, and confers, no authority in that state; no
rollback required (nothing was committed); reconciliation recommended over
either silent status-flip or unnecessary rollback.

**Reconciled — 2026-09-04 (Batch 4D-RECONCILE).** This revision narrows §1,
§3, §4, §5, §6, §7, §9, §10, §11, §13, §15, §18, and the Decision Statement
to describe exactly the as-built implementation, explicitly separating
Implemented Scope (§3, §3.1, §4) from Deferred/Not Implemented Scope (§3.2),
and documents the actual correlation mechanism and its limitations (§6.1).
**`Status` remained `Proposed`** as of the reconciliation pass itself. No
architecture-owner acceptance act had occurred yet at that point.

**Accepted — 2026-09-04 (Batch 4D-ACCEPT).** The architecture owner
explicitly accepted this ADR, in exactly the reconciled form left by
Batch 4D-RECONCILE, through the act recorded in `## Acceptance` above.
`Status` now reads `Accepted`, scoped exactly to §3/§3.1/§4's implemented
items and excluding everything in §3.2. This acceptance was not inferred
from the pre-existing implementation, from the reconciliation text change,
or from any other source — it was recorded here as a direct, explicit act.
Per ADR-058 D2, this document additionally requires tracking/landing on the
default branch (i.e., a commit) before it is fully authoritative; that has
not occurred as of this entry. The three docstrings previously asserting
"ADR-065 (Accepted)" — `sentinel_engine/domain/decision_state.py`,
`sentinel_engine/tests/test_decision_state.py`, and
`sentinel_engine/tests/test_recommendation_governance_lifecycle.py` — were
reviewed against this now-accepted, reconciled scope and found to already
accurately describe it (each already attributes `DECISION_EXECUTED` solely
to `DecisionService.record_execution()` as the real producer, and none of
the three references, describes, or relies on the deferred read-half/
`EntryContext.decision_id` mechanism in §3.2). No textual edit was made to
any of the three files: the correction those docstrings needed was for
their "(Accepted)" claim to become true, not for their content to change,
and that claim is now true.
