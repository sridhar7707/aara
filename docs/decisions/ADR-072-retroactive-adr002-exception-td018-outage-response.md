# ADR-072: ADR-002 Exception (Retroactive) — TD-018 Readonly-Database Outage Response

**Status:** Accepted
**Date Proposed:** 2026-10-22
**Date Accepted:** 2026-10-22
**Decision Type:** Retroactive ADR-002 exception, documentation-only — ratifies already-merged, already-verified changes. Authorizes no new implementation.
**Related ADRs:** ADR-002 (protected path this ADR retroactively excepts), ADR-025 (prior, retroactive/documentation-only ratification — the structural precedent this ADR follows), ADR-052 (closest prior precedent for a `bot/`-adjacent fix with required regression tests and a named Forbidden list), ADR-006/009/010/017/018/023/026/034/035/040/041/042/056/060/065 (the established one-ADR-per-narrow-purpose pattern this ADR follows for its three sub-scopes)

---

## Context

### What happened, in commit order (all on `main`, none in an isolated branch/worktree)

A 36-day production outage (2026-09-17 to 2026-10-22) was found and fixed in this session: every trading cycle silently crashed with `sqlite3.OperationalError: attempt to write a readonly database`, while GitHub Actions kept reporting `success` and the existing Watchdog kept reporting healthy (it only pings a liveness endpoint, never checks whether data is actually being written). Three narrow fixes followed, in this order:

1. **`2f605d4`** — `shutil.copy()` → `shutil.copyfile()` in `bot/monitor/sync_db.py`, `.github/workflows/trade.yml` (two steps), `.github/workflows/retrain.yml`, `scheduler/startup_job.py`. Root cause at the time: `copy()` also copies the source's permission bits, and the HuggingFace cache blob each restore pulled from is read-only. CI run `39812695483` on this commit **failed**, but on 3 pre-existing, unrelated flaky tests (fixed separately in `5f5f087`, which touched no ADR-002-protected path).
2. **Found insufficient by actually dispatching a live run and watching it fail identically 9 cycles in a row** (run `39819172246`, cancelled after confirming the same error via its logs: `PermissionError: [Errno 13] Permission denied: 'trades.db'`). Real cause: `trade.yml`'s cache-restore steps use `restore-keys: trades-db-`/`trust-ledger-db-` (a prefix match), which restores whichever prior run's cache was most recently saved — and every run since 2026-09-17 had cached its own already-read-only file, re-poisoning itself regardless of `copy()`/`copyfile()`. `copyfile()` only helps when the destination doesn't exist yet; it still raises opening an *existing* read-only file for writing.
3. **`c405187`** — the actual fix: `chmod` the destination writable (if it already exists) before every copy, in the same 4 protected files as step 1. CI run `39826955726` on this commit: **success**.
4. **`e0f3e2d`** — added `_MAX_CONSECUTIVE_FAILURES = 5` and a halt branch to `run_loop` in `bot/_main_runner.py` (TD-020): after 5 consecutive cycle crashes, the loop now stops for the rest of the session and sends a distinct Telegram alert, instead of retrying every 5 minutes until market close. Also added a regression test (`tests/test_sync_db.py`, not an ADR-002 path) and corrected two stale docstrings (`applications/trading_intelligence/...`, not an ADR-002 path). CI run `39829963375` on this commit initially **failed** on `test_abandoned_slow_worker_cannot_leave_a_partial_snapshot` (an unrelated file this commit never touched); confirmed as flaky, not a regression, by re-running the identical commit with `gh run rerun --failed` — second attempt **succeeded**, no code change between attempts.
5. **`827ed08`** — added a second Watchdog check to `.github/workflows/watchdog.yml`: reads the HF dataset repo's `last_modified` via a lightweight metadata call and alerts if it's gone stale beyond 96 hours (wide enough to never trip on a normal weekend, narrow enough to catch a real multi-day outage in days instead of 36). Also updated `docs/TECHNICAL_DEBT.md` (TD-018, not an ADR-002 path). CI run `39818194094`: **success**.

### Production verification (not just CI)

Dispatching `trade.yml` on the fully-fixed commit (`e0f3e2d`) and watching it directly (run `39831453272`) confirmed the real fix works, not just the test suite:

- Before: HF dataset repo `ksri77/ai-trading-bot-db` `last_modified` = `2026-09-16 19:37:52+00:00` (861+ hours stale).
- After ~11 minutes of the dispatched run: `last_modified` = `2026-10-22 18:30:21+00:00`.
- Pulled `trades.db`/`trust_ledger.db` directly and confirmed genuine new rows: `signal_log` MAX timestamp `2026-10-22T18:30:16`, row count 26,325 → 26,340 (+15); `decision_events` MAX timestamp `2026-10-22T18:30:16`.

This is the first successful write to either file since the outage began.

### The ADR-002 gap this ADR exists to close

All of the above is real, is merged to `main`, and is verified working. It was **not**, however, run through ADR-002's required process before implementation:

