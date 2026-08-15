# ADR-026: Market-Data Pipeline Defect Correction (Narrow ADR-002 Exception)

**Status:** Accepted
**Date:** 2026-08-14
**Decision Type:** Architecture — Narrow ADR-002 Exception (Accepted)
**Related ADRs:** ADR-002 (protected path this ADR would except), ADR-006 (structural precedent for a narrow, additive ADR-002 exception)

---

## 1. Context

A read-only diagnostic investigation (2026-08-14, this session) traced why
`decision_events` stopped accumulating on 2026-08-06 while
`candidate_evaluation_events`/`risk_evaluation_events` continued through
2026-08-14. That investigation, and two follow-on investigations into the
Alpaca 5-minute feed and `alpaca-py` SDK compatibility, root-caused two
distinct, independent defects — both confined to a single protected file,
`bot/_main_market.py`. Neither defect was found to be caused by strategy
logic, execution logic, feed selection, or a dependency version problem;
both are narrow, local call-site/logic corrections.

`bot/_main_market.py` is protected under
[ADR-002](ADR-002-bot-runtime-protection.md) (`bot/` — all submodules). Per
ADR-002 §"Lifting This Protection," any change to it requires its own,
separately governed ADR naming the specific modules, an isolated
branch/worktree, a full regression pass, a stated rollback plan, and
verification of both known trading-trigger paths. This ADR is written to
meet that checklist for exactly these two corrections and no more.

## 2. Evidence

**Defect 1 — `get_calendar()` call-signature incompatibility.**
`bot/_main_market.py:116` calls `alpaca_api.get_calendar(start=today_str,
end=today_str)`. The installed `alpaca-py` SDK (`0.43.5` locally, `0.44.0`
in the production GitHub Actions run, confirmed via `pip show` and
`inspect.signature()`) defines `TradingClient.get_calendar(self, filters:
Optional[GetCalendarRequest] = None)` — no `start`/`end` keyword parameters
exist on the method itself. Every call raises `TypeError: get_calendar()
got an unexpected keyword argument 'start'`, confirmed verbatim in
production logs and caught by the surrounding `try/except`
(`bot/_main_market.py:114-120`), silently falling back to a hardcoded
holiday list (`_US_MARKET_HOLIDAYS`). `GetCalendarRequest`'s actual fields,
confirmed directly: `{'start': datetime.date, 'end': datetime.date}` — the
values passed today are correct in content, only wrapped incorrectly. A
full repository grep confirms this is the only `get_calendar()` call site,
and the only alpaca-py call anywhere in `bot/` still using bare kwargs
where every other call (`get_bars`, `get_latest_price`, `list_open_orders`,
order submission) already uses the SDK's typed-request convention.

**Defect 2 — valid yfinance daily bars discarded when only the Alpaca
5-minute feed is stale.** `bot/_main_market.py:363-397`'s `_fetch_symbol()`
fetches Alpaca 5-minute bars and, independently, reads pre-fetched
yfinance daily bars from `yf_batch`. When the Alpaca 5-minute bars are
judged stale (`age_mins > 30`, line 382), the function executes `if
feed_stale: return symbol, pd.DataFrame(), pd.DataFrame()` (lines
396-397) — discarding **both** `bars_5m` and `bars_daily`, even though
`bars_daily` was already successfully fetched and sits unread in
`yf_batch`; the function returns before ever reaching the daily-bars
computation block (lines 399-408). Confirmed in production logs from the
2026-08-14 run: yfinance reported `20/20 symbols loaded` (daily bars
genuinely available) while the same run logged 1,255 "Stale bars for X"
warnings across the day, including for SPY with its last Alpaca bar frozen
at the same pre-market timestamp for the entire multi-hour session —
directly matching the `data_available=False` pattern found in
`candidate_evaluation_events` since 2026-08-06.

Neither defect has any existing test coverage: `grep -rn
"stale|age_mins|feed_stale" tests/test__main_market.py` and `grep -rn
"get_calendar" tests/` both return zero matches.

## 3. Decision

