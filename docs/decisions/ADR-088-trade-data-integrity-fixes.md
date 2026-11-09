# ADR-088: Trade-Data Integrity Fixes and Disclosure

**Status:** Accepted by ksri77 on 2026-11-08. Implemented: snapshot guard (`bot/_main_prep.py`, `write_heartbeat_if_consistent`, tests in `tests/test_snapshot_guard.py`). Journal item revised below: no code change needed.
**Decision Type:** Narrow ADR-002 exception, prospective, for three defects found in production data on 2026-11-08. Does not change any governed trading value.
**Related:** ADR-002 (frozen paths), ADR-071 (single write path), ADR-046 (derived views only), ADR-074 (degraded LSTM weight transfer).

## 1. Findings (from read-only checks)

**A. Portfolio snapshot glitch, 2026-07-07.** Ten snapshots between 14:33 and 16:16 UTC record a portfolio value of 35,479, equal to cash, with zero open positions. Surrounding values are near 100,000. The writer (`bot/_main_prep.py` line 71) records the first `get_positions()` read without re-verification, even though `bot/_main_reconcile.py` already re-verifies an empty read that conflicts with the database. The run log for that day has expired, so the cause is a hypothesis: a transient empty positions read. Effect: a raw drawdown of −65%, against −9.5% on clean data.

**B. Trade journal coverage.** 12 of 17 closing sells have no `trade_journal` row. The gap covers July exits, and the BUYs are present. The journal writer does not cover all exit paths.

**C. Degraded LSTM outputs in recorded decisions.** 6,338 decision rows from 2026-07-30 to 2026-10-22 carry an LSTM output flagged `is_degraded: true`, and every one of them has a BUY or SELL LSTM signal. The fallback that neutralises a degraded model was committed on 2026-10-22 (`b1b69a0`, ADR-074). So a degraded model was producing recorded signals for about 12 weeks.

## 2. Decision (proposed)

1. **Snapshot guard.** Before writing a snapshot, re-verify an empty positions read against the database, using the existing reconcile re-verification. Do not write a snapshot that contradicts the database without a logged reason.
2. **Journal coverage: no code change.** Revised after checking the code. Every exit path (`_main_positions.py`, sell, reconcile and gap-down) already calls `close_entry`, which always writes a row. The journal's first write was 2026-08-21, and the 12 sells with no journal row all happened before that date. The gap is historical. It is disclosed, and no backfill is made without a separate decision, because the journal is an analysis table, not the ledger.
3. **Degraded period: disclose, do not rewrite.** The ledger is append-only (ADR-046). Affected decisions are annotated in analysis documents as "degraded LSTM output recorded". No ledger row is changed.
4. **Tests.** Each fix has a test that reproduces the defect with a fake positions read and a fake journal write.

## 3. Consequences

- Performance figures for 2026-07-30 to 2026-10-22 carry a caveat. Any scorecard must state it.
- The snapshot and journal fixes change production writes, so they need a shadow comparison before they replace the current writer.

## 4. Acceptance

Owner: __________________ Date: __________

## 5. Revision, 2026-11-08 (after quant review)

The snapshot skip described in section 2.1 was **rejected** and replaced:

- The writer now always records the real account value, so no point is dropped. The skip removed the deepest-drawdown readings, which biased max drawdown and Sharpe. The quant review (approve with changes) found this, and that the skip ran after reconcile had already cleared the database, so it did not prevent the phantom SELL_RECONCILE rows.
- The open-position count comes from the live read. If that read is empty while the database holds open positions, the database count is written and a warning is logged.
- The duplicate broker re-verify is removed, because the cycle already re-verifies an empty read earlier.

**Still open:** the phantom SELL_RECONCILE rows. Fixing them needs the verified-positions decision to run before `_reconcile_positions` in `bot/main.py`, which is a frozen path. That change is drafted as a separate ADR item and is not implemented.

## 6. Correction, 2026-11-08 (point 1 of the quant review)

Section 5 said reconcile runs before the guard and so cannot be protected. That is only partly right. In `bot/main.py`, `positions` comes from `_fetch_positions_for_reconcile` (line 272), which re-verifies an empty read, and `_reconcile_positions` is called with that same verified read (line 283). Reconcile therefore does not act on an unverified empty read.

