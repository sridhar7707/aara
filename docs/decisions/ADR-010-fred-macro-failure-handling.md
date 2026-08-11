# ADR-010: Narrow Exception to ADR-002 for FRED/Macro Data-Quality Failure Handling

**Status:** Accepted — Implemented (commits `6bc2d03`, `675ec49`)
**Date:** 2026-08-11
**Accepted:** 2026-08-11 — ADR-002 remains in force except for the two files and scope named in the Decision below

## Context

A forensic trace (this conversation, G2 investigation) established the real
behavior of the VIX-derived market-halt gate, the one identified
preventive, actually-blocking safety control in the current Phase 1A
trading path (every other blocking control — `RiskManager.halted`/
daily-loss/portfolio-drawdown — is reactive, triggered only after a
realized loss; Constitution Rules 1 and 4 are advisory-only in Phase 1A and
block nothing).

**Current behavior, as traced:**

- `bot/strategy/macro.py::_get_cached()` fetches FRED data (VIX, yield
  curve, fed funds), computes `halt = vix >= MACRO_HALT_VIX` (default 28.0),
  and caches the result in-process for 4 hours.
- On any fetch failure, `_get_cached()` **never raises** — it silently
  returns the last successfully-cached value if one exists, or a hardcoded
  `{"score":0.5,"cap":1.0,"halt":False}` on cold start. Because a failed
  refresh simply retains the prior in-process value, the module can
  **silently continue serving stale data beyond its intended TTL** — how
  long depends on process lifetime and invocation pattern, not a bounded
  window.
- `bot/db/macro_cache.py::get_macro()` wraps `_get_cached()` with its own
  separate SQLite-backed 4-hour cache and its own `except Exception` block
  — including a Telegram alert intended to notify a human when FRED is
  unreachable — but because `_get_cached()` never raises, **this except
  block, and the alert inside it, is unreachable dead code** for an
  ordinary FRED outage.
- `bot/main.py:356` → `bot/_main_cycle.py:97` gate BUY eligibility on
  `macro_halt` exactly as returned above — a silent stale or defaulted
  `False` reaches the gate indistinguishably from a genuine, fresh,
  successful computation.
- `bot/_main_positions.py` (`_handle_exits()` and every exit type within
  it — gap-down, take-profit, ATR stop-loss, time-exit) has **zero
  dependency** on `macro_halt` or any FRED-derived value, confirmed by
  direct reading and a whole-file grep. This independence is already
  recorded as an existing invariant in the G1 addendum
  (`DECISION_INTELLIGENCE_ARCHITECTURE_PHASE1_ADDENDUM.md` §3), which this
  ADR does not reopen and defers entirely to here for FRED's specific
  handling.

**Observed safety consequence:** the one identified preventive control in
the current trading path can silently continue serving stale data beyond
its intended TTL, with its own intended human-alert mechanism structurally
unable to fire, and with no way for anything downstream to know the
difference between "market is calm" and "we don't actually know."

Both files this ADR authorizes changing — `bot/strategy/macro.py` and
`bot/db/macro_cache.py` — are inside `bot/`, protected by
[ADR-002](ADR-002-bot-runtime-protection.md). No existing exception covers
them: [ADR-006](ADR-006-confidence-integrity-phase1-exception.md) names
four unrelated files; [ADR-009](ADR-009-sentinel-evidence-integration.md)
names one unrelated file (`bot/_main_trust_decisions.py`).

## Decision

Grant a narrow exception to ADR-002 for exactly two files, authorizing the
BUY-eligibility-path failure-state handling described below. This is
explicitly **not** a one-line default-value change — the forensic trace
established that the defect requires a failure signal to survive one
additional hop than it currently does, and both files are necessary to
carry that signal from where it originates to where it is consumed.

### Protected files

- `bot/strategy/macro.py`
- `bot/db/macro_cache.py`

### Failure-state semantics (the substantive decision)

| State | Meaning | BUY eligibility |
|---|---|---|
| Fresh successful fetch | Current macro state known | Normal evaluation, `halt` computed from real data |
| Valid cached data within TTL | Recent known macro state, not a failure state | Normal evaluation using the cached value |
| No valid data — cold start, or cache expired and the due refresh attempt failed | Macro state genuinely unknown | **BUY blocked** |
| Any exit condition (SELL/stop/gap/time-exit) | Existing position needs risk reduction | **Unaffected — no FRED dependency, unchanged** |

