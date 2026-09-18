# TradeGenius AI — Architecture

Last updated: 2026-09-18

Scope: the legacy single-bot/single-dashboard system (`bot/`, `dashboard/`, `database/`) only — see
`docs/DOCUMENT_INDEX.md` for the separate Sentinel Engine / Trading Intelligence platform layer
(`sentinel_engine/`, `applications/`), which this document does not cover.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  GitHub Actions (cron, every 5 min, market hours)               │
│                                                                   │
│  bot/main.py → _main_runner.py → _main_cycle.py                 │
│       │              │                  │                         │
│       │         market check       per-symbol loop               │
│       │              │           (signals → risk → execute)       │
│       │              │                                            │
│       └──────► sync_db.py → HuggingFace Dataset (trades.db)     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (dashboard reads)
┌─────────────────────────────────────────────────────────────────┐
│  HuggingFace Spaces (always-on, auto-deployed from main)        │
│                                                                   │
│  dashboard/app.py                                                │
│       ├── gr.Timer(60s) → render_* functions                    │
│       ├── dashboard/data.py (55s TTL cache, DB reads)           │
│       └── dashboard/components/ (32 component modules)          │
└─────────────────────────────────────────────────────────────────┘
```

## 6-Layer Bot Architecture

Data flows strictly **downward** — upper layers may not import lower layers.

```
┌────────────────────────────────────────────────────────────────────┐
│ Layer 1 — Data Ingestion                                           │
│  bot/strategy/features.py      compute_features(): ATR,RSI,EMA    │
│  bot/strategy/macro.py         FRED VIX + T-bill, 4h DB cache     │
│  bot/strategy/sentiment.py     FinBERT (NewsAPI) + Reddit WSB      │
├────────────────────────────────────────────────────────────────────┤
│ Layer 2 — Regime Classification                                    │
│  bot/strategy/regime_classifier.py   TRENDING_UP/RANGING/etc      │
├────────────────────────────────────────────────────────────────────┤
│ Layer 3 — Signal Generation                                        │
│  bot/strategy/xgb_predictor.py    XGBoost probability + SHAP      │
│  bot/strategy/lstm_predictor.py   LSTM 30-bar sequence score       │
│  bot/strategy/ensemble.py         Weighted blend → BUY/HOLD/SELL   │
│  bot/strategy/rl_agent.py         PPO RL agent (position sizer)    │
│  bot/strategy/signal_gate.py      10-gate entry filter             │
├────────────────────────────────────────────────────────────────────┤
│ Layer 4 — Risk Management                                          │
│  bot/risk/risk_manager.py         Daily/weekly loss limits         │
│                                    PDT guard, drawdown CB           │
│                                    Position sizing (Kelly)          │
│                                    Stop-loss check                  │
├────────────────────────────────────────────────────────────────────┤
│ Layer 5 — Execution                                                │
│  bot/execution/alpaca_client.py   Limit buy + fill confirmation    │
│                                    Limit/market sell + escalation   │
├────────────────────────────────────────────────────────────────────┤
│ Layer 6 — Monitoring                                               │
│  bot/monitor/telegram_bot.py      BUY/SELL/risk/daily alerts       │
│  bot/monitor/sync_db.py           trades.db push to HuggingFace    │
│  dashboard/                       Gradio read-only dashboard        │
│  database/                        DuckDB analytics service          │
└────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

