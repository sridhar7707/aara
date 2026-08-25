# ADR-052: ADR-002 Exception — Retrain Workflow Backtest Quality Gate Enforcement

**Status:** Accepted
**Date Proposed:** 2026-08-24
**Related ADRs:** ADR-002 (protected path this ADR would except), ADR-006
(prior, narrower `.github/workflows/ci.yml` exception — does not cover this
file), ADR-042 (prior, narrower `.github/workflows/ci.yml` exception — does
not cover this file; cited here only as the closest structural precedent
for a pure CI-workflow exception)

---

## Context

`.github/workflows/retrain.yml` runs a weekly (and manually dispatchable)
model-retraining pipeline. Its "Backtest quality gate" step is intended to
block a bad model from reaching production:

```yaml
- name: Backtest quality gate
  continue-on-error: true   # informational during paper trading — don't block model push
  run: python scripts/backtest_gate.py
```

A read-only investigation (this session, 2026-08-24) traced the actual
execution semantics of this step against `scripts/backtest_gate.py`'s full
source and the rest of `retrain.yml`'s job:

- `scripts/backtest_gate.py::main()` is correctly implemented: it calls
  `sys.exit(1)` on every genuine failure path (no backtest results at all;
  average Sharpe/return/drawdown/win-rate missing the configured thresholds
  — lines 72-73, 109-111 of that file). The gate's own pass/fail logic is
  not in question and is not touched by this ADR.
- `continue-on-error: true` on the step tells GitHub Actions to record that
  step's failure as non-fatal to the job's overall status.
- The very next step, "Push model to HuggingFace" (line 87-91 of
  `retrain.yml`), carries **no `if:` condition of its own**, which defaults
  to GitHub Actions' implicit `if: success()`. Because the gate step's
  failure was already absorbed by `continue-on-error`, the job's running
  status remains "success" at the point this default is evaluated, and the
  push proceeds regardless of the gate's actual verdict.
- **Confirmed: a failing quality gate today does not prevent the push.**
  The gate is currently advisory only, contradicting its own stated purpose
  ("Backtest quality gate: run backtest on holdout data and block model
  push if metrics fail" — `scripts/backtest_gate.py`'s own module
  docstring).

`.github/workflows/retrain.yml` is protected under ADR-002
("`.github/workflows/*.yml`" — "no file changes of any kind"). No existing
exception covers it:

- ADR-006 authorizes exactly one workflow file, `.github/workflows/ci.yml`,
  for exactly one purpose (appending the `sentinel_engine` boundary-test
  step), and its own Forbidden list explicitly excludes "any change to
  `trade.yml`, `watchdog.yml`, `keepalive.yml`, or other workflow files."
- ADR-009 and ADR-045 (the two exceptions authorizing `bot/`-side
  integration calls) both explicitly forbid "any `.github/workflows/*.yml`
  change" and neither touches or references `retrain.yml`.
- ADR-042 (CI virtualenv cache-key fix) is scoped exclusively to
  `.github/workflows/ci.yml` and its own Forbidden list explicitly names
  `retrain.yml` among the workflow files it does *not* authorize touching.

No existing Accepted ADR authorizes any change to `retrain.yml`. A new,
standalone exception is required, per the same pattern ADR-006/009/042/045
each followed rather than reusing or amending an earlier exception ADR.

## Decision

Authorize a narrowly scoped exception to ADR-002's `.github/workflows/*.yml`
freeze, authorizing removal of one specific configuration line —
`continue-on-error: true` — from `retrain.yml`'s "Backtest quality gate"
step, so that a failing gate correctly fails the job and blocks the
subsequent "Push model to HuggingFace" step via GitHub Actions' existing
default `if: success()` semantics on that step. No new condition needs to
be added to the push step itself.

## 1. Named Module/File and Precise Scope

- **File:** `.github/workflows/retrain.yml`
- **Step:** `"Backtest quality gate"` only
- **Edit:** delete the single line `continue-on-error: true` from that step
- No other step, line, job, trigger, or file is in scope.

