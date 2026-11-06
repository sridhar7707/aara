# ADR-081: Quant Review Remediation

**Status:** Accepted by ksri77 on 2026-11-06 ("yes fix all"). Implementation status per item is in the section "Implementation status" below. Items not implemented are owner decisions or larger work, and are listed there.
**Date Proposed:** 2026-11-06
**Decision Type:** Remediation plan for findings from a full-codebase quant review. Each item names its own scope, tier and tests. Items marked **ADR-002** need an isolated worktree and named scope before code changes.

---

## Context

A full-codebase quant review (strategy, risk, capital, training, backtest, readiness) reported findings. The most serious one was checked against code before this proposal was written:

- **Verified:** `scripts/train_model.py:86` concatenates per-symbol frames and sorts by date. `bot/strategy/xgb_predictor.py:119-120` then builds the target with `close.shift(-FORWARD_PERIODS)` on the combined frame, and the `symbol` column has already been dropped (`train_model.py:97`). The 21-row-ahead price is usually from a different ticker. The reported validation AUC (0.556, `models/validation_report.json`) is measured on this target, so the live model's skill is not established.

The other findings are reported by the review agent. They are not yet confirmed one by one. Each item below must be confirmed by reading the code before its fix is merged.

Because the live model and live gates are affected, **no item in this ADR should be implemented until it is accepted.** Items are grouped by risk.

---

## Decision

Remediate in four tiers. Each tier is a separate change, with its own tests, merged in order.

### Tier 1: Model validity (blocks any trust in current AUC)

| # | Finding | Fix | Class |
|---|---------|-----|-------|
| 1.1 | Forward-return target crosses symbols (`xgb_predictor.py:119-120`, `train_model.py:86,97`) | Compute `shift(-N)` per symbol (`groupby("symbol")`) before concatenation, or keep the symbol column through training and build the target inside the group. | ADR-002, retrain required |
| 1.2 | Validation split reuses the early-stopping and calibration set; "last 30 days" docstring does not match the split (`xgb_predictor.py:125-126`) | Split into train / early-stop / holdout by time. Holdout is never used for early stopping or calibration. Correct the docstring. | ADR-002, retrain required |
| 1.3 | Overlapping 21-bar labels inflate effective sample size | Report AUC standard error with effective N = N / horizon. Add a purge gap of `FORWARD_PERIODS` bars between train and holdout. | ADR-002 |
| 1.4 | Regime labels recomputed on the combined frame (`regime_classifier.py:77`) | Keep per-symbol labels from `load_combined`. | ADR-002, retrain required |
| 1.5 | `FWD_VOL_THRESHOLD=0.18` is below typical single-stock volatility, so nearly all bars are HIGH_VOLATILITY, which is in `ENTRY_REGIMES` | Set the threshold from the empirical volatility distribution. Recheck the label distribution before and after. Decide whether the regime gate should pass HIGH_VOLATILITY (owner decision). | ADR-002 (threshold change needs owner approval) |

**Acceptance for Tier 1:** a new holdout AUC with a standard error, computed on per-symbol targets. Per-regime label distribution reported. If holdout AUC is not clearly above 0.5, the owner decides whether the model stays in use.

### Tier 2: Trading-behaviour correctness (small, bounded)