Authorize exactly two corrections, both confined to `bot/_main_market.py`:

### 3.1 Fix 1 — `get_calendar()` typed-request migration

- **File/line:** `bot/_main_market.py:116`
- **Current:** `cal = alpaca_api.get_calendar(start=today_str, end=today_str)`
- **Corrected:** `cal = alpaca_api.get_calendar(filters=GetCalendarRequest(start=today_str, end=today_str))`, with `GetCalendarRequest` imported from `alpaca.trading.requests`.
- **Risk:** Low. Same two date values, same intent, no new external call — the call already executes every run and currently always fails. The existing `try/except` fallback (lines 114-120) remains in place as a safety net regardless of this fix.

### 3.2 Fix 2 — preserve valid daily bars when only the 5-minute feed is stale

- **File/lines:** `bot/_main_market.py:396-397` (the `if feed_stale:` early return inside `_fetch_symbol()`)
- **Current:** Returns `pd.DataFrame(), pd.DataFrame()` for both `bars_5m` and `bars_daily` whenever the Alpaca 5-minute feed is stale, discarding daily bars that were never actually stale.
- **Corrected:** On `feed_stale`, force only `bars_5m` empty; still compute and return `bars_daily` from `yf_batch` via the existing block (lines 399-408), unconditionally of the 5-minute feed's staleness.
- **Risk:** Moderate relative to Fix 1 — this changes what data reaches downstream code, not just an error path. `bot/main.py:313-315`'s `current_price` calculation (`bars_5m.iloc[-1]["close"] if not bars_5m.empty else latest["close"]`) already handles an empty `bars_5m` correctly today and was reviewed this session for consistency, but must be explicitly re-verified as part of implementation, not assumed correct by this ADR. No change to entry/exit gate thresholds, position sizing, order logic, or the 30-minute staleness threshold itself.

## 4. Explicit Non-Authorization

This ADR, if accepted, authorizes **only** the two corrections in §3, inside
`bot/_main_market.py`. It does not authorize:

- Any strategy/signal logic change (`bot/strategy/*`, ensemble weighting, entry/exit gate thresholds).
- Any execution-path change (`bot/execution/*`, order submission, `EXECUTION_BACKEND` behavior).
- Any feed-selection change (e.g. explicitly requesting `feed=IEX`/`SIP` on `StockBarsRequest`) — the open question of Alpaca account entitlement, identified but not resolved this session, is not addressed here.
- Any dependency/`requirements.txt` version change — `alpaca-py`'s `>=0.40.0` floor is unchanged; this ADR fixes a call-site incompatibility with the *currently installed* version, not a version bump.
- Any persistence or ledger-backend change — unrelated to `ADR-004`'s deferred scope.
- Any Phase 1B work — `analytics/calibration.py`/`regime_views.py` remain untouched and still gated on their own documented acceptance criteria.
- Any real-money/live-trading activation, `EXECUTION_BACKEND=live` change, or Paper→Supervised→Autonomous progression.
- Any change to `.github/workflows/*.yml`, `dashboard/`, `database/`, `scheduler/`, or top-level `ledger/`.
- Any change to `bot/_main_market.py` beyond the two named line ranges — no broader refactor of `_fetch_symbol()`, no change to the 30-minute staleness threshold, no change to any other function in the file.
- Any change to `ADR-002`, `ADR-004`, `ADR-006`, `ADR-024`, or `ADR-025`.

This is a narrow, additive/corrective exception — it does not reopen `bot/`
generally, does not establish a precedent for unscoped `bot/` changes, and
lapses in scope the moment these two named corrections are implemented and
verified.

## 5. ADR-002 Compliance Requirements

Per `ADR-002` §"Lifting This Protection," before implementation begins:

