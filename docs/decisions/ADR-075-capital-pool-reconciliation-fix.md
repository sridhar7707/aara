# ADR-075: ADR-002 Exception — Capital-Pool Reconciliation Fix

**Status:** Accepted
**Date Proposed:** 2026-11-04
**Date Accepted:** 2026-11-04
**Decision Type:** Narrow ADR-002 exception, prospective. Authorizes a named bug fix to `bot/capital/pool.py`'s drift against the real broker account, which is currently suppressing real trading.

---

## Context

Investigated this session: the bot has not executed a new BUY in ~8 weeks despite finding qualifying candidates almost every day. Live production logs (`gh run view`, runs from 2026-10-27 through 2026-11-02) show the same rejection, daily:

> `Position size $7,933.08 exceeds max $7,087.73 (sized from managed_capital=$35,438.65).`

`managed_capital` is `capital_pools.tradeable_cash` (`bot/capital/pool.py`), read via `ctx.pool.tradeable_cash` at `bot/_main_cycle.py:320` and enforced as a hard cap in `bot/risk/risk_manager.py:268-276` (`max_notional = sizing_base * MAX_POSITION_PCT`). The real, current Alpaca cash balance (pulled fresh from the production HuggingFace snapshot, 2026-11-04) is **$51,189.93** — 45% higher than the $35,438.65 the risk gate is sizing against. Every qualifying candidate since at least 10/27 has been rejected purely because of this stale figure, not because of any real risk or strategy judgment.

**Root cause, found by reading `_reconcile_positions` (`bot/_main_positions.py:177-226`):** this function runs every cycle and correctly reconciles `position_state` against Alpaca's real holdings — when it finds a position in the DB that Alpaca no longer holds, it logs a `SELL_RECONCILE` trade (`log_trade(...)` + `_journal_close(...)`) and deletes the stale `position_state` row. **It never calls `_pool_sell()`.** Every other sell path in this codebase (`_main_positions.py:247,327,410`, and the buy path's `_pool_buy` at `_main_cycle.py:411`) does call the matching pool-ledger function. `trades.db` has 10 `SELL_RECONCILE` rows historically — each one closed a real position and should have credited real cash back into `capital_pools.available_cash`, and none of them did. That is the specific, confirmed leak that produced the $15.8K drift now blocking trading.

A second, independent audit of this session (general codebase review) separately confirmed there is **no reconciliation job of any kind** for `capital_pools` against the real broker account — unlike `position_state`, which self-heals every cycle, `capital_pools` has no analogous safety net, so any future silent failure in the buy/sell pool-update calls (`_pool_buy`/`_pool_sell`, neither wrapped in its own try/except at any call site) would reproduce this exact failure mode with no alert.

Separately: `bot/_main_runner.py:_do_clean_db()` (the documented full-reset flow) wipes `trades`, `position_state`, `risk_state`, `portfolio_snapshots`, `signal_log`, `screener_log` — but not `capital_pools`/`capital_ledger`. A reset account would size its first post-reset trades against the stale pre-reset pool balance.

---

## Decision

Authorize the following three named changes, and no others, to be developed and validated in an isolated worktree before any merge to `main`.

## 1. Named Scope

