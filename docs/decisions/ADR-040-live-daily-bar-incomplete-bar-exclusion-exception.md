# ADR-040: Live Daily-Bar Incomplete-Bar Exclusion (Narrow ADR-002 Exception)

**Status:** Accepted
**Date:** 2026-08-19
**Decision Type:** Architecture — Narrow ADR-002 Exception (Accepted)
**Related ADRs:** ADR-002 (protected path this ADR would except), ADR-026 (structural precedent — prior narrow, single-file `bot/_main_market.py` exception for a market-data pipeline defect)

---

## 1. Context

A read-only implementation-point audit (2026-08-19, this session) traced a confirmed production defect: during market hours, `bot/_main_market.py::prefetch_bars()` fetches daily bars via `yf.download(period="2y", interval="1d", ...)` while the current trading day is still open. The last row of that fetch is an in-progress daily bar (partial volume, partial OHLC), not a completed session. `compute_features()` (`bot/strategy/features.py`) computes every `FEATURE_COLS_V4` field — including `volume_ratio = volume / volume_sma(20)` — using that row as the "current" observation, so `latest.volume_ratio` reflects partial-day volume divided against a complete 20-day average, producing artificially low values. This was confirmed as the cause of 74/75 post-cutover entry REJECTs against the existing `MIN_VOLUME_RATIO=0.3` gate.

The audit further established:

- The defect is confined to the live path. Training (`scripts/train_model.py`, `TRAIN_CUTOFF = today − 30d`) and all backtest/walk-forward paths (`backtest/engine.py`, `scripts/walkforward_backtest.py`, `scripts/walkforward_validate.py`) consume historical CSV data where the last row is never "today, in-progress" — those paths are unaffected and require no change.
- Because rolling/pct_change/diff operations in `compute_features()` are causal, the incomplete bar contaminates **every** `FEATURE_COLS_V4` column computed at that row, not `volume_ratio` alone — ruling out a `volume_ratio`-only patch as incomplete.
- `_is_market_hours()` confirms "now" is inside the tradeable window at gate-check time; a short, unavoidable gap exists between that check and the actual `yf.download()` call (intervening Alpaca calls and DB I/O), so completeness is established at the gate, not re-verified at the moment of fetch. This gap does not reintroduce the original bug — worst case is a one-cycle lag near the close, self-correcting the next cycle — so no new market-calendar logic is required.
- `prefetch_bars()` force-includes `"SPY"` in the yfinance batch download (`_batch_syms`) independent of the day's `active_symbols` list, but `yf_batch["SPY"]` is not guaranteed populated — if the per-symbol yfinance slice for `"SPY"` fails or is empty, `prefetch_bars()` already detects this and logs "SPY missing from yfinance batch — relative strength gate disabled" (lines 445-447). Separately, every symbol's `_fetch_symbol()` call reads `spy_raw = yf_batch.get("SPY")` at line 413 to compute that symbol's `rs_vs_spy_21d`/`rs_vs_spy_63d` features; the existing code already guards this as `spy_close = spy_raw["close"] if (spy_raw is not None and not spy_raw.empty) else None` (line 414). The trim in §2 must therefore apply at two points and preserve this existing null/empty-safe behavior: (a) the `raw_d` frame for whichever symbols `_fetch_symbol()` is actually called with, and (b) this `spy_raw` re-read at line 413, which runs on every call regardless of whether `"SPY"` itself is present in `active_symbols` that day — and regardless of whether the `"SPY"` fetch succeeded that day. No SPY-specific branch is introduced — both points reuse the same trim logic — but the coverage is via the shared `spy_raw` re-read, not because SPY happens to be a member of `config.SYMBOLS`.

`bot/_main_market.py` is protected under ADR-002. Per ADR-002 §"Lifting This Protection," any change requires its own ADR naming the specific modules, an isolated branch/worktree, a full regression pass, a stated rollback plan, and verification of both known trading-trigger paths. This ADR is written to meet that checklist for exactly one correction and no more.

## 2. Decision

Authorize exactly one correction, confined to `bot/_main_market.py`, live daily-bar assembly path only:

**Exclude today's incomplete daily bar before `compute_features()` is called**, for every symbol including the separately consumed SPY reference data, so that `compute_features()` — and everything computed by it — only ever sees completed daily sessions in the live path, matching the invariant that already holds for training/backtest.

