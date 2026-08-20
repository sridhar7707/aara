# ADR-042: ADR-002 Exception — CI Virtualenv Cache Key Python-Version Pinning

**Status:** Accepted
**Date:** 2026-08-20
**Related ADRs:** ADR-002 (protected path this ADR would except), ADR-006 (prior, narrower `.github/workflows/ci.yml` exception — does not cover this change; see "Relationship" below)

## Context

CI's `test` job (`.github/workflows/ci.yml`) caches its Python virtualenv to
avoid reinstalling `torch` and the rest of `requirements.txt` on every run:

```yaml
- name: Cache virtualenv
  uses: actions/cache@v6
  id: cache-venv
  with:
    path: .venv
    key: venv-${{ runner.os }}-py311-${{ hashFiles('requirements.txt') }}
```

The `py311` segment is a **literal string**, not tied to the actual resolved
Python interpreter version `actions/setup-python@v6` provides. A read-only
investigation (this session, 2026-08-20) traced the following via
`gh run view --log` against actual CI run history, not inferred:

- Run `32379382747` ("ADR-040 merge", 2026-08-20T14:20 UTC, **last known
  green CI**): `pythonLocation: /opt/hostedtoolcache/Python/3.11.15/x64`.
  `Cache virtualenv` hit key
  `venv-Linux-py311-5cbcdd61c70ba0e99fb6933c6f95cfa53c7f269a2f0d1ff198f38d7515e0d20c`.
  All test steps passed.
- Run `32394841845` ("ADR-041 merge", 2026-08-20T16:56 UTC, **first
  failure**) and every run since (`32397823467`, `32404676917`):
  `pythonLocation: /opt/hostedtoolcache/Python/3.11.16/x64`. `Cache
  virtualenv` hit the **identical** key (`requirements.txt` unchanged across
  all these commits). `Sentinel brand governance validation` failed with
  `ModuleNotFoundError: No module named 'yaml'`; `Run sentinel_engine
  boundary tests` failed with `/opt/hostedtoolcache/Python/3.11.16/x64/bin/python:
  No module named pytest`.

Root cause: `python -m venv .venv` (in the `Install dependencies` step,
which only runs on a cache miss) creates `.venv/bin/python` as a symlink to
the exact base interpreter that built it — at the time this cache was
populated, `/opt/hostedtoolcache/Python/3.11.15/x64/bin/python3.11`. GitHub's
`ubuntu-latest` runner image rotated its bundled Python 3.11 patch version to
3.11.16 between the two runs above. Because the cache key never encoded the
Python version, the stale cache — whose `.venv/bin/python` symlink now points
at a path that no longer exists on the runner — keeps matching and keeps
being restored. Bash's PATH search silently skips a dangling symlink and
falls through to the next `python` on `PATH`: the bare, dependency-less
`/opt/hostedtoolcache/Python/3.11.16/x64/bin/python`. `requirements.txt`
already correctly declares `pytest>=7.4.0` and `PyYAML>=6.0.0` (confirmed by
inspection) — this is a CI cache-invalidation defect, not a missing
dependency declaration, and it has existed since the cache key was
introduced (`b5d8bf9`, 2026-07-25); it was dormant until the runner's image
update on 2026-08-20 exposed it. No commit in this repository (including the
three most recent ones, which triggered the observed failures) touched
`.github/workflows/ci.yml`, `requirements.txt`, or any Python-environment
setup.