| # | Finding | Fix | Class |
|---|---------|-----|-------|
| 2.1 | Earnings gate fails open on exception and caches the failure for 12h (`_main_market.py:169-175, 225-227`) | On exception, treat as "unknown" and block the buy for that cycle. Do not write the failure to `earnings_cache`. | ADR-002 (restrictive only) |
| 2.2 | Partial fills: pool debited and `position_state` written at requested notional, not filled quantity (`_main_cycle.py:382, 450, 453`) | Size the DB writes and the pool debit by the filled quantity. Log the requested and filled amounts. | ADR-002, touches ADR-075 pool logic (owner review) |
| 2.3 | Logged stop is fixed at entry ATR, but the enforced stop moves with current ATR (`_main_positions.py:462-463` vs `_main_cycle.py:431`) | Decide one definition, then align the logged and enforced stop. Recommended: log the stop actually enforced, and cap the ATR widening at the risk budget. | ADR-002 (risk logic, owner decision) |
| 2.4 | Sizing base decays within a cycle because deployed notional is subtracted from a value that does not fall on buys (`main.py:432`, `_main_cycle.py:281`) | Compute the sizing base once per cycle from the start-of-cycle capital. | ADR-002 (sizing; owner decision) |
| 2.5 | Kelly floor of 2% applies even at negative edge (`risk_manager.py`) | Floor at 0 when the edge is negative, so no entry is sized from a losing estimate. | ADR-002 (sizing) |

**Acceptance for Tier 2:** each change has a test that fails before the fix. Position sizes for a fixed fixture are reported before and after.

### Tier 3: Readiness and measurement (no effect on live trades)

| # | Finding | Fix | Class |
|---|---------|-----|-------|
| 3.1 | Win rate counts `SELL_RECONCILE` and `SELL_TRIM` rows (`scripts/confidence_check.py:99`) | Count only real exit actions. Exclude reconcile and trim rows. | Scripts only |
| 3.2 | `min_win_rate=0.52` has no sample-size floor (`confidence_check.py:15`) | Report the 95% Wilson interval. Return UNKNOWN below a minimum trade count (proposed 30). | Scripts only |
| 3.3 | Walk-forward "out-of-sample" uses the deployed model, trained inside the window (`walk_forward.py`, `backtest/engine.py`) | Train a model per window on data before that window, or label the result as in-sample and remove it from the readiness case. | ADR-002 for the harness; owner decision on use |
| 3.4 | Backtest parameters differ from live: TP clamp, trail arm, sizing, missing gates (`backtest/engine.py`) | Align parameters to live config, or document each gap. Add a backtest-to-live parity table. | Documentation first, then ADR-002 |

**Acceptance for Tier 3:** `confidence_check` reports UNKNOWN below the sample floor, and its win-rate figure excludes reconcile and trim rows (tested on fixture data).

### Tier 4: Documentation and dead code (no behaviour change)

| # | Finding | Fix |
|---|---------|-----|
| 4.1 | `_main_cycle.py:188` says VIX >= 40; `config.py` sets `MACRO_HALT_VIX=28` | Correct the comment to match the constant. |
| 4.2 | `_main_cycle.py:271` says STRONG_BUY 1.67x; actual is 1.25x | Correct the comment. |
| 4.3 | `_main_cycle.py:300` MIN_TP gate can never fire at a 6% TP floor | Remove the dead branch, or document it as a guard for a future TP change. |
| 4.4 | Correlation gate fails open on missing bars or fewer than 20 common rows (`_main_positions.py:97, 108, 115`) | Document as accepted, or fail closed. Owner decision. |
| 4.5 | Sentiment (17.5% weight) is not in training or backtest | Document as unvalidated, or remove from the score until validated. Owner decision. |
| 4.6 | Calibration margin understated because labels overlap | Note in calibration docs. Observation-only, so no behaviour change. |

---

## Not in scope of this ADR

- Replacing the XGB model architecture.
- Survivorship bias in `TRAINING_SYMBOLS` (needs point-in-time membership data; separate ADR).
- Reddit sentiment, RL agent, and the screener (not reached in the review; separate review).
- Changing any live risk limit (`MAX_POSITION_PCT`, `STOP_LOSS_PCT`, `DAILY_LOSS_LIMIT_PCT`). These need the owner's decision in a separate ADR.

## Governance

- Tier 4 can ship as a documentation PR once this ADR is accepted.
- Tiers 1–3 each need their own ADR-002 worktree and named scope before code changes. This document names the intent; each tier's implementation gets its own worktree.
- Model retrain (Tier 1) produces a new `validation_report.json` and new `models/` artifacts, which go to HuggingFace. Those artifacts are not committed.