**Modified files (protected, under `bot/`):**
- `bot/capital/pool.py` — add `reconcile_pool(conn, pool_id, real_available_cash, real_invested_cost_basis, tolerance=1.0) -> bool`: compares the pool's current `available_cash`/`invested_amount` against the two real values passed in; if either differs by more than `tolerance`, updates both fields, appends one `capital_ledger` event (`event_type="reconcile"`, `amount` = the cash delta, `notes` stating both deltas) via the existing `append_ledger()`, and returns `True`. Returns `False` (no write, no ledger entry) when both are already within tolerance — this keeps the ledger free of noise on cycles where nothing has drifted, which is the common case once the leak below is fixed.
- `bot/_main_positions.py` — `_reconcile_positions()`'s `SELL_RECONCILE` branch (around line 211-214): add the same `_pool_sell(con, pool.id, cost_basis, sell_notional, symbol=sym)` call every other sell path already makes, using the `notional`/`entry_price`/`net_shares` values already computed in that branch. Requires threading a `pool: CapitalPool | None` parameter into `_reconcile_positions()`'s signature (mirroring how `_handle_exits` already receives `pool=`).
- `bot/main.py` — two call-site changes: (a) pass the now-required `pool=` argument to `_reconcile_positions()` at line 266 (the pool must be loaded before this call, so `_load_pool()`'s call at line 279 moves earlier, to immediately after `positions`/`portfolio_value` are known and before `_reconcile_positions()`); (b) immediately after loading the pool, call `reconcile_pool(con, _capital_pool.id, real_available_cash, real_invested_cost_basis)` — where `real_invested_cost_basis` is computed as `sum(entry_price * shares for each row in position_state)` (the same table `_reconcile_positions` just finished truing up against Alpaca, so this is reality, not a second independent read of the broker). If `reconcile_pool()` returns `True`, re-load the pool (`_capital_pool = _load_pool(con)`) so the corrected values are what sizing actually uses for the rest of the cycle.
- `bot/_main_runner.py` — `_do_clean_db()`'s `tables` tuple: add `"capital_pools"` and `"capital_ledger"`.

**Explicitly not touched:**
- `bot/risk/risk_manager.py` — `approve_buy()`'s sizing logic itself is correct given accurate inputs; this ADR fixes the input's accuracy, not the sizing formula.
- `update_on_buy`/`update_on_sell`/`deposit`/`withdraw` in `bot/capital/pool.py` — unchanged; `reconcile_pool()` is a new, separate function alongside them.
- No change to `MAX_POSITION_PCT`, `KELLY_FRACTION_MAX`, or any other risk/sizing constant.

## 2. Reconciliation Rule (stated precisely)

- **`available_cash`** reconciles against the real Alpaca cash balance (`real_available_cash`, already fetched once per cycle in `bot/main.py` via `client.get_account()` — no new API call).
- **`invested_amount`** reconciles against the sum of `position_state.entry_price * position_state.shares` across all open positions — i.e., real cost basis, from the table `_reconcile_positions()` just finished truing up against Alpaca in the same cycle. Deliberately **not** reconciled against mark-to-market portfolio value: `capital_pools.invested_amount` has always tracked cost basis (see `update_on_buy`/`update_on_sell`'s own arithmetic), and reconciling it against a fluctuating market value would conflate two different things and make `tolerance`-based noise suppression impossible (the figure would differ by a few dollars almost every cycle purely from price movement).
- **`allocated_amount`, `reserve`, `realized_profit`, `profit_withdrawn` are never touched by reconciliation** — these aren't derivable from a point-in-time broker snapshot and touching them risks corrupting P&L/withdrawal history. This ADR fixes sizing-input accuracy only.
- `tolerance=1.0` (one dollar) — small drift from float rounding doesn't need a ledger entry; the kind of drift this ADR is fixing is four orders of magnitude larger.

## 3. Risk Tier and Rationale

**High.** This changes a live, currently-active risk gate's input, on the next real trading cycle after merge. Mitigated by:

- The change is strictly corrective: it makes an already-intended check (`risk.approve_buy()`'s managed-capital cap) size against reality instead of an 8-week-stale figure. It does not loosen, remove, or bypass the cap itself.
- `reconcile_pool()` is a new, isolated function — it does not modify the logic of `update_on_buy`/`update_on_sell`, so the existing, already-tested buy/sell pool-accounting paths are unchanged.
- The one-time correction (available_cash moving from $35,438.65 toward the real ~$51,189.93) will change `managed_capital` significantly on the first post-fix cycle — this is the explicit, intended effect, not a side effect: it's what unblocks trading. Stated here so it isn't a surprise.
- Development and testing happen in an isolated worktree per ADR-002 item 2, not on `main`.

## 4. Isolated Branch/Worktree Requirement

Required, per the process established this session (ADR-073/074). No commit touching the protected files in §1 lands on `main` until test results (§6) have been reviewed.

## 5. Workflow-Reference Analysis (ADR-002 item 3)

No `.github/workflows/*.yml` file is touched. `trade.yml` invokes `bot/main.py` by name; no reference to `pool.py`'s internals.

## 6. Test Requirements and Validation Performed Before Any Merge to `main`

1. New unit tests in `tests/test_pool.py` (already exists, covers `bot/capital/pool.py`) for `reconcile_pool()`: (a) no drift beyond tolerance → no write, no ledger entry, returns `False`; (b) cash drift beyond tolerance → `available_cash` updated, one `capital_ledger` "reconcile" row appended, returns `True`; (c) invested-amount drift beyond tolerance → same for `invested_amount`; (d) both drift → single ledger entry covering both, not two.
2. New/updated test for `_reconcile_positions()`'s `SELL_RECONCILE` branch: with a `pool` argument supplied, confirm `_pool_sell()` is called with the correct `cost_basis`/`sell_notional`/`symbol` (mock or real in-memory pool) when a stale position is closed.
3. Updated test for `_do_clean_db()`: confirm `capital_pools`/`capital_ledger` row counts go to zero after a clean, alongside the existing six tables.
4. All existing `tests/test_pool.py` and `tests/test__main_positions.py` tests re-confirmed green, unchanged.
5. Full `tests/` suite — zero regressions versus the pre-change baseline.
6. Manual trace: with a synthetic pool pre-set to a stale `available_cash` and a `position_state`/Alpaca-mock pair representing a closed position, run one simulated cycle and confirm `capital_pools.available_cash` ends up within `tolerance` of the real value, and that exactly one `capital_ledger` reconcile row was appended (not one per cycle going forward, once in sync).
7. `git diff --name-only` against the base commit, confirmed to match §1 exactly.

## 7. CLI and Scheduler/HTTP Entry-Point Confirmation

**CLI path** (`trade.yml` → `bot/main.py --mode paper --loop`): directly affected, intentionally — `reconcile_pool()` runs every cycle starting with the first run after merge, and will correct the current ~$15.8K drift on that very first run. **Scheduler/HTTP path**: no separate entry point touches `pool.py` or `_reconcile_positions()`; unaffected beyond the CLI path.

## 8. Rollback Plan

- **If not yet merged:** discard the worktree. No state on `main` to unwind.
- **If merged and the reconciliation itself looks wrong (e.g., corrects to an implausible value):** revert the commit. `capital_pools` would remain at whatever value the last reconciliation left it at — not ideal, but no worse than today's silently-stale state, and the next `scripts/`-level manual correction (a direct `UPDATE capital_pools...`) remains available as a manual override if ever needed. This ADR does not add or require a new rollback mechanism beyond the standard git revert, since the fix is additive (a new function plus three call sites) rather than a rewrite of existing logic.

---

## Constraints

**Allowed:** Exactly the changes named in §1, developed in an isolated worktree.

**Forbidden:**
- Any change to `MAX_POSITION_PCT`, `KELLY_FRACTION_MAX`, or any other risk/sizing constant in `config.py`.
- Any change to `update_on_buy`/`update_on_sell`/`deposit`/`withdraw`'s existing logic.
- Reconciling `allocated_amount`, `reserve`, `realized_profit`, or `profit_withdrawn`.
- Any `.github/workflows/*.yml` change.
- A full transactional rewrite of the trade-write path (wrapping `log_trade` + journal + pool-update + position-state in one DB transaction) — a real, separately-identified hardening opportunity from this session's broader audit, but a materially larger, riskier change deserving its own ADR, not bundled into this urgent, narrow fix.

---

## Explicitly Not Established By This ADR

- Does not address the broader "trade-write path isn't transactional" finding (silent future failures in `_pool_buy`/`_pool_sell` itself) beyond adding this reconciliation safety net, which mitigates but doesn't eliminate that risk class. A future ADR may take this on directly.
- Does not retroactively correct `realized_profit` for any mis-tracking that may have occurred during the drift window — reconciliation only corrects `available_cash`/`invested_amount` going forward from the fix.
- Does not change the `MAX_POSITION_PCT`-based sizing cap's design — only fixes the accuracy of its input.

---

## Acceptance

*(Per ADR-058 D4, this document is a proposal and carries no authority until it is landed under ADR-058 D2, by explicit act of the Architecture Owner.)*

**Status:** Accepted
**Date Accepted:** 2026-11-04
**Accepted By:** ksri77 (Architecture Owner) — explicit acceptance given in-session

---

## Status Log

- **2026-11-04 — Proposed.** Found while investigating a direct user question ("why is ~50% of capital sitting uninvested"). Root-caused via live production log evidence (`gh run view`, 5+ separate days all showing the identical rejection) plus two independent code-reading passes (this session's own trace of `_reconcile_positions`, and a separately-launched audit agent's finding that no `capital_pools` reconciliation job exists at all). High confidence, high urgency — this has very likely been suppressing real trading for approximately 8 weeks.
- **2026-11-04 — Accepted.** Accepted by ksri77 (Architecture Owner). Implementation to proceed in an isolated worktree per §4.
