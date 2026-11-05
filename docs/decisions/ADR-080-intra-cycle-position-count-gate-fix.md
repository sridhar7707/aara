# ADR-080: ADR-002 Exception — Intra-Cycle Position-Count and Sector Gate Fix

**Status:** Accepted
**Date Proposed:** 2026-11-05
**Date Accepted:** 2026-11-05
**Decision Type:** Narrow ADR-002 exception, prospective. Fixes a verified gap where risk gates read a per-cycle position snapshot that is never refreshed after a buy fills, so several buys in one cycle can together exceed MAX_POSITIONS and per-sector limits.

---

## Context

`bot/main.py` fetches the open-position dict once per trading cycle (`positions = _fetch_positions_for_reconcile(...)`, line ~266) and passes that same dict into every per-symbol `EntryContext` for the whole loop (line ~302 onward, `positions=positions` at ~411). No code path inserts a newly-filled buy into that dict. Confirmed by reading the code: no `positions[...] =`, `positions.update`, or equivalent mutation exists in the cycle or its helpers.

The gates that read this dict are `RiskManager.approve_buy`'s `len(open_positions) >= MAX_POSITIONS` check, `RiskManager.sector_check` (`bot/risk/risk_manager.py`, per-sector limit `MAX_SECTOR_POSITIONS`), the sector-exposure cap in `bot/_main_cycle.py` (~292–305), and the correlation gate in `bot/_main_positions.py` (~83–115).

Concrete failure: with 7 positions open and `MAX_POSITIONS=8`, three correlated same-sector symbols that all generate BUY signals in one cycle each see "7 open" and "0 held in sector" (or one held), and can all pass. The cycle can end with 10 positions, exceeding the position cap, the per-sector cap, and the sector-exposure cap at once. Correlated names tend to break out together, which is exactly when these limits matter most.

Only aggregate cash is tracked cumulatively across the loop (`_remaining_tradeable`). Position count, sector count, and correlation state are not.

No test currently simulates a multi-symbol cycle, so this path has no regression coverage.

---

## Decision

Authorize the following named changes, and no others, to be developed and validated in an isolated worktree before any merge to `main`.

## 1. Named Scope

**Modified file (protected — bot/main.py):**
- In the per-symbol loop, after a BUY is submitted and its fill is recorded, add the new position to the local `positions` dict so every later gate in the same cycle counts it. Insert a lightweight placeholder with the symbol and the notional value, not a live broker object, so `sector_check`, the sector-exposure cap, and the correlation gate see it through the same interface they already use.
- Also count symbols with an open buy order (`buy_order_syms`, already tracked in the loop) toward the position cap, so a submitted-but-unfilled order cannot be overlooked by the next gate.

**Modified file (protected — bot/risk/risk_manager.py), only if required:**
- No logic change is expected. If the placeholder type needs an attribute the gates currently read, add that read-only attribute, and nothing else.

**Explicitly not touched:**
- Gate thresholds (`MAX_POSITIONS`, `MAX_SECTOR_POSITIONS`, `MAX_SECTOR_EXPOSURE_PCT`, correlation threshold) — values unchanged.
- The cycle-start reconciliation (`_fetch_positions_for_reconcile`, `_reconcile_positions`) and its ADR-075 capital-pool logic.
- Exit and trailing-stop logic (`_handle_exits`, `check_trailing_stop`).
- Any `.github/workflows/*.yml` file, or any live entry point.

## 2. Risk Tier and Rationale

**Medium.** This changes what the entry gates see within a live cycle, so it can change which real BUY orders are placed. The change is strictly restrictive (it adds positions to the count, so gates block more, never fewer), which limits the downside. The main risk is a placeholder that makes a gate raise an exception or double-count a symbol that later reconciles. §5 names tests for both.

## 3. Isolated Branch/Worktree Requirement

Required, consistent with protected-path handling this session.

## 4. Workflow-Reference Analysis (ADR-002 item 3)

No `.github/workflows/*.yml` file is touched. The change runs inside the existing `trade.yml` → `bot/main.py` cycle and needs no new entry point.

## 5. Test Requirements and Validation Performed Before Any Merge to `main`

