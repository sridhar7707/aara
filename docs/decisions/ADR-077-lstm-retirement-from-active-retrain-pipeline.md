# ADR-077: ADR-002 Exception — Retire LSTM from the Active Retrain Pipeline

**Status:** Accepted
**Date Proposed:** 2026-11-04
**Date Accepted:** 2026-11-04
**Decision Type:** Narrow ADR-002 exception. Stops weekly LSTM retraining and the now-meaningless weekly LSTM quality alert. Makes zero change to live trading behavior, decision data shape, or any downstream consumer of `lstm_prob`.

---

## Context

This session's investigation (real `retrain.yml` logs, 79 real weekly commits on the HF model repo configured via `HF_REPO_ID`) found that the LSTM has been degraded — val_loss above the 0.58 "no directional signal" threshold — for at least 10 straight weekly retrains, with an identical failure mode every time: train loss falls every epoch, val loss bottoms out at epoch 2 (best ever: 0.617, still above threshold) and diverges every epoch after. More training data each week has not changed this once in 10 weeks — the failure is structural (sliding-window overlap + cross-symbol correlation shrink the *effective* independent sample size far below the raw row count relative to the model's ~217K parameters), not a "needs more data" problem.

Because of the existing degradation-reweighting logic (`bot/strategy/ensemble.py`'s `_reweight_score`), the LSTM's 0.175 ensemble weight has already been transferring to XGB on every cycle for this entire period — it has not influenced a single live trading decision in at least 10 weeks. Retraining it weekly costs ~6.5 minutes of the ~8-minute `train_model.py` run (confirmed from the 2026-11-01 run, id `41263357877`) for a model that is discarded every time.

The user confirmed: retire it from the active pipeline rather than keep training a design that has failed identically for 10 straight weeks under the hope that more of the same data will fix it.

---

## Decision

Authorize the following named changes, and no others, to be developed and validated in an isolated worktree before any merge to `main`.

## 1. Named Scope

**Modified file (unprotected):**
- `scripts/train_model.py`:
  - Remove the `LSTMPredictor()` instantiation and its `.train(...)` call — no more weekly LSTM training.
  - Remove the now-unused `from bot.strategy.lstm_predictor import LSTMPredictor` and `from bot.strategy.lstm_predictor import LSTM_DEGRADED_VAL_LOSS` imports.
  - In the `report` dict written to `models/validation_report.json`, replace the real `lstm.val_loss` read with an explicit, documented **retirement sentinel**: `"lstm_val_loss": 1.0` (a value, not a measurement — chosen because it must stay `> LSTM_DEGRADED_VAL_LOSS` (0.58) forever so every downstream consumer of this field keeps treating the LSTM as degraded, exactly as it already has been for 10 weeks). Add `"lstm_retired": true` and `"lstm_retired_since": "2026-11-04"` alongside it so the sentinel is self-explanatory to anyone reading the JSON, not silently indistinguishable from a real bad week.
  - Remove the LSTM branch of the "Model quality gate" section (the `if report["lstm_val_loss"] > LSTM_DEGRADED_VAL_LOSS: issues.append(...)` check) — this is a settled, chosen state now, not a weekly anomaly to flag.
  - Remove `"LSTM model"` and `"LSTM scaler"` from the "Artifact verification" `required` dict — `train_model.py` no longer produces `models/saved/lstm_predictor.pt`/`lstm_scaler.pkl`, so requiring them would make the script `sys.exit(1)` and fail the entire weekly retrain (this was confirmed as a real failure mode during scoping, not a hypothetical — the artifact-verification step currently hard-requires both files).
  - Update the module docstring's outputs comment and the final quality-gate log line to stop implying `lstm_val_loss` is a live weekly measurement.

**Modified file (protected — workflow):**
- `.github/workflows/retrain.yml`: in the inline "Model quality alert" Python step, remove `lstm_loss = r.get('lstm_val_loss', 1)` and its `if lstm_loss > 0.58: issues.append(...)` branch (this is a *second*, independent place the same now-meaningless weekly "LSTM degraded" check lives — leaving it in place would keep sending a false "model quality issue" Telegram alert every week about a settled, intentional state). Drop `lstm_loss=` from the "Models OK" success message string. No other line in this workflow changes.

**Explicitly not touched:**
- `bot/strategy/lstm_predictor.py` — the `LSTMPredictor` class, `is_degraded`/`_check_degradation()`/`predict_proba()`'s fallback logic, and `train()` itself all stay exactly as they are. This is deliberate: `_check_degradation()` reading the sentinel `lstm_val_loss=1.0` (always `> 0.58`) is the exact mechanism that keeps `is_degraded=True`, which keeps `predict_proba()` returning exactly `0.5`, which keeps `ensemble.py`'s `_lstm_is_indeterminate(0.5)` evaluating `True`, which keeps the ensemble weight transfer to XGB happening — removing or weakening any part of this chain, instead of feeding it a safe sentinel, is exactly how a retirement could accidentally *re-enable* a known-broken frozen model in live trading. `train()` is left callable (not deleted) so a future, separately-scoped experiment can still use it deliberately.
- `bot/strategy/ensemble.py`, `bot/main.py`, `bot/_main_cycle.py`, `bot/db/trade_log.py`, every dashboard component, `applications/trading_intelligence/*`, `sentinel_engine/*` evidence adapters, and every other of the ~79 files that read or write `lstm_prob`/`lstm_val_loss`/`is_degraded` — **none of these change**, because none of them receive a different value than they already have been receiving for 10+ weeks (`lstm_prob≈0.5`, degraded=True). This is the reason the blast radius of this ADR is far smaller than the 79-file surface its grep touches.
- `scripts/load_model_hf.py` / `scripts/save_model_hf.py` — unchanged. Both already handle a missing/unchanged LSTM artifact gracefully: `save_model_hf.py` already skips any model file that doesn't exist on disk (now always true for the two LSTM files, since `train_model.py` no longer creates them) without failing the push; `load_model_hf.py` already wraps each file's download in its own try/except. The last real LSTM model pushed to HF (before this ADR) simply stays the latest version on HF forever, and the live bot keeps pulling that same frozen file, exactly as it pulls the last real model today.
- `.github/workflows/trade.yml` — unchanged; it already pulls whatever is on HF via `load_model_hf.py`, which needs no change.

## 2. Risk Tier and Rationale

**Low**, contingent entirely on the sentinel value in §1 being correct — which is why it is specified exactly, not left to a default:

- No live decision path changes. The LSTM's live contribution has been zero for 10+ weeks already (confirmed via the existing degradation-reweighting logic); this ADR stops paying for a weekly training run that produces a result that gets discarded every time, and nothing else.
- The one real risk is the sentinel: if `lstm_val_loss` were ever allowed to read as `≤ 0.58` (e.g., via an omitted key defaulting to `0.0`, or a copy-paste of the wrong constant), `is_degraded` would flip to `False` and the live bot would start trusting a frozen, never-retrained-again LSTM output at full ensemble weight — a real regression, not a cosmetic one. §5's test requirements name this as the primary thing to verify, not an afterthought.

## 3. Isolated Branch/Worktree Requirement

Required, per the process established this session.

## 4. Workflow-Reference Analysis (ADR-002 item 3)

`.github/workflows/retrain.yml` is touched (see §1) — only the inline quality-alert Python block changes; no job, step, trigger, secret, or other step is added, removed, or reordered. `.github/workflows/trade.yml` is not touched.

## 5. Test Requirements and Validation Performed Before Any Merge to `main`

1. **Primary safety test**: construct a `models/validation_report.json` matching the new post-ADR format (`lstm_val_loss: 1.0, lstm_retired: true`), load a fresh `LSTMPredictor()` against it, and assert `is_degraded is True`. Then assert `predict_proba()` on a real feature sequence returns exactly `0.5`. Then assert `ensemble_signal(xgb_prob=0.7, lstm_prob=0.5, ...)` reweights to `w_xgb=0.825` (i.e., matches what 10 weeks of real production behavior has already shown) — this is the exact chain identified as the one way this change could go wrong, verified end-to-end rather than assumed.
2. New/updated tests for `scripts/train_model.py`: `LSTMPredictor.train()` is never called (mock and assert not called); the written report always has `lstm_val_loss >= 0.58` and `lstm_retired: true`; the "Artifact verification" step does not require `models/saved/lstm_predictor.pt`/`lstm_scaler.pkl` and does not `sys.exit(1)` when they're absent (simulating the real fresh-CI-checkout condition where they genuinely won't exist going forward).
3. Existing `tests/test_xgb_predictor.py`, `tests/test_lstm_predictor.py` (the class itself, unchanged) re-confirmed green, unchanged.
4. Manual extraction and local execution of the edited inline Python block from `.github/workflows/retrain.yml` against a sample report, confirming it runs without error and no longer flags the LSTM.
5. Full `tests/` suite — zero regressions versus the pre-change baseline (expected: unchanged, since nothing the 79-file consumer web reads is different).
6. `git diff --name-only` against the base commit, confirmed to match §1 exactly (two files: `scripts/train_model.py`, `.github/workflows/retrain.yml`).

