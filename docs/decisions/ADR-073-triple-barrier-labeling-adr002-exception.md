# ADR-073: ADR-002 Exception — Triple-Barrier Labeling for XGB/LSTM Training

**Status:** Accepted
**Date Proposed:** 2026-10-22
**Date Accepted:** 2026-10-22
**Decision Type:** Narrow ADR-002 exception, prospective (implementation not yet started). Authorizes a specific, named change to the model-training label scheme; authorizes no deployment of any resulting model to production.
**Related ADRs:** ADR-002 (protected path this ADR excepts), ADR-052 (prior exception governing `retrain.yml`'s backtest quality gate — not reopened or amended here; this ADR's resulting model still passes through that same gate), ADR-072 (prior retroactive exception — this ADR follows its process correctly from the start rather than retroactively, per that ADR's own stated position)

---

## Context

### The finding that motivates this change

Investigated this session (read-only, no code changed yet): `bot/strategy/xgb_predictor.py` and `bot/strategy/lstm_predictor.py` train on two different, internally inconsistent, fixed-horizon labels —

- XGB (`xgb_predictor.py:14-15,81-82`): label = 1 if `close` 21 bars ahead is ≥0.3% higher than today's `close`. Comment claims this "aligns with `MAX_HOLD_DAYS=45`" — it does not (21 ≠ 45).
- LSTM (`lstm_predictor.py:16,125-126`): label = 1 if `close` 10 bars ahead is ≥0.3% higher. Comment claims this "matches XGBPredictor and 14-day max hold" — also wrong on both counts (XGB uses 21, not 10; the real config value is 45, not 14).

Neither label reflects how a real position actually exits. Real exits (`bot/_main_cycle.py:262-267`, `bot/_main_positions.py:125`) use an ATR-derived stop (`ATR_STOP_MULTIPLIER=2.0`, clipped to [1.5%, 10%]), an ATR-derived take-profit (`ATR_TP_MULTIPLIER=4.0`, clipped to [6%, 25%]), and a 45-day time-exit that only fires if unrealized P&L is still <1%. Confirmed against the 14 actual closed trades in `trades.db`: observed `holding_days` ranges from 0 to 57, clustering near 7 and near 50 — nothing resembling either model's fixed 21-bar or 10-bar window. The models are trained to answer "will price be up at one arbitrary point," not "will this position hit its real take-profit before its real stop-loss or time limit" — the actual question that determines live P&L.

This is the textbook case for triple-barrier labeling (López de Prado, *Advances in Financial Machine Learning*): label each training example by which of the three real exit conditions — the real take-profit %, the real stop-loss %, or the real max-hold-days — would have been hit first, using the same thresholds the live code already enforces.

### Why this also needs purged validation, not just a new label

Triple-barrier labels have variable-length, overlapping windows (a trade that hits its stop in 2 days and one that times out in 45 days both become training examples). Ordinary k-fold or naive walk-forward validation on overlapping label windows produces an optimistically biased accuracy estimate — this is well documented (purged cross-validation exists specifically to delete training examples whose label window overlaps a test window, plus an embargo buffer after each test block). `scripts/walkforward_backtest.py` currently has no purge/embargo step. Implementing triple-barrier labeling without also adding this would risk a backtest comparison that *looks* better without actually being better.

---

## Decision

Authorize the following named changes, and no others, to be developed and validated in an isolated worktree before any merge to `main`.

## 1. Named Scope

**New file (protected — under `bot/strategy/`):**
- `bot/strategy/triple_barrier.py` — pure functions only. No import of any execution, order-placement, Alpaca, or live-trading-cycle module. Not imported by `bot/main.py`, any `bot/_main_*.py` file, or any file reachable from either ADR-002 live-trading entry point. Used only by `train()` methods and by training/backtest scripts.

**Modified files (protected):**
- `bot/strategy/xgb_predictor.py` — replace the fixed-horizon label computation (`xgb_predictor.py:81-82`) with a call to the new triple-barrier function. `FORWARD_PERIODS`/`MIN_MOVE_PCT` constants may be retained for backward-compatible loading of already-trained model metadata but are no longer used to compute new labels.
- `bot/strategy/lstm_predictor.py` — the same replacement at the analogous label-computation line (`lstm_predictor.py:125-126`), using the *same* triple-barrier function as XGB (fixing the XGB/LSTM horizon mismatch as a side effect, not a separate change).

**Modified files (unprotected — not an ADR-002 path, cited for completeness):**
- `scripts/walkforward_backtest.py` — `_train_window_xgb` updated to use the same triple-barrier labeling; add a purge/embargo step to its train/test split.
- `scripts/train_model.py` — no label-logic change; verify the dataframe it passes to `.train()` retains the raw `atr` column (`bot/strategy/features.py:43`) the new labeling needs (it is already computed, just not in `FEATURE_COLS`, so this is a verification step, not a new computation).
- New test file under `tests/` for `bot/strategy/triple_barrier.py`'s pure functions.

## 2. The Labeling Rule (stated precisely, not left to implementation-time judgment)

For a training example at bar *i* of a given symbol's history:
- `entry_price = close[i]`; `stop_pct`, `tp_pct` computed by the *same* formula as `bot/_main_cycle.py:262-264` (ATR-based, same multipliers and clips; same flat fallback if ATR is unavailable for that bar).
- Scan forward from bar *i+1* up to `min(i + MAX_HOLD_DAYS, len(df)-1)`:
  - label = **1** if `close` (or high, for the take-profit side — stated here as `close`-only for a first implementation, matching this project's existing bar-granularity convention; using intrabar high/low is an explicit non-goal of this ADR, see below) reaches `entry_price * (1 + tp_pct)` before it reaches `entry_price * (1 - stop_pct)`.
  - label = **0** if the stop level is reached first.
  - if neither is reached by the time horizon: label = **1** if unrealized return at that point is ≥ 0, else **0** (a stated, documented choice — matches the live code's own time-exit condition being gated on `pnl_pct < 0.01`, simplified to a breakeven threshold for label-generation purposes rather than re-deriving the exact 1% figure).
- Training examples within `MAX_HOLD_DAYS` bars of the end of a symbol's available history (no room to resolve the label) are dropped, not labeled by truncated/partial information.

## 3. Risk Tier and Rationale

**High.** Unlike ADR-072's three sub-scopes (infrastructure/plumbing), this changes the actual trained artifact backing every live BUY/SELL decision. Mitigated by:

- Development and all backtesting happens in an isolated worktree, per ADR-002 item 2, not on `main`.
- Almost the entire surface area of this change is unprotected (`scripts/`, `tests/`) or a new, pure, non-execution-path module. The only edits to files already reachable from a live-trading entry point are the two label-computation lines named in §1.
- No resulting model is authorized to reach production by this ADR. A retrained artifact only reaches HuggingFace via the existing weekly `retrain.yml` pipeline, which ADR-052 already made a *blocking* gate (`scripts/backtest_gate.py`) — this ADR does not touch, loosen, or bypass that gate. Promoting a new model remains a separate, explicit, human-triggered act.
- The comparison between old and new labeling is made on identical historical data via `scripts/walkforward_backtest.py`, both before implementation (current baseline) and after (with purge/embargo), so the decision to proceed to an actual retrain is evidence-based, not assumed.

## 4. Isolated Branch/Worktree Requirement

Per ADR-002 item 2 — **explicitly required, and explicitly not waived**, unlike the gap documented in ADR-072. All implementation and backtesting work happens in an isolated git worktree. No commit touching the protected files in §1 lands on `main` until backtest comparison results (§6) have been reviewed.

## 5. Workflow-Reference Analysis (ADR-002 item 3)

No `.github/workflows/*.yml` file is touched by this ADR. `retrain.yml` references `scripts/train_model.py` by name but this ADR makes no change to that script's invocation, only (if at all) to the dataframe columns it forwards — verified: `retrain.yml` does not reference `xgb_predictor.py`, `lstm_predictor.py`, or `triple_barrier.py` by name, only the training script.

## 6. Test Requirements and Validation Performed Before Any Merge to `main`

**Required, in order, before this ADR's implementation is considered complete:**

1. Unit tests for `bot/strategy/triple_barrier.py` (new, under `tests/`): synthetic price paths covering (a) take-profit hit first, (b) stop-loss hit first, (c) neither hit within the horizon with a positive ending return, (d) neither hit with a negative ending return, (e) a bar sequence too short to resolve — confirms it's correctly dropped, not mislabeled.
2. `tests/test_xgb_predictor.py` and `tests/test_lstm_predictor.py` (existing) re-confirmed green against the modified `train()` methods.
3. Full test-suite baseline (`tests/`, `sentinel_engine/tests/`, `applications/`) — zero regressions versus the pre-change baseline.
4. `scripts/walkforward_backtest.py` run twice on identical historical data and date range: once against the current (fixed-horizon) labeling as a recorded baseline, once against the new triple-barrier labeling with purge/embargo added — Sharpe, win rate, max drawdown, and return compared side by side. **This ADR does not predetermine the outcome of that comparison or pre-authorize a retrain based on it** — see Explicitly Not Established.
5. `git diff --name-only` against the base commit, confirmed to show only the files named in §1 (plus the new test file) — no incidental changes to any other protected path.

## 7. CLI and Scheduler/HTTP Entry-Point Confirmation

Both stated, not assumed, per ADR-002 item 6:

- **CLI path** (`trade.yml` → `bot/main.py --mode paper --loop`): unaffected by this ADR directly — this ADR changes what a model is *trained on*, not the live prediction call (`XGBPredictor.predict_proba()`/`LSTMPredictor`'s inference method, neither of which is touched). The live path only sees an effect once a human explicitly promotes a retrained model via `retrain.yml` — a separate, later, human-gated act this ADR does not authorize in advance.
- **Scheduler/HTTP path**: same reasoning — this ADR touches training code, not the dispatch path, and the same "no change until a model is explicitly promoted" logic applies.

## 8. Rollback Plan (stated before implementation begins, per ADR-002 item 5)

- **If not yet merged:** discard the worktree. No state on `main` to unwind.
- **If merged (label/training code only, no model promoted yet):** revert the commit; `bot/main.py`'s live predictions are unaffected either way, since no new model artifact was ever pushed to HuggingFace under this ADR alone.
- **If a retrained model was separately promoted via `retrain.yml` and behaves badly in production:** `retrain.yml`'s existing "Pull trade database from HuggingFace" / model-push history provides the prior model artifact; re-running `scripts/load_model_hf.py` against the previous HuggingFace model revision restores it. This ADR does not itself authorize that promotion step — it is named here only so a rollback path exists if a future, separate decision promotes a model trained under this scheme.

---

## Constraints

**Allowed:**
- Exactly the files and changes named in §1, developed in an isolated worktree.
- The labeling rule as precisely stated in §2 — any deviation from that rule discovered to be necessary during implementation requires returning to this ADR for an amendment or a follow-up ADR, not a silent judgment call.

**Forbidden:**
- Any change to `scripts/backtest_gate.py`'s thresholds (`MIN_SHARPE`, `MIN_RETURN`, `MAX_DRAWDOWN`, `MIN_WIN_RATE`) — ADR-052 already governs that gate's enforcement; this ADR does not reopen it.
- Any change to `bot/_main_cycle.py`, `bot/_main_positions.py`, or any other live decision/execution-path file, including the real ATR-based stop/target computation itself — this ADR reads and reuses that formula for labeling, it does not modify it.
- Any `.github/workflows/*.yml` change.
- Promoting, pushing, or deploying any resulting retrained model to HuggingFace or to production — that is explicitly a separate, later, human-gated decision, not authorized here.
- Implementing meta-labeling (a secondary classifier on top of the primary signal) as part of this ADR — noted below as a candidate for a future, separate ADR, not bundled into this one.

---

## Explicitly Not Established By This ADR

- Does not authorize deploying any model trained under the new labeling scheme to production. That remains a separate, later, explicit decision, made after reviewing the backtest comparison in §6.4.
- Does not predetermine that triple-barrier labeling will outperform the current scheme — this ADR authorizes the *experiment*, stated and scoped, not the conclusion.
- Does not adopt meta-labeling, intrabar (high/low) barrier resolution, or any alternative to the `close`-only barrier check named in §2 — each would be a separate, future ADR if pursued.
- Does not change `MAX_HOLD_DAYS`, `ATR_STOP_MULTIPLIER`, `ATR_TP_MULTIPLIER`, or any other live-trading risk parameter — this ADR reuses their current values for label computation, unchanged.

---

## Acceptance

*(Per ADR-058 D4, this document is a proposal and carries no authority until it is landed under ADR-058 D2, by explicit act of the Architecture Owner.)*

**Status:** Accepted — Implemented, Not Merged (Experiment Concluded Negative)
**Date Accepted:** 2026-10-22
**Accepted By:** ksri77 (Architecture Owner) — explicit acceptance given in-session after being asked directly, following an earlier ambiguous message that was deliberately not treated as acceptance
**Outcome:** The authorized experiment ran to completion per §6. The evidence did not support the hypothesis — see Status Log below. Per Rollback Plan §8 ("If not yet merged: discard the worktree. No state on main to unwind"), the isolated worktree was discarded and no code under this ADR reached `main`. This document is kept as the governance record of what was tried and why it was not adopted.

---

## Status Log

- **2026-10-22 — Proposed.** Drafted following the ADR-052 precedent for a narrow, prospective ADR-002 exception, and ADR-072's own stated position that the isolated-worktree requirement should be followed from the start rather than retroactively excused. Not yet accepted; no implementation has started.
- **2026-10-22 — Accepted.** Accepted by ksri77 (Architecture Owner) after explicit confirmation. Implementation to proceed in an isolated worktree per §4.
- **2026-10-22 — Implementation complete (in the isolated worktree only, later discarded — see below); Section 6 validation run.** `bot/strategy/triple_barrier.py` was added there (pure, new); `xgb_predictor.py`/`lstm_predictor.py` label lines were replaced; `scripts/walkforward_backtest.py`/`scripts/train_model.py` were updated. One necessary addition beyond the original named scope, disclosed not hidden: `train_model.py`'s XGB call site had to stop dropping the `symbol` column, since per-symbol grouping (required by §2's "a given symbol's history") needs it — XGB's call site previously dropped it, LSTM's did not. A real bug was caught before merge: an early version wrote grouped labels back via `.loc[group.index]`, which silently corrupts results once symbols share calendar dates (true in production — every symbol has rows on the same trading days); fixed to use positional boolean-mask assignment, verified via a manual multi-symbol integration run. New unit tests (7, covering all 5 required cases) passed; existing `test_xgb_predictor.py`/`test_lstm_predictor.py` passed; full `tests/` (1438 passed/11 skipped), `sentinel_engine/tests` + `applications/` (3033 passed/6 skipped) showed zero regressions. `git diff --name-only main` matched the named scope exactly. None of this code exists on `main` — see the closing entry below.
- **2026-10-22 — Backtest comparison (small, valid run): NEGATIVE.** 15 symbols, 3 windows (2023–2025), identical data on both runs, both models trained non-degenerately (baseline: tree 5, AUC 0.513; triple-barrier: tree 49, AUC 0.525). Baseline (fixed-horizon, main) — 53.2% mean win rate, +32.2% mean return, Sharpe 2.16, 10,116 trades, +8.7% alpha (2/3 positive windows). Triple-barrier — 49.9% mean win rate, +13.6% mean return, Sharpe 0.91, 4,175 trades, -9.8% alpha (0/3 positive windows). Triple-barrier underperformed on every metric.
- **2026-10-22 — Backtest comparison (full scale: all ~44 symbols, 5 windows): INVALID, not used to decide.** Baseline showed 49,683 total trades but its XGB model had collapsed to a near-constant ~0.598 output (verified by direct inspection of `predict_proba` across 5,000 held-out rows — min 0.5917, max 0.6062), meaning it fired on nearly every candidate rather than discriminating; triple-barrier showed only 22 total trades from the same underlying collapse landing on the other side of the 0.52 confidence gate. Root-caused to a pre-existing weakness in `_train_window_xgb`'s per-window retraining (early-stopping terminates at tree 1-2 for at least the 2024-12-31 cutoff, for both labeling schemes identically) — confirmed unrelated to this ADR by checking the actual deployed production model (`models/saved/xgb_predictor.pkl`, trained via the unmodified `train_model.py` path): 87 boosting rounds, AUC 0.556, healthy. This full-scale result is an artifact of the backtest tool, not evidence about triple-barrier labeling; recorded here so a future session doesn't re-derive this. Filed as a separate TD item (see `docs/TECHNICAL_DEBT.md`) — low urgency since production training is unaffected.
- **2026-10-22 — Closed: not merged.** Architecture Owner (ksri77) reviewed the above and agreed with the recommendation to not proceed. The only valid comparison (the 15-symbol/3-window run) showed a consistent, explainable regression: triple-barrier labeling asks the model to predict a materially harder, path-dependent target (which of three ATR-scaled barriers is touched first over up to 45 days) than the fixed-horizon label, and the existing 22 generic technical-indicator features did not carry enough signal for that harder target. Isolated worktree (`worktree-triple-barrier-labeling`) discarded per §8; `main` remains on fixed-horizon labeling. A narrower, lower-risk follow-up remains available if desired: simply aligning XGB's 21-bar and LSTM's 10-bar horizons to the same fixed value (the original comment-drift defect that motivated this ADR) without adopting triple-barrier labeling itself — not authorized by this ADR, would need its own.
