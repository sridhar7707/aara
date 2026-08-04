# Bot Runtime Baseline

**Purpose:** Read-only snapshot of how `bot/` actually runs in production today, as
input to future `applications/trading_intelligence/` extraction planning (ADR-001).
No code, workflow, or import changes were made to produce this document.

**Method:** Direct inspection of `.github/workflows/*.yml`, `bot/main.py` imports,
`bot/execution/`, `scripts/load_model_hf.py`/`save_model_hf.py`, and the SQLite files
present in the repo. Not exhaustive of every code path — flagged where verification
would need more than static reading.

---

## 1. Runtime Entry Points

**Primary entry point:** `bot/main.py`, invoked with different flags per phase of the
trading day:

| Invocation | Purpose |
|---|---|
| `python bot/main.py --clean-db` | Full data reset (manual `workflow_dispatch` only) |
| `python bot/main.py --reset-daily-start` | Reset day P&L baseline anchor |
| `python bot/main.py --mode paper --loop` | Main trading cycle (paper execution) |
| `python bot/main.py --summary` | End-of-day summary/report |

**Supporting scripts invoked around it** (all under `scripts/`, called as separate
processes from workflow YAML, not imported by `bot/main.py`):
- `load_model_hf.py` — pulls trained models from Hugging Face Hub before a trading run
- `phase1a_bootstrap_ledger.py` — ledger bootstrap
- `screen_universe.py` — pre-market candidate screening
- `prefetch_sentiment.py` — sentiment cache warm-up
- `download_data.py`, `train_model.py`, `backtest_gate.py`, `save_model_hf.py`,
  `weekly_report.py` — weekly retrain pipeline only (see `retrain.yml`)

`bot/main.py`'s own import graph (from its top-level imports) pulls in:
`bot.execution.{base,factory}`, `bot.strategy.{features,regime_classifier,
xgb_predictor,lstm_predictor,sentiment,macro,reddit_sentiment,ensemble,signal_gate}`,
`bot.risk.risk_manager`, `bot.monitor.telegram_bot`, `bot.capital.pool`,
`bot.trust_ledger.{connection,candidates}`, `bot._main_*` orchestration modules, and
**`ledger.integrity`** (the top-level, non-`bot` hash-chain ledger package).

## 2. GitHub Actions Dependencies

8 workflows in `.github/workflows/`:

