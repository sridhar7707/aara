# ADR-078: ADR-002 Exception — LSTM Retirement Display & Log Message Fix

**Status:** Accepted
**Date Proposed:** 2026-11-05
**Date Accepted:** 2026-11-05
**Decision Type:** Narrow ADR-002 exception, follow-on to ADR-077. Fixes two misleading messages left behind by ADR-077's retirement sentinel — display and log text only, no logic change, no gate/threshold touched.

---

## Context

A `/code-review` pass on ADR-077's merge (`89f916a`) found two real, user-facing problems caused by the retirement sentinel (`lstm_val_loss: 1.0, lstm_retired: true`) that `scripts/train_model.py` now writes every week:

1. `dashboard/components/models.py` renders `lstm_val_loss` as a live "LSTM Val Loss" metric in both `render_validation_report()` (technical view) and `_model_quality_fallback()` (plain-language investor view), coloring it red ("LOSS") whenever the value is `≥ 0.70` — which `1.0` always is. An operator or investor reading the dashboard now sees a permanently red, degraded-looking metric with no indication it's an intentional retirement rather than a live problem.
2. `bot/strategy/lstm_predictor.py`'s `_check_degradation()` logs `⚠ LSTM model is DEGRADED ... Run: python scripts/train_model.py` every time a fresh `LSTMPredictor()` loads the sentinel report. That instruction is now permanently false — `train_model.py` no longer trains the LSTM at all, so running it can never change `lstm_val_loss`.

Both files are governance-protected (`dashboard/` per CLAUDE.md's explicit "do not modify unless an ADR allows it"; `bot/strategy/lstm_predictor.py` per ADR-077's own Forbidden list), which is why ADR-077 left them alone and this is a separate ADR rather than a casual follow-up fix.

---

## Decision

Authorize the following named changes, and no others, to be developed and validated in an isolated worktree before any merge to `main`.

## 1. Named Scope

**Modified file (protected — dashboard):**
- `dashboard/components/models.py`:
  - `render_validation_report()`: when `r.get("lstm_retired")` is truthy, render the "LSTM Val Loss" row's **value** as `"Retired (ADR-077)"` in a neutral color (`TEXT2`, the same muted tone already used for non-numeric fields like "Symbols"/"Cutoff") instead of the numeric sentinel in `LOSS` (red). When `lstm_retired` is absent/false (e.g. a report from before ADR-077 was ever deployed, or if a future ADR un-retires it), behavior is **byte-for-byte unchanged** — this is an added branch, not a replacement of the existing numeric-display logic. Also append one short clause to the existing "How to read this" help text's `LSTM Val Loss` line noting that a retired model shows "Retired" instead of a number, so the help text doesn't contradict what's on screen.
  - `_model_quality_fallback()`: identical fix for its "LSTM Val Loss" stat card (same `lstm_retired` check, same neutral-color/"Retired" text, same untouched-when-absent guarantee).

**Modified file (protected — explicitly forbidden by ADR-077, now narrowly reopened by this ADR):**
- `bot/strategy/lstm_predictor.py`: in `_check_degradation()` only — when `report.get("lstm_retired")` is truthy, log `logger.info("LSTM retired from the active retrain pipeline (ADR-077) — ensemble weight permanently excluded; this is expected, not an error.")` instead of the existing `logger.warning(...)` "DEGRADED ... Run: python scripts/train_model.py" message. **The `self.is_degraded = True` and `self.val_loss = saved_val_loss` assignments immediately above this log call are completely unchanged** — this ADR touches only which message gets logged after that point, never whether degradation is set. When `lstm_retired` is absent/false, the exact original warning text and behavior fire, unchanged — this preserves the real-degradation-alert path for any future, different LSTM attempt that degrades for genuine, unplanned reasons.

**Explicitly not touched:**
- The `is_degraded`/`val_loss` assignment logic itself, `predict_proba()`, `train()`, and every other method of `LSTMPredictor`.
- `bot/strategy/ensemble.py`, `scripts/train_model.py`, `.github/workflows/retrain.yml` — ADR-077's own territory, already shipped; nothing here changes any of it.
- Any other dashboard component, chart, or view beyond the two named functions in `dashboard/components/models.py`.
- Any live trading decision, gate, or threshold.

## 2. Risk Tier and Rationale

**Low.** Pure display/log-message text, gated behind a new boolean flag that is additive (defaults to the pre-ADR-078 behavior when absent). No numeric value a downstream consumer could read differently, no change to `is_degraded`/`predict_proba()`'s actual return values, no change to any file outside these two.