1. **Reproduction test (written first, must fail on current code):** a simulated multi-symbol cycle with 7 open positions and three same-sector BUY candidates, asserting that at most `MAX_SECTOR_POSITIONS` of them can be approved in total and that total positions never exceed `MAX_POSITIONS`. This test must fail on `main` before the fix and pass after.
2. Same test with one correlated pair, asserting the correlation gate sees the first buy when evaluating the second.
3. A test that a submitted-but-unfilled buy order counts toward the position cap.
4. A test that the placeholder is not double-counted when the real position appears in the next cycle's fetch.
5. Existing `tests/test_main.py` correlation, sector, and position tests re-run unchanged and green.
6. Full `tests/` suite: zero regressions.
7. `git diff --name-only` against the base commit, confirmed to match §1 exactly.

## 6. CLI and Scheduler/HTTP Entry-Point Confirmation

Live path: `trade.yml` → `bot/main.py --mode paper --loop`. The change only affects gate inputs within the existing per-symbol loop, so it applies to the CLI path and to any caller of `bot.main.run()`. No new entry point.

## 7. Rollback Plan

- **If not yet merged:** discard the worktree.
- **If merged and something looks wrong:** revert the commit. Reverting restores the stale-snapshot behavior, which is the current state, so the rollback is safe.

---

## Constraints

**Allowed:** Exactly the changes named in §1, in an isolated worktree, with the reproduction test (§5.1) written and failing before any fix.

**Forbidden:**
- Changing any gate threshold or limit constant.
- Changing exit logic, trailing stops, or ADR-075 capital-pool reconciliation.
- Making any gate less restrictive.
- Any `.github/workflows/*.yml` change.

---

## Explicitly Not Established By This ADR

- Does not decide whether the per-sector and correlation limits are themselves the right values. That is a separate tuning question.
- Does not address the broader question of whether an intra-cycle order should be fetched live from the broker before each gate. That is a larger architectural choice, deferred.

---

## Acceptance

*(Per ADR-058 D4, this document is a proposal and carries no authority until it is landed under ADR-058 D2, by explicit act of the Architecture Owner.)*

**Status:** Accepted
**Date Accepted:** 2026-11-05
**Accepted By:** ksri77

---

## Status Log

- **2026-11-05 — Proposed.** Found by a fresh `bot/` audit and verified by reading `bot/main.py`: the position snapshot is fetched once per cycle and never refreshed after buys fill.
- **2026-11-05 — Accepted by ksri77.** Implementation to follow in an isolated worktree per §3, starting with the reproduction test in §5.1 (must fail on current code).

---

## Amendment A1 (Proposed — not in force until accepted by the Architecture Owner)

**Status:** Proposed. Under ADR-058 D4 this amendment carries no authority until landed under ADR-058 D2 by the Architecture Owner.

**Why:** Two findings from the implementation worktree (`intra-cycle-gate`):

1. The fill is recorded in `_handle_entry` (`bot/_main_cycle.py`), which §1 does not name. The §5.1 reproduction calls `_handle_entry` directly, so it can only pass if that file is in scope. The fix already committed (`330ca18`) lives in `bot/main.py` and is verified by the full suite, but the repro still xfails for this reason.
2. §1 bullet 2 (count submitted-but-unfilled buys toward the cap) cannot be implemented by adding pending symbols to the `positions` dict. `_handle_exits` reads that same dict, so a pending buy would be evaluated for stops and exits with no real position behind it. The clean design is a separate input to the cap check.

**Amended scope (additions to §1 only; §2–§7 unchanged):**

- **Add** `bot/_main_cycle.py`: `_handle_entry` may register a fill in `ctx.positions`. Limited to that one assignment after a recorded fill. No gate logic changes.
- **Add** `bot/risk/risk_manager.py` `approve_buy`: an optional keyword `pending_count: int = 0` that is added to `len(open_positions)` in the position-cap check. Default `0` keeps current behaviour. `bot/main.py` passes the count of symbols in `buy_order_syms` not already in `positions`.
- Pending symbols are **never** inserted into `positions`, so `_handle_exits` is unaffected.

**Explicitly still not touched:** gate thresholds, exit and trailing-stop logic, ADR-075 reconciliation, workflows.

**Acceptance criteria:** §5.1 repro must pass with the marker removed; §5.2 (correlated pair) and a new §5.3 test (pending order counts toward the cap, via `pending_count`) must pass; §5.4 no-double-count must pass; full suite green.

**Rollback:** revert the amendment's commit; the `pending_count` default of `0` makes that safe.