Verified against the actual tree 2026-09-18 (previous version of this doc undercounted every module
group roughly 2x — it hadn't been refreshed since 2026-06-27):

```
ai-trading-bot/
├── bot/
│   ├── _main_candidates.py  candidate screening for entry
│   ├── _main_cycle.py       per-symbol entry/exit logic
│   ├── _main_db.py          DB write helpers for trades/state
│   ├── _main_market.py      market open check, SPY bar fetch
│   ├── _main_positions.py   position reconciliation at startup
│   ├── _main_prep.py        pre-cycle preparation
│   ├── _main_reconcile.py   broker/local state reconciliation
│   ├── _main_runner.py      outer loop orchestration
│   ├── _main_signals.py     signal preparation per symbol
│   ├── _main_trust_decisions.py  Trust Ledger decision recording
│   ├── main.py              entrypoint (run_loop)
│   ├── core/
│   │   ├── api_guard.py           rate-limit guard for Alpaca
│   │   ├── error_logger.py        safe_render, timed, log_exception
│   │   ├── recommendation_engine.py  shared dashboard helpers
│   │   └── recommendation_portfolio.py
│   ├── execution/  (6 modules: alpaca_client, base, factory, paper_executor,
│   │                supervised, timeframe — see docs/SECURITY.md for the
│   │                paper-vs-real-money boundary)
│   ├── monitor/  (10 modules: sync_db, telegram_bot, dashboard_data, and
│   │              7 `_dashboard_*` internal render-support modules)
│   ├── risk/
│   │   └── risk_manager.py
│   └── strategy/  (11 modules: ensemble, features, lstm_predictor, macro,
│                   model_output_adapter, reddit_sentiment, regime_classifier,
│                   rl_agent, sentiment, signal_gate, xgb_predictor)
├── backtest/
│   ├── engine.py            walk-forward simulator
│   └── metrics.py           Sharpe, win rate, drawdown
├── dashboard/
│   ├── app.py               Gradio wiring (431 lines)
│   ├── builders.py          view-model builder functions
│   ├── charts.py            Plotly chart renderers
│   ├── data.py              55s-TTL cache + DB reader
│   ├── design_system.py     tokens + component helpers
│   ├── http_endpoints.py    cron trigger + health endpoints
│   ├── layout.py            CSS + static HTML
│   ├── prerender.py         startup pre-render cache warm
│   ├── registry.py          component registration / refresh groups
│   ├── timers.py            gr.Timer wiring
│   ├── viewmodels.py        pure-Python dataclasses
│   └── components/          32 modules — every dashboard panel (AI recommendations,
│                             risk, portfolio, decision center, trust scorecard,
│                             trade journal, capital tracking, thesis/counterfactual
│                             review, weekly summary, and more)
├── database/
│   ├── query_metrics.py             dashboard query performance tracking
│   ├── trade_journal.py             manual/annotated trade journal entries
│   ├── user_settings.py             user preference key/value store
│   ├── repositories/
│   │   └── analytics_repository.py   DuckDB CRUD
│   ├── services/
│   │   ├── analytics_service.py      Sharpe, drawdown, snapshot
│   │   └── decision_service.py
│   └── sync/                         sqlite_to_duckdb.py + sync_jobs.py + validators.py
├── config.py                all trading parameters + env vars
├── scripts/                 maintenance + deployment scripts
├── tests/                   1,441 tests across 69 test files (this folder only —
│                             4,538 repo-wide across tests/ + sentinel_engine/ +
│                             applications/, see docs/TEST_STRATEGY.md)
└── docs/                    this directory
```

## SQLite Schema (trades.db)

21 tables (verified via `grep CREATE TABLE` + tracing each caller's connection target, 2026-09-18 —
previous count of 8 was stale), managed by `bot/_main_db.py` plus several `bot/`/`database/` helper
modules that take a shared connection rather than owning their own file:

| Table | Purpose |
|-------|---------|
| `trades` | Every BUY/SELL with price, P&L, ensemble score, SHAP drivers |
| `position_state` | Current open positions (reconciled at startup) |
| `risk_state` | Daily/weekly loss totals, PDT counter, drawdown state |
| `earnings_cache` | Upcoming earnings dates (±2 day block window) |
| `macro_cache` | FRED VIX + macro score (4-hour TTL) |
| `portfolio_snapshots` | Hourly portfolio value + health score snapshots |
| `signal_log` | All ensemble signals per symbol per cycle |
| `screener_log` | Pre-market screener rankings and scores |
| `signal_history` | High-confidence signal tracking history |
| `recommendations` | AI BUY/SELL/HOLD recommendation records |
| `news_cache` | Cached news headlines per symbol |
| `user_settings` | User preference key/value store |
| `capital_accounts` | Capital account balance and initial deposit tracking |
| `investment_theses` | Recorded investment thesis per position |
| `decision_log` | AI decision audit log (superset of `trades` — includes non-executed decisions) |
| `daily_changes` | Daily since-yesterday change tracking per symbol |
| `trade_journal` | Manual/annotated trade journal entries |
| `query_metrics` | Dashboard query performance metrics |
| `capital_pools` | Active capital pool state (`bot/capital/pool.py`) |
| `capital_ledger` | Append-only ledger of deposits/withdrawals/buys/sells against a capital pool |
| `daily_actions` | Recorded daily trade actions (`bot/decision/daily_actions.py`) |

Note: `paper_account`/`paper_fills`/`paper_positions` (used by `bot/execution/paper_executor.py`) live
in a **separate** file, `data/paper_portfolio.db` — not `trades.db`. `trades_archive`/`signal_archive`/
`portfolio_history` are DuckDB analytics tables (`database/duckdb/analytics.duckdb`, via
`database/sync/sqlite_to_duckdb.py`), not SQLite tables in this file.

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| SQLite over PostgreSQL | File-based; syncs as a single binary to HuggingFace; no external DB to manage |
| Gradio + HTML strings | Matches Python ML codebase; avoids React build pipeline |
| GitHub Actions cron | Free tier; 5-min granularity; easily observable via Actions UI |
| Single trades.db push | Avoids partial-state on dashboard; atomic file replace |
| 55-second cache TTL | Prevents N×DB reads per 60-second refresh cycle across all render functions |
