# ADR-079: ADR-002 Exception — Split dashboard/components/models.py

**Status:** Accepted
**Date Proposed:** 2026-11-05
**Date Accepted:** 2026-11-05
**Decision Type:** Narrow ADR-002 exception. Pure extraction refactor — splits one 501-line file into four smaller files plus a thin re-export facade. No behavior change, no HTML output change, no function signature change.

---

## Context

`/code-review` flagged `dashboard/components/models.py` at 501 lines, 1 over this project's "keep files under 500 lines" rule (CLAUDE.md), introduced by ADR-078's otherwise-minimal display fix. Rather than accept the 1-line overage (ADR-078's own documented tradeoff) or keep squeezing the same file, the user asked for a real fix: split it.

The file already has four clearly separated sections, each marked by its own `# ──` header comment and `@safe_render(...)` decorator, with no shared mutable state between them (the one piece of cross-section reuse — `_lstm_loss_display()` — is a small pure helper, not shared state):

1. `render_paper_trading_scorecard()` — lines ~20-161
2. `_lstm_loss_display()`, `render_validation_report()` — lines ~163-224
3. `render_institutional_metrics()` — lines ~227-347
4. `_model_quality_fallback()`, `render_investor_view()` — lines ~350-494

Followed by a one-time `register(ComponentSpec(...))` block (lines ~497-501) that runs at import of this module and wires all four public render functions into `dashboard/registry.py`'s refresh system.

`dashboard/components/models.py` is a real public import surface — `dashboard/app.py`, `dashboard/__init__.py`, and `tests/test_gradio_client.py` all import specific function names from `dashboard.components.models` directly. The lowest-risk split, and the one consistent with this project's own stated "facade pattern" coding standard, keeps that import path and every external name working exactly as it does today.

---

## Decision

Authorize the following named changes, and no others, to be developed and validated in an isolated worktree before any merge to `main`.

## 1. Named Scope

**New files (protected — dashboard), each a pure move of existing code with only the imports each needs:**
- `dashboard/components/models_scorecard.py` — `render_paper_trading_scorecard()` and its module-level `_BENCH_CACHE`/`_BENCH_CACHE_TS`/`_BENCH_CACHE_TTL` state, moved verbatim.
- `dashboard/components/models_validation.py` — `_lstm_loss_display()` and `render_validation_report()`, moved verbatim.
- `dashboard/components/models_institutional.py` — `render_institutional_metrics()`, moved verbatim.
- `dashboard/components/models_investor.py` — `_model_quality_fallback()` and `render_investor_view()`, moved verbatim. Imports `_lstm_loss_display` from `dashboard.components.models_validation` (the one cross-section dependency, already present today within the single file).

**Modified file (protected — dashboard), rewritten as a thin re-export facade:**
- `dashboard/components/models.py` — after the move, contains only: the module docstring (updated to note the split and point to the four new files), imports of all four public render functions plus the two helpers that tests import directly (`_lstm_loss_display`, `_model_quality_fallback`), and the unchanged `register(ComponentSpec(...))` block. Every name currently importable from `dashboard.components.models` stays importable from it, unchanged — `dashboard/app.py`, `dashboard/__init__.py`, and `tests/test_gradio_client.py` require **zero changes**.

**Explicitly not touched:**
- Every function body — moved verbatim, not rewritten. No HTML output, color logic, threshold, or computation changes anywhere.
- `dashboard/app.py`, `dashboard/__init__.py`, `dashboard/registry.py`, `tests/test_gradio_client.py`, `tests/test_dashboard_models.py`, `tests/test_lstm_predictor.py` — all keep working unmodified against the facade's preserved public surface.
- Any other dashboard component or chart.
- Any live trading decision, gate, or threshold.

## 2. Risk Tier and Rationale

**Low.** This is a mechanical extraction, not a rewrite — every moved function's body is unchanged byte-for-byte; only its file location and that file's import list change. The facade preserves 100% of the existing public API, so every external caller is unaffected. The one real risk is a copy-paste import mistake (missing an import in a new file, causing an `ImportError` or `NameError` at runtime) — caught immediately and loudly by both the existing dashboard smoke tests and a full import of `dashboard.components.models` in CI, not silently.

## 3. Isolated Branch/Worktree Requirement

Required, per the process established this session, consistent with these files' protected status.

## 4. Workflow-Reference Analysis (ADR-002 item 3)

No `.github/workflows/*.yml` file is touched.

## 5. Test Requirements and Validation Performed Before Any Merge to `main`

1. Every existing test that exercises these functions — `tests/test_gradio_client.py`'s four registered-component smoke tests (`validation_report`, `investor_view`, `paper_trading_scorecard`, `institutional_metrics`), `tests/test_dashboard_models.py` (ADR-078's retirement-display tests), and `tests/test_lstm_predictor.py` — re-run and pass unmodified, with no change to their import statements. This is the primary proof the facade's public surface didn't shift.
2. A new, explicit import-surface test: `import dashboard.components.models as m` followed by asserting `hasattr(m, name)` for each of the six names other files import today (`render_validation_report`, `render_investor_view`, `render_paper_trading_scorecard`, `render_institutional_metrics`, `_lstm_loss_display`, `_model_quality_fallback`).
3. A new test confirming the `register(...)` side effect still fires exactly as before: after importing `dashboard.components.models`, `dashboard.registry`'s registered components include `investor_out`, `scorecard_out`, `metrics_out`, `val_out` (the same four keys, same priorities, same `RefreshGroup`s as today).
4. `wc -l` on all five files (the four new ones plus the rewritten facade), confirming every one is comfortably under 500 lines.
5. `python scripts/arch_review.py --diff` — confirms 0 block/error/warning (no file over the line limit).
6. Full `tests/` suite — zero regressions versus the pre-change baseline.
7. `git diff --name-only` against the base commit, confirmed to match §1 exactly (one rewritten file, four new files).

