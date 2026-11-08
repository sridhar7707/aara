# ADR-086: Forward-Test Fold Structure, Measurement and Review Verdicts

**Status:** Accepted by ksri77 on 2026-11-08 (wording amended after risk review, before any recorded rebalance) ("ok do them"). Pre-registration: this text is fixed before any forward result exists. Changes after the first recorded rebalance require a new ADR.
**Decision Type:** Pre-registration of how the ETF overlay's forward test is measured, split and judged. Amends ADR-082 (review date and folds) and ADR-081 (risk criterion applied to the forward window). Does not change the trading rule or any limit.

## Context
- The forward test starts with the first real month-end rebalance and reviews on 2027-11-07 (ADR-082).
- The rule rebalances monthly, so the window holds about 12 decisions.
- The in-sample test used five folds of several years each. Five folds of one year is not possible, and twelve monthly observations cannot support a significance test on returns.
- Before this ADR the runner recorded sleeve value as zero on every run, so the drawdown comparison could not be computed.

## Decision 1: measurement (what is recorded, and when)
1. **Sleeve value at each run that reaches the account read.** Sum of the overlay positions' market values, read from the account. An unreadable account is recorded as `unreadable` with an empty sleeve value, never as zero. Refusals that happen before the account read (the approval flag, the halt file, the stock-bot position check, and failures reading the price data) produce an exit code and a stderr message only. They write no row. A run that crashes before the account read counts as a logged non-run.
2. **Fills.** Each submitted order's submitted time, filled time, filled quantity and filled average price. Rows are appended on every lookup until the order reaches a terminal status, so several rows can exist per order. The latest terminal row per `order_id` is authoritative.
3. **Execution timing.** Orders are placed after the 16:30 New York cut-off and fill at the next open. The realised fill is compared with the month-end close the rule used. The gap is reported for every rebalance.
4. **Basis for drawdown.** The month-end sleeve value is the pre-trade `sleeve_value` on that month's execute row (`started` or `executed`), compared with the month-end SPY close. The same points are used for both, so the comparison is like for like. Intra-month drawdowns are not measured, and this is stated as a limitation. Rows written before this ADR carry `sleeve_value` 0 and are excluded from the forward window.
5. **Daily sleeve value is not part of this ADR.** It would need the scheduled job to hold account credentials, which needs a security review first. It is listed as a future item.

## Decision 2: folds
- **Four calendar quarters** of the forward window: Q1 (Nov–Jan), Q2 (Feb–Apr), Q3 (May–Jul), Q4 (Aug–Oct). Each contains three rebalances.
- The first quarter starts with the first executed rebalance. If the first execution is later than the planned start, the window is shortened and the review date does not move.

## Decision 3: verdicts
A review is one of three outcomes. The outcome is decided by these rules only.

- **INCONCLUSIVE** if fewer than 10 of the 12 planned rebalances were executed, or if sleeve values are missing for more than one run. An inconclusive review is not a pass.
- **KILL** if any risk criterion fails (below).
- **PASS** only if every risk criterion and every process criterion holds.

**Risk criteria (from ADR-081, applied to the forward window):**
1. Full-window maximum drawdown of the sleeve no worse than 60% of SPY's, on the month-end basis.
2. Full-window annualised Sharpe at least SPY's, on the month-end basis.
3. In at least three of the four quarters, the sleeve's maximum drawdown within that quarter is smaller than SPY's over the same quarter.

**Process criteria:**
4. Every execute run that reaches the account read is recorded with a status. A run refused before the account read is recorded by exit code and stderr only, and is not a criterion failure.
5. Every submitted order has a recorded fill or a recorded terminal failure.
6. No manual trade on an overlay name is recorded.
7. The rule used matches the tested 10-month month-end definition (ADR-085 amendment A1, aligned 2026-11-08).

**Return result, reported but not a pass criterion.** The excess return over SPY is reported with its uncertainty. Twelve monthly observations cannot support a significance test at the usual level: a t-statistic of 2 would need an average monthly excess return of about 0.6 of its own standard deviation. So the review cannot confirm an edge and will not pretend to. An edge claim requires a longer test and a new ADR.

**Reader rule.** An execute run is a row with `mode == "execute"` and `status` in `{started, executed, failed}`. Rows with status `refused`, `unreadable` or `dry_run` never count as an execute run.

## Decision 4: what is not decided here
- Changes to the trading rule, the universe, costs or any limit.
- Real-money use. That requires its own ADR and the owner's acceptance, after a PASS and the legacy-row audit.

## Consequences
- The review on 2027-11-07 is either INCONCLUSIVE, KILL or PASS. A PASS supports continued paper operation and nothing more.
- Any drawdown or Sharpe figure must use the month-end basis defined here.