The residual risk is a broker outage that lasts longer than the re-verify window (three attempts, about 8 seconds in total). That window is a trading decision, not a code defect, and is now proposed in ADR-091.

## 7. Sanity baseline fix, 2026-11-08 (quant review, finding 1)

The revised writer recorded the account value on every cycle, including sanity-blocked cycles. The sanity baseline was the latest snapshot, so a blocked glitch reading became the next cycle's baseline. Reconcile could then unblock on the following cycle. Fixed:

- The baseline is a **trusted value** stored in `risk_state` (`last_trusted_portfolio_value`). It is saved only on cycles that pass the sanity check. A blocked reading is never saved.
- `sanity_check()` in `bot/_main_prep.py` implements this. `bot/main.py` calls it. Tests: `tests/test_sanity_baseline.py` (6 tests, including the reviewer's 10,000 then 4,000 scenario, stays blocked on every following cycle).
- Snapshots still record every cycle, so the drawdown series is unchanged by this fix.

### Open review findings (not fixed here)

- **Finding 2:** when reconcile is skipped by the sanity block and positions are empty, the heartbeat writes the database count without flagging it as unverified. Needs an error-level log with the flag. **Open.**
- **Finding 3:** early returns in `bot/main.py` (account value zero, or a failed account read) write no snapshot, so outage cycles are missing from the drawdown series. Needs a gap count stated next to any drawdown figure. **Open.**
- **Finding 4:** the dashboard Sharpe (`bot/monitor/_dashboard_performance.py`) annualises with a fixed cadence, but snapshots are now written per cycle. The Sharpe needs daily resampling. This is a change to reported metrics, so it needs the owner's decision. **Open.**
- **Finding 5:** the weekly baseline (`bot/_main_runner.py`) and the first-snapshot fallback for `reinvest_profits_only` (`bot/capital/pool.py`) read raw snapshots, so they should read the trusted value. **Open.**

## 8. Decisions and implementation, 2026-11-09 (financial expert, on the owner's delegation)

- **Weekly P&L baseline and capital first-snapshot fallback read trusted anchors.** `record_trusted_anchors()` (in `bot/_main_prep.py`) records `first_trusted_value` and `week_trusted_start:<ISO week>` once, from trusted readings only. `bot/_main_runner.py` and `bot/capital/pool.py` read these first and fall back to the old snapshot query only if an anchor is missing.
- **Dashboard Sharpe and Sortino are daily-return figures.** `analytics/perf_metrics.py` resamples to one value per day and annualises with sqrt(252). The old per-cycle figure is superseded and is not shown as current. Tests: `tests/test_perf_metrics.py`.
- **Journal gap accepted and disclosed; no backfill.** See the decisions record in the private folder.
- **Findings 2 and 3 remain open** (the unflagged database-count fallback and the outage gap in the snapshot series). They are recorded for the next change.

## 9. Correction and fixes after the second quant review, 2026-11-09

**Corrections to section 8:**
- The claim that "a blocked reading never becomes the baseline" holds for the sanity check and the trusted anchors. It does **not** hold for the automatic daily and weekly starts: `prepare_cycle_context` calls `reset_daily(real_portfolio_value)` on every cycle, including sanity-blocked ones. This predates the revision and is **open**.
- The capital pool no longer reads `first_trusted_value`. Reading it would have moved the reinvest base from the earliest snapshot to the deploy-day equity, which can shrink tradeable capital toward zero when reinvest is on. The pool now uses the earliest snapshot again, as before.

**Fixed in this round:**
- Sortino divides by all observations (target-downside form), not only the negative ones.
- The Sharpe and Sortino gate counts daily returns (at least 20), not per-cycle rows.
- Timestamps that are None are filtered before sorting.

**Still open:**
- Automatic daily and weekly starts accept blocked readings (see the correction above). Fix: skip the start-value writes in `reset_daily` when the sanity check blocks, and restore the trusted value to the week start.
- The first trusted reading is not cross-checked. Fix: require two agreeing passing readings (within about 1%) before the first anchor is written.
- The weekly anchor is the first trusted reading of the week, so a late first reading hides Monday's move. Fix: use the last trusted value of the prior ISO week as the week start.
- The models scorecard computes its own daily Sharpe on trades only. Fix: route it through `analytics/perf_metrics.py`.
