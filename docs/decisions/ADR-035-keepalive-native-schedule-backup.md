# ADR-035: Native GitHub Schedule Backup for `keepalive.yml` (Narrow ADR-002 Exception)

**Status:** Accepted
**Date:** 2026-08-16
**Decision Type:** Architecture — Narrow ADR-002 Exception (Accepted)
**Related ADRs:** ADR-002 (protected path this ADR would except), ADR-026 (structural precedent for this ADR's format and narrow-exception discipline)

---

## 1. Context

Investigating a report of zero BUY/SELL activity since 2026-07-20 (this
session), the trade-execution root cause was found and is already fixed:
`ADR-026`'s two market-data corrections (merged `8549702`,
2026-08-15) address a universal per-symbol data-fetch failure that was
tripping `bot/main.py`'s `_SYM_ERROR_SKIP_THRESHOLD` circuit breaker for
every symbol, every cycle, since ~2026-07-21 — meaning no candidate ever
reached the entry-gate pipeline. That fix has not yet been exercised by a
live run (last `trade.yml` run: 2026-08-14T14:30 UTC, pre-dating the fix
by a day).

While tracing *why* no run had fired since then, this session initially
misdiagnosed a ~2.5-day gap in `trade.yml`/`watchdog.yml` activity as an
active trigger outage. That diagnosis was wrong and is corrected here:
2026-08-14 was a Friday; both `keepalive.yml` (external cron-job.org,
`workflow_dispatch` only) and `watchdog.yml` (native GitHub `schedule:`,
`cron: '0 14,15,16,18,20 * * 1-5'`) are Mon-Fri-only by design, and the
gap was simply the weekend — confirmed via `gh run list --workflow=
watchdog.yml`, which shows the native-scheduled workflow firing reliably
on its 5x/weekday cadence right up through Friday, with no gap outside
the weekend.

That correction, however, surfaced a real, independent structural gap:
this repository has **two separate live-trading execution paths**
(`ADR-002`'s own documented finding — the CLI/GitHub-Actions path via
`trade.yml`, and the HTTP path via `watchdog.yml` → HF Space `/run/cron`
→ `scheduler.dispatcher.main()` → `bot.main.run()` in-process on the
Space). One of the two paths (`watchdog.yml`) already has native GitHub
scheduling and needs no change. The other does not:

- `.github/workflows/trade.yml:3-6` — `workflow_dispatch` only; no
  `schedule:` block. Its own comment (lines 4-5) says it is "Triggered by
  cron-job.org at 8:30, 10:30, 12:30, 2:30 PM CDT Mon-Fri (GitHub's
  built-in scheduler was too unreliable — replaced with external cron)."
- `.github/workflows/keepalive.yml:3-6` — also `workflow_dispatch` only,
  same external-cron dependency, same comment pattern. This is the file
  that actually dispatches `trade.yml`: its one job step (`Dispatch
  trade.yml`, lines 14-43) checks weekday and NYSE market hours (lines
  18-34), then `curl -X POST`s `trade.yml`'s `dispatches` API endpoint
  (lines 36-43) if both checks pass. Its own inline comment at line 43 —
  `"Dispatch failed — trade.yml will rely on its own cron"` — shows the
  original design already assumed a second, independent trigger existed
  as backup; today only one (cron-job.org) actually does, for both
  files.

So: if cron-job.org's account or a specific job genuinely goes down (not
merely "it's the weekend," which was this session's false alarm), there
is no fallback anywhere in this repository for the `trade.yml` execution
path — only the `watchdog.yml`/HF-Space path would keep running, and per
the point above, that path was itself broken by the same underlying bug
regardless of which one fired. This ADR closes that one gap.

`.github/workflows/keepalive.yml` is protected under
[ADR-002](ADR-002-bot-runtime-protection.md) (`.github/workflows/*.yml`).
Per ADR-002 §"Lifting This Protection," any change to it requires its
own, separately governed ADR naming the specific modules, an isolated
branch/worktree, a full regression pass, a stated rollback plan, and
verification of both known trading-trigger paths. This ADR is written to
meet that checklist for exactly the one correction in §3 below, and no
more.

## 2. Evidence

**The danger of a naive fix.** `trade.yml:20-26` already has a
`concurrency: {group: trading-bot, cancel-in-progress: true}` block,
whose own comment explains why: "Two simultaneous runs would read the
same `trades.db` from HuggingFace, submit duplicate orders, and race to
push back — last writer wins and the earlier cycle's trades are lost."
`cancel-in-progress: true` means *whichever dispatch arrives second
cancels whichever run is currently in progress* — including a healthy,
legitimately-running primary session. Since real runs take 5h20m+
(confirmed across every sampled run this session), a blind second
scheduled trigger — fired hours after the primary, while it's still
mid-session — would kill a working run, not add resilience. A safe
backup must not dispatch at all if the primary already has today's run
in flight or completed; simply adding a `schedule:` block without that
check would make reliability worse, not better.

