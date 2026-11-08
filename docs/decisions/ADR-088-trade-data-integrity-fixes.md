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