## 6. CLI and Scheduler/HTTP Entry-Point Confirmation

**Retrain path** (`retrain.yml` → `scripts/train_model.py`): now trains two models instead of three and writes an explicit retirement sentinel instead of a real LSTM measurement; artifact verification and the quality-alert step are updated to match. No new entry point. **CLI/live-trading path** (`trade.yml` → `bot/main.py`): unaffected — it keeps pulling and running against the frozen, last-real LSTM model exactly as it does today, via the unchanged `load_model_hf.py`.

## 7. Rollback Plan

- **If not yet merged:** discard the worktree.
- **If merged and something looks wrong:** revert the commit. `lstm.train()` resumes on the next scheduled retrain; worst case is paying the ~6.5-minute weekly compute cost again while a fix is made — no live-trading exposure either way, since the LSTM is excluded from live decisions in both the pre- and post-ADR state.

---

## Constraints

**Allowed:** Exactly the two file changes named in §1, developed in an isolated worktree.

**Forbidden:**
- Any change to `bot/strategy/ensemble.py`'s `WEIGHTS`, `_reweight_score`, or `_lstm_is_indeterminate` — the existing reweighting logic is what makes this retirement safe; it is not being touched or "simplified" as part of this ADR.
- Any change to `bot/strategy/lstm_predictor.py` itself (the class, its degradation check, or its `train()`/`predict_proba()` methods).
- Deleting `models/saved/lstm_predictor.pt`/`lstm_scaler.pkl` from the live HF model repo, or editing `scripts/load_model_hf.py`/`save_model_hf.py`.
- Writing a `lstm_val_loss` value `≤ 0.58` anywhere in `scripts/train_model.py`'s report — the sentinel must stay above the degradation threshold.
- Any change to `trade.yml` or any live-trading entry point.

