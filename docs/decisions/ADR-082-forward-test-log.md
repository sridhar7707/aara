# ADR-082: Forward-Test Log and 12-Month Review

**Status:** Accepted by ksri77 on 2026-11-07 ("ok finish the forward-test log and 12 months review point"). Implementation follows this text. Review date fixed below.
**Decision Type:** Pre-registration of an out-of-sample forward test. Scores and rules are fixed here. Changing them later requires a new ADR, and the review is only valid if the rules are unchanged.

## Purpose
Obtain an unbiased test of two candidate signals on data that did not exist when the rules were written. Historical tests on free data are survivorship-biased, because about half of removed S&P 500 members cannot be priced. A forward log avoids that bias.

## Pre-registered rules

1. **Universe.** S&P 500 constituents as listed on Wikipedia's "List of S&P 500 companies" on each snapshot date. The list is saved with the date, so membership is point-in-time going forward.
2. **Score A (cross-sectional).** 12-1 month momentum: `close(t-21) / close(t-252) - 1`, computed from daily closes, for each member on each trading day.
3. **Target.** 21-trading-day forward return minus SPY's, over the same window.
4. **Score B (time-series overlay, ETFs).** Sector and index ETFs XLC, XLE, XLF, XLI, XLK, XLP, XLV, XLY, GLD, TLT, QQQ, IWM. Signal on each day: close above its 210-trading-day moving average (proxy for the 10-month average). Evaluated by the ADR-081 risk criteria against SPY.
5. **Evaluation for Score A.** `scripts/validate_signal.py` as pre-registered in ADR-081: daily rank IC with Newey-West t (lag 20), decile spread net of 20 bp, verdict PASS only if every criterion holds. Folds: the review is one fold of the whole window, plus a fold per quarter for the consistency check.
6. **Snapshot frequency.** Daily, at the close, each trading day. Only the score is written at snapshot time. Outcomes are computed later, when 21 trading days have passed. Rows are never edited after they are written.

## Review date
**2027-11-07**, twelve months after the first snapshot. Only snapshots taken on or before the review date are used. The review is written up under this ADR as an addendum. A PASS or KILL verdict follows the criteria above and is not revised afterwards.

## What counts as a result
- Score A PASS: meets all criteria in `validate_signal.verdict`. Reopens the discussion of model-driven entries, which still needs a new ADR.
- Score A KILL: recorded as the outcome. The forward signal is abandoned unless a new ADR with a new pre-registration replaces it.
- Score B: PASS or KILL under the risk criteria. A PASS supports only use as a risk overlay, never as alpha, and still requires its own ADR.

## Constraints
- The log is append-only. Snapshots are not corrected.
- No rule is changed during the window. A change requires a new ADR and restarts the clock.
- Model-driven entries stay suspended (ADR-081 step 1) throughout. This ADR does not re-enable them.
- No real capital is involved in this test.

## Implementation record (2026-11-07)
- First snapshot: **2026-11-06** (the last trading day before this record; 7 November 2026 is a Saturday). Logged 513 prices, 500 momentum scores and 12 trend signals.
- The review date stays **2027-11-07**, as fixed above. That is one day more than twelve months from the first snapshot. The extra day is deliberate: it lets the review include the full twelve months of closes.
- Snapshots must run on every trading day. A missed day is not lost: membership can be rebuilt from the change table, and the score is a function of closes, so a missed day can be backfilled under the same rules and must be recorded as a backfill.
- A snapshot is refused if the price bar is stale, if the day is a weekend, if fewer than 95% of members have prices, or if the date is already logged. A refused day leaves no files.
