# ADR-009: Narrow Exception to ADR-002 for Sentinel Evidence Integration

**Status:** Accepted
**Date:** 2026-08-10

## Context

`docs/architecture/EVIDENCE_POLICY_DECISIONS.md` ("V5-B") established that
`sentinel_engine.Evidence` is the downstream representation for production
model-output data, with vocabulary value `MODEL_OUTPUT` and a `data` shape
matching `bot/strategy/model_output_adapter.py::build_model_outputs()`
exactly (one `Evidence` record per model — xgboost/lstm/finbert — three per
decision).

A subsequent read-only investigation ("V5-C") traced the real production
call chain and found:

- `build_model_outputs()` runs before any `decision_id` exists.
- `bot/trust_ledger/decisions.py::write_decision_event()` is where
  `decision_id` is actually created (`new_decision_id(asset)`), as part of
  the same payload dict that already contains `model_outputs`.
- `bot/_main_trust_decisions.py::record_decision_safe()` (lines 50-86) is
  the single production chokepoint through which every decision write
  (BUY/SELL/HOLD/REJECT) passes — `write_decision_event()` has exactly one
  production caller, this function, confirmed by inspection and consistent
  with `scripts/verify_single_write_path.py`'s existing single-write-path
  guarantee.
- Immediately after `write_decision_event()` returns (line 78), the local
  variable `decision_row` already contains both the real `decision_id` and
  the unmodified `model_outputs` dict — the first and only point in the
  call chain where both are simultaneously available, post-commit.
- This function already contains a directly analogous precedent: line 80's
  `constitution.check_and_log(trust_conn, decision_row, risk)`, a
  post-write, `decision_row`-keyed side effect, wrapped in the same
  try/except (lines 64/79/83/85) that already isolates side-effect failures
  from the ledger write itself.

`bot/_main_trust_decisions.py` is inside `bot/`, protected by
[ADR-002](ADR-002-bot-runtime-protection.md) — "no moves, no import
changes, no refactors, no file changes of any kind." No existing exception
covers it: [ADR-006](ADR-006-confidence-integrity-phase1-exception.md)
names four different, unrelated files for a completed, different purpose.
There is no existing `bot → sentinel_engine` import anywhere in the
repository today.

## Decision

Grant a narrow, permanent exception to ADR-002 for exactly one file and
one function, authorizing exactly one additive integration call.

### Protected file

`bot/_main_trust_decisions.py`

### Protected function

`record_decision_safe()`

### Authorized change

After `decisions.write_decision_event(...)` (current line 74) returns
successfully, and using only the resulting `decision_row` — specifically
`decision_row["decision_id"]` and `decision_row["model_outputs"]` — a
single additive evidence-integration point may be added, consisting of the
following two-stage flow against the accepted
[ADR-012](ADR-012-sentinel-engine-evidence-intake-for-bot-model-outputs.md)
contract:

1. Call `to_evidence_records(decision_row["model_outputs"])` (the
   authoritative translation boundary ADR-012 establishes at
   `sentinel_engine/adapters/evidence_adapter.py`) and receive exactly
   three `Evidence` records in return. This call passes only
   `model_outputs` — `to_evidence_records` does not accept, and must
   never be made to accept, `decision_id`; that constraint is fixed by
   ADR-012 and is not reopened here.
2. For each of the three returned `Evidence` records, call
   `EvidenceService.associate_evidence(decision_row["decision_id"], evidence)`
   to link it to the decision. This is the sole mechanism by which
   `decision_id` reaches Evidence — `Evidence` itself carries no
   `decision_id` field.

Together, these two stages — translation, then association, repeated for
each of the three records — constitute the single additive
evidence-integration point this ADR authorizes. This ADR does not
authorize adding `EvidenceService`, `LedgerRepository`, `ProjectionRepository`,
or any persistence call inside `evidence_adapter.py` itself — those calls
belong only at this `bot/`-side call site, exactly as ADR-012 requires.

The call sequence must:

- occur only after `write_decision_event()` has returned (never before —
  no invented interim identifier, no second decision identifier),
- use `decision_row["decision_id"]` verbatim for all three
  `EvidenceService.associate_evidence` calls — the exact identifier
  `new_decision_id(asset)` created inside `write_decision_event()`,
  unmodified,