## Rollback

Each tier reverts independently. Tier 1 reverts by restoring the previous model artifacts on HuggingFace.

---

## Acceptance

*(Proposal. Carries no authority until accepted under ADR-058 D2.)*

**Status:** Proposed
**Accepted By:** —

---

## Status Log

- **2026-11-06 — Proposed.** Drafted from the full-codebase quant review. Item 1.1 verified against code; the rest pending per-item confirmation.

---

## Implementation status (2026-11-06)

Full suite: 1508 passed, 12 skipped, 0 failed.

| # | Item | Status | Where / test |
|---|------|--------|--------------|
| 1.1 | Per-symbol forward target | **Done** | `forward_target()` applied per symbol in `scripts/train_model.py`; `XGBPredictor.train` refuses a frame without a per-symbol target. `tests/test_model_validity.py` |
| 1.2 | Three-way split, holdout not used for early stopping | **Done** | `time_split()` in `bot/strategy/xgb_predictor.py`: 70 / 15 / 15 with purge. Reported AUC and calibration use holdout only. Tests check disjointness and purge gaps |
| 1.3 | Effective-N reporting, purge | **Partly done** | Purge is in. Logged holdout line reports effective n ≈ n / horizon. A proper standard error is not computed yet |
| 1.4 | Regime labels recomputed on combined frame | **Done** | `RegimeClassifier.train` refuses frames without per-symbol labels (`bot/strategy/regime_classifier.py`). Test in `tests/test_model_validity.py` |
| 1.5 | `FWD_VOL_THRESHOLD` vs. single-stock volatility | **Not done: owner decision** | Needs the per-regime label distribution on the corrected labels before a threshold is chosen. Also decide whether HIGH_VOLATILITY should pass Gate 1 |
| 2.1 | Earnings gate fails open and caches the failure | **Done** | Exceptions block the symbol for that cycle and are not cached (`bot/_main_market.py`). Tests in `tests/test_quant_tier2.py` |
| 2.2 | Partial fills recorded at requested notional | **Not done** | Touches the ADR-075 pool debit. Needs owner review of the pool path |
| 2.3 | Logged stop differs from enforced stop | **Not done: owner decision** | Choose one definition and a cap on ATR widening |
| 2.4 | Sizing base decays within a cycle | **Not done: owner decision** | Fix is to use start-of-cycle capital. Sizing is a governed decision |
| 2.5 | Kelly floor applies to a negative edge | **Done** | Non-positive edge sizes to 0 (`bot/risk/risk_manager.py`). The existing test `test_kelly_fraction_minimum_floor` encoded the old floor and was updated to `test_kelly_fraction_negative_edge_sizes_to_zero`. Tests in `tests/test_quant_tier2.py` |
| 3.1 | Win rate counts `SELL_RECONCILE` / `SELL_TRIM` | **Done** | Excluded in `scripts/confidence_check.py` |
| 3.2 | No sample-size floor on win rate | **Done** | Wilson 95% interval is shown. Below 30 closed exits the row is marked UNKNOWN and cannot pass readiness. Tests in `tests/test_confidence_readiness.py` |
| 3.3 | Walk-forward "out-of-sample" uses the deployed model | **Not done** | Needs a per-window model train. Larger harness change |
| 3.4 | Backtest parameters differ from live | **Not done** | Needs a parity table, then alignment |
| 4.1 | VIX comment says 40; actual halt is `MACRO_HALT_VIX=28` | **Done** | Comment corrected (`bot/_main_cycle.py`) |
| 4.2 | STRONG_BUY ratio comment | **Done** | Comment corrected to 0.10 / 0.08 = 1.25 |
| 4.3 | Unreachable MIN_TP gate | **Done (documented)** | Kept as a guard, comment says why |
| 4.4 | Correlation gate fails open on missing bars | **Not done: owner decision** | Either document as accepted or fail closed |
| 4.5 | Sentiment unvalidated | **Not done: owner decision** | Document or remove from score |
| 4.6 | Calibration margin note | **Not done** | Documentation only, low value |