1. **Named modules:** `bot/_main_market.py` only — line 116 (Fix 1) and lines 396-397 plus the surrounding `_fetch_symbol()` return path (Fix 2). No other file.
2. **Isolated branch/worktree**, not directly on `main`.
3. No workflow YAML changes are implied by either fix, so criterion 3 (updating referencing workflow files) does not apply here — confirmed neither fix touches any path referenced by `.github/workflows/*.yml`.
4. **Full regression pass** before and after (see §6).
5. **Rollback plan stated before the change starts** (see §7).
6. **Both known trading-trigger paths verified** — the CLI path (`trade.yml` → `python bot/main.py --mode paper --loop`) and the `scheduler`-mediated HTTP path (`watchdog.yml` ping → HF Space `/run/cron` → `scheduler/trading_job.py` → `bot.main.run()`) — per ADR-002's own two-entry-point finding.

## 6. Tests Required

- New unit test(s) for `get_calendar()`'s corrected call shape — asserting `GetCalendarRequest(start=, end=)` is constructed and passed via `filters=`, mocking `TradingClient.get_calendar` the same way `tests/test_alpaca_client.py` already mocks other Alpaca calls.
- New unit test(s) for `_fetch_symbol()` asserting: when the 5-minute feed is stale but `yf_batch` has valid data for the symbol, the returned `bars_daily` is **non-empty** and correctly computed, while `bars_5m` is empty.
- Full existing suite re-run, at minimum: `tests/test__main_market.py`, `tests/test_main.py`, `tests/test_alpaca_client.py`, and the full `pytest tests/` baseline — zero regressions required, matching `ADR-006`'s own validation precedent (that exception recorded "1274 tests passed, no regressions" before being considered satisfied).

## 7. Verification

- **CLI path:** a local or CI dry run of `python bot/main.py --mode paper --loop` (or an equivalent scoped invocation) confirming `get_calendar()` no longer raises, and that at least one symbol with a genuinely stale 5-minute feed but valid daily bars now reaches `record_candidate_safe(..., data_available=True, ...)` instead of being silently skipped.
- **Watchdog/HF entry path:** confirmation that `watchdog.yml`'s ping to the HF Space `/run/cron` endpoint, and the resulting `scheduler/trading_job.py` → `bot.main.run()` invocation, exercise the same corrected `bot/_main_market.py` code path with the same result — not merely assumed identical to the CLI path.
- Both verifications must be performed; per `ADR-002`'s own stated finding, verifying only one entry point and assuming the other is unaffected is exactly the gap that ADR exists to prevent.

## 8. Rollback Plan

Both fixes are isolated, single-file, non-schema, non-persistent changes
with no data migration involved. Rollback is a plain `git revert` of the
implementing commit(s). No database schema, ledger record, or external
state is written or altered by either fix, so no data-level rollback step
is required beyond reverting the code.

## 9. Consequences

**Positive:**
- Restores `get_calendar()` to Alpaca's authoritative, live market-calendar data instead of a static, driftable hardcoded holiday list.
- Restores the daily-bars fallback `bot/main.py:295` already assumes exists, closing the specific gap that produced `data_available=False` for the large majority of candidates since 2026-08-06 — directly addressing a confirmed, evidenced production defect, not a hypothetical one.
- Both fixes are covered by new, previously-nonexistent tests, closing a real test-coverage gap identified this session.

**Negative:**
- Does not resolve, or attempt to resolve, whether the underlying Alpaca 5-minute feed staleness itself reflects an account entitlement/feed-tier issue — that remains an open, separately-scoped question.
- Does not address the unrelated 7-day `keepalive.yml`/`trade.yml` external-scheduler silence (2026-08-07 through 2026-08-12) identified in the same investigation chain — that is a separate, non-code, operational issue outside this ADR's scope.

## 10. Status

**Accepted.** This ADR is now authoritative per `docs/DOCUMENT_INDEX.md`'s
documentation hierarchy — the two corrections named in §3 are authorized,
strictly bounded by §4's Explicit Non-Authorization list. Acceptance
authorizes the exception itself; it does not waive §5's ADR-002 compliance
requirements (isolated branch/worktree, full regression pass, stated
rollback plan, both trading-trigger paths verified) or §6's required
tests — those remain preconditions to be satisfied during implementation,
not retroactively satisfied by acceptance.
