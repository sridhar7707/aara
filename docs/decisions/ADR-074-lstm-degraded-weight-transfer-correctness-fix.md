# ADR-074: ADR-002 Exception — LSTM Degraded-Weight-Transfer Correctness Fix

**Status:** Accepted
**Date Proposed:** 2026-10-22
**Date Accepted:** 2026-10-22
**Decision Type:** Narrow ADR-002 exception, prospective (implementation not yet started). Authorizes a specific, named bug fix to the live LSTM prediction path.
**Related ADRs:** ADR-002 (protected path this ADR excepts), ADR-073 (prior exception this session; this ADR follows the same isolated-worktree-from-the-start process)

---

## Context

Investigated this session (read-only, no code changed yet) as part of a broader review of ensemble-weighting correctness (triggered by the user's "improve prediction accuracy" request). Found a mismatch between what the bot tells the user via Telegram and what the code actually does — and, on self-review before drafting a fix, found that the first fix location considered would only have been a partial correction.

`bot/main.py:168-176`, when `lstm.is_degraded` is `True`, sends:

> "⚠️ LSTM model degraded — val_loss={val_loss} (near-random). **LSTM weight transferred to XGB for today's cycle.** Run `python scripts/train_model.py`..."

This message claims LSTM's ensemble weight is transferred to XGB for the whole cycle whenever the model is degraded. That is not what happens.

`LSTMPredictor.predict_proba()` (`bot/strategy/lstm_predictor.py:232-263`) forces its `0.5` fallback return (and sets `last_prediction_is_fallback = True`) in exactly three cases: `self.model is None`, fewer than `SEQ_LEN` bars available, or a NaN in the input sequence/output. It never checks `self.is_degraded`. A degraded-but-otherwise-functioning model (loaded fine, runs a real forward pass, produces a non-NaN number) returns whatever its actual sigmoid output is — which can fall anywhere in `[0, 1]`, not forced toward neutral.

Downstream, `bot/strategy/ensemble.py`'s `_reweight_score()` only transfers LSTM's weight to XGB when `_lstm_is_indeterminate(lstm_prob)` is true, i.e. when *that specific prediction* falls in `[_LSTM_INDETERMINATE_LO, _LSTM_INDETERMINATE_HI]` = `[0.45, 0.55]`. It has no awareness of `self.is_degraded` — only of the numeric value it's handed.

**An earlier version of this ADR proposed fixing this at the `ensemble_signal()` call site** (threading an `lstm_is_degraded` flag through `bot/main.py` and `ensemble.py`). On self-review, that fix was found to be incomplete: it would correct the BUY/SELL/HOLD decision but leave `ensemble_confidence()` — used for the dashboard, Telegram alert text, `signal_log`, `trades`, `decision_log`, and `decision_events.final_confidence` — still computing against the same un-neutralized, potentially noisy `lstm_prob`. That would trade one inconsistency for another: the decision would correctly ignore a wild degraded reading while every displayed/logged confidence number still included it at full weight.

**Net effect of fixing it at the right layer instead:** the live LSTM model is currently degraded (`val_loss=0.6195` vs. `LSTM_DEGRADED_VAL_LOSS=0.58` — confirmed by reading `models/validation_report.json` this session). Forcing `predict_proba()` itself to return the neutral fallback whenever `is_degraded` is `True` makes every consumer — the trading decision, the logged confidence, the dashboard, the Telegram text — consistently treat a known-bad model as neutral, with a single change in a single already-tested code shape (the existing early-return-0.5 pattern), rather than needing to update every caller individually.

---

## Decision

Authorize the following named change, and no other, to be developed and validated in an isolated worktree before any merge to `main`.

## 1. Named Scope

**Modified file (protected):**
- `bot/strategy/lstm_predictor.py` — in `predict_proba()`, add a check at the top (alongside the existing `self.model is None` check): if `self.is_degraded` is `True`, set `self.last_prediction_is_fallback = True` and return `0.5`, before attempting any real prediction. No other branch of `predict_proba()` changes.

**Explicitly not touched:**
- `bot/strategy/ensemble.py` — `ensemble_signal()`, `ensemble_confidence()`, `_reweight_score()`, `_lstm_is_indeterminate()`, `WEIGHTS`, all thresholds — unchanged. Once `predict_proba()` returns exactly `0.5` for a degraded model, the existing `_lstm_is_indeterminate(lstm_prob)` check (`[0.45, 0.55]`) already catches it correctly — no signature or logic change needed here at all.
- `bot/main.py` — the `ensemble_signal(...)` call at line 324, the `_models_ok` audit computation at line 331, and the Telegram alert at lines 168-176 are all unchanged; they already read `lstm.is_degraded` independently for their own purposes and continue to work as before.
- `bot/_main_cycle.py`, `bot/_main_trust_decisions.py`, `bot/trust_ledger/decisions.py` — unaffected; these already receive `lstm_is_degraded` for audit-trail purposes and are untouched.
- `backtest/engine.py` — not modified, but its behavior improves as a side effect if it is ever given a real (non-stub) degraded `LSTMPredictor`; this is a welcome consequence, not a new risk, since that file is not ADR-002-protected.

## 2. Risk Tier and Rationale

**Low.** Smaller and lower-risk than the originally-considered fix: one file, one new early-return branch copying the shape of an existing, already-tested one (`self.model is None` → `last_prediction_is_fallback = True; return 0.5`).

- No new decision logic is introduced anywhere in `ensemble.py` or `main.py` — the existing, already-tested indeterminate-handling path now simply receives a `0.5` it previously wouldn't have, for a case (`is_degraded`) it was always meant to be protected against per the Telegram alert's own claim.
- **Explicitly flagged, not hidden:** because the live LSTM model is degraded right now, this fix changes live trading and dashboard/Telegram display behavior as soon as it is deployed. This is the intended, correct effect (making the code match the alert the bot already sends), not an unintended side effect.

## 3. Isolated Branch/Worktree Requirement

Per ADR-002 item 2 — required, consistent with the process established in ADR-073 (not waived). All implementation and testing happens in an isolated git worktree. No commit touching the protected file in §1 lands on `main` until test results (§5) have been reviewed.

## 4. Workflow-Reference Analysis (ADR-002 item 3)

No `.github/workflows/*.yml` file is touched. `trade.yml` invokes `bot/main.py` by name but makes no reference to `lstm_predictor.py`'s internals.

## 5. Test Requirements and Validation Performed Before Any Merge to `main`

1. New unit test(s) in `tests/test_lstm_predictor.py`: with a mocked model that would otherwise return a confident, non-neutral value (e.g. logit=2.0, as the existing `test_lstm_predictor_genuine_prediction_return_type_and_value_unchanged` test already does), setting `predictor.is_degraded = True` must make `predict_proba()` return exactly `0.5` with `last_prediction_is_fallback is True` — proving the degraded flag overrides even a confident-looking model output. A second test confirms `is_degraded = False` (the default) preserves exactly today's existing behavior for the same mocked model — no regression for the non-degraded case.
2. All existing `tests/test_lstm_predictor.py` and `tests/test_ensemble.py` cases re-confirmed green, unchanged — this fix requires no edits to either existing test file.
3. Full `tests/` suite — zero regressions versus the pre-change baseline.
4. `git diff --name-only` against the base commit, confirmed to show only `bot/strategy/lstm_predictor.py` (plus the test file).
5. Manual trace: confirm `bot/main.py:331`'s `_models_ok` computation and the Telegram alert at `bot/main.py:168-176` are unaffected (both continue to read `lstm.is_degraded` independently, as before — this fix doesn't touch either).

