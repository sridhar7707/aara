# ADR-017: ADR-002 Exception — Deploy `analytics/` to Dashboard Space

**Status:** Accepted
**Date:** 2026-08-13

## Scope

The following protected path (frozen by [ADR-002](ADR-002-bot-runtime-protection.md))
is authorized for one additive-only change:

- `.github/workflows/deploy_ui.yml`

## Reason

The HF Space (`ksri77/ai-trading-bot`) has been in `RUNTIME_ERROR` since
2026-07-30 (confirmed live via the HF Space runtime API):

```
ModuleNotFoundError: No module named 'analytics'
  at dashboard/app.py:91 → dashboard/components/phase2_preview.py:19
  → from analytics.regime_views import regime_performance, RegimePerformance
```

`dashboard/components/phase2_preview.py` (added in commit `778f2bd`,
2026-07-30) imports `analytics/regime_views.py` at module load time.
`deploy_ui.yml`'s Space-staging step copies `dashboard/`, `database/`,
`bot/`, `ledger/`, `scheduler/`, `scripts/` into the deploy, but never
`analytics/` — so every deploy since `778f2bd` (14+ successful "push"
runs, per `gh run list`) has shipped code that crashes on Space startup
before serving a single request.

This also silently breaks the second of ADR-002's two documented live-trading
entry points: `watchdog.yml`'s ping → `dashboard/http_endpoints.py`
`GET /run/cron` → `scheduler.dispatcher.main()` → `bot.main.run()`. Every
call to that endpoint has returned 503 since the Space entered
`RUNTIME_ERROR`. `watchdog.yml` didn't surface this in GitHub Actions status
because its Python script catches the resulting exception and only sends a
Telegram alert — the job itself still reports "success."

A repo-wide check (`grep -r "analytics" .github/workflows/`) confirms no
workflow file other than `deploy_ui.yml` references the `analytics/`
package — the only other match anywhere in `.github/workflows/` is an
unrelated comment in `deploy_ui.yml` itself about `database/analytics_service.py`,
a different module. This satisfies ADR-002 item 3: no other workflow YAML
file needs updating alongside this one.

## Constraints

**Allowed:**

- Exactly one new Space-staging line in `deploy_ui.yml`, matching the
  existing pattern for the other copied packages:
  ```python
  # analytics package (dashboard/components/phase2_preview.py imports
  # analytics.regime_views at module load — required for the Space to boot)
  shutil.copytree("analytics", staging / "analytics",
                  ignore=shutil.ignore_patterns("__pycache__"))
  ```
- Nothing else. No other line in `deploy_ui.yml` is touched, reformatted,
  or re-commented as part of this change.

**Forbidden:**

- Any change to `trade.yml`, `watchdog.yml`, `keepalive.yml`, `ci.yml`,
  `premarket.yml`, `retrain.yml`, `secret-scan.yml`, or any workflow file
  other than `deploy_ui.yml`.
- Any change to `deploy_ui.yml`'s trigger conditions, job structure, existing
  `copytree` calls (including their comments), `requirements_space.txt`
  selection, or the README/metadata-writing step.
- Any change to `analytics/`, `dashboard/`, `bot/`, `scheduler/`,
  `database/`, or `ledger/` source code — this ADR authorizes copying an
  existing package into the deploy staging area, not modifying its contents
  or behavior.
- Expanding `requirements_space.txt`. If `analytics/`'s own dependencies
  turn out not to be covered by the Space's existing minimal requirements
  file, that is a separate gap to investigate and scope on its own — not
  folded into this ADR.

## Rollback Plan

Stated before implementation begins, per ADR-002 item 5:

- **If the change hasn't been deployed yet:** revert the single added
  `copytree` line in `deploy_ui.yml`. No other state to unwind.
- **If the change has been deployed and the Space still fails or regresses
  in a new way:** redeploy the prior working Space commit (the last
  `deploy_ui.yml` run before this ADR's change) via the HF Hub API
  (`HfApi().restore_space()` or equivalent) or by re-running the previous
  `deploy_ui.yml` workflow run against the prior commit SHA. The Space has
  been in `RUNTIME_ERROR` since 2026-07-30 regardless, so rollback restores
  a known-broken-but-no-worse state at minimum, and a full recovery to the
  last known-good Space state (pre-`778f2bd`, 2026-07-29) remains available
  as a fallback if needed.
- No `bot/`, `database/`, or `ledger/` state is touched by this change, so
  rollback carries no risk to trading data or the live write path.

## Validation

Before this ADR is considered satisfied:

- Full test suite passes before and after (baseline ~1200+ tests, 0
  failures, per `docs/implementation/SENTINEL_EXTRACTION_PLAN.md`).
- A deploy using the updated `deploy_ui.yml` results in the HF Space
  reaching `RUNNING` stage (verified via `HfApi().space_info()` or
  equivalent) — not merely "files uploaded successfully."
- `GET /run/cron` on the deployed Space returns a body containing
  `"accepted"` (`watchdog.yml`'s own success condition), confirming the
  second live-trading entry point is actually restored, not just that the
  dashboard UI renders.
- The CLI trading path (`trade.yml` → `bot/main.py --mode paper --loop`) is
  explicitly confirmed unaffected — it doesn't consume `deploy_ui.yml` or
  the Space, but ADR-002 criterion 6 requires this stated, not assumed.

## Relationship to ADR-002, ADR-004, and ADR-006

This ADR supersedes ADR-002's freeze *only* for `.github/workflows/deploy_ui.yml`,
and only for the single additive `copytree` line above. All other ADR-002
protections remain in force unchanged — including the four files ADR-006
already reopened (`ledger/schema.sql`, `ledger/ledger.py`,
`bot/trust_ledger/ids.py`, `.github/workflows/ci.yml`), which this ADR does
not touch or extend. This ADR has no relationship to the Option A/B/C
ledger-ownership choice deferred by [ADR-004](ADR-004-sentinel-ledger-ownership-strategy.md).