**No existing guard against this exists today.** `keepalive.yml`'s
dispatch step (lines 14-43) checks weekday and market-hours only; it has
no check for whether `trade.yml` has already run today. Today this is
harmless because only one trigger source (cron-job.org) exists. Adding a
second source without also adding this check would introduce the exact
race the `concurrency` block's own comment warns about.

**No workflow YAML linting/test infrastructure exists in this repo** —
confirmed via repo-wide search for `actionlint`/`yamllint`. Verification
here is necessarily YAML-syntax-validity plus a live `workflow_dispatch`
dry run, not a pytest suite (see §6).

## 3. Decision

Authorize exactly one correction, confined to
`.github/workflows/keepalive.yml`:

### 3.1 Add a native `schedule:` trigger, and a same-day dedup guard

- **File/lines:** `.github/workflows/keepalive.yml:3-6` (trigger block)
  and `:14-43` (dispatch step).
- **Trigger block — corrected:**
  ```yaml
  on:
    # Primary: cron-job.org (external, workflow_dispatch). Backup: native
    # GitHub schedule below, in case the external trigger is down for a
    # reason other than the weekend/holiday calendar it already respects.
    workflow_dispatch:
    schedule:
      # 15:00 UTC = 10:00 AM CDT, Mon-Fri -- after cron-job.org's
      # documented 8:15 AM CDT slot, so the guard below sees a completed
      # or in-progress primary run and no-ops on a normal day.
      - cron: '0 15 * * 1-5'
  ```
- **Dispatch step — corrected:** before the existing `curl -X POST`
  dispatch call (current lines 36-43), add a check via `gh api` (or
  equivalent `curl` GET) against
  `GET /repos/${GITHUB_REPOSITORY}/actions/workflows/trade.yml/runs?
  created=>=<today's UTC date>` — if any run today has status
  `queued`/`in_progress`, or a `completed` run exists for today, log
  `"trade.yml already ran today — skipping duplicate dispatch."` and
  `exit 0` before reaching the POST. Only dispatch when no such run is
  found. The existing weekday/market-hours checks (current lines 18-34)
  are unchanged and still run first.
- **Permissions:** the job already declares `permissions: {actions:
  write}` (line 12) — unchanged. `write` is a superset of `read` for the
  same GitHub Actions permission scope, so this already covers the new
  `GET .../runs` dedup-guard call alongside the existing dispatch POST;
  no permissions change needed. (An earlier implementation pass briefly
  added a duplicate `actions: read` key alongside it, which is invalid
  YAML — caught immediately and corrected to this single-key form.)
- **Risk:** Low. The new schedule path only ever *dispatches* an
  existing, unmodified `trade.yml` — no change to `trade.yml` itself, no
  change to what a dispatch does once accepted. The dedup guard is the
  one piece of new logic; without it this would be Moderate risk (a
  plausible way to kill a healthy run), which is exactly why it's
  included rather than deferred.

## 4. Explicit Non-Authorization

This ADR, if accepted, authorizes **only** the one correction in §3,
inside `keepalive.yml`. It does not authorize:

- Any change to `trade.yml` — its `concurrency` block, its own
  `workflow_dispatch` inputs, and its (now partially stale) trigger-time
  comment are all unchanged. Correcting that comment is a separate,
  smaller, non-`bot/`-adjacent cleanup this ADR does not bundle in.
- Any change to `watchdog.yml` — it already has native scheduling and
  needs none.
- Any change to the weekday/market-hours check logic already in
  `keepalive.yml` (current lines 18-34) — reused as-is.
- Any change to the HF Space ping step (current lines 45-56).
- Any change to `bot/`, `dashboard/`, `scheduler/`, `database/`, or
  top-level `ledger/`.
- Any change to `sentinel_engine/` or `applications/`.
- Any change to `ADR-002` or `ADR-026`.
- Removing or reducing cron-job.org's role — this is additive backup
  only, not a replacement of the primary trigger.

This is a narrow, additive exception — it does not reopen
`.github/workflows/` generally and lapses in scope the moment this one
named correction is implemented and verified.

## 5. ADR-002 Compliance Requirements

Per `ADR-002` §"Lifting This Protection," before implementation begins:

1. **Named module:** `.github/workflows/keepalive.yml` only — the
   trigger block and the dispatch step's guard logic. No other file.
2. **Isolated branch/worktree**, not directly on `main`.
3. Only `keepalive.yml` itself references the changed paths; no other
   workflow YAML needs updating as a consequence of this change.