## 6. CLI and Scheduler/HTTP Entry-Point Confirmation

Per ADR-002 item 6: **CLI path** (`trade.yml` → `bot/main.py --mode paper --loop`) is directly affected — `predict_proba()` is called every cycle for every evaluated symbol, so this fix takes effect on the very next live run after merge. This is the intended effect, stated here rather than discovered later. **Scheduler/HTTP path**: no separate HTTP/scheduler entry point calls `predict_proba()` outside the main trading loop; unaffected beyond the CLI path already covered.

## 7. Rollback Plan (stated before implementation begins, per ADR-002 item 5)

- **If not yet merged:** discard the worktree. No state on `main` to unwind.
- **If merged and live behavior looks wrong:** revert the commit. The only behavioral change is forcing a known-degraded model's output to neutral — reverting restores today's existing (already-imperfect) behavior, not an untested new one.

---

## Constraints

**Allowed:**
- Exactly the change named in §1, developed in an isolated worktree.

**Forbidden:**
- Any change to `bot/strategy/ensemble.py`, `bot/main.py`, `WEIGHTS`, `_LSTM_INDETERMINATE_LO`/`_LSTM_INDETERMINATE_HI`, or any BUY/SELL/HOLD threshold — the fix is confined to `predict_proba()`'s early-return logic, which makes changes elsewhere unnecessary.
- Any `.github/workflows/*.yml` change.
- Any change to the LSTM model itself, `LSTM_DEGRADED_VAL_LOSS` threshold, or retraining — this ADR only changes how an already-known-degraded state is reflected in `predict_proba()`'s return value.

