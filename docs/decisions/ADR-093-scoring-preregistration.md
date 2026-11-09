# ADR-093: Pre-registered Scoring Rules for the Strategy (extends ADR-082)

**Status:** Accepted by the financial expert on the owner's delegation, 2026-11-09. Owner ratification pending.
**Decision Type:** Pre-registration. Fixes how the strategy is judged before its results are seen.
**Related:** ADR-082 (forward-test log and review date), ADR-092.

## Pre-registered rules
1. **Primary metric:** expectancy per closed trade, net of costs (round-trip cost assumption stated per trade).
2. **Verdict threshold:** 200 closed trades. Monitoring reports at 50 and 100 are not verdicts.
3. **Pass condition:** the lower 95% bootstrap bound of expectancy is above zero.
4. **Hit-rate floor:** 45% at the 2:1 design (breakeven 40% at 0.2% costs, plus a 5-point margin). Reported with a Wilson interval.
5. **Drawdown cap:** maximum drawdown no greater than 8% (matches the real-money gate in the goals document).
6. **Benchmark:** SPY buy-and-hold over the same calendar window. A strategy that does not beat it is not a success regardless of expectancy.
7. **Data rule:** the trade record is taken from the broker-reconciled trades table. Reconcile artifacts are excluded and counted.
8. **Sealed window:** rules 1 to 7 cannot be changed after the first closed trade in the window.

## Reason
A fixed rule set, written before the results, prevents the bar from moving to fit the outcome.

## Acceptance
Owner ratification required before the verdict window opens.
