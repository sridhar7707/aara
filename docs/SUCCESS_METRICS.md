# TradeGenius AI — Success Metrics

Last updated: 2026-09-18

All metrics are computed from live paper-trading data in `trades.db`.
The Paper Trading Scorecard panel (`render_paper_trading_scorecard()`) shows live values.
Run `python tests/measure_performance.py` to capture a point-in-time snapshot.

**Two different bars exist and this doc previously conflated them (corrected 2026-09-18, verified
against `scripts/confidence_check.py`):** the numbers below are `GOALS.md`'s aspirational "north
star" targets — what the project is working toward. The actual **enforced** go-live gate in
`scripts/confidence_check.py` is deliberately more lenient on two of these (a documented, deliberate
choice — see `feedback_xgb_threshold_constraint` history: a 60% win-rate bar killed trade volume when
tried). Both are shown so neither reads as the other:

## Primary Metrics

| Metric | Aspirational Goal (`GOALS.md`) | Actually Enforced Gate (`confidence_check.py`) | Current | Source |
|--------|--------|--------|---------|--------|
| Win Rate | ≥ 60% | **≥ 52%** (`min_win_rate`) | See scorecard | `trades` table: closed BUY→SELL pairs |
| Total Return vs SPY | Beat SPY by ≥ 5 pp | not separately gated | See scorecard | yfinance SPY price since first trade |
| Total Return vs QQQ | Beat QQQ by ≥ 0 pp | not separately gated | See scorecard | yfinance QQQ price since first trade |
| Max Drawdown | ≤ 12% (live circuit breaker, `PORTFOLIO_DRAWDOWN_LIMIT_PCT`) | **≤ 15%** (`max_drawdown`, go-live gate only) | See scorecard | `portfolio_snapshots`: peak-to-trough |
| Sharpe Ratio | ≥ 1.0 | ≥ 1.0 (`min_sharpe`, matches) | See scorecard | `analytics_service.get_sharpe_ratio()` |
| Paper trading duration | ≥ 60 days | ≥ 60 days (`min_days`, matches) | See scorecard | `trades` table: first-to-last trade span |
| Max consecutive losing days | ≤ 4 | ≤ 4 (`max_consecutive_losing_days`, matches) | See scorecard | `risk_state` table |
| AI Follow Rate | ≥ 70% | not gated by `confidence_check.py` | See scorecard | BUY recs executed within same day (30d window) |

## Secondary Metrics (operational health)

| Metric | Target | How to Check |
|--------|--------|--------------|
| Average hold days | 3–25 days | `trades` table: avg(days between BUY and SELL) |
| Average P&L per trade | > 0% | `trades` table: avg(pnl_pct) |
| Largest single loss | < -8% | `trades` table: min(pnl_pct) |
| Daily loss limit breaches | 0 | `risk_state` table: `daily_loss_exceeded` flag |
| PDT trades used | < 3 / 5 days | `risk_state` table: `day_trades_today` |
| Positions at max (8) | < 20% of days | `portfolio_snapshots`: count open_positions = 8 |
| Cash reserve maintained | ≥ 10% at end of each day | `portfolio_snapshots`: cash / portfolio_value |

## Model Quality Metrics (checked at each retraining)

Corrected 2026-09-18 against the actual enforced constants — the previous numbers (0.65 AUC, 55%
backtest win rate, 0.8 backtest Sharpe) didn't match any real threshold in code. 0.65 specifically was
a deprecated signal-gate value; `bot/strategy/signal_gate.py`'s own comment records why it was lowered
to 0.62 ("AUC 0.546 makes 3pt diff noise").

| Metric | Actual Enforced Threshold | Source |
|--------|--------|--------|
| XGBoost validation AUC (retrain sanity check) | ≥ 0.52 ("near coin-flip" floor) | `scripts/train_model.py`, `.github/workflows/retrain.yml` |
| Backtest win rate (retrain quality gate) | ≥ 40% (`MIN_WIN_RATE`) | `scripts/backtest_gate.py` |
| Backtest Sharpe (retrain quality gate) | ≥ 0.3 (`MIN_SHARPE`) | `scripts/backtest_gate.py` |
| Backtest max drawdown (retrain quality gate) | ≤ 30% (`MAX_DRAWDOWN`) | `scripts/backtest_gate.py` |
| Signal-gate high-confidence threshold | ≥ 0.62 (`_HC_XGB_MIN`, inference-time, distinct from validation AUC) | `bot/strategy/signal_gate.py` |

Note the retrain-time gate is intentionally loose (catches only catastrophic model failures, not a
quality bar) — see `docs/TEST_STRATEGY.md` §2 for why the backtest gate and the unit-test suite serve
different purposes.

## Non-Functional Metrics

See `docs/NFR.md` for latency, memory, and reliability targets with real measured numbers.

## Definition of Done

A feature is "Done" when:
1. Code merged to `main` with no arch-review WARN or BLOCK
2. `python tests/ui_tester.py` → 0 FAIL 0 WARN
3. `pytest tests/ -q` → all pass
4. `docs/REQUIREMENTS.md` updated (run `python tests/requirements_tracker.py`)
5. At least one happy-path test exists for any new function
6. For risk/execution changes: explicit approval from owner after reviewing config.py diff