No grace period beyond the existing 4-hour TTL is introduced: a cached
value remains usable exactly as long as it is within its already-defined
TTL. The failure state exists only when a refresh is actually due *and*
that attempt fails — never merely because the cache is old but not yet due
for refresh. A still-valid cached value is explicitly **not** a failure
state and must not be treated as one.

**Implementation guardrail (the most important one in this ADR):** the
implementation must not treat the mere existence of an in-process
`_MACRO_CACHE` value as sufficient evidence that macro data remains valid
after its defined TTL. TTL validity must be evaluated on its own terms,
independent of whether a previous in-process value happens to still be
present — otherwise the module-level cache can continue masking the SQLite
cache's own expiration, reproducing the exact defect this ADR exists to
close.

**No schema change:** no database schema, cache-table schema, or
persistence-format change is authorized by this ADR. `macro_cache`'s
existing table shape is unaffected.

### Scope boundary

This exception applies **only** to the risk-adding BUY eligibility path. It
must not introduce any dependency, of any kind, between FRED availability
and `_handle_exits()` or any exit type within it. The existing
zero-dependency invariant (G1 addendum §3) must remain exactly as it is
after this change as before it.

## Non-Goals

This ADR does not authorize, and explicitly excludes:

1. Changing `MACRO_HALT_VIX`'s threshold (28.0) or its meaning.
2. Changing macro scoring (`_compute_from_raw`'s sigmoid score) or position
   sizing cap (`cap`) behavior.
3. Adding new FRED indicators or data sources.
4. Modifying `bot/_main_cycle.py`'s BUY gate — the trace found this gate
   already has the correct semantics (`macro_halt=True` → reject,
   `macro_halt=False` → continue evaluation); the defect is entirely
   upstream, in the system's inability to distinguish "halt=False" from
   "macro state unavailable." If implementation later proves this file
   must change anyway, that requires its own scope amendment to this ADR,
   not a silent expansion.
5. Modifying `bot/_main_positions.py` in any way.
6. A universal external-data failure policy — this ADR decides FRED/macro
   handling only. Any other provider's failure semantics (NewsAPI, SEC,
   Reddit) is a separate decision, per G1 addendum §3's own boundary.
7. Thesis, Conviction, Investment Memory, or `sentinel_engine`-native
   Capital Pool — unaffected, per the G1 addendum, untouched by this ADR.
8. Any part of G3 (extending `data_quality_events` coverage generally)
   beyond whatever is strictly necessary to carry the FRED failure signal
   for this specific gate.

## Testing / Acceptance Criteria

- A test confirming: fresh successful fetch → correct `halt` value used.
- A test confirming: fetch failure with a still-within-TTL cached value →
  cached value used, **not** treated as a failure state.
- A test confirming: fetch failure with no valid cached data (cold start or
  expired-and-failed-refresh) → BUY path blocked.
- A test confirming: TTL expiration is detected correctly even when an
  in-process `_MACRO_CACHE` value is still present (the guardrail above,
  verified directly).
- A test confirming: the same failure conditions above produce **no**
  change whatsoever in `_handle_exits()`'s behavior — exit tests continue
  to pass unmodified.
- A test confirming that a genuine unavailable FRED state produces the
  existing human-visible alert/notification path, rather than silently
  defaulting or continuing without notification — the specific mechanism
  is not prescribed by this ADR.
- Full existing suite before/after: `python -m pytest tests/ -v --tb=short`
  and `python -m pytest sentinel_engine/tests -v --tb=short`.
- Both ADR-002 entry points verified (CLI + scheduler/HTTP), per its own
  "Lifting This Protection" checklist.
- Isolated branch or worktree, not directly on `main`.

## Rollback

Revert the commit(s) touching `bot/strategy/macro.py` and
`bot/db/macro_cache.py`. No schema change, no data migration, and no other
source file is authorized by this ADR.

## Relationship to G1

This ADR does not reopen or modify
`DECISION_INTELLIGENCE_ARCHITECTURE_PHASE1_ADDENDUM.md`. That addendum
recorded the exit-path independence invariant as an existing fact and
explicitly deferred FRED/VIX's specific handling to this ADR (addendum
§3/§5) — this ADR is that deferred decision, and nothing more.