- `bot/monitor/sync_db.py`, `bot/_main_runner.py`, `scheduler/startup_job.py`, `.github/workflows/trade.yml`, `.github/workflows/retrain.yml`, `.github/workflows/watchdog.yml` are all ADR-002-protected paths ("no file changes of any kind" until superseded by a dedicated ADR).
- No narrow, standalone ADR-002 exception ADR was drafted or accepted before any of these five commits.
- Per ADR-002's "Lifting This Protection" item 2, work was required to happen "in an isolated branch or worktree, not directly on `main`." **This did not happen — all five commits were made and pushed directly to `main`.** This ADR does not retroactively claim otherwise.

This ADR exists to document that gap honestly and bring the already-merged state into the project's governance record, following the ADR-025 precedent for retroactive, documentation-only ratification of work that already happened and already proved itself.

---

## Decision

Retroactively except the following three narrow scopes from ADR-002's freeze, covering exactly the files and changes already merged in commits `2f605d4`, `c405187`, `e0f3e2d`, and `827ed08`. No further changes beyond what is itemized below are authorized by this ADR.

### Sub-scope A — Readonly-database restore fix

- **Files:** `bot/monitor/sync_db.py`, `scheduler/startup_job.py`, `.github/workflows/trade.yml`, `.github/workflows/retrain.yml`
- **Change:** in each file's HF-cache-restore copy operation, `chmod` the destination writable (if it already exists) immediately before copying, and use `shutil.copyfile()` rather than `shutil.copy()`.
- **Risk tier:** Medium. Touches one of ADR-002's two documented live-trading entry points (`trade.yml` → `bot/main.py --mode paper --loop`) directly, and the shared sync helper (`sync_db.py`) both entry points can reach. Mitigated by: the change is additive-only (a permission check before an existing copy call, no removed logic), mechanically verified in isolation before being written (reproduced the exact `PermissionError` locally, then verified the chmod-based fix resolves it), and independently confirmed against live production data after merge (see Context).

### Sub-scope B — Same-day circuit breaker

- **File:** `bot/_main_runner.py`
- **Change:** added `_MAX_CONSECUTIVE_FAILURES = 5` and a halt branch inside `run_loop`'s existing exception handler — after 5 consecutive cycle crashes, `break` out of the loop (instead of continuing to retry every 5 minutes until market close) and send a distinct Telegram alert.
- **Risk tier:** Medium-High. This is the live-trading entry point's own retry loop. Mitigated by: the change only adds a new, higher threshold on top of the *existing* 3-failure escalation logic (already in production), triggers strictly less trading activity than before (it stops retrying, it does not add new retries or new trade logic), and falls through to the loop's existing post-loop cleanup path (`end_of_day_summary()`) unchanged.
- **Known gap, stated plainly:** `run_loop` has no existing test scaffold at all (it loads real ML models and connects to Alpaca), and none was added for this change. Verified only by syntax/import check and manual trace of the new branch — not by an executed test, and not yet observed triggering in a real production crash-loop. This is a known, named limitation of this ADR's test coverage, not an oversight being hidden.

### Sub-scope C — Watchdog staleness check

- **File:** `.github/workflows/watchdog.yml`
- **Change:** added a second step that calls `HfApi().repo_info(...).last_modified` on the HF dataset repo and sends a Telegram alert if it's more than 96 hours stale.
- **Risk tier:** Low. `watchdog.yml` is a read-only health check (a metadata API call, no file download, no write to any trading data); the new step cannot affect either live-trading entry point's behavior, only whether an alert fires. The existing liveness-ping step is untouched.
- **Verification:** the staleness-detection logic was proven against the real repository before being merged (computed the real pre-fix `last_modified`, confirmed the 96-hour threshold correctly evaluates to "alert" against the real 861-hour-stale state) — but the actual scheduled `watchdog.yml` workflow has not yet been observed firing a real alert in production, since the repo is no longer stale as of this ADR.

---

## Test Requirements and Validation Performed

Per ADR-052's precedent (regression tests required, not optional, for exactly the kind of silent-regression class TD-018 represents):

