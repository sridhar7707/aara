# CI Sentinel Engine Test Integration Plan

**Status:** Plan only — documentation. `.github/workflows/ci.yml` was not
modified to produce this document, confirmed via `git status` before and
after. No file was changed.

**Purpose:** design the minimal CI change to add `sentinel_engine/tests`'
26 architecture-boundary tests to the CI-enforced surface, without touching
`tests/`'s existing 1162-test canonical run.

---

## 1. Current State (Verified Directly)

`.github/workflows/ci.yml`, single job `test`, relevant steps in order:

1. Checkout, Python 3.11 setup, cached venv, `pip install -r requirements.txt`.
2. `scripts/arch_review.py` — a fast structural gate (file size, missing type
   hints, etc.), blocking on BLOCK/ERROR severity.
3. `tools/validate_brand_system.py` — informational only (`continue-on-error: true`).
4. **`python -m pytest tests/ -v --tb=short`** (line 63) — the canonical run,
   1162 tests, ~2 minutes locally.
5. A Telegram failure notification, gated on `failure()` (the whole job's
   step history, not just the immediately-preceding step) and
   `github.event_name == 'push'`.

`sentinel_engine/tests/` is not referenced anywhere in this file — confirmed
by direct inspection, not assumed. `deploy_ui.yml` gates the dashboard
deploy on this workflow's overall success, so any step added here that can
fail already participates in that gate without further changes.

## 2. Dependency Impact — None

`sentinel_engine`'s production code imports only stdlib (`dataclasses`,
`datetime`, `typing`, `enum`, `abc`, `uuid`) plus its own submodules —
verified in the prior Architecture Boundary Review. Its test suite adds only
`ast`, `importlib`, `pathlib`, `pytest` — all either stdlib or already
installed for the existing `tests/` run. **No `requirements.txt` change, no
new pip install step, no cache-key change required.**

## 3. Runtime Impact — Negligible

`pytest sentinel_engine/tests` runs in **0.42s locally** (108 tests). Against
the existing suite's ~126s runtime, this is not a meaningful addition to
total CI time under either design option below.

## 4. Combined Command vs. Separate Step

**Recommendation: a separate step. Not combined into the existing command.**

### Option A — Combine (`pytest tests/ sentinel_engine/tests -v --tb=short`)

- Fewer lines changed in one sense (one step edited instead of one step added).
- **But it edits the existing "Run tests" step's command string** — a literal
  reading of requirement 2 ("preserve existing canonical command") is
  violated even though behavior for `tests/`'s own 1162 tests would be
  unchanged.
- Runs both suites in one pytest session. `tests/conftest.py` exists and was
  checked directly — it defines no `autouse=True` fixtures, so no known
  cross-suite state leakage risk today. But this is a point-in-time fact,
  not a structural guarantee: a future `autouse` fixture added to
  `tests/conftest.py` for `tests/`'s own needs would silently start applying
  to `sentinel_engine/tests` too, with no test or CI failure flagging that
  it happened.
- Interleaves both suites' `-v` output in one log stream — harder to see at
  a glance whether a failure belongs to the 1162-test suite or the 108-test
  one.

### Option B — Separate step (recommended)

- **The existing "Run tests" step (line 62-63) is not touched at all** —
  zero characters changed, the safest possible reading of "preserve the
  existing canonical command" and "do not change existing test behavior."
- Full isolation: `sentinel_engine/tests` runs in its own pytest process,
  with zero possibility of inheriting a `tests/`-side fixture, plugin, or
  collection-order effect, now or in the future.
- Independently visible pass/fail in the GitHub Actions UI — a failure is
  immediately attributable to one suite or the other without reading log
  content.
- The existing Telegram failure step already covers this automatically —
  `if: failure()` checks the whole job's step history, not just the
  step immediately before it. **No change needed there.**
- Trivial to revert in isolation (delete one step) if this ever needs to be
  rolled back, versus Option A requiring the "Run tests" step itself to be
  edited back.

The negligible runtime difference between one combined pytest invocation and
two separate ones (both well under a second of added overhead) does not
offset Option A's cost to isolation and literal compliance with the stated
requirements.

## 5. Proposed Change (Not Applied)

Insert a new step immediately before the existing "Run tests" step —
grouping it with `scripts/arch_review.py` in spirit (both are fast,
structural/boundary gates, appropriately run before the slower, broader
1162-test suite so a cheap structural violation fails fast rather than
waiting behind a ~2-minute run):

```yaml
      - name: Run sentinel_engine boundary tests
        run: python -m pytest sentinel_engine/tests -v --tb=short

      - name: Run tests
        run: python -m pytest tests/ -v --tb=short
```

That is the entire diff: one new step, zero lines changed in any existing
step. `requirements.txt`, the venv cache key, the Telegram notification
step, and every other part of the workflow remain byte-for-byte unchanged.

## 6. Requirements Checklist

1. **Do not change existing test behavior** — satisfied; the existing step
   is untouched, and the new step runs in full isolation (Option B).
2. **Preserve existing canonical command** — satisfied literally; `python -m
   pytest tests/ -v --tb=short` remains exactly as it is today.
3. **Add sentinel_engine tests explicitly** — satisfied; a dedicated,
   separately-named step, not folded into another command's argument list.
4. **Keep CI runtime reasonable** — satisfied; +0.42s locally against a
   ~126s existing run is not material.
5. **Combining vs. separate step, explained** — Section 4, above.

---

## Constraints Confirmed

`.github/workflows/ci.yml` was not modified. No other file was changed. This
document is a plan only.