## 2. Risk Tier and Rationale

**Low.** `retrain.yml` is not one of ADR-002's two documented live-trading
entry points (`trade.yml` → `python bot/main.py --mode paper --loop`;
`watchdog.yml` → `dashboard/http_endpoints.py` `GET /run/cron` →
`scheduler/trading_job.py` → `bot.main.run()`). It runs on an independent
schedule (`cron: '0 2 * * 0'`) and `workflow_dispatch`, has its own
concurrency group (`group: retrain`), and shares no job, step, or trigger
condition with either entry-point workflow. The change is a single-line
deletion with no new logic, no new step, no new external action, and no
change to `scripts/backtest_gate.py`'s own pass/fail computation. This is
the exact class of change ADR-002 exists to gate (a `.github/workflows/`
edit) — not the class of change ADR-002 exists to prevent (uncoordinated
changes near the two live-trading entry points).

## 3. Isolated Branch/Worktree Requirement

Per ADR-002's "Lifting This Protection" item 2, implementation must occur
in an isolated branch or worktree, not directly on `main`.

## 4. Workflow-Reference Analysis (Companion YAML Changes)

Per ADR-002's checklist item 3 ("All workflow YAML files that reference the
moved paths are updated in the same change"): verified that no other
workflow file references `retrain.yml`, its "Backtest quality gate" step,
or `scripts/backtest_gate.py` by name — `retrain.yml` is a standalone,
independently-triggered workflow with no `workflow_call`/`needs:`
relationship to `ci.yml`, `trade.yml`, `watchdog.yml`, `keepalive.yml`, or
any deploy workflow. **No companion workflow YAML change is required or
authorized by this ADR.**

## 5. Test Requirements and Full-Test-Suite Baseline

**A regression-guard test for the workflow configuration is REQUIRED as
part of this ADR's implementation completeness, not optional.**

This change has no application-code surface, but the defect it fixes is
exactly the kind that can silently regress (someone re-adds
`continue-on-error: true`, or edits the step in a way that reintroduces the
same gap) without a test ever failing. A new test must be added asserting,
by parsing `.github/workflows/retrain.yml` as YAML (no GitHub Actions
simulation required):

- the `"Backtest quality gate"` step exists in the `retrain` job;
- that step does **not** have `continue-on-error: true` (or any
  `continue-on-error` key at all);
- the `"Push model to HuggingFace"` step is otherwise unchanged and has
  **no** newly-added `if:` condition (it must continue relying on GitHub
  Actions' implicit default `if: success()`, not an explicit one this ADR
  does not authorize adding);