---

## Explicitly Not Established By This ADR

- Does not decide whether a redesigned sequence model is ever worth building. That is a separate, future, explicitly-scoped experiment (different architecture size, possibly different data/labeling) with its own pass/fail bar — not a resurrection of the current implementation.
- Does not remove `lstm_prob`/`lstm_val_loss` as concepts from the trades/signal_log schema, the dashboard, or the Trust Ledger/evidence layers. Those ~79 files keep working exactly as they do today, reading a value that is already — and remains — the degraded fallback.
- Does not address the XGB AUC plateau (~0.552, flat for 10 weeks) found in the same investigation — that is a feature-engineering/labeling question, not an LSTM question, and is out of scope here.

---

## Acceptance

*(Per ADR-058 D4, this document is a proposal and carries no authority until it is landed under ADR-058 D2, by explicit act of the Architecture Owner.)*

**Status:** Accepted
**Date Accepted:** 2026-11-04
**Accepted By:** ksri77

---

## Status Log

- **2026-11-04 — Proposed.** Found via real production evidence (10 weeks of identical LSTM overfitting in `retrain.yml` logs; 79 real weekly commits on the HF model repo confirming the pattern never changes). User explicitly confirmed retirement over continued weekly retraining of a design that has failed identically every week it's been tried.
- **2026-11-04 — Accepted by ksri77.** Implementation to follow in an isolated worktree per §3.
