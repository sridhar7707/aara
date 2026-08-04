# ADR-004: Sentinel Ledger Ownership Strategy

**Status:** Deferred — Decision Framework Recorded
**Date:** 2026-08-04

## Context

`TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md` compared three
architectures for how `sentinel_engine`'s ledger relates to Trading Intelligence's
existing ledger (top-level `ledger/` + `bot/trust_ledger/`, currently the live
system of record, 8 hash-chained tables, active production history):

- **Option A** — Trading Intelligence owns the operational ledger; Sentinel
  consumes/derives from it. Low risk, no `bot/` changes, trivial rollback.
- **Option B** — Sentinel Engine becomes the canonical ledger; Trading
  Intelligence writes into it directly. Architecturally cleanest long-term, but
  requires `bot/` changes and directly touches the live write path.
- **Option C** — Dual ledger with synchronization. Risk is mechanism-dependent;
  introduces its own new risk (two ledgers both claimed authoritative can
  disagree).

That document deliberately chose no winner. This ADR does not choose one either —
it records *why* the choice is deferred, *what* stays true in the meantime, and
*what must be true* before the choice can responsibly be made.

`bot/`, `bot/trust_ledger/`, and top-level `ledger/` are live production code
under an active Phase 1A 30-day live-validation window (per project history:
started 2026-07-28) and are protected by
[ADR-002](ADR-002-bot-runtime-protection.md). `sentinel_engine/ledger/ledger.py`
today is `LedgerStore(ABC)` — an abstract `append`/`read_all` interface with **no
backend implementation**. `LedgerRepository` (concrete facade) and
`ProjectionRepository(ABC)` exist and are exercised by 82 tests, all against
in-memory fakes — never against real `trust_ledger` data.

## Decision

**Defer the Option A/B/C choice until Phase 1A validation completes.** No
implementation of any option begins from this ADR.

### Why Sentinel Engine stays ledger-contract-ready but backend-neutral

`LedgerStore` is deliberately an abstract interface with zero backend today. This
is not an oversight — it's what keeps all three options open at zero sunk cost:

- The interface (`append`/`read_all`) doesn't presuppose whether the eventual
  backend is a derived/consumer-side store (Option A), a canonical store
  (Option B), or a synced store (Option C) — any of the three can implement the
  same `LedgerStore` contract.
- No backend code exists yet that would need to be discarded or reworked if a
  different option is eventually chosen. Deferring the choice costs nothing
  architecturally, because nothing has been built that commits to one direction.
- `DecisionService`, `LedgerRepository`, and `decision_adapter` are already
  storage-independent by construction (ADR-001), so they don't need to change
  regardless of which option is eventually picked.

### ADR-002 protections are preserved, unchanged

This ADR does not touch, weaken, or supersede ADR-002. `bot/`, `dashboard/`,
`scheduler/`, `.github/workflows/`, `database/`, and top-level `ledger/` remain
frozen exactly as ADR-002 states. Whichever option is eventually chosen, if it
requires a `bot/` change (Option B does; Option C does if synchronous), that
change still requires its own dedicated ADR meeting ADR-002's "Lifting This
Protection" checklist — this ADR does not shortcut that requirement.

## Future Decision Criteria

The Option A/B/C choice should not be made until **all** of the following hold:

1. **Phase 1A's 30-day live-validation window has completed**, and its results
   (win rate, trade count, data-integrity record) have been reviewed. Choosing a
   ledger architecture — especially Option B or a synchronous Option C — before
   this window closes would mean touching the live write path during the exact
   measurement period it's protecting.
2. **The open questions in `TRADING_INTELLIGENCE_EVENT_MODEL.md` and
   `TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md` are resolved** — in particular,
   `DECISION_EXECUTED` payload fields, `evidence_reference` construction, and
   whether constitution/data-quality/capital-ledger events get promoted to new
   `EventType` values. The amount of translation work implied by each option
   differs depending on these answers.
3. **A tested dry run exists against real `trust_ledger` data**, not just the
   current 82 tests (which all run against in-memory fakes). Whichever option is
   chosen, nothing about `sentinel_engine`'s adapters has ever been exercised
   against the shapes real `decision_events`/`risk_evaluation_events`/etc. rows
   actually take in production.
4. **A concrete rollback plan is written for the specific option chosen**,
   before implementation starts — not reconstructed after, per ADR-002's existing
   principle for any protected-path change.
5. **Whether/when a second product (Wealth Intelligence or other) will actually
   consume the same ledger is clearer than it is today.** Option A/C are
   incremental and cheap to walk back if only one product ever materializes;
   Option B's higher migration cost is easier to justify if a second product's
   arrival is imminent and known, not speculative.
6. **Whichever option is chosen gets its own ADR** (or an amendment to this one)
   naming it explicitly, before any implementation work begins.

## Consequences

- No `sentinel_engine/ledger/` backend implementation should be started until
  this ADR is superseded or amended with a chosen option.
- `sentinel_engine/ledger/ledger.py`'s `LedgerStore` stays abstract, with no
  concrete implementation, in the interim.
- Future sessions/agents resuming this decision should start from "Future
  Decision Criteria" above, not re-derive the comparison from scratch — the
  underlying tradeoffs are recorded in
  `TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md`.
- This ADR itself does not require review on a fixed schedule, but should be
  revisited when Phase 1A's validation window closes, per criterion 1.