- the three existing `if: always()` steps ("Model quality alert," "Pull
  trade database from HuggingFace," "Send weekly report") are unchanged,
  each still carrying `if: always()`.

**This test lives under `tests/`, which is not one of ADR-002's protected
paths (`bot/`, `dashboard/`, `.github/workflows/*.yml`, `scheduler/`,
`database/`, top-level `ledger/`). Adding it therefore requires no
additional ADR-002 exception beyond this one.** The test is a regression
guard for workflow *configuration* only — it parses the YAML file's
structure and asserts on specific keys/values; it does not need to invoke
`actions/runner`, simulate job execution, or exercise
`scripts/backtest_gate.py` itself.

**Post-change validation, in order, before this ADR's implementation is
considered complete:**

1. Run the new regression-guard test in isolation and confirm it passes
   against the post-change `retrain.yml`, and (as a sanity check during
   development) confirm it fails against the pre-change version — proving
   it actually detects the condition it guards.
2. Run the existing tests most directly adjacent to this change:
   `tests/test_save_model_hf.py` (unaffected by this ADR, but exercises the
   same retrain pipeline's HF-push logic and should be re-confirmed green
   as a sanity check that nothing in the surrounding pipeline was
   disturbed).
3. Run the full test suite (`tests/`, `sentinel_engine/tests/`, and any
   other CI-invoked suite) and confirm the existing baseline (~1200+ tests
   per ADR-002, 1274 most recently restated per ADR-006) still passes with
   zero regressions.
4. Verify the exact diff: `git diff` (or `git diff --name-only`) against
   the base commit must show only `.github/workflows/retrain.yml` changed,
   and the diff on that file must show exactly one removed line
   (`continue-on-error: true`) and nothing else — no reformatting, no
   whitespace changes, no other step touched.

## 6. Rollback Plan

Stated before implementation begins, per ADR-002's "Lifting This
Protection" item 5:

- **If not yet merged:** discard the one-line diff (and the new test, if
  not wanted independently of this ADR). No other state to unwind.
- **If merged and the change misbehaves** (e.g., an unrelated,
  already-failing gate now unexpectedly blocks a retrain the operator
  wanted to push anyway): re-add `continue-on-error: true` to the same
  step. The prior behavior is restored verbatim; the regression-guard test
  would then need its assertion temporarily reverted or removed alongside
  it, since it would otherwise correctly fail against the rolled-back file.
- This change touches no `bot/`, `dashboard/`, `scheduler/`, `database/`,
  or `ledger/` state, writes no persistent data, and has no code path
  connecting to either live-trading entry point, so rollback carries no
  risk to trading data or either entry point.

## 7. CLI and Scheduler/HTTP Entry-Point Confirmation

**Both confirmed unaffected, stated rather than assumed, per ADR-002 item
6:**

- **CLI path** (`trade.yml` → `python bot/main.py --mode paper --loop`):
  `trade.yml` is a separate workflow file, not touched by this ADR, with no
  trigger or job dependency on `retrain.yml`.
- **Scheduler/HTTP path** (`watchdog.yml` → `dashboard/http_endpoints.py`
  `GET /run/cron` → `scheduler/trading_job.py` → `bot.main.run()`):
  `watchdog.yml` is likewise untouched, with no dependency on `retrain.yml`
  or its steps.

Neither entry point reads, triggers, or is triggered by `retrain.yml`, so
this change has no code path connecting to either.

## Why the Existing `backtest_gate.py` Logic Is Not Being Changed

`scripts/backtest_gate.py`'s pass/fail computation (thresholds, holdout
window, stress-check informational logging) is already correct and already
calls `sys.exit(1)` on every genuine failure path. The defect is entirely
in how `retrain.yml` responds to that exit code, not in the gate's own
logic. Changing thresholds or gate logic is explicitly out of scope (see
Constraints).

## Why the Default `success()` Behavior of the HF Push Step Is Sufficient

`retrain.yml`'s "Push model to HuggingFace" step already carries no `if:`
condition, which defaults to GitHub Actions' implicit `if: success()`. Once
`continue-on-error: true` is removed from the gate step, a gate failure
correctly makes the job's running status "failure," which the push step's
existing default condition already respects. No new `if:` needs to be
added to the push step itself — the fix is entirely contained in the one
line removed from the gate step, and the regression test in §5 explicitly
asserts that no such new condition is added.

## Why the Three `if: always()` Steps Remain Unaffected

"Model quality alert," "Pull trade database from HuggingFace," and "Send
weekly report" each carry `if: always()`, which unconditionally runs
regardless of any prior step's outcome. This is correct and desired both
before and after this change: the operator should still be notified of a
gate failure (and see quality metrics) even when the push is correctly
blocked. This ADR does not alter any of these three steps, and the
regression test in §5 explicitly asserts they remain unchanged.

## Why This Is CI/Model-Integrity Protection, Not Sentinel Decision-Time Governance