## 3. Isolated Branch/Worktree Requirement

Required, per the process established this session, consistent with these files' protected status.

## 4. Workflow-Reference Analysis (ADR-002 item 3)

No `.github/workflows/*.yml` file is touched.

## 5. Test Requirements and Validation Performed Before Any Merge to `main`

1. New test for `LSTMPredictor._check_degradation()`: given a report with `lstm_retired: true` and `lstm_val_loss: 1.0`, assert `is_degraded is True` (unchanged) and assert the logged message does **not** contain "DEGRADED" or "Run: python scripts/train_model.py", and does contain "retired"/"ADR-077". A second test with `lstm_retired` absent (or a pre-ADR-077-style report) asserts the **original** warning text still fires verbatim — proving the new branch doesn't regress the genuine-degradation alert path.
2. New tests for `dashboard/components/models.py`: `render_validation_report()` and `_model_quality_fallback()`, each given a report with `lstm_retired: true`, assert the rendered HTML contains `"Retired"` and does not contain the raw sentinel formatted as a number (e.g. `"1.0000"`). A second case per function, with `lstm_retired` absent, asserts the existing numeric rendering is unchanged (byte-identical to pre-ADR-078 output for that input).
3. Existing `tests/test_lstm_predictor.py` and the dashboard smoke-test registrations in `tests/test_gradio_client.py` re-confirmed green, unchanged.
4. Full `tests/` suite — zero regressions versus the pre-change baseline.
5. `git diff --name-only` against the base commit, confirmed to match §1 exactly (two files).

## 6. CLI and Scheduler/HTTP Entry-Point Confirmation

No entry point changes. The dashboard renders this on every page load exactly as before, now with one additional conditional branch; `bot/main.py`'s live cycle is unaffected (`_check_degradation()` runs at `LSTMPredictor()` construction, same as always — only its log output differs when the sentinel is present).

## 7. Rollback Plan

- **If not yet merged:** discard the worktree.
- **If merged and something looks wrong:** revert the commit. No live-trading or data-shape impact either way — this is display/log text only.

---

## Constraints

**Allowed:** Exactly the two file changes named in §1, developed in an isolated worktree.

**Forbidden:**
- Any change to `is_degraded`, `val_loss`, `predict_proba()`, or `train()` in `bot/strategy/lstm_predictor.py`.
- Any change to `bot/strategy/ensemble.py`, `scripts/train_model.py`, or `.github/workflows/retrain.yml`.
- Any change to the numeric rendering path for a report where `lstm_retired` is absent or false.
- Any change to any other dashboard component, chart, or page.

---

## Explicitly Not Established By This ADR

- Does not revisit ADR-077's retirement decision itself.
- Does not add a general "retired model" UI pattern reusable elsewhere — this is a narrow fix to the two specific LSTM displays named above, not a new design system component.

---

## Acceptance

*(Per ADR-058 D4, this document is a proposal and carries no authority until it is landed under ADR-058 D2, by explicit act of the Architecture Owner.)*

**Status:** Accepted
**Date Accepted:** 2026-11-05
**Accepted By:** ksri77

---

## Status Log

- **2026-11-05 — Proposed.** Found by `/code-review` on ADR-077's merge. User confirmed fixing both as a small, separately-scoped ADR rather than silently touching protected files.
- **2026-11-05 — Accepted by ksri77.** Implementation to follow in an isolated worktree per §3.
- **2026-11-05 — Implementation complete, merged to main (`9168863`).** Built in worktree `worktree-lstm-retirement-display`, now removed. `git diff --name-only` confirmed exactly 2 named files touched (`bot/strategy/lstm_predictor.py`, `dashboard/components/models.py`), plus the test files added/updated — matching §1. Full suite on `main` post-merge: 1477 passed, 2 skipped, 0 failed. `arch_review.py --diff`: 0 block(s), 0 error(s), 1 warning — `dashboard/components/models.py` landed at 501 lines (1 over the 500-line soft limit). A DRY refactor (one shared `_lstm_loss_display()` helper replacing duplicated color/value logic at both call sites) already cut what would otherwise have been +11 lines down to +3 net; further compression was judged to cost more in readability (repeated `.get()` calls, cramped one-liners) than the 1-line warning is worth, and is noted here rather than silently accepted.

  Both of §5's "unchanged when absent" tests passed, confirming the fix is purely additive: a report without `lstm_retired` renders and logs byte-identical output to before this ADR.