## Retrain result (local, not deployed)

A local retrain on the corrected pipeline was run from the worktree. Nothing was uploaded to HuggingFace, and the tracked `models/` report files were restored, so no artifacts are committed.

- Training rows: 199,485 across 45 symbols (2008-01-03 to 2026-07-22, cutoff 2026-10-07).
- XGB early stopping stopped at **tree 0**. The validation log loss did not improve after the first tree.
- Holdout AUC: **0.510** (previously reported 0.556 on the contaminated target).
- Calibration Brier raw 0.2466, calibrated 0.2456, ECE 0.0187.

**Reading:** the earlier 0.556 was an artifact of the cross-symbol target, as the review predicted. With the corrected target the features show no measurable skill at this configuration. Early stopping at tree 0 needs its own check before the result is trusted. It could be a real absence of signal, or a problem in the feature set or the learning rate. Until that is resolved, the live XGB model's skill is **not established**.

**Consequence for live trading:** the bot currently runs the model trained on the old labels. Do not treat its performance history as evidence of skill. Deploying the corrected model is a separate decision and needs the early-stopping question answered first.

## Status log (addition)

- **2026-11-06 — Accepted by ksri77** ("yes fix all"). Implemented Tiers 1–4 where listed above. Tier 1 retrain shows holdout AUC 0.510 with early stopping at tree 0.

## Feature research: cross-sectional IC, 2026-11-06

**Target:** 21-day forward return minus SPY's, cross-sectionally ranked each day. Score = mean daily rank IC (Spearman), by period. Selection on train and validation only. Holdout reported once. t-stat uses every 21st day to allow for overlapping labels.

**Candidates tested (10 features, 45 symbols, 2008–2026-07):** 12-1 momentum, 1-month and 1-week reversal, 63-day low volatility, 52-week high proximity, 252-day beta, 126-day relative strength, 63-day volume z-score, residual volatility, distance from 200-day MA.

**Results at 21 days (holdout IC / t):**
- 12-1 momentum: +0.050 / 0.94. Positive in all three periods, and at 5, 10 and 63 days.
- Low volatility and low beta: negative IC in train and holdout. High-risk names outperformed in this sample, which is the reverse of the textbook effect.
- Everything else: |IC| below 0.03 and |t| below 1.7 on holdout.
- No feature has holdout |t| ≥ 2. With 10 candidates, a single t of 2 is not strong evidence after correction for multiple tests.

**Adding 12-1 momentum to the XGB feature set:** holdout AUC 0.523 → 0.535. Holdout log loss 0.6952 → 0.6951. Still above the no-skill value of 0.693. Univariate AUC 0.506 (val) to 0.524 (holdout).

**Conclusion:** no robust new feature has been found. Momentum is the strongest candidate, and its effect is small. It needs rolling-origin validation across several folds before it can be trusted. It is not added to the live feature set.

**Next:** (1) rolling-origin test of 12-1 momentum, and of a model with it, across five or more folds. (2) New data sources, since OHLCV alone appears to carry little signal for this target. Candidates are earnings and fundamentals, and sentiment with a validated history. (3) Threshold decision, once a candidate shows multi-fold skill.

Scratch scripts are in the session scratchpad, not in the repository.
## XGB investigation: tree-0 early stop (2026-11-06)

**Question:** why did XGB early stopping halt at tree 0 on the corrected per-symbol labels?

**Findings (scratch probes, not committed):**
- The absolute-return target has base rate 0.40–0.71 by year (overall 0.58). The validation slice is at 0.52 against a training rate of 0.60. Validation log loss at tree 0 (0.7045) equals a constant predictor at the training base rate. Early stopping reacted to base-rate drift, not to missing features.
- Univariate AUCs on train and holdout cluster at 0.47–0.53. The features carry little signal individually.
- Under the absolute-return label the target is mostly market direction. The model was learning the market, not the stock.

