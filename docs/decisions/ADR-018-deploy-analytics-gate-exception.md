# ADR-018: ADR-002 Exception — Add `analytics/` to Deploy-Change Detection Gate

**Status:** Accepted
**Date:** 2026-08-13

## Scope

The following line, still frozen by [ADR-002](ADR-002-bot-runtime-protection.md)
and not authorized by [ADR-017](ADR-017-deploy-analytics-exception.md), is
authorized for one additive-only change:

- `.github/workflows/deploy_ui.yml`, line 40 (the deploy-change-detection
  regex inside the "Check whether dashboard files changed" step)

## Reason

ADR-017 fixed the HF Space's `RUNTIME_ERROR` by adding `analytics/` to
`deploy_ui.yml`'s Space-staging `copytree` calls — `dashboard/components/phase2_preview.py`
imports `analytics.regime_views` at module load, and the Space could not boot
without that package present in the deploy.

ADR-017 deliberately did not touch anything else in `deploy_ui.yml`,
including the separate "Check whether dashboard files changed" step at lines
31–46, which gates whether a push-triggered deploy happens at all:

```yaml
elif git diff --name-only HEAD~1 HEAD \
      | grep -Eq '^(dashboard/|database/|bot/|ledger/|scheduler/|scripts/|requirements_space\.txt|config\.py|\.github/workflows/deploy_ui\.yml)'; then
```

This regex still does not include `analytics/`. A future commit that
modifies only `analytics/` (no `dashboard/`, `database/`, `bot/`, `ledger/`,
`scheduler/`, or `scripts/` change in the same commit) would set
`deploy=false` and silently skip the Space rebuild — leaving the previously
deployed `analytics/` snapshot in place indefinitely, undetected, via the
same class of gap ADR-017 just closed for the `copytree` step. This ADR
closes the remaining half of that gap.

A repo-wide check (`grep -r "analytics" .github/workflows/`) — reused from
ADR-017's own verification — confirms no workflow file other than
`deploy_ui.yml` references `analytics/` in any form. No other of the 8
workflow YAML files needs a corresponding update.

## Constraints

**Allowed:**

- Adding `analytics/` to the regex alternation on line 40 only:

  ```diff
  - | grep -Eq '^(dashboard/|database/|bot/|ledger/|scheduler/|scripts/|requirements_space\.txt|config\.py|\.github/workflows/deploy_ui\.yml)'; then
  + | grep -Eq '^(dashboard/|database/|bot/|ledger/|scheduler/|scripts/|analytics/|requirements_space\.txt|config\.py|\.github/workflows/deploy_ui\.yml)'; then
  ```

- Nothing else. No other character on line 40, and no other line in
  `deploy_ui.yml`, is touched, reformatted, or re-commented.

**Forbidden:**

- Any change to `trade.yml`, `watchdog.yml`, `keepalive.yml`, `ci.yml`,
  `premarket.yml`, `retrain.yml`, `secret-scan.yml`, or any workflow file
  other than `deploy_ui.yml`.
- Any change to `deploy_ui.yml`'s trigger conditions (`on:` block), job
  structure, the `copytree`/`copy` calls already authorized by ADR-017,
  `requirements_space.txt` selection, or the README/metadata-writing step.
- Any change to `analytics/`, `dashboard/`, `bot/`, `scheduler/`,
  `database/`, or `ledger/` source code.
- Broadening this exception to cover any line in `deploy_ui.yml` other than
  line 40 — including re-opening ADR-017's already-authorized-and-executed
  `copytree` addition, which remains governed solely by ADR-017.

## Rollback Plan

Stated before implementation begins, per ADR-002 item 5:

- **If not yet deployed:** revert the one-word regex addition (`analytics/`
  removed from the alternation). No other state to unwind — this line only
  affects whether a future commit triggers a deploy, not any currently
  running system.
- **If deployed and the gate misbehaves** (e.g., unexpectedly triggers
  deploys on unrelated commits due to a regex error): revert the line; the
  prior regex is restored verbatim from `git log`, and the worst-case
  interim effect is redundant Space rebuilds, not incorrect ones — the
  Space's actual file contents come from the `copytree` calls (ADR-017,
  unaffected by this ADR), not from this gate.
- This change touches no `bot/`, `database/`, or `ledger/` state and carries
  no risk to trading data or the live write path.

## Validation

Before this ADR is considered satisfied:

- Full test suite passes before and after (baseline ~1200+ tests, 0
  failures, per `docs/implementation/SENTINEL_EXTRACTION_PLAN.md`; current
  observed baseline this session: 1483 passed, 2 skipped, 0 failed).
- A synthetic or real commit that modifies only a file under `analytics/`
  is confirmed to set `deploy=true` (previously would have set
  `deploy=false`), verifying the gate now recognizes `analytics/` changes.
- A commit that modifies none of the listed directories/files still sets
  `deploy=false`, confirming the fix didn't broaden the gate beyond its
  intended purpose (e.g., no accidental regex greediness matching unrelated
  paths).
- The CLI trading path (`trade.yml` → `bot/main.py --mode paper --loop`) is
  explicitly confirmed unaffected — per ADR-002 criterion 6, stated not
  assumed, though this change has no code path connecting to it.
- The HTTP live-trading entry path (`watchdog.yml` → `GET /run/cron` →
  `scheduler.dispatcher.main()` → `bot.main.run()`) is explicitly verified,
  not assumed, per ADR-002 criterion 6: after any deploy triggered by the
  `analytics/` gate addition, `GET /run/cron` on the deployed Space returns
  HTTP 200 with a body containing `"accepted"`.
- The HF Space remains at `RUNNING` stage after any deploy triggered
  through the updated gate (verified via `HfApi().space_info()` or
  equivalent), consistent with ADR-017's own validation.

## Relationship to ADR-002, ADR-017 (and ADR-004, ADR-006)

This ADR supersedes ADR-002's freeze — not ADR-017's, which never
authorized or touched this line and left it frozen — only for
`.github/workflows/deploy_ui.yml` line 40, and only for adding `analytics/`
to the existing regex alternation. It does not reopen, modify, or restate
ADR-017's own authorization (the `copytree` addition), which stands as
already executed and validated under ADR-017 alone.

All ADR-002 protections not explicitly named here remain in force
unchanged — including the four files ADR-006 reopened (`ledger/schema.sql`,
`ledger/ledger.py`, `bot/trust_ledger/ids.py`, `.github/workflows/ci.yml`)
and every line of `deploy_ui.yml` not named in this ADR's Scope. This ADR
has no relationship to the Option A/B/C ledger-ownership choice deferred by
ADR-004.

Per `docs/AI_AGENT_GUIDELINES.md` §6 ("ADRs define decisions — nothing
overrides them except a superseding ADR") and `docs/DOCUMENT_INDEX.md` §5,
this is issued as a new, standalone ADR rather than an in-place edit to
ADR-017 — consistent with how ADR-006 relates to ADR-002.
