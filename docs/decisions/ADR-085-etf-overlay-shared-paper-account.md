# ADR-085: ETF Overlay on the Shared Paper Account

**Status:** Accepted by ksri77 on 2026-11-07 ("yes temporarily ... first etf's and then stocks"; shared paper account chosen by the owner). Supersedes the separate-account rule in ADR-083 decision 1.
**Decision Type:** Isolation fix. The stock bot must not adopt or trade ETF-overlay holdings that share its paper account.

## Context
The owner chose one Alpaca paper account for both the stock bot and the ETF overlay. The stock bot's reconciliation adopted any broker position it did not record and then applied stock exit rules to it (`bot/_main_positions.py`, adoption loop). Six symbols in the stock universe also belong to the overlay (GLD, IWM, QQQ, XLE, XLF, XLV). Left alone, the stock bot would have traded the overlay's holdings on stock rules.

## Decision
1. **One source for the overlay universe.** `config.ETF_OVERLAY_SYMBOLS`. Used by the overlay rule, by the stock bot, and by the tests.
2. **No adoption.** `_reconcile_positions` skips overlay symbols, so they never enter `position_state`.
3. **No stock trading.** `bot/main.py` removes overlay symbols from the stock universe for the day. The stock bot therefore never sets or manages a stop on them.
4. **Runner uses the paper keys.** `scripts/etf_paper_rebalance.py` reads `ALPACA_KEY` / `ALPACA_SECRET` and is still limited to the exact paper endpoint.

## Consequences
- Overlay symbols held in the stock universe are no longer traded by the stock bot, which is intended. Those six names now belong to the overlay only.
- Stock entries stay suspended on `main` (ADR-081 step 1). When stock entries are re-enabled, the overlay exclusion still applies.
- **Size limit, pre-existing:** `bot/main.py` (503 lines) and `bot/_main_positions.py` (547 lines) were already over the project's 500-line limit before this ADR, and this change adds two lines to each. Splitting them is a separate refactor and is not part of this ADR.

## Tests
`tests/test_etf_overlay_isolation.py`: a stock position is still adopted; an overlay holding is not; the overlay list is defined once.

## Rollback
Revert the commit. Positions held on the paper account are then adopted again by the stock bot, so close them first.
