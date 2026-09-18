# TradeGenius AI — Test Strategy

Last updated: 2026-09-18

4,538 tests exist repo-wide (`tests/` + `sentinel_engine/` + `applications/`; verified 2026-09-18 via
`pytest -q`: 4,485 passed, 49 skipped, 4 failed — see `TECHNICAL_DEBT.md` for the 4 known failures,
which sit in an in-progress, not-yet-committed Performance Learning view refactor, not a regression).
`NFR.md`'s previous "535" figure only ever counted `tests/`; it never included the Sentinel Engine or
`applications/` suites, which is most of the real number — `tests/measure_performance.py` has been
fixed to measure all three going forward. This document is the reasoning the test suite itself can't
carry: what each category is for, and — the genuinely hard part of testing a system with three ML
models and a live market feed — how you test something stochastic without either asserting on noise
or testing nothing real.

## 1. The Core Problem: You Can't Unit-Test a Prediction

`bot/strategy/xgb_predictor.py` and `lstm_predictor.py` produce probabilities that drift every time
the model is retrained on new data. A test asserting `predict(AAPL) == 0.63` is not a test — it just
freezes today's model weights into an assertion that breaks on the next legitimate retrain. Two
things follow from this:

- **Unit and integration tests assert invariants, not predictions.** `test_xgb_predictor.py`,
  `test_lstm_predictor.py`, `test_ensemble.py`, and `test_signal_gate.py` check contract shape
  (probability in `[0,1]`, required fields present), deterministic logic (gate thresholds, ensemble
  weighting math), and degraded-input behavior (what happens when a provider returns nothing — see
  `EXTERNAL_SERVICES.md`'s outage table) — never "is this specific prediction correct."
- **Predictive quality is judged by the backtest gate, not the unit suite,** covered next.

## 2. The Backtest Quality Gate Is the Real Trust Boundary

`test_retrain_workflow_gate.py` and `test_backtest_engine.py` back the check ADR-052 ratifies: a
retrained model is only promoted to production if its walk-forward backtest clears the thresholds in
`SUCCESS_METRICS.md` (win rate, Sharpe, drawdown). Walk-forward — training only on data before a
point in time and testing only after it — is the specific mitigation for R-001 in `RISK_REGISTER.md`
("model overfits training data, degrades on live market"). A model can pass every unit test and still
fail this gate; that failure is the system working as designed, not a bug. A green unit-test suite
never promotes a model on its own — only the backtest gate does that.

## 3. Test Categories

| Category | Example files | What it's for |
|---|---|---|
| Deterministic unit logic | `test_risk_manager.py`, `test_signal_gate.py`, `test_regime_classifier.py` | Pure functions with no randomness: gate thresholds, Kelly sizing math, stop-loss calculation. Asserted on exact expected output. |
| Model contract/invariant | `test_xgb_predictor.py`, `test_lstm_predictor.py`, `test_ensemble.py`, `test_rl_agent.py` | Shape and range of model output, graceful degradation when an input feed is missing — never the literal prediction value. |
| Backtest/promotion gate | `test_backtest_engine.py`, `test_retrain_workflow_gate.py` | Walk-forward backtest metrics against `SUCCESS_METRICS.md` targets. This is what actually gates whether a new model goes live. |
| Integration across modules | `test_main.py`, `test__main_cycle`-family (`test__main_signals.py`, `test__main_positions.py`, `test__main_market.py`, `test__main_prep.py`) | The full per-symbol cycle (signals → gates → risk → execution) wired together with mocked broker/data calls. |
| Data/infra resilience | `test_sqlite_threading.py`, `test_db_indexes.py`, `test_sync_db.py`, `test_macro_cache.py`, `test_alpaca_client.py` | Concurrency, caching, and provider-outage behavior — backs the mitigations listed in `RISK_REGISTER.md` and `EXTERNAL_SERVICES.md`. |
| Dashboard/UI | `test_dashboard_render.py`, `test__dashboard_*.py`, `ui_tester.py`, `check_ui.py` | Rendering correctness and design-system compliance (0 FAIL / 0 WARN gate — see root `CLAUDE.md`). |
| Architecture conformance | `test_arch_review_decision_engine_layer.py`, `test_no_undefined_names.py` | Structural rules: layer boundaries, no accidental cross-imports. |

## 4. What Isn't Tested, and Why That's Covered Elsewhere

Real market microstructure (actual fills, slippage, live order-book behavior) cannot be unit-tested —
Alpaca paper trading itself is the extended integration test for that layer, and its outcomes feed
`RISK_REGISTER.md`'s R-001/R-011 mitigations, not a pytest file. This is a deliberate boundary, not a
gap: paper trading exists specifically because some behavior can only be validated against a live
(simulated) market.

## 5. Running the Suite

```bash
pytest tests/ -q                    # full suite — 535 passed in ~24s (NFR.md)
python tests/ui_tester.py           # design-system compliance, must be 0 FAIL 0 WARN
python tests/measure_performance.py --update   # refresh NFR.md latency/memory numbers
```