- be wrapped in its own exception handling so that any failure anywhere
  in this two-stage sequence can never fail, delay, retry, or otherwise
  affect the decision write, the trading decision, execution, or risk
  logic — the same failure-isolation principle already demonstrated by
  this function's existing `constitution.check_and_log` call.

No other line, function, class, or file in `bot/` is authorized to change
under this ADR.

## Constraints

**Allowed:**

- New `import` statements in `bot/_main_trust_decisions.py` referencing
  `to_evidence_records` (`sentinel_engine/adapters/evidence_adapter.py`,
  per accepted ADR-012) and `EvidenceService.associate_evidence`
  — both live outside `bot/`, unprotected by ADR-002 already, per its own
  text: "does not restrict work inside `sentinel_engine/`".
- The two-stage call sequence inside `record_decision_safe()`, after the
  existing `write_decision_event()` call, as described above under
  "Authorized change": one call to
  `to_evidence_records(decision_row["model_outputs"])`, followed by up to
  three calls to `EvidenceService.associate_evidence(decision_row["decision_id"], evidence)`.
- Nothing further regarding `EvidenceService` instance construction or
  wiring. This ADR does **not** authorize constructing, wiring, or reusing
  any `EvidenceService` instance — locally in `bot/`, or anywhere else —
  to make `associate_evidence` callable from this integration point. See
  "EvidenceService Instance / Wiring" below, which governs this
  exhaustively.
- Any new file(s) outside `bot/` needed to implement the plain-data intake
  boundary and the `Evidence` translation — this is exactly what accepted
  ADR-012 already provides; this ADR does not authorize modifying it.

**Forbidden — this ADR does NOT authorize:**

1. Any change to model computation (`bot/strategy/`).
2. Any change to BUY/SELL/HOLD/REJECT decision logic or gate sequencing.
3. Any change to risk logic (`bot/risk/`, `RiskManager`).
4. Any change to execution/order-fill behavior.
5. Any change to ledger ownership or ADR-004's deferred Option A/B/C
   choice.
6. Any change to root ledger schema (`ledger/schema.sql`).
7. Implementation of a `sentinel_engine/ledger/` production backend.
8. Any persistence redesign, for either the root ledger or
   `sentinel_engine`.
9. Any modification to ADR-004's text, status, or deferral.
10. Any `sentinel_engine → bot` import, in either direction beyond the one
    authorized `bot → sentinel_engine` call.