4. **Full regression pass** before and after (see §6 — necessarily
   YAML-validity plus live dry-run verification, not pytest, since no
   workflow-YAML test infrastructure exists in this repo).
5. **Rollback plan stated before the change starts** (see §7).
6. **Both known trading-trigger paths verified** — the CLI path
   (`trade.yml` → `python bot/main.py --mode paper --loop`, dispatched by
   `keepalive.yml`) and the `scheduler`-mediated HTTP path (`watchdog.yml`
   → `dashboard/http_endpoints.py` `GET /run/cron` →
   `scheduler.dispatcher.main()` → `scheduler/trading_job.py` →
   `bot.main.run()`) — confirming this change to `keepalive.yml` has no
   effect on the second path, since it touches neither `watchdog.yml` nor
   any file that path depends on.

## 6. Tests Required

- **YAML validity:** `python -c "import yaml; yaml.safe_load(open('.github/workflows/keepalive.yml'))"` (or equivalent) must pass — no existing linter to extend.
- **Manual `workflow_dispatch` dry run** of the modified `keepalive.yml`, twice:
  1. With no `trade.yml` run yet today — confirm the dispatch fires (matching today's existing behavior).
  2. Immediately after — confirm the second invocation's guard detects the just-dispatched (or already-running) `trade.yml` run and skips with the logged no-op message, **not** a second dispatch.
- **Cron syntax check:** confirm `'0 15 * * 1-5'` parses as intended (15:00 UTC, Mon-Fri) via `gh workflow view keepalive.yml` after push, or a local cron-expression validator.
- **Permissions check:** confirm the added `actions: read` scope is sufficient for the `GET .../runs` call by exercising it in the dry run above — a 403 there is a failed test, not a soft warning.
- No existing test suite (`pytest tests/`, `sentinel_engine/tests/`, `applications/trading_intelligence/`) is affected — none reference `.github/workflows/`. A full baseline re-run is not required by this change's own scope, but is still owed per ADR-002 §5.4 as a matter of process discipline, not because this change is expected to touch it.

## 7. Verification

- **CLI path:** confirm via the dry runs in §6 that `trade.yml` still
  gets dispatched normally on a day with no prior run, and that the new
  schedule/guard combination does not prevent or duplicate that dispatch.
- **Watchdog/HF entry path:** confirm by inspection (this ADR touches
  neither `watchdog.yml` nor any file it depends on) and by one live
  observation that `watchdog.yml`'s own next scheduled firing is
  unaffected — its `/run/cron` ping and this ADR's change are fully
  independent code paths.
- **The actual backup scenario** (cron-job.org silent, native schedule
  catches it) cannot be forced in a review — it will only be genuinely
  proven the first time cron-job.org actually misses a weekday slot.
  Until then, this ADR's confidence rests on the dry-run guard-logic
  verification above, not a live incident replay.

## 8. Rollback Plan

Single-file, additive-only change (a new `schedule:` block and a new
guard check ahead of existing logic) — no schema, no persistence, no
change to what a successful dispatch does. Rollback is a plain `git
revert` of the implementing commit, which removes the native schedule
and the guard check, returning `keepalive.yml` to today's
`workflow_dispatch`-only, cron-job.org-dependent behavior. No data-level
rollback step is required.

## 9. Consequences

**Positive:**
- Closes the one remaining single-point-of-failure trigger gap for the
  `trade.yml` execution path — `watchdog.yml`'s path already had native
  scheduling; this brings the other path to parity.
- The dedup guard makes the backup safe to coexist with the existing
  external trigger, rather than introducing a duplicate-dispatch/
  cancelled-run risk.
- Corrects this session's own earlier misdiagnosis (weekend gap treated
  as an outage) by recording, in writing, what the real gap was.

**Negative:**
- Does not fix, and is unrelated to, the actual root cause of the
  July-20-through-August-14 trading gap — that's `ADR-026`, already
  merged, unverified by a live run until the next one completes.
- Does not correct `trade.yml`'s own stale trigger-time comment
  (lines 4-5) — left as a known, separate, minor documentation gap.
- Introduces one new GitHub API call (read) per `keepalive.yml`
  invocation, all sources combined — negligible cost, noted for
  completeness.

## 10. Status

**Accepted.** This ADR is now authoritative per `docs/DOCUMENT_INDEX.md`'s
documentation hierarchy — the one correction named in §3 is authorized,
strictly bounded by §4's Explicit Non-Authorization list. Acceptance
authorizes the exception itself; it does not waive §5's ADR-002
compliance requirements (isolated branch/worktree, full regression pass,
stated rollback plan, both trading-trigger paths verified) or §6's
required tests — those remain preconditions to be satisfied during
implementation, not retroactively satisfied by acceptance.