## Relationship to ADR-002

Creates a narrow exception to ADR-002's freeze **only** for the two named
files and only for the failure-state handling described above. All other
ADR-002 protections remain in force, unchanged.

## Amendment 1 (2026-08-11): Authorizing Downstream Distinction Between VIX Halt and Macro-Data-Unavailable States

### Trigger

Post-implementation governance inspection found that `macro_halt=True` now
represents two distinct conditions — genuine `VIX >= MACRO_HALT_VIX` and
FRED/macro-data-unavailable (fail-closed) — and that two downstream
consumers assumed only the former: `bot/_main_prep.py` unconditionally
fires the VIX-specific Telegram alert, and `bot/monitor/_dashboard_overview.py`
reads `macro_cache` directly (bypassing `get_macro()`), so it can show
"ACTIVE" during an active FRED outage rather than any halt indication.

### Authorized scope

This amendment authorizes the **capability** — not a specific mechanism —
to expose the distinction between a genuine VIX halt and a FRED/macro
data-unavailable state to downstream presentation and notification
consumers, while preserving `get_macro()`'s existing three-value return
contract `(score, cap, halt)` unchanged for all existing callers.

Protected files, extended:

- `bot/db/macro_cache.py` *(already protected by ADR-010; extended to
  include this capability)*
- `bot/_main_prep.py` *(new)*
- `bot/monitor/_dashboard_overview.py` *(new)*

The specific implementation mechanism (how the distinction is carried — in-
process signal, an additional table key, or otherwise) is deferred to the
implementation, subject to the persistence/TTL rule below and the semantic
distinction below. This amendment authorizes the capability and constrains
its shape; it does not select the mechanism.

### Explicit exclusions

- `bot/monitor/telegram_bot.py` — not authorized for modification.
  `alert_vix_halt()` is correctly implemented; responsibility for deciding
  when to call it belongs to the caller.
- `bot/_main_cycle.py` — not authorized for modification. Gate 0's reason-
  agnostic fail-closed reject on `macro_halt=True` is correct per this
  ADR's original Non-Goal #4 and remains correct under this amendment: BUY
  must stay blocked regardless of which of the two reasons produced
  `halt=True`.
- `bot/_main_positions.py` — not authorized for modification. Exit-path
  independence is unaffected by this amendment and remains exactly as this
  ADR established it.
- No database schema/DDL change is authorized (see Persistence/TTL rule
  below).
- No unrelated dashboard refactoring is authorized — this amendment
  concerns the halt-state distinction only, not
  `bot/monitor/_dashboard_overview.py`'s broader behavior.

### Preserved ADR-010 invariants

All carried forward unmodified by this amendment:

- Fail-closed BUY behavior: `macro_halt=True`, for either reason, continues
  to block BUY via the existing, unmodified Gate 0.
- `MACRO_HALT_VIX` threshold value and meaning, unchanged.
- Macro scoring (`_compute_from_raw`) and position-cap formulas, unchanged.
- `bot/_main_cycle.py` and `bot/_main_positions.py`, unmodified.
- Exit-path independence (`_handle_exits()` and every exit type),
  unaffected.
- No database schema/DDL change.
- The `score`/`cap`/`halt` cache's TTL logic remains the sole authority
  over when a refresh is due, in both `bot/db/macro_cache.py::get_macro()`'s
  SQLite-backed check and `bot/strategy/macro.py::_get_cached()`'s in-
  process check.

### New semantic distinction being authorized

This amendment distinguishes two categories of macro-related state, and
authorizes action only on the second:

**(A) Persisted trading-state values — `score`, `cap`, `halt`.** These are
the values this ADR already governs. They must continue to reflect only a
genuine successful fetch or a valid within-TTL cached value. A FRED failure
must **not** create or refresh these values, and must **not** advance their
`cached_at`/freshness marker. This is unchanged from this ADR's original
Decision and this amendment does not reopen it.

**(B) Optional observational metadata — a halt-reason signal.** A FRED
failure may be additionally observable, past this point, only insofar as it
lets a presentation or notification consumer know that *the most recent
macro evaluation attempt failed*, as distinct from *the most recent macro
evaluation succeeded and found calm markets*. This amendment authorizes
exposing (B) — by whatever mechanism the implementation selects — subject
strictly to the Persistence/TTL rule below. (A) and (B) are governed
independently; authorizing (B) does not relax any constraint on (A).