**Fix applied (ADR-081 1.6):** the target is now "stock beats SPY over the same 21 bars". The benchmark is computed on SPY's own dates and aligned. SPY's own target is NaN. Base rate is about 0.50. Tests in `tests/test_model_validity.py`.

**Retrain on the excess target (local, not deployed):**
- Early stopping: tree 50 (was tree 0). Validation log loss is no longer degenerate.
- Holdout AUC: **0.520**. Holdout log loss ≈ 0.696, above the no-skill value of 0.693.
- Regularised variants (depth 2–3, larger min child weight), selected on validation: holdout AUC 0.509–0.514.
- Probe with no early stopping (400 trees): holdout AUC 0.538. Single run, sensitive to the stopping point. Standard error for the holdout is roughly 0.015 (effective n ≈ holdout / 21).

**Conclusion:** the pipeline is now correct, and the model shows **no demonstrated out-of-sample skill** for 21-day excess returns with these 22 features in this period. The earlier 0.556 was the contaminated label. The corrected model must not be deployed as a signal.

**Consequence for live gates:** about 77% of holdout predictions clear the live `XGB_MIN_CONFIDENCE` of 0.52. The gate would no longer select candidates. Any deployment of a retrained model therefore needs the threshold reconsidered together with the model. That is a trading decision and is not made here.

**Not done, and why:** no model is deployed or uploaded to HuggingFace. The live bot still loads the HF model trained on the old labels. Improving the features is a research task, not a bug fix.

## Rolling-origin validation, five folds (2026-11-06)

**Setup:** five test windows (2014–16, 2017–19, 2019–21, 2022–23, 2024–26). Training is expanding and ends 21 bars before each test window. Early stopping uses the last 15% of each training window. Excess-over-SPY target. Models: the 22-feature base set, base plus 12-1 momentum, and momentum alone.

**Results (test AUC by fold):**

| Model | 2014–16 | 2017–19 | 2019–21 | 2022–23 | 2024–26 | Mean |
|---|---|---|---|---|---|---|
| base22 | 0.505 | 0.504 | 0.518 | 0.513 | 0.523 | 0.513 |
| base22 + momentum | 0.502 | 0.522 | 0.514 | 0.519 | 0.531 | 0.518 |
| momentum alone | 0.500 | 0.531 | 0.489 | 0.521 | 0.522 | 0.513 |

**Cross-sectional decile spread** (top minus bottom decile, 21-day excess return, daily averages):
- Momentum alone: +1.20%, +0.15%, +1.61%, +0.55%, +2.65%. Positive in every fold.
- base22: −0.39%, −0.34%, +1.54%, +0.22%, +0.55%.

**Correction to the t-statistics.** The t-stats computed on daily spreads treat overlapping 21-day returns as independent, which overstates significance by about √21. Corrected, momentum's t-stats are about 1.0, 0.1, 0.8, 0.3 and 1.6. None is significant at 2.

**Threshold check:** the live 0.52 gate passed between 24% and 97% of candidates across folds, depending on the period. It does not select consistently, so changing the threshold cannot produce a reliable edge with this model.

**Conclusions**
1. The XGB model has no reliable out-of-sample skill on this target. Mean AUC is 0.513.
2. Momentum has a positive sign in every fold, but its significance does not survive the overlap correction. It is a candidate, not a finding.
3. No threshold change is justified. The threshold is not the problem; the model has no skill to threshold.
4. The live bot's entry logic depends on a model that has not been validated under the corrected label. This is the most important open risk.

**Recommended decisions (owner):**
- Whether model-driven entries should be suspended until a candidate passes a corrected multi-fold test.
- Whether to pursue new data sources (fundamentals, earnings, validated sentiment) before any further feature research on price data.