| Workflow | Trigger | Runs |
|---|---|---|
| `keepalive.yml` | `workflow_dispatch`, dispatched externally by cron-job.org at 8:15 AM CDT Mon–Fri | Dispatches `trade.yml` if within NYSE hours (9:30–15:45 ET); also pings to keep the HF Space warm |
| `trade.yml` ("Trading Bot") | `workflow_dispatch`, dispatched externally by cron-job.org at 8:30/10:30/12:30/2:30 PM CDT Mon–Fri (GitHub's built-in scheduler was dropped as unreliable — see workflow comment) | `load_model_hf.py` → `phase1a_bootstrap_ledger.py` → `screen_universe.py` → `prefetch_sentiment.py` → `bot/main.py --mode paper --loop` → `bot/main.py --summary` |
| `watchdog.yml` | `schedule` cron `0 14,15,16,18,20 * * 1-5` (30 min after each trading slot) | Pings the HF Space `/run/cron` endpoint; Telegram alert if down |
| `premarket.yml` | `workflow_dispatch`, dispatched externally by cron-job.org at 6:30 & 7:00 AM CDT Mon–Fri | `screen_universe.py` |
| `retrain.yml` | `schedule` cron `0 2 * * 0` (Sunday 2am UTC) | `download_data.py` → `train_model.py` → `backtest_gate.py` → `save_model_hf.py` → `weekly_report.py` |
| `deploy_ui.yml` | `workflow_run` (triggered by another workflow completing) | Deploys dashboard to HF Space |
| `ci.yml` | (not inspected in depth) | `arch_review.py`, `validate_brand_system.py`, `pytest tests/` |
| `secret-scan.yml` | (not inspected in depth) | `check_forbidden_paths.py` |

**Note:** GitHub's own cron scheduler is explicitly *not* used for `trade.yml`/
`keepalive.yml` — an external cron-job.org trigger calls `workflow_dispatch` instead,
per comments in both files ("GitHub's built-in scheduler was too unreliable"). Any
future move of `bot/main.py` must account for this external trigger, not just the
in-repo YAML.

## 3. Broker / Execution Path

`bot/execution/` (7 files): `alpaca_client.py` (Alpaca broker client),
`base.py` (`Executor` interface), `factory.py` (`get_executor` — selects
implementation), `paper_executor.py` (paper trading), `supervised.py`,
`timeframe.py`. `bot/main.py` imports only `Executor` and `get_executor` — the
concrete broker choice is a runtime decision inside `factory.py`, not hardcoded in
`main.py`. (Per project memory: `EXECUTION_BACKEND` currently stays `alpaca_paper`
through the Phase 1A 30-day validation window.)

## 4. Model Loading

Models are trained/stored/loaded, not baked into `bot/main.py` directly:

- **Local storage:** `models/saved/` (`xgb_predictor.pkl`, `lstm_predictor.pt`,
  `lstm_scaler.pkl`, `regime_classifier.pkl`), plus `models/validation_report.json`,
  `feature_importance.json`, `runtime_versions.json`.
- **Loaded by:** `bot/strategy/xgb_predictor.py`, `lstm_predictor.py`,
  `regime_classifier.py` (the three files referencing model-loading calls).
- **Synced from Hugging Face Hub:**
  - `scripts/load_model_hf.py` — pulls all model artifacts via `hf_hub_download`,
    using `HF_TOKEN`/`HF_REPO_ID` from `config`. Run at the start of every `trade.yml`
    execution.
  - `scripts/save_model_hf.py` — pushes retrained models back, run only from
    `retrain.yml` (weekly).

## 5. Database Dependencies

Multiple, distinct SQLite stores are in play — not one shared database:

| File / Location | Owner | Purpose |
|---|---|---|
| `trades.db`, `trading_bot.db` (repo root) | `bot/db/trade_log.py`, `bot/_main_db.py` | Core operational trade log |
| `bot/db/macro_cache.py`, `risk_state.py` | `bot/db/` | Bot-local caches, not shared |
| `data/trust_ledger.db` | `bot/trust_ledger/connection.py` | Decision/candidate/outcome audit trail (Phase 1A) |
| Top-level `ledger/` package (`ledger.integrity`, imported directly by `bot/main.py`) | — | Hash-chain integrity/reproducibility layer, separate from `bot/trust_ledger/` |
| `database/` package | `database/repositories/analytics_repository.py`, `database/services/analytics_service.py` (2 files import `bot`) | Analytics layer, has its own (thin) coupling back into `bot/` |

`bot/` reaches into the top-level `database/` package from 4 files
(`bot/_main_cycle.py`, `bot/_main_db.py`, `bot/_main_positions.py`,
`bot/capital/pool.py`) — see `BOT_DEPENDENCY_MAP.md` for the full matrix.

---

## Correction: scheduler/ Is a Second Live Entry Point

The original version of this document treated `bot/main.py`'s CLI (invoked by
`trade.yml`) as the sole entry point. **That was incomplete.** Investigated
directly: `scheduler/dispatcher.py`'s own docstring calls it "the sole cron entry
point," and it's reachable via `dashboard/http_endpoints.py`'s `GET /run/cron` route
— the exact endpoint `watchdog.yml` calls 5×/day. That "watchdog ping" is a real,
unconditional trigger of `scheduler.dispatcher.main()`, not a passive health check —
the endpoint spawns the dispatcher on every GET regardless of caller intent. From
there, `scheduler/trading_job.py`, `startup_job.py`, `shutdown_job.py` each locally
import and call into `bot/` (`bot.main.run`, `bot.execution.alpaca_client.AlpacaClient`,
`bot.core.recommendation_engine.get_portfolio_health`). Full detail and
implications: see `BOT_DEPENDENCY_MAP.md` (updated) and
`docs/decisions/ADR-002-bot-runtime-protection.md`.

**Practical effect on this baseline:** "Runtime Entry Points" (Section 1) should be
read as incomplete — add `scheduler/dispatcher.py` (via the `/run/cron` HTTP route)
as a second, independent entry point alongside `bot/main.py`'s CLI.

## Other Open Items

- `bot/monitor/` contains files named `_dashboard_charts.py`, `_dashboard_html.py`,
  `_dashboard_overview.py`, etc. — naming that overlaps with the separate top-level
  `dashboard/` package. Confirmed via import search: these are only imported from
  within `bot/monitor/` itself (by `bot/monitor/dashboard_data.py`) and by
  `tests/test__dashboard_*.py` — not by the top-level `dashboard/` package, and not
  by `bot/main.py`'s direct imports. Appears to be a self-contained internal
  reporting/rendering path (name collision only, not a code entanglement) — but this
  is based on static import search, not runtime tracing, and given the scheduler/
  miss above, that caveat now carries more weight than it did originally.
- **Resolved:** the git worktree at `.claude/worktrees/sentinel-phase2a-governance-freeze/`
  is a separate, `locked` (deliberately reserved) worktree that forked from the same
  commit as `main` (`c068477`) but diverged into Design Governance CI tooling (YAML
  contract validators, `validate_all.py`, VERSION_LOCK checks, a "Phase 2A freeze
  report generator"). It is unrelated to the Sentinel/AARA architecture work in this
  document — the "Phase 2A" in its latest commit message refers to the Design
  Governance system's own Phase 2A, not the Sentinel product's. No further action
  needed here.
