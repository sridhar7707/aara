# ADR-089: Fundamentals Reject-Only Test on Free Data

**Status:** Accepted by ksri77 on 2026-11-08 ("ok follow your recommendation"). Pre-registration: fixed before any result is produced. Changes after results exist need a new ADR.
**Decision Type:** A cost-free research test that can reject a signal. It cannot confirm one.

## Purpose
Test whether two standard fundamentals signals show any monthly predictive power, using free data only (SEC EDGAR fundamentals and yfinance prices). The test runs on today's S&P 500 members, so it is biased upward. A FAIL rejects the signal. A PASS does not confirm it. Confirmation requires the licensed or forward test already described.

## Pre-registered design
1. **Universe.** Current S&P 500 members with usable EDGAR facts (see ADR-086 coverage check). No attempt to add removed companies.
2. **Signals.**
   - **ROE (quality):** trailing annual net income divided by shareholders' equity, both taken from the latest annual filing whose filing date is on or before the signal date.
   - **Earnings yield (value):** the same annual net income divided by market capitalisation on the signal date. Market capitalisation is the adjusted close times the most recent shares-outstanding figure filed on or before that date.
   - Signal direction is fixed: higher is better for both. No other signal is tested in this ADR.
3. **Point-in-time rule.** A figure is used only from its filing date onward. No figure is used on or before its filing date.
4. **Sampling.** Month-end cross-sections, from 2010 to 2026-07.
5. **Target.** One-month forward return minus SPY's one-month return. Costs: 20 basis points round trip, applied to the decile spread.
6. **Statistics and folds.** Identical to `scripts/validate_signal.py` as pre-registered in ADR-081, with five folds and the same thresholds:
   - Newey-West t of the monthly rank IC at least 2.0 (lag 2 for monthly overlap);
   - the net decile spread positive in at least four of five folds.
   The fold boundaries are the same as ADR-086's five test periods, adapted to monthly sampling.
7. **Outcomes.**
   - **REJECT** if either criterion fails for a signal. Recorded and not revisited.
   - **NOT REJECTED** if both pass. This is not a confirmation, because the universe is biased upward.
8. **Multiple testing.** Two signals are tested, both pre-registered here. Any further signal needs its own ADR and a stricter bar.

## Known bias, stated in advance
- Survivorship: only companies still in the index are tested. Companies that failed and left are missing. This flatters every signal, so a REJECT is informative and a NOT REJECTED is not.
- Data: EDGAR facts are used where they exist. Filing dates are the public-availability date. Any figure that cannot be dated is dropped.

## Consequences
- Results are reported in `docs/analysis/` with the same numbers the script prints. The script is committed with this ADR.
- A REJECT on either signal closes that signal for the bot. A NOT REJECTED result authorises only the free forward log for that signal, as described in ADR-082's structure. It does not authorise trading.
- No real money, no change to any limit, no change to the stock path (entries stay suspended under ADR-081 step 1).