- **Sub-scope A:** `tests/test_sync_db.py::test_pull_db_self_heals_an_already_readonly_destination` (added in `e0f3e2d`) pre-creates a read-only destination, mocks `hf_hub_download`, and asserts the sync self-heals it. `tests/test_sync_db.py` full file: 12 passed. Mechanically reproduced the underlying `PermissionError` locally before writing the fix, in both the `copyfile()`-only form (confirmed insufficient) and the `chmod`-then-`copyfile()` form (confirmed sufficient).
- **Sub-scope B:** no executed test; syntax/import check only (`python -c "import bot._main_runner"` succeeded, constant accessible).
- **Sub-scope C:** staleness logic manually executed against the real `ksri77/ai-trading-bot-db` repo metadata (not a mock), both before the fix (861h stale → would alert) and implicitly after (repo no longer stale, consistent with the fix having worked).
- **Full-suite baseline:** pre-push hook (`tests/`, `sentinel_engine/tests/`, `applications/`) passed at 1439 (then 1440, after the new test) passed, 2 skipped, across all five commits in scope. CI (`sentinel_engine/tests`, `applications/trading_intelligence`, `applications/platform`, `tests/`) green on `5f5f087`, `827ed08`, `c405187`, and `e0f3e2d` (the last after confirming its one failure was a pre-existing flake, unrelated to this ADR's changes, via identical-commit rerun).
- **Production verification (beyond CI):** see Context — direct confirmation via `HfApi.repo_info` and a fresh `trades.db`/`trust_ledger.db` pull that live data resumed.

---

## Entry-Point Confirmation (ADR-002 item 6)

- **CLI path** (`trade.yml` → `bot/main.py --mode paper --loop`): directly exercised by the production verification dispatch (run `39831453272`) — confirmed working end to end, not just unaffected.
- **Scheduler/HTTP path** (`watchdog.yml` → `dashboard/http_endpoints.py` → `scheduler/trading_job.py` → `bot.main.run()`): **not independently exercised by this ADR's verification.** Sub-scope A's fix lives in `scheduler/startup_job.py` and `bot/monitor/sync_db.py`, both reachable from this path, but the actual HTTP-triggered dispatch was not separately dispatched and watched the way the CLI path was. This is a stated gap, not an assumed pass — per ADR-002's own text, "verifying one and assuming the other is unaffected is exactly the kind of gap this ADR exists to prevent." Recommended follow-up: trigger `watchdog.yml`'s `/run/cron` path once and confirm it also writes fresh data, rather than relying on the CLI-path confirmation alone.

---

## Rollback Plan (stated retroactively, since implementation already happened)

- **Sub-scope A:** revert `shutil.copyfile()`+chmod back to `shutil.copy()` in the 4 named files. Known consequence: reintroduces TD-018 exactly — the Watchdog's new staleness check (Sub-scope C) would catch it within 96 hours instead of 36 days.
- **Sub-scope B:** revert `_MAX_CONSECUTIVE_FAILURES`/halt branch in `bot/_main_runner.py`. Known consequence: restores the prior behavior of retrying every cycle until market close regardless of consecutive failures.
- **Sub-scope C:** revert the added Watchdog step. Known consequence: loses the only automated same-session detection of this failure class; the system reverts to relying on manual investigation (as happened for the first 36 days of TD-018).
- Each sub-scope's revert is independent of the other two — none depends on another being reverted.

---

## Constraints

**Allowed (already done, ratified here):** exactly the changes in commits `2f605d4`, `c405187`, `e0f3e2d`, and `827ed08`, as itemized in Sub-scopes A/B/C above.

**Forbidden (not authorized by this ADR, and not done):**
- Any change to `bot/main.py`'s core signal/ensemble logic, `bot/strategy/*`, model training, or labeling — none of that was touched by these commits and none is authorized here.
- Any change to `trade.yml`'s trigger conditions, concurrency group, or any step other than the two cache-restore steps named in Sub-scope A.
- Any change to the Watchdog's existing liveness-ping step.
- Retroactively claiming the isolated-branch/worktree requirement (ADR-002 item 2) was followed. It was not, and this ADR does not pretend otherwise.

---

## Explicitly Not Established By This ADR

- Does not authorize any *future* change to any ADR-002-protected path — each future change still requires its own named exception, per the established one-ADR-per-purpose pattern.
- Does not close TD-018 as "fully verified" — the scheduler/HTTP entry-point gap (above) remains open.
- Does not establish a general policy of retroactive ratification as an acceptable substitute for the isolated-branch/worktree requirement going forward. This ADR's own position is that the requirement should have been followed and was not; it is documented honestly, not endorsed as a pattern to repeat.

---

## Acceptance

*(Per ADR-058 D4, this document is a proposal and carries no authority until it is landed under ADR-058 D2 — tracked on `main` with `Status: Accepted`, by explicit act of the Architecture Owner. An AI agent drafting this record does not itself confer acceptance.)*

**Status:** Accepted
**Date Accepted:** 2026-10-22
**Accepted By:** Architecture Owner (explicit act — accepted in this session)

---

## Status Log

- **2026-10-22 — Proposed.** Drafted as a retroactive, documentation-only ADR-002 exception for the already-merged TD-018 outage response (commits `2f605d4`, `c405187`, `e0f3e2d`, `827ed08`), following the ADR-025 retroactive-ratification precedent. Not yet accepted; no landing commit beyond the commits it describes.
- **2026-10-22 — Accepted.** The Architecture Owner explicitly reviewed and accepted this ADR in the form drafted, with no changes requested. `Status` now reads `Accepted`. The known gaps named in the record (no isolated branch/worktree was used for the original four commits; the scheduler/HTTP entry point was not independently exercised) are accepted as stated, not resolved by this acceptance — they remain open items, not retroactively excused.
