# ADR-083: ETF Trend Overlay on a Dedicated Alpaca Paper Account

**Status:** Accepted by ksri77 on 2026-11-07 ("agreed lets fix and finish all above"). Implementation follows this text.
**Decision Type:** Narrow execution path, paper only. Adds one module and one runner. Does not change the stock entry path, which stays suspended under ADR-081 step 1.

## Context
The ETF trend overlay (ADR-082 rule B, ADR-081 risk criterion) is the only candidate that has passed a pre-registered test. It has passed only in-sample. Its forward evidence must be gathered on paper, with the same rule and the same criteria.

## Decision

1. **Dedicated paper account.** The overlay runs on its own Alpaca paper account, with its own keys (`ETF_PAPER_KEY`, `ETF_PAPER_SECRET`). It must never share the account used by the stock bot. The stock bot's position reconciliation would otherwise read ETF holdings as unknown positions and act on them.
2. **Paper endpoint guard.** The runner refuses to start unless the base URL is exactly `https://paper-api.alpaca.markets`. Any other value, including the live endpoint, raises an error before any call is made.
3. **Rule, fixed.** Universe: XLC, XLE, XLF, XLI, XLK, XLP, XLV, XLY, GLD, TLT, QQQ, IWM. On the last trading day of each month, hold each ETF whose close is above its 210-trading-day mean, equal-weighted, and hold cash for the rest of the account. Positions below $25 of target value are not traded.
4. **Dry run by default.** The runner prints the planned orders and submits nothing unless run with `--execute`.
5. **Order sequence.** Sells first, then buys, so cash is available for the buys. Market orders.
6. **Logging.** Each run appends the plan, the orders and the account equity to `data/etf_paper/runs.csv`. The file is git-ignored, append-only, and reviewed against SPY.
7. **Stock entries.** Not in scope. Any stock module requires its own ADR and a passed pre-registered test.

## Scope (named)
- New: `bot/execution/etf_paper.py` (rule, planning, endpoint guard), no imports from `scripts/`.
- New: `scripts/etf_paper_rebalance.py` (runner, dry run by default).
- New: `tests/test_etf_paper.py`.
- Unchanged: `bot/main.py`, `bot/_main_cycle.py`, `config.py` entry switch, all workflows.

## Governance and limits
- Paper only. Nothing in this ADR places an order against a live account.
- A rebalance requires a human to run the script at month-end. No scheduler is added by this ADR.
- The review date for the overlay's forward result is set by the ADR-082 log and is not changed here.
- Rollback: delete the two new files. Positions held on the paper account are closed manually.