## 6. CLI and Scheduler/HTTP Entry-Point Confirmation

No entry point changes. The dashboard imports `dashboard.components.models` exactly as it does today; that import now transitively pulls in four small files instead of containing everything itself, with identical net behavior.

## 7. Rollback Plan

- **If not yet merged:** discard the worktree.
- **If merged and something looks wrong:** revert the commit (a single commit restoring the original `dashboard/components/models.py` and removing the four new files). No live-trading or data-shape impact either way — this is a file-layout change only.

---

## Constraints

**Allowed:** Exactly the five file changes named in §1 (four new files, one rewritten facade), developed in an isolated worktree.

**Forbidden:**
- Any change to any moved function's logic, output, or signature.
- Any change to `dashboard/app.py`, `dashboard/__init__.py`, `dashboard/registry.py`, or any test file's import statements (if a test needs an import change, that means the facade is incomplete, not that the test should change).
- Any change to any other dashboard component.
- Any change to any live trading decision, gate, or threshold.

---

## Explicitly Not Established By This ADR

- Does not revisit any of the display or logic decisions made in ADR-077/ADR-078 — those are carried over verbatim.
- Does not establish a general policy for how large dashboard component files may grow before splitting; this is a one-time fix for the file flagged by code review, not a new standing rule.

---

## Acceptance

*(Per ADR-058 D4, this document is a proposal and carries no authority until it is landed under ADR-058 D2, by explicit act of the Architecture Owner.)*

**Status:** Accepted
**Date Accepted:** 2026-11-05
**Accepted By:** ksri77

---

## Status Log

- **2026-11-05 — Proposed.** `/code-review` flagged `dashboard/components/models.py` at 501 lines after ADR-078. User asked for a real split rather than accepting the overage.
- **2026-11-05 — Accepted by ksri77.** Implementation to follow in an isolated worktree per §3.