---

## Explicitly Not Established By This ADR

- Does not address whether `_LSTM_INDETERMINATE_LO`/`_LSTM_INDETERMINATE_HI` = [0.45, 0.55] is the right band — that's a separate, pre-existing calibration question, not reopened here.
- Does not address probability calibration (Platt/isotonic scaling) of XGB's or LSTM's raw outputs — identified as a separate, larger follow-up in this session's broader "improve prediction accuracy" discussion, not bundled into this narrow fix.
- Does not retrain or otherwise change the LSTM model — fixing the degraded model itself remains the existing, separate remedy (`python scripts/train_model.py` / weekly retrain workflow), already named in the Telegram alert text.

---

## Acceptance

*(Per ADR-058 D4, this document is a proposal and carries no authority until it is landed under ADR-058 D2, by explicit act of the Architecture Owner.)*

**Status:** Accepted
**Date Accepted:** 2026-10-22
**Accepted By:** ksri77 (Architecture Owner) — explicit acceptance given in-session after the revised (smaller-footprint) fix was presented

---

## Status Log

- **2026-10-22 — Proposed.** Drafted following the ADR-073 precedent (isolated worktree from the start, narrow named scope). Found while investigating ensemble-weighting correctness as part of a broader "improve prediction accuracy" review; two other hypotheses investigated in the same pass (macro weight, sentiment data quality) were ruled out as non-issues and are not part of this ADR. Not yet accepted; no implementation has started.
- **2026-10-22 — Revised before acceptance, on self-review.** The initial draft proposed fixing this at the `ensemble_signal()` call site (`bot/main.py` + `bot/strategy/ensemble.py`). Re-examined when asked to critique the draft: that fix would have corrected the trading decision but left `ensemble_confidence()` (dashboard, Telegram, logging, `decision_events.final_confidence`) still exposed to the same un-neutralized degraded output — trading one inconsistency for another. Revised to fix `LSTMPredictor.predict_proba()` directly instead, which corrects every consumer at once with a smaller, single-file change. Verified against all 3 real callers of `lstm.predict_proba()` (`bot/main.py`, `backtest/engine.py`, `tests/test__main_market.py`'s determinism check) before finalizing — none are broken by this change.
- **2026-10-22 — Accepted.** Accepted by ksri77 (Architecture Owner) after the revised fix was presented. Implementation to proceed in an isolated worktree per §3.