### Persistence/TTL rule

If the implementation chooses to persist any form of (B) observational
metadata:

- It must be structurally distinct from the (A) `score`/`cap`/`halt`
  values — a different persisted signal, not a variant encoding folded
  into those same values.
- It must **never** be consulted by any refresh-due / TTL-freshness
  decision, in either `get_macro()` or `_get_cached()`. Those decisions
  must depend solely on (A)'s own freshness, exactly as this ADR
  established.
- Writing or refreshing (B) must have no effect — none — on whether a
  subsequent call treats (A) as valid-within-TTL. A FRED failure recorded
  in (B) must not be capable of causing a later call to skip a genuine
  refresh attempt of (A).

If the implementation instead chooses to expose (B) without persistence
(e.g., confined to the process that observed the failure), that satisfies
this amendment too — persistence of (B) is optional, not required, and is
authorized only under the rule above if chosen.

### Cold-start limitation

This amendment does not close, and does not claim to close, the following
gap: if no trading process has attempted a macro refresh since the
dashboard-reading process last observed state, and no (B) observational
metadata yet exists (e.g., true cold start, or (B) implemented as
in-process-only and thus invisible across process boundaries), the
dashboard **cannot** infer a current FRED outage merely from an empty or
stale `macro_cache` table. In that circumstance the dashboard's display is
undetermined with respect to the current live state — it is not authorized
to be asserted as accurate, and no claim to the contrary should be made in
the implementation, its tests, or its documentation. Closing this residual
gap, if desired, is out of scope for this amendment and would require its
own future decision.

### Required tests

- `bot/db/macro_cache.py`: a test confirming (A)'s `cached_at`/freshness is
  unaffected by whatever mechanism carries (B) — i.e., a FRED failure that
  produces a halt-reason signal still leaves the next call's refresh-due
  decision exactly as this ADR's existing tests already establish (no
  regression of `test_get_macro_does_not_persist_failure_state` and
  `test_get_macro_retries_every_call_while_fred_stays_down`).
- `bot/db/macro_cache.py` or `bot/_main_prep.py` (implementation-dependent):
  a test confirming the VIX-threshold reason and the data-unavailable
  reason are each observable and distinguishable by a downstream consumer.
- `bot/_main_prep.py`: a test confirming `tg.alert_vix_halt()` fires for a
  genuine VIX halt and does **not** fire for a data-unavailable halt.
- `bot/monitor/_dashboard_overview.py`: a test confirming the dashboard
  renders a distinct status for a data-unavailable state when (B) is
  observable to it, and a separate test confirming the cold-start/no-
  metadata case is not asserted as "ACTIVE" in a way that implies
  certainty — consistent with the Cold-start limitation above, this test
  should not assert the dashboard *correctly detects* an outage it
  structurally cannot detect; it should assert the dashboard does not
  misrepresent that undetermined state as a confirmed "ACTIVE, all clear."
- Full existing suite before/after, consistent with this ADR's original
  Testing / Acceptance Criteria: `python -m pytest tests/ -v --tb=short`
  and `python -m pytest sentinel_engine/tests -v --tb=short`.

### Acceptance criteria

- `get_macro()`'s return signature and every existing caller's unpacking of
  it (`bot/_main_cycle.py`, `bot/_main_runner.py`) are unchanged — verified
  by an unmodified test suite for those callers.
- A genuine VIX halt and a data-unavailable halt are each distinguishable
  by at least `bot/_main_prep.py` and `bot/monitor/_dashboard_overview.py`,
  by the mechanism the implementation selects.
- No (A) value's freshness/TTL behavior changes from this ADR's already-
  accepted behavior, verified by this ADR's existing tests continuing to
  pass unmodified.
- Any persisted (B) metadata is demonstrated, by test, to have zero
  influence on any refresh-due decision.
- The cold-start limitation above is reflected in the implementation's
  behavior (no false-confidence display) and in at least one test asserting
  that limitation rather than asserting false certainty.
- `bot/monitor/telegram_bot.py`, `bot/_main_cycle.py`, and
  `bot/_main_positions.py` remain byte-for-byte unmodified.
- No `macro_cache` (or any other) table DDL change.
