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

## Review findings and status (2026-11-07)

Found by `/code-review` on the overlay branch. Fixed in this change:
- **Whole-account sizing.** The runner used total account equity and all positions. It now manages only a fixed `--sleeve` and only overlay symbols.
- **NaN prices.** A NaN last close was read as off-trend, and a NaN price reached an order. Both now refuse the run.
- **Sell sizing.** A full exit was sized from dollars divided by the yfinance price. It now sells the actual held quantity, including residual dust.
- **Partial runs.** Orders went out with no per-order record. Each order is now logged as submitted, a failure stops the run and is logged, and a failed execute blocks a re-run that month until a person checks.
- **Intraday bars.** Execute is refused before 16:30 New York time, and when the latest bar is not today's.
- **Buying power.** The plan refuses buys that exceed available cash.

Open, and blocking any `--execute` on the shared account until resolved:
1. **Stock-bot capital is computed on the whole shared account** (`bot/main.py` cash and portfolio value). Overlay holdings are counted as stock-bot capital. Stock entries are suspended, so the impact is limited today, but it must be fixed before stock entries return. Needs a design decision: subtract the sleeve, or split the account.
2. **Pre-existing overlay rows in `position_state`.** Any overlay symbol adopted before ADR-085 stays in state and counts in invested-capital calculations. Check and clear these by hand before the first execute.
3. **Line limits (pre-existing).** `bot/main.py` and `bot/_main_positions.py` are over 500 lines before this change. Their unused imports (56 in `bot/main.py`) were already present; the lint hook now reports them on every commit that touches those files.

## Amendment A1 (accepted by ksri77, 2026-11-07)

**Status:** Accepted by ksri77 on 2026-11-07 ("yes please draft and accept"). Supersedes decision 3 of this ADR (the stock bot never manages overlay names). Decisions 1, 2 and 4 stand.

**Status log:** 2026-11-08: the live rule in `bot/execution/etf_paper.py` was aligned to the tested 10-month month-end definition (`TREND_MONTHS = 10`, replacing the 210-daily-close proxy); C3 is met on the rule-definition point.

**Why:** the risk review (APPROVE WITH CONDITIONS) and the quant review (blocking finding 1) found that overlay names the stock bot already holds lost their stop-loss, trailing stop, time exit and signal sell when the overlay names were removed from the stock loop. That is a risk-control regression. It is restored by this amendment.

**Decisions**

- **D1 (restore exits).** Overlay names are excluded from stock ENTRIES and from universe selection. An overlay name that has a `position_state` row AND a broker position is managed by the stock bot's EXIT rules: gap-down floor, stop, trailing stop, take-profit, drift trim, time exit and signal sell. Exit evaluation for these names runs without entries, signal publication or candidate records.
- **D2 (legacy rows).** Each existing overlay-named `position_state` row must be audited before any `--execute`: confirm the lot's shares against the stock bot's trade history, and record who owns the shares. This audit needs production database access and is OPEN. Until it is complete, `--execute` stays refused (see C1 below).
- **D3 (runner conflict).** The runner does NOT subtract stock-held shares. It refuses to execute while ANY overlay name has a `position_state` row or any open overlay order exists. Fail closed, not subtract.
- **D4 (wind-down).** Accepted. Overlay lots of the stock bot are never added to. They close through their own exit rules (stop, trailing stop, time exit, take-profit, drift trim, or signal sell).
- **D5 (pattern day trading).** Accepted with a documented limitation: an overlay buy on the same day as a stock-lot sale is not counted by the bot's day-trade counter, because `_opened_today` reads only the trades table. The paper account's equity must be recorded at each execute; the $25K threshold check is a manual step until it is automated.

**Required behaviour (for the implementation that follows this amendment)**
1. The exit position passed to `_handle_exits` is a copy built with `position_placeholder`. Its quantity is `min(broker qty, position_state.shares, net stock-bot shares from the trades table)`. A name whose clamped quantity is below 0.001 is dropped, with a warning.
2. Its `avg_entry_price` is `position_state.entry_price`, not the broker's blended average. Its `unrealized_plpc` is computed from that basis. `positions` and `EntryContext.positions` are never mutated.
3. An exit-only name never reaches the entry call, even when `_handle_exits` returns False. The guard sits immediately after the exit call.
4. `_handle_entry` returns early for any overlay name, before the decision recorder is created.
5. The overlay runner sells only overlay-owned quantity, and refuses per D3.

**Files touched by the implementation** (bot/ is frozen under ADR-006 except as amended here): `bot/main.py`, `bot/_main_positions.py`, `bot/_main_cycle.py`, a new `bot/_main_overlay.py`, and `scripts/etf_paper_rebalance.py`. No change to `config.py`, `bot/risk/*`, the stop, daily-loss or max-position values, or the XGB threshold.

**Tests required**
- A clamped sell never exceeds `position_state.shares` or the net trades shares.
- With shares 0 or NULL: no sell is sent and no entry is reached.
- Blended-basis scenario: stock lot at $100, overlay lot at $90, price $91: the stop fires on the stock lot's own basis.
- An exit-only name never reaches `client.buy`, even with `MODEL_ENTRIES_ENABLED` patched True.
- `EntryContext.positions` still carries the full broker quantity.
- `test_etf_overlay_isolation`, the ETF safety tests, and the phase1a integration tests all pass.

**Conditions still open (gate any `--execute`)**
- **C1:** D2 audit complete, and the production database checked for overlay-named rows.
- **C2:** the implementation above passes its tests and a risk-officer review.
- **C3:** the rule question is settled (see ADR-085 review notes): the live rule must match the tested 10-month month-end definition, or the 210-day rule needs its own pre-registration. Met 2026-11-08: the live rule now is the tested definition.
- **C4:** the measurement gap is closed: sleeve value and fills recorded per run.

**Line limits:** `bot/main.py` (504 lines) and `bot/_main_positions.py` (548 lines) are already over the project limit. The change adds lines there, so the logic goes in `bot/_main_overlay.py`.