`.github/workflows/ci.yml` is protected under ADR-002 ("no file changes of
any kind" applies to `.github/workflows/*.yml` as a whole, confirmed by
ADR-006/017/018/041 precedent — none of them treat `ci.yml` as exempt from
the freeze merely because it isn't a live-trading entry point). ADR-006
already granted `ci.yml` one narrow exception (appending the
`sentinel_engine` boundary-test step), but ADR-006's own Constraints
explicitly forbid "modification of any existing CI step" and "change to
trigger conditions, job matrix, or existing test invocation" — both of which
this fix requires (adding an `id:` to the existing `Set up Python` step;
changing the existing `Cache virtualenv` step's `key:`). ADR-006's exception
therefore does not cover this change; a new, standalone exception is
required, per the same pattern ADR-017/018/041 each followed rather than
reusing or amending an earlier exception ADR.

## Decision

Authorize one narrow, additive-only exception to ADR-002's
`.github/workflows/*.yml` freeze: pin the CI virtualenv cache key to the
resolved Python version instead of a literal `py311` tag, so a future
runner-image Python patch bump invalidates the cache and forces a fresh
install, rather than restoring an interpreter-mismatched, silently-broken
`.venv`.

## Why This Is a Narrow Exception to ADR-002

- Touches only `.github/workflows/ci.yml`, and only two lines within it —
  not `trade.yml`, `watchdog.yml`, or any other workflow file ADR-002
  protects.
- Changes no trigger condition (`on:` block), no job matrix, and no existing
  test invocation (`python -m pytest ...` commands are untouched, byte for
  byte).
- Is a pure cache-key computation fix — it adds no new step, no new job, no
  new permission, and no new external action.
- Is the exact class of change ADR-002 exists to gate (a `.github/workflows/`
  edit), not the class of change ADR-002 exists to prevent (uncoordinated
  changes near the two live-trading entry points). Neither `trade.yml` nor
  `watchdog.yml` is touched, referenced, or affected by this change.

## Scope

The following protected path (frozen by
[ADR-002](ADR-002-bot-runtime-protection.md), and not authorized by
[ADR-006](ADR-006-confidence-integrity-phase1-exception.md), whose own scope
explicitly excludes modification of existing CI steps) is authorized for the
two additive-only edits below, and no others:

- `.github/workflows/ci.yml`

## Constraints

**Allowed:**

- Add `id: setup-python` to the existing `Set up Python` step (no other
  attribute of that step changed).
- Change only the `Cache virtualenv` step's `key:` value, from:
  ```yaml
  key: venv-${{ runner.os }}-py311-${{ hashFiles('requirements.txt') }}
  ```
  to:
  ```yaml
  key: venv-${{ runner.os }}-${{ steps.setup-python.outputs.python-version }}-${{ hashFiles('requirements.txt') }}
  ```
- The natural consequence of the key change — a cache miss on first run
  under the new key, and a fresh `.venv` build via the existing (unmodified)
  `Install dependencies` step logic.

**Forbidden:**

- Any other line in `.github/workflows/ci.yml` — including the `Install
  dependencies` step's install commands, the `Activate venv` step, the
  architecture-review step, the brand-governance step, any of the four
  `python -m pytest ...` test-invocation steps, or the Telegram
  notification step.
- Any change to `ci.yml`'s trigger conditions (`on:` block) or job matrix.
- Any change to any dependency manifest (`requirements.txt`,
  `requirements_space.txt`, `requirements_trading_intelligence.txt`,
  `requirements_wealth_intelligence.txt`, `pyproject.toml`, or any other).
- Any change to `trade.yml`, `watchdog.yml`, `keepalive.yml`, `deploy_ui.yml`,
  `deploy_trading_intelligence.yml`, `deploy_wealth_intelligence.yml`,
  `premarket.yml`, `retrain.yml`, `secret-scan.yml`, or any workflow file
  other than `ci.yml`.
- Any source-code or test-code change of any kind as part of this
  remediation — this ADR authorizes a CI cache-key fix only.
- Any weakening, bypass, or skip of pre-push verification or any existing CI
  gate (`arch_review.py`, brand-governance validation, or any test step) —
  the fix must make the existing gates work as originally intended, not
  loosen them.
- Reopening any part of `.github/workflows/ci.yml` beyond the two named
  edits, or any part of ADR-006's own already-granted scope.

## Technical Verification Basis

Verified against actual CI run history via `gh run view --log`, not
inferred from workflow-file inspection alone:

- **Green baseline** (run `32379382747`): `pythonLocation:
  /opt/hostedtoolcache/Python/3.11.15/x64`; cache key
  `venv-Linux-py311-5cbcdd61c70ba0e99fb6933c6f95cfa53c7f269a2f0d1ff198f38d7515e0d20c`
  hit; all steps green.
- **First and subsequent failures** (runs `32394841845`, `32397823467`,
  `32404676917`): `pythonLocation:
  /opt/hostedtoolcache/Python/3.11.16/x64`; **identical** cache key still
  hit (no `requirements.txt` change across any of these commits, confirmed
  via `git log --oneline -- requirements.txt`); `Sentinel brand governance
  validation` and `Run sentinel_engine boundary tests` both fail with
  `ModuleNotFoundError`-class errors, both naming the bare hostedtoolcache
  interpreter as the executable that ran, not `.venv/bin/python`.
- `scripts/arch_review.py` (the CI-enforced structural gate) was confirmed,
  by direct inspection, to scan only `.py` files under `bot/`, `dashboard/`,
  `database/`, `scripts/`, `config.py` — it does not inspect
  `.github/workflows/*.yml` and imposes no technical constraint on this
  change.
- `git blame` on the cache-key line confirms it has been unchanged since
  `b5d8bf9` (2026-07-25) — this is a pre-existing latent defect, not a
  regression introduced by any recent commit.

## Rollback Plan

Stated before implementation begins, per ADR-002's "Lifting This Protection"
item 5:

- **If not yet merged:** revert the two-line diff (`id:` addition,
  `key:` value). No other state to unwind.
- **If merged and the change misbehaves** (e.g., the new key computation
  produces an unexpected value, or cache restore fails unexpectedly): revert
  the same two-line diff. The prior key is restored verbatim from `git log`.
  Worst case during rollback is a return to the pre-fix defect (silent
  fallback to a dependency-less interpreter on the next runner-image
  rotation) — a known, already-diagnosed failure mode, not a new one.
- This change touches no `bot/`, `database/`, or `ledger/` state, writes no
  persistent data, and has no code path connecting to either live-trading
  entry point, so rollback carries no risk to trading data or either entry
  point.

## Validation / Testing Expectations

Before this ADR's implementation is considered satisfied:

- The cache key's computed value changes when `steps.setup-python.outputs.python-version`
  changes (verified by inspecting the `Cache virtualenv` step's resolved
  `key:` in a CI run log, or by a controlled `python-version` bump).
- A fresh `.venv` is built (cache miss, `Install dependencies` step actually
  runs) on the first CI run under the new key.
- `.venv/bin/python` resolves to the same interpreter version
  `actions/setup-python@v6` reports for that run (no dangling symlink).
- `python -m pytest sentinel_engine/tests -v --tb=short` executes using the
  venv's interpreter (confirmed via the step's log not naming
  `/opt/hostedtoolcache/.../bin/python` directly as the failing executable,
  and via the run completing without `ModuleNotFoundError`).
- `import yaml` succeeds in the `Sentinel brand governance validation` step.
- All four existing `python -m pytest ...` steps in `ci.yml` pass, and
  `scripts/arch_review.py` runs with its existing baseline (0 block(s), 0
  error(s)).
- The CLI live-trading path (`trade.yml` → `python bot/main.py --mode paper
  --loop`) is explicitly confirmed unaffected — stated, not assumed, per
  ADR-002 item 6, though this change has no code path connecting to it.
- The HTTP live-trading path (`watchdog.yml` → `GET /run/cron` →
  `scheduler.dispatcher.main()` → `bot.main.run()`) is explicitly confirmed
  unaffected, for the same reason.
- `git diff --name-only` against the base commit shows only
  `.github/workflows/ci.yml` changed, and `git diff` on that file shows only
  the two authorized edits — no unrelated file or line touched.

## Explicitly Not Established By This ADR

- No general policy on `.github/workflows/` cache-key design is adopted
  platform-wide.
- No broader review or rewrite of `ci.yml`'s caching strategy, job
  structure, or dependency-installation approach is authorized.
- This ADR does not reopen, extend, or restate ADR-006's own
  already-granted, separate `ci.yml` exception (the `sentinel_engine`
  boundary-test step remains governed solely by ADR-006).
- This ADR does not touch or extend ADR-017, ADR-018, ADR-040, or ADR-041 —
  none of which concern `ci.yml`.
- Whether the runner's Python 3.11 patch version itself should be pinned
  (e.g., `python-version: '3.11.16'` instead of `'3.11'`) is a separate,
  out-of-scope question — this ADR fixes cache *invalidation*, not runner
  *version selection*.

## Relationship to ADR-002 and ADR-006

This ADR provides a narrowly scoped exception to ADR-002's freeze only for
`.github/workflows/ci.yml`, and only for the two edits named in
Scope/Constraints above. All other ADR-002 protections remain in force,
unchanged — including every other `.github/workflows/*.yml` file, `bot/`,
`dashboard/`, `scheduler/`, `database/`, and top-level `ledger/`.

This ADR does not reopen, amend, or extend ADR-006's own separate `ci.yml`
exception (limited to appending the `sentinel_engine` boundary-test step);
that authorization stands unchanged and independent of this one. Per
`docs/AI_AGENT_GUIDELINES.md` §6 ("ADRs define decisions — nothing overrides
them except a superseding ADR") and consistent with how ADR-006/017/018/041
each relate to ADR-002 as separate, standalone exceptions rather than
amendments to one another, this is issued as a new, standalone ADR.

## Status

**Accepted.** This ADR authorizes the two edits named in §Constraints; it
does not waive the ADR-002 compliance requirements (isolated
branch/worktree, full validation pass, stated rollback plan, both
trading-trigger paths verified) — those remain preconditions to be
satisfied during implementation.