- **File:** `bot/_main_market.py` only.
- **Location:** `_fetch_symbol()` — two trim points, both before the existing `compute_features(raw_d, spy_close=spy_close)` call (current line 415): (a) trim `raw_d` immediately before it is passed into `compute_features()` at line 415, dropping its last row when that row's index date equals "today" in `America/New_York`; (b) trim `spy_raw` immediately after it is read (`spy_raw = yf_batch.get("SPY")`, current line 413) and *before* `spy_close` is derived from it (`spy_close = spy_raw["close"] if ... else None`, current line 414), applying the same "today" row-drop, so that the `spy_close` passed into `compute_features()` at line 415 is computed from the already-trimmed `spy_raw`. Trimming `spy_raw` after `spy_close` has already been derived would not affect `spy_close` and must not be done.
- **Scope of the trim:** a data-selection filter on the raw OHLCV frame only. No column is added, removed, or recomputed by this ADR — `compute_features()` runs unmodified on whatever frame it receives.
- **SPY coverage:** `prefetch_bars()` force-includes `"SPY"` in the yfinance batch independently of `active_symbols`, but that fetch can still fail or return empty for `"SPY"` specifically; each `_fetch_symbol()` call separately reads `yf_batch.get("SPY")` for relative-strength features. The same incomplete-bar exclusion applies to that `spy_raw` frame, applied per the ordering in the Location bullet above, and must preserve the existing null/empty-safe handling of `spy_raw`/`spy_close` (including the existing "SPY missing from yfinance batch — relative strength gate disabled" behavior when `"SPY"` itself is absent from `yf_batch`). No separate SPY branch or universe-membership assumption is introduced.

## 3. Explicit Non-Authorization

This ADR, if accepted, authorizes **only** the trim described in §2, inside `bot/_main_market.py`. It does not authorize:

- Any change to `compute_features()` (`bot/strategy/features.py`) — signature, logic, or `FEATURE_COLS_V4` definition.
- Any change to the `volume_ratio` formula (`volume / volume_sma(20)`).
- Any change to `MIN_VOLUME_RATIO` or any other threshold/config value.
- Any change to entry/exit gate ordering (`bot/_main_cycle.py`, `bot/strategy/signal_gate.py`).
- Any change to risk logic (`bot/risk/*`).
- Any change to execution logic (`bot/execution/*`, order submission, `EXECUTION_BACKEND` behavior).
- Any change to model weights or retraining.
- Any change to `scripts/train_model.py`, `backtest/engine.py`, `scripts/walkforward_backtest.py`, `scripts/walkforward_validate.py`, or any other training/backtest path — these are already unaffected per §1 and remain untouched.
- Any change to `bot/_main_market.py` beyond the single named trim point — no broader refactor of `_fetch_symbol()` or `prefetch_bars()`, no change to `_is_market_hours()` itself, no change to the 5-minute-feed staleness logic (ADR-026 Fix 2) it sits next to.
- Any change to `dashboard/`, `database/`, `scheduler/`, `ledger/`, or `.github/workflows/*.yml`.
- Any change to ADR-002, ADR-004, ADR-006, or ADR-026.

This is a narrow, additive/corrective exception — it does not reopen `bot/` generally and lapses in scope the moment this one named correction is implemented and verified.

## 4. ADR-002 Compliance Requirements

Per ADR-002 §"Lifting This Protection," before implementation begins:

1. **Named module:** `bot/_main_market.py` only — `_fetch_symbol()`, immediately before the `compute_features()` call. No other file.
2. **Isolated branch/worktree**, not directly on `main`.
3. No workflow YAML references this specific line range; no `.github/workflows/*.yml` change is implied.
4. **Full regression pass** before and after (see §6).
5. **Rollback plan stated before the change starts** (see §7).
6. **Both known trading-trigger paths verified** — the CLI path (`trade.yml` → `python bot/main.py --mode paper --loop`) and the scheduler-mediated HTTP path (`watchdog.yml` → HF Space `/run/cron` → `scheduler/trading_job.py` → `bot.main.run()`).

## 5. Tests Required

New tests in `tests/test__main_market.py`:

1. **In-progress bar not consumed** — feed `_fetch_symbol()`/`prefetch_bars()` a synthetic `yf_batch` whose last row is dated "today" (with the module's notion of "now" fixed via the same monkeypatch pattern already used for `_is_market_hours()` tests in this file); assert the resulting `bars_daily` frame's last index date is the prior completed session, not today.
2. **Latest completed bar used** — assert `bars_daily.iloc[-1]` is numerically identical to running `compute_features()` on the same raw data with the synthetic today-row removed beforehand (proves the trim point is equivalent to computing features on a pre-trimmed frame).
3. **`volume_ratio` formula preserved** — diff of `bot/strategy/features.py` shows no change; existing `tests/test_features.py` passes unmodified.
4. **`FEATURE_COLS_V4` compatibility** — extend `tests/test_features.py` (or the new `test__main_market.py` case) to assert all 22 `FEATURE_COLS_V4` values match a reference computed from data that never included the partial bar — not `volume_ratio` alone.
5. **No other model inputs unexpectedly change** — golden-value regression: `xgb.predict_proba(latest)` / `lstm.predict_proba(sig_bars)` outputs on a fixed, already-complete historical fixture must be bit-identical before/after, since the trim only activates when the last row is dated "today".
6. **`MIN_VOLUME_RATIO` gate unchanged** — assert the constant and `bot/_main_cycle.py:110` comparison are byte-identical in the diff.
7. **SPY relative-strength path covered** — for a **non-SPY** symbol (e.g. `"AAPL"`), construct `yf_batch["SPY"]` with a last row dated "today," call `_fetch_symbol("AAPL", client, yf_batch)`, and assert the resulting `rs_vs_spy_21d`/`rs_vs_spy_63d` values match those computed from `yf_batch["SPY"]` with that last row excluded — verifying the line-413 `spy_raw` re-read is trimmed *before* `spy_close` is derived from it, on the path that runs every cycle regardless of universe screening. Also assert, via a second case where `yf_batch` has no `"SPY"` key (or an empty frame for it), that `_fetch_symbol("AAPL", client, yf_batch)` still returns successfully with `rs_vs_spy_21d`/`rs_vs_spy_63d` at their existing null-SPY default (`spy_close=None` path) rather than raising — confirming the trim preserves the existing missing/empty-SPY safety.
8. Full existing suite re-run, at minimum `tests/test__main_market.py`, `tests/test_features.py`, `tests/test_main.py` — zero regressions required.

## 6. Verification

- **CLI path:** a local or CI dry run of `python bot/main.py --mode paper --loop` during simulated market hours, confirming the daily-bar frame consumed by `compute_features()` never includes a today-dated row, and that `volume_ratio` for at least one previously-affected symbol now reflects the completed prior session's ratio.
- **Watchdog/HF entry path:** confirmation that the `scheduler/trading_job.py` → `bot.main.run()` invocation exercises the same corrected `bot/_main_market.py` code path with the same result — not assumed identical to the CLI path.
- Both verifications must be performed; per ADR-002's own stated finding, verifying only one entry point and assuming the other is unaffected is exactly the gap this ADR exists to prevent.
- Re-run the 74 previously-REJECTed post-cutover cases and confirm their `volume_ratio` now reflects the completed prior day's ratio — this ADR does not assert or require any specific PASS/REJECT outcome change, since gate/threshold behavior is explicitly out of scope (§3).

## 7. Rollback Plan

Single-file, non-schema, non-persistent change with no data migration involved. Rollback is a plain `git revert` of the implementing commit. No database schema, ledger record, or external state is written or altered by this trim, so no data-level rollback step is required beyond reverting the code.

## 8. Consequences

**Positive:**

- Live `volume_ratio` (and every other `FEATURE_COLS_V4` field) is computed from the same "completed bars only" invariant that already holds for training/backtest, closing the specific inconsistency identified in the audit.
- No threshold, gate, or model change is needed to address the confirmed defect — the correction is purely a data-completeness fix at the ingestion boundary.
- Covered by new tests closing a real gap (no existing coverage for this scenario per the audit).

**Negative:**

- Does not address whether `MIN_VOLUME_RATIO=0.3` itself is still the right threshold once `volume_ratio` reflects completed-bar values — that remains a separate, out-of-scope question.
- Does not change behavior on days the market is closed or after-hours (`_is_market_hours()` already prevents the cycle from running then) — no consequence there, noted for completeness.

## 9. Status

**Accepted.** This ADR is now authoritative per `docs/DOCUMENT_INDEX.md`'s documentation hierarchy — the one correction named in §2 is authorized, strictly bounded by §3's Explicit Non-Authorization list. Acceptance authorizes the exception itself; it does not waive §4's ADR-002 compliance requirements (isolated branch/worktree, full regression pass, stated rollback plan, both trading-trigger paths verified) or §5's required tests — those remain preconditions to be satisfied during implementation, not retroactively satisfied by acceptance.
