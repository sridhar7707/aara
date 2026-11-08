# ADR-084: Daily Forward-Test Snapshot on GitHub Actions

**Status:** Proposed (needs the Architecture Owner's acceptance; workflows are protected under ADR-002)
**Decision Type:** New workflow that runs the ADR-082 forward log daily. It does not touch trading, the stock bot, or any entry path.

## Decision
1. **Schedule.** `forward_log.yml` runs weekdays at 23:00 UTC (19:00 EDT, 18:00 EST), after the US close. GitHub's scheduler can delay or skip runs, and this repo already moved its trading job to an external cron for that reason. If the schedule proves unreliable, the same workflow is started with `workflow_dispatch` from an external cron, as `trade.yml` does.
2. **Retry.** A second run after midnight UTC covers a bar that Yahoo publishes late. If the first run logged the day, the retry is a SKIP.
3. **Persistence.** Runners are wiped after each job. Each run commits its new rows to an append-only branch, `forward-log-data`, which contains only data. The workflow never pushes to `main` and never edits code.
4. **Skips are not failures; errors are.** Weekends, holidays, stale price bars and already-logged days exit 0 as `SKIP`. Empty downloads, incomplete days, a benchmark with no price, and half-written logs exit 1 as `ERROR` and fail the job, so someone looks.
5. **Permissions.** `contents: write` is granted for the push to `forward-log-data`. The workflow uses no secrets: the data sources are public (Wikipedia and Yahoo Finance).
6. **Concurrency.** One run at a time, and runs are never cancelled mid-write.

## Setup required once
- Create the empty `forward-log-data` branch before the first run, for example as an orphan branch with a single empty commit. The checkout step fails without it.
- Merge PR #15 first. Scheduled runs use the default branch, and the script lives on the forward-log branch until then.

## Risks
- Yahoo Finance may rate-limit GitHub's IP addresses, which would show as incomplete days (refused and logged as SKIP). Monitor the skip count in the first month.
- A missed day is not backfilled. No backfill path exists, and adding one needs its own ADR. The evaluation masks forward returns across the gap, so a missed day shortens the record rather than corrupting it.
- Ownership of the `forward-log-data` branch means its history is part of the audit record. It must not be rewritten.

## Rollback
Disable or delete `forward_log.yml`. The `forward-log-data` branch is kept as the record of every snapshot taken.