11. Any direct import of a `bot` type into `sentinel_engine` (the
    boundary crossing must remain plain-data-in, per
    `decision_adapter.py`'s existing pattern).
12. Any integration of `bot/decision_engine` — it remains deferred per
    V5-B §8 and has no role here.
13. Physical removal of `Decision.evidence_reference` — it stays
    deprecated-but-present per V5-B §7; unrelated to this exception.
14. Any change to `dashboard/`, `scheduler/`, `database/`, top-level
    `ledger/`, or any `.github/workflows/*.yml` file.
15. Any modification to `bot/` files other than
    `bot/_main_trust_decisions.py`. If implementation reveals a second
    `bot/` file must change, implementation must stop and a scope
    amendment to this ADR must be sought — this ADR does not pre-authorize
    that.
16. General lifting of ADR-002 for any other purpose.

## Failure Isolation

The authorized two-stage evidence-integration sequence (translation via
`to_evidence_records`, then association via
`EvidenceService.associate_evidence`, ×3) must never cause ledger write
failure, trading decision failure, execution failure, risk failure, or
scheduler failure. The full sequence must be exception-isolated the same
way `constitution.check_and_log` already is at this call site (line 80,
inside the try/except spanning lines 64-86) — a failure here should, at
most, log a warning, mirroring this file's existing `logger.warning(...)`
pattern for non-fatal ledger side-effect failures (e.g. line 82, line 86).

This ordering and isolation is non-negotiable:

- `write_decision_event()` completes and returns the committed
  `decision_id` first.
- Evidence translation and association happen strictly afterward, never
  before, never concurrently.
- Any exception raised anywhere in the two-stage sequence — translation
  or any of the three association calls — is caught by this same
  exception-isolated block.
- An evidence failure can never cause the already-successful decision
  write to fail, retry, or be rolled back, and can never alter the
  decision outcome (BUY/SELL/HOLD/REJECT) already committed by
  `write_decision_event()`.

## Transaction / Ordering

Evidence association is authorized **only after** `write_decision_event()`
returns the authoritative, already-committed `decision_id`. This ADR does
not authorize writing Evidence before the decision event exists, and does
not authorize inventing a temporary or second identifier to work around
that ordering.

## Identity

All Evidence records produced for one decision must be associated using
`decision_row["decision_id"]` — the exact value produced by
`new_decision_id(asset)` inside `write_decision_event()`
(`bot/trust_ledger/decisions.py:140`) — unmodified. No new correlation
identifier is introduced by this ADR. `Evidence` itself intentionally has
no `decision_id` field (per accepted ADR-012); `decision_id` reaches
Evidence only through the three
`EvidenceService.associate_evidence(decision_row["decision_id"], evidence)`
calls described above, never as adapter input.

## ADR-004 Boundary

This ADR does not choose among ADR-004's Option A/B/C ledger-ownership
options, does not establish persistent Evidence storage, does not
authorize synchronization between the root ledger and
`sentinel_engine/ledger/`, and does not authorize implementation of a
production `LedgerStore`. It authorizes only the runtime *call-site
boundary* — where in `bot/` the call is made, with what data, in what
order, under what failure isolation.

**Known limitation, stated explicitly rather than solved here:** as of
this writing, `sentinel_engine`'s `LedgerStore`/`ProjectionRepository` have
no production backend anywhere in the repository — the only non-test
instantiation is `applications/trading_intelligence/bootstrap.py`'s
explicitly-labeled "minimal in-memory placeholder... not a production
persistence choice." Exercising the call authorized here, before ADR-004
resolves, would therefore accumulate Evidence only in memory scoped to
whatever process makes the call, with no durability guarantee across the
bot's per-cycle process lifecycle. This ADR authorizes the code-level
integration point to exist and be tested; it does not assert that
invoking it in the live trading runtime is currently meaningful, and does
not authorize standing up a durable backend to make it so — that remains
squarely ADR-004's decision.

## EvidenceService Instance / Wiring

`EvidenceService.associate_evidence` requires an `EvidenceService`
instance, which in turn requires a `LedgerRepository` and a
`ProjectionRepository` (both mandatory constructor arguments). As of this
writing, no `EvidenceService` instance reachable from `bot/` exists
anywhere in the repository — the only non-test instantiation sites
(`applications/trading_intelligence/bootstrap.py`,
`applications/wealth_intelligence/bootstrap.py`) construct one as a
private local variable inside their own `build_application()` composition
root, never exposed or returned for reuse elsewhere.

This ADR authorizes only the *call* to `EvidenceService.associate_evidence`
described under "Authorized change" above — it does **not** authorize
obtaining an instance to call it on. Specifically:

- This ADR does **not** authorize constructing, wiring, or reusing any
  `EvidenceService` instance — locally in `bot/`, in a new file outside
  `bot/`, or by reaching into an existing composition root such as
  `applications/trading_intelligence/bootstrap.py` — to make
  `associate_evidence` callable from this integration point. This
  includes not authorizing a fresh, local, in-memory placeholder
  `LedgerRepository`/`ProjectionRepository`/`EvidenceService` instance,
  even one that merely duplicates the already-precedented non-production
  in-memory pattern used in `applications/*/bootstrap.py`.
- A reachable `EvidenceService` wiring path — however minimal or
  non-durable — must be established by a **separate governance decision**
  before implementation of this ADR begins. Until that separate decision
  is made and implemented, the two-stage call sequence this ADR
  authorizes has no instance to call `associate_evidence` on and remains
  unimplementable, by design.
- Once such wiring is separately authorized, it does **not** authorize a
  new persistence architecture, a new database, a new ledger backend, or
  a new `LedgerRepository`/`ProjectionRepository` implementation. It does
  not make, shortcut, or imply any ADR-004 Option A/B/C ledger-ownership
  choice. Whatever wiring that separate decision provides must remain
  consistent with this ADR's existing memory-only, non-durable
  limitation — association under this ADR is not expected to survive
  beyond the process that makes the call.

## Relationship to ADR-001, ADR-002, ADR-004, ADR-006

This ADR supersedes ADR-002's freeze **only** for
`bot/_main_trust_decisions.py`, and only for the single additive call
described above. All other ADR-002 protections (`bot/` more broadly,
`dashboard/`, `scheduler/`, `database/`, top-level `ledger/`, all
`.github/workflows/*.yml` files) remain in force, unchanged. This ADR does
not amend, weaken, or extend ADR-006 — it is a separate, independent
exception for a different file and a different purpose. This ADR does not
alter ADR-001's rule that `sentinel_engine` must not import `bot` — the
authorized call is one-directional (`bot → sentinel_engine`), consistent
with ADR-001. This ADR does not make, shortcut, or amend the ledger-
ownership choice ADR-004 defers.

[ADR-012](ADR-012-sentinel-engine-evidence-intake-for-bot-model-outputs.md)
is now Accepted and implemented
(`sentinel_engine/adapters/evidence_adapter.py`) and provides the
authoritative translation contract this ADR's integration point calls:
`to_evidence_records(model_outputs: dict) -> list[Evidence]`. This ADR
does not modify ADR-012 or its contract. This ADR retains `decision_id`
separately, on the `bot/`-side, and performs `EvidenceService` association
outside the adapter — ADR-012's adapter never accepts or handles
`decision_id` in any form.

## Validation Gate (before implementation is considered complete)

- Full existing suite, both currently-run CI steps, before and after:
  `python -m pytest sentinel_engine/tests -v --tb=short` (boundary-
  enforcement tests, including
  `test_sentinel_engine_does_not_import_bot_dashboard_scheduler_ledger_database_or_applications`,
  which must continue to pass unchanged — it only constrains
  `sentinel_engine`'s imports, not `bot`'s, so this direction of import is
  not something it currently forbids) and
  `python -m pytest tests/ -v --tb=short` (bot-side suite; baseline
  ~1200+ tests per ADR-002, 1274 passed most recently per ADR-006).
- `scripts/verify_single_write_path.py` re-run and still passing — it
  proves `write_decision_event()` has exactly one production caller; this
  ADR's change must not create a second call path into it or a bypass of
  `record_decision_safe()`.
- Both of ADR-002's documented entry points verified, per its own
  "Lifting This Protection" checklist item 6: the CLI path
  (`trade.yml` → `python bot/main.py --mode paper --loop`) and the
  scheduler/HTTP path (`watchdog.yml` → `dashboard/http_endpoints.py`
  `GET /run/cron` → `scheduler/trading_job.py` → `bot.main.run()`) — both
  reach `record_decision_safe()` and must both be exercised, not just one.
- New tests specific to this change: (a) `record_decision_safe()` still
  writes the decision event and returns normally when the Evidence
  translation or association call raises; (b)
  `EvidenceService.associate_evidence` is invoked with the identical
  `decision_id` for all three `Evidence` records produced for one
  decision — not "the three `Evidence` records carry `decision_id`",
  since `Evidence` itself has no `decision_id` field; the assertion is on
  the arguments `associate_evidence` is called with; (c) no
  `to_evidence_records` or `associate_evidence` call occurs before
  `write_decision_event()` returns.
- Isolated branch or worktree for implementation, not directly on `main`,
  per ADR-002's checklist item 2.
- A rollback plan written before implementation starts, per ADR-002's
  checklist item 5 (see Rollback below) — not reconstructed after the
  fact.

## Rollback

Revert the single commit that adds the import and the call in
`bot/_main_trust_decisions.py::record_decision_safe()`. Because the change
is strictly additive (no existing line altered, no signature changed, no
other call site touched), reverting it restores `record_decision_safe()`
to its exact pre-change behavior with no secondary cleanup — no schema
change, no data migration, no other file to revert. Any `sentinel_engine`-
side adapter/wiring code added to support the call may be reverted
independently or left in place (inert, uncalled) without affecting `bot/`.

## Consequences

- `bot/` gains its first-ever import of `sentinel_engine`, in the
  direction ADR-001 already permits.
- `record_decision_safe()` gains one additional, failure-isolated side
  effect, structurally identical in isolation guarantees to the existing
  `constitution.check_and_log` call already present there.
- No trading, risk, execution, or ledger-write behavior changes.
- The call's practical value remains contingent on ADR-004 resolving a
  production `sentinel_engine` backend — this ADR does not accelerate,
  shortcut, or presuppose that resolution.
- All other ADR-002 protections remain exactly as stated, for every file
  and directory not named above.