This exception governs whether a newly *trained* model artifact is
permitted to reach the distribution channel (HuggingFace) *before* any
trading decision is ever made with it. It is a pre-deployment,
model-quality gate operating entirely within the weekly retraining
pipeline (`scripts/train_model.py` → `scripts/backtest_gate.py` →
`scripts/save_model_hf.py`). It has no relationship to, and does not
modify, alter, or characterize: `bot/trust_ledger/constitution.py`'s six
rules (governed by ADR-047/048/049/050/051), `sentinel_engine`'s
Evidence/Governance/Audit Trail composition (ADR-009/012/013/014/045/046),
`RiskManager`'s per-decision blocking checks, or any `decision_events`/
Trust Ledger write path. It operates strictly upstream of, and
independently from, every decision-time governance mechanism this session
has ratified.

## Scope

The following protected path (frozen by ADR-002, and not authorized by
ADR-006 or ADR-042, neither of which names this file) is authorized for the
single edit below, and no others:

- `.github/workflows/retrain.yml`

## Constraints

**Allowed:**

- Remove the single line `continue-on-error: true` from the "Backtest
  quality gate" step.
- The natural consequence of that removal — a failing gate now correctly
  fails the job, and the unconditional-by-default "Push model to
  HuggingFace" step is correctly skipped by its existing implicit
  `if: success()`.
- Add the regression-guard test required by §5, under `tests/` — this
  requires no additional ADR-002 exception since `tests/` is not an
  ADR-002-protected path.

**Forbidden:**

- Any other line in `.github/workflows/retrain.yml` — including the
  "Download latest market data," "Train model," "Model quality alert,"
  "Push model to HuggingFace," "Pull trade database from HuggingFace," or
  "Send weekly report" steps, and the job's `on:`/`concurrency:` blocks.
- Any threshold or logic change in `scripts/backtest_gate.py`
  (`MIN_SHARPE`, `MIN_RETURN`, `MAX_DRAWDOWN`, `MIN_WIN_RATE`, the
  all-zero-trades informational path, or the stress-check logic).
- Any change to `trade.yml`, `watchdog.yml`, `keepalive.yml`, `ci.yml`, or
  any other `.github/workflows/*.yml` file.
- Any change to `bot/`, `dashboard/`, `scheduler/`, `database/`, or
  top-level `ledger/`.
- Any M-11 change (HuggingFace push/pull file lists in
  `scripts/save_model_hf.py` / `scripts/load_model_hf.py`) — those are
  unprotected (`scripts/` is not an ADR-002 path) and are explicitly
  outside this ADR's scope; they require no ADR-002 exception and must be
  pursued, if at all, separately from this one.
- Any weakening, bypass, or skip of the gate's actual thresholds — this
  ADR makes the existing gate enforceable, it does not loosen it.

## Explicitly Not Established By This ADR

- No general policy on CI quality-gate enforcement across other workflows
  is adopted.
- No decision about `scripts/backtest_gate.py`'s permissive,
  paper-trading-era thresholds (documented in that file as "tighten before
  going live with real money") is made — this ADR concerns only whether a
  failure blocks the push, not what counts as a failure.
- This ADR does not reopen, extend, or amend ADR-006's or ADR-042's own
  separate `ci.yml` exceptions.
- Whether `models/validation_report.json`'s staleness (the separate M-11
  finding) should be remediated via a fresh retrain is not addressed here;
  this ADR only ensures that whenever such a retrain next runs, its result
  is actually gated before reaching HuggingFace.

## Relationship to ADR-002, ADR-006, and ADR-042

This ADR provides a narrowly scoped exception to ADR-002's freeze only for
`.github/workflows/retrain.yml`, and only for the single line named in
Scope/Constraints above. All other ADR-002 protections remain in force,
unchanged — including every other `.github/workflows/*.yml` file, `bot/`,
`dashboard/`, `scheduler/`, `database/`, and top-level `ledger/`. This ADR
does not reopen, amend, or extend ADR-006's `ci.yml` exception or ADR-042's
`ci.yml` exception; both stand unchanged and independent of this one. Per
the same pattern ADR-006/009/042/045 each followed, this is issued as a
new, standalone ADR rather than an amendment to any of them.

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-08-24
**Accepted By:** Architecture Owner
