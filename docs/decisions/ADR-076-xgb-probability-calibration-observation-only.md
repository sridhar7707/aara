# ADR-076: ADR-002 Exception — XGB Probability Calibration (Observation-Only)

**Status:** Accepted
**Date Proposed:** 2026-11-04
**Date Accepted:** 2026-11-04
**Decision Type:** Narrow ADR-002 exception, prospective. Adds a calibrated probability alongside XGB's existing raw output, recorded for observation only — authorizes no change to any live BUY/SELL decision or threshold.

---

## Context

This session's broader "what's missing in the ML/algorithm layer" review found that `XGBPredictor.predict_proba()`'s raw tree-ensemble output is never calibrated — `XGB_MIN_CONFIDENCE=0.52` and `ensemble_signal()`'s thresholds (`BUY_THRESHOLD=0.52`, `STRONG_BUY_THRESHOLD=0.65`, etc.) all read that raw score directly. Tree ensembles are well-documented to produce probabilities that don't match true empirical frequencies out of the box (this is *why* `sklearn.calibration` exists as a standard tool). Nothing in this codebase has ever checked whether "XGB says 56%" corresponds to an actual ~56% empirical win rate.

The user, when asked to proceed, added one explicit constraint: the calibration must be **more accurate than liberal** — i.e., when uncertain, it should understate confidence rather than overstate it. This matters specifically because the eventual goal (user's own words) is investing real money once the system is "confident enough" — a calibration method that leans optimistic would quietly undermine that exact judgment call.

The user separately confirmed this should be **surface-only**: computed and recorded for observation, with zero change to any live decision, gate, or threshold. That scopes this ADR narrowly and keeps risk low despite touching protected `bot/` files.

---

## Decision

Authorize the following named changes, and no others, to be developed and validated in an isolated worktree before any merge to `main`.

## 1. Named Scope

**New file (protected, under `bot/strategy/`):**
- `bot/strategy/calibration.py` — pure functions only, same convention as `bot/strategy/triple_barrier.py` (no execution/order-placement/live-trading-cycle imports; not imported by `bot/main.py`'s decision path, only by `XGBPredictor`'s training/inference and by `scripts/train_model.py`'s reporting). Two functions:
  - `wilson_lower_bound(k: int, n: int, confidence: float = 0.95) -> float` — the standard Wilson score interval's lower bound for a binomial proportion. Returns 0.0 when `n == 0`.
  - `fit_conservative_calibration(raw_scores: np.ndarray, labels: np.ndarray, n_bins: int = 10, confidence: float = 0.95) -> IsotonicRegression` — bins `raw_scores` into `n_bins` equal-*frequency* bins (not equal-width — guarantees every bin has a real sample count, never an empty or near-empty one), computes each bin's **Wilson lower bound** (not the raw empirical mean) of its win rate, and fits `sklearn.isotonic.IsotonicRegression(out_of_bounds="clip")` on (bin-midpoint-raw-score, wilson-lower-bound) control points. This is the "more accurate than liberal" mechanism, stated precisely: every calibration target is a statistically conservative lower bound, not a point estimate, so the fitted curve is biased toward understating confidence, with the size of that conservative margin shrinking automatically as bin sample size grows (irrelevant in today's thousands-of-rows validation sets, protective if a future retrain ever has a smaller one).

**Modified files (protected):**
- `bot/strategy/xgb_predictor.py` — `train()`: after the existing holdout `X_val`/`y_val` computation (already there, used for the existing `val_auc` metric — no new data split), call `fit_conservative_calibration(val_proba, y_val.values)` and save the result via `joblib.dump` to a new `models/saved/xgb_calibration.pkl`. `_load()`: load that file if present (optional — a model trained before this ADR simply has no calibration file, and calibrated prediction is unavailable, not an error). New method `calibrated_proba(row: pd.Series) -> float | None`: returns `None` when no calibration model is loaded or when the base model is unavailable (mirrors `predict_proba()`'s own `None`/fallback discipline exactly — a `None` here is never treated as "0.5" or any other fabricated value by callers); otherwise returns `float(self._calibration.predict([self.predict_proba(row)])[0])`.
- `bot/db/trade_log.py` — `log_signal()`: new optional parameter `xgb_calibrated_prob: float | None = None`, written into a new `signal_log.xgb_calibrated_prob` column. `NULL` when calibration is unavailable — never backfilled or estimated.
- `bot/_main_db.py` — `signal_log` table DDL: add `xgb_calibrated_prob REAL` column, plus an `ALTER TABLE` migration guard for existing databases (same pattern `bot/capital/pool.py`'s `_ensure_tables()` already uses for `profit_withdrawn`).
- `bot/main.py` — the one call site that calls `_log_signal(...)` (`bot/main.py:338` per this session's own earlier reading): compute `xgb_calibrated = xgb.calibrated_proba(latest)` alongside the existing `xgb_prob = xgb.predict_proba(latest)` call, pass it through as the new argument.

**Modified file (unprotected):**
- `scripts/train_model.py` — after training, compute and record two calibration-quality metrics into the existing `models/validation_report.json`: `xgb_calibration_brier_score` (Brier score of the calibrated probabilities on `X_val`/`y_val` — standard calibration-quality metric, lower is better) and `xgb_calibration_ece` (Expected Calibration Error, binned). Both computed on the SAME `X_val`/`y_val` the calibration itself was fit on (no new data, no new read) — stated as in-sample-relative-to-calibration-fit, not held out from it, since this project's data volume doesn't support a third split; this is a documented limitation, not hidden.

**Explicitly not touched:**
- `bot/strategy/ensemble.py` — `ensemble_signal()`, `ensemble_confidence()`, `WEIGHTS`, every threshold constant. None of these read the new calibrated value. This is the entire point of "surface-only."
- `bot/_main_cycle.py`'s `XGB_MIN_CONFIDENCE` gate (Gate 3) — continues reading the raw `predict_proba()` output exactly as before.
- `bot/strategy/lstm_predictor.py` — out of scope; this ADR is XGB-only. (This session separately found the LSTM in persistent, severe overfitting every week — a different, larger problem the user has not yet decided how to address; not bundled here.)

## 2. Risk Tier and Rationale

**Low.** Despite touching protected `bot/` files, this is additive and read-only with respect to every existing decision path:

- No existing function's return value, type, or behavior changes for any existing caller. `predict_proba()` is completely untouched. `log_signal()`'s new parameter defaults to `None`, so every existing call site compiles and behaves identically without modification (only the one call site in `bot/main.py` is updated, per §1).
- The new `calibrated_proba()` method's output is written to a new, nullable DB column and nowhere else. No gate, threshold, or sizing calculation reads it. A bug in the calibration math would produce a wrong *number in a log column* — not a wrong trade.
- Development and testing happen in an isolated worktree per ADR-002 item 2.

## 3. Isolated Branch/Worktree Requirement

Required, per the process established this session. No commit touching the protected files in §1 lands on `main` until test results (§5) have been reviewed.

## 4. Workflow-Reference Analysis (ADR-002 item 3)

No `.github/workflows/*.yml` file is touched. `retrain.yml` invokes `scripts/train_model.py` by name; this ADR adds reporting fields to that script's existing output file, not a new invocation or argument.

## 5. Test Requirements and Validation Performed Before Any Merge to `main`

1. New unit tests for `bot/strategy/calibration.py`: `wilson_lower_bound` against known textbook values (e.g. k=50,n=100 → center ≈0.5, lower bound measurably below 0.5; k=0,n=100 → 0.0; n=0 → 0.0); `fit_conservative_calibration` on a synthetic dataset with a known true relationship, confirming (a) the fitted curve is monotonically non-decreasing (isotonic regression's own guarantee), (b) at every bin, the calibration target used was strictly ≤ that bin's raw empirical win rate (the "more accurate than liberal" invariant, checked directly against the Wilson-bound math, not just asserted).
2. New tests for `XGBPredictor.calibrated_proba()`: returns `None` when no calibration file exists (e.g. a pre-ADR model); returns `None` when `self.model is None`; returns a float in `[0,1]` when both are present; a confidence check that for a genuinely overconfident raw score the calibrated value is not simply equal to it (proves calibration is actually being applied, not passed through).
3. Existing `tests/test_xgb_predictor.py` re-confirmed green, unchanged.
4. New test for `log_signal()`'s new parameter: existing call sites (no new argument) write `NULL` into the new column; a call that does pass `xgb_calibrated_prob` writes the real value.
5. Full `tests/` suite — zero regressions versus the pre-change baseline.
6. Manual trace over the real, current production validation data (pulled fresh from HF this session) confirming the fitted calibration curve is sane end-to-end: no `inf`/`nan`, monotonic, and its Brier score is reported and sanity-checked against the uncalibrated raw score's own Brier score (calibration should not make things measurably worse).
7. `git diff --name-only` against the base commit, confirmed to match §1 exactly.

## 6. CLI and Scheduler/HTTP Entry-Point Confirmation

**CLI path** (`trade.yml` → `bot/main.py --mode paper --loop`): the live cycle now computes and logs one additional number per symbol per cycle — a cheap, synchronous dict/array lookup (`IsotonicRegression.predict()` on a single value), not a new model inference or I/O call. No change to what trades execute or when. **Scheduler/HTTP path**: not applicable; same reasoning. **Retrain path** (`retrain.yml` → `scripts/train_model.py`): now also fits and saves the calibration model and reports its quality metrics — additive to an already-running step, no new entry point.

## 7. Rollback Plan

- **If not yet merged:** discard the worktree. No state on `main` to unwind.
- **If merged and the calibration output looks wrong:** revert the commit. Since nothing reads `xgb_calibrated_prob` for any decision, a revert has zero live-trading effect — it simply stops logging a column that was never acted on.

---

## Constraints

**Allowed:** Exactly the changes named in §1, developed in an isolated worktree.

**Forbidden:**
- Any change to `ensemble_signal()`, `ensemble_confidence()`, `WEIGHTS`, or any BUY/SELL/HOLD threshold.
- Any change to `XGB_MIN_CONFIDENCE`, `bot/_main_cycle.py`'s Gate 3, or any other live entry/exit gate.
- Using the calibrated value anywhere a trading decision, position size, or risk calculation is computed.
- Any `.github/workflows/*.yml` change.
- Any change to `bot/strategy/lstm_predictor.py` or the LSTM's own degraded-model handling (ADR-074, separate and already resolved).

---

## Explicitly Not Established By This ADR

- Does not decide whether or when the calibrated probability should ever replace the raw score in a live gate — that is a separate, future, explicit decision, to be made only after this ADR's own observation period shows the calibration is trustworthy (per the user's own stated "surface first, don't gate yet" choice).
- Does not address the deeper "does the raw score even answer the right question" gap (meta-labeling, still under discussion, not started).
- Does not address the LSTM's persistent severe overfitting, found separately this session.
- Does not claim the calibration is validated against *real trade outcomes* — the sample size for that (today, ~20 closed trades) is far too small; this calibrates against the existing, much larger fixed-horizon validation set instead, which is a real, honest limitation stated here rather than glossed over.

---

## Acceptance

*(Per ADR-058 D4, this document is a proposal and carries no authority until it is landed under ADR-058 D2, by explicit act of the Architecture Owner.)*

**Status:** Accepted
**Date Accepted:** 2026-11-04
**Accepted By:** ksri77

---

## Status Log

- **2026-11-04 — Proposed.** Found while doing an expert-level review of the ML/algorithm layer at the user's request. User explicitly required the calibration bias toward understating rather than overstating confidence, and explicitly chose observation-only (not live-gating) as the rollout scope for this first pass.
- **2026-11-04 — Accepted by ksri77.** Implementation to follow in an isolated worktree per §3.
