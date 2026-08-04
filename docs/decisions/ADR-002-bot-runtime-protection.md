# ADR-002: Bot Runtime Protection During Phase 2A Preparation

**Status:** Accepted
**Date:** 2026-08-04

## Context

`bot/` is live production code, not a sandbox. Per `BOT_RUNTIME_BASELINE.md` and
`BOT_DEPENDENCY_MAP.md`:

- Trading is triggered on a real schedule (external cron-job.org, since GitHub's
  native scheduler was found unreliable — per comments in `trade.yml`/`keepalive.yml`),
  executing paper trades via Alpaca during an active Phase 1A 30-day live-validation
  window.
- **Two independent entry points** exist into `bot/` trading logic: the CLI path
  (`trade.yml` → `python bot/main.py --mode paper --loop`) and a second,
  previously-undocumented HTTP path (`watchdog.yml`'s "health check" ping →
  `dashboard/http_endpoints.py` `GET /run/cron` → `scheduler.dispatcher.main()` →
  `scheduler/trading_job.py` → `bot.main.run()`). The watchdog ping is not passive —
  every GET to `/run/cron` unconditionally spawns a real dispatch.
- This codebase has had real production incidents from exactly this class of
  change: an undefined-name bug in `bot/main.py` shipped unnoticed for days, and
  trading workflows went dark for 3+ days with no root cause ever conclusively
  found (per project history).
- `dashboard/` imports `bot` directly from 33 files; `database/` from 2 files
  (plus 4 files where `bot/` imports `database/` back); `scheduler/` imports `bot`
  from 3 files via deferred (function-local) imports specifically in the live
  dispatch path described above.

None of this has been touched by the `sentinel_engine/` extraction work (ADR-001) —
confirmed zero coupling between `sentinel_engine/` and `bot/` in either direction.
But "no coupling yet" is not the same as "safe to start moving things."

## Decision

Until superseded by a dedicated ADR that explicitly authorizes it, the following are
**protected — no moves, no import changes, no refactors, no file changes of any kind**:

- `bot/` (all submodules)
- `dashboard/` (all files, including `http_endpoints.py`)
- `.github/workflows/*.yml`
- `scheduler/` (all files — confirmed part of the live trading trigger path, not a
  separate/legacy system as originally suspected)
- `database/`, top-level `ledger/`, and the SQLite files they manage

**Permitted in this area:** read-only investigation and additive documentation
(analysis docs, ADRs, architecture-boundary docs). This ADR does not restrict work
inside `sentinel_engine/`, `docs/`, or other packages with zero coupling to the
above.

## Lifting This Protection

A future ADR may supersede this one for a *specific, scoped* piece of work (e.g.,
"move `bot/strategy/` only") when all of the following hold:

1. The specific modules to move are named, with their `BOT_EXTRACTION_CANDIDATES.md`
   risk tier and coupling count restated.
2. Work happens in an isolated branch or worktree, not directly on `main`.
3. All 8 workflow YAML files that reference the moved paths are updated in the same
   change, not a follow-up.
4. The full test suite passes both before and after (baseline: per
   `docs/implementation/SENTINEL_EXTRACTION_PLAN.md`, ~1200+ tests, 0 failures).
5. A rollback plan is stated before the change starts, not written retroactively.
6. Given the two-entry-point finding above, both the CLI path and the
   `scheduler`-mediated HTTP path are verified against the change — verifying one
   and assuming the other is unaffected is exactly the kind of gap this ADR exists
   to prevent.

## Consequences

- Phase 2 extraction (`bot/` → `applications/trading_intelligence/`, per
  `CODEBASE_MIGRATION_MATRIX.md`) does not start as a side effect of any
  documentation or `sentinel_engine/` work. It requires its own ADR.
- `scheduler/`'s role must be treated as first-class in any future dependency
  analysis of this codebase — the original `BOT_DEPENDENCY_MAP.md` pass missed it
  because it only checked top-level imports, not function-local ones. Future static
  analysis of this codebase should account for deferred imports.
