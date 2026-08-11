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
