# Bot Extraction Candidates

**Purpose:** Assess which `bot/` submodules are self-contained enough to become
`applications/trading_intelligence/*` candidates later (per `CODEBASE_MIGRATION_MATRIX.md`,
ADR-001), and which are entangled and higher-risk. **This document identifies
candidates only — it does not recommend moving anything now, and no files were
moved, refactored, or changed to produce it.**

Coupling figures below are static import counts from `BOT_DEPENDENCY_MAP.md`.
"Extraction risk" is a judgment call based on coupling + how central the module is
to the live, real-money-adjacent trading path — not a precise metric.

---

## Submodule Assessment

| Module | Files | Purpose | Coupling | Extraction Risk | Notes |
|---|---|---|---|---|---|
| `bot/strategy/` | 12 | XGB/LSTM/RL/ensemble/regime/sentiment models, feature computation, signal gating | No `dashboard`/`database` imports found | **LOW** structural risk, **HIGH** criticality | Core IP and the actual live signal generator. Structurally clean to move; the risk is entirely in getting HF model-loading paths (`models/saved/...`) right afterward, not in code coupling. |
| `bot/execution/` | 7 | Broker/paper execution: `alpaca_client.py`, `base.py`, `factory.py`, `paper_executor.py`, `supervised.py`, `timeframe.py` | Self-contained around `config` + Alpaca SDK | **MEDIUM** | Touches live broker credentials via `config`. Moving this is the closest thing to touching "real money" in the whole tree — needs its own dedicated, tested migration, not a bundled move. |
| `bot/capital/` | 2 | `pool.py` — tradeable capital calculation | Imported by `bot/main.py`, `bot/_main_cycle.py` | LOW | Small, single-purpose. |
| `bot/risk/` | 2 | `risk_manager.py` — Kelly sizing, risk gates | Self-contained | LOW | Small, single-purpose. |
| `bot/trust_ledger/` | 9 | `candidates.py`, `decisions.py`, `outcomes.py`, `risk.py`, `constitution.py`, `data_quality.py` | Uses `bot/db/`, writes to `data/trust_ledger.db` | MEDIUM | Per `CODEBASE_MIGRATION_MATRIX.md`, this is a **Sentinel-side** candidate (→ `sentinel_engine/evidence/`), not a `trading_intelligence` candidate — different destination than the rest of this table. |
| `bot/monitor/` | 11 | `telegram_bot.py`, `sync_db.py`, `dashboard_data.py`, and 7 `_dashboard_*.py` report-rendering files | `_dashboard_*` files import each other only, plus referenced by `tests/`; not imported by the separate `dashboard/` package | **MEDIUM–HIGH** | Mixed bag: notification (`telegram_bot.py`) is low-risk; the `_dashboard_*` internal reporting system needs disambiguation from `dashboard/` before anyone assumes they're related — same naming, apparently different code paths. Needs a closer look before categorizing further. |
| `bot/core/` | 5 | `recommendation_engine.py`, `recommendation_portfolio.py`, `api_guard.py`, `error_logger.py` | Imported broadly across `bot/` | MEDIUM | Foundational utilities other `bot/` modules depend on — moving this affects import order for everything else in the table. |
| `bot/decision/` | 2 | `daily_actions.py` | Not individually profiled in this pass | Unassessed | |
| `bot/eval/` | 4 | `ablation.py`, `loader.py`, `metrics.py` | Not individually profiled in this pass | Unassessed | Likely research/backtesting-adjacent, not live-path critical — worth a closer look before assuming either way. |
| `bot/db/` | 4 | `macro_cache.py`, `risk_state.py`, `trade_log.py` | Bot-local SQLite caches | LOW–MEDIUM | Local to `bot/`, but `trade_log.py` is the operational trade record — high criticality even if structurally simple. |
| `bot/main.py` + `bot/_main_*.py` (11 files) | 11 | Orchestration/CLI entry point | Imports nearly everything above; **is the literal path 5 of 8 GitHub Actions workflows invoke** (`python bot/main.py ...`) | **HIGHEST** | Any move requires updating every workflow's `run:` command in lockstep with zero path-mismatch tolerance, since these are triggered by an external cron (cron-job.org) hitting `workflow_dispatch` on a live schedule. This is the highest-blast-radius single change in the entire tree. |

## Summary

**Lowest-risk candidates if/when Phase 2 begins:** `bot/strategy/`, `bot/capital/`,
`bot/risk/` — self-contained, no `dashboard`/`database` coupling found, though
`bot/strategy/`'s criticality (it's the live model layer) means "low structural risk"
does not mean "low-stakes."

**Needs disambiguation before any move:** `bot/monitor/`'s `_dashboard_*` files —
naming collision with `dashboard/` should be resolved/understood first.

**Different destination entirely:** `bot/trust_ledger/` is a Sentinel Engine
candidate per `CODEBASE_MIGRATION_MATRIX.md`, not a `trading_intelligence` one.

**Highest risk, do last and separately:** `bot/main.py` + `bot/_main_*.py`
(the orchestration layer GitHub Actions calls directly) and `bot/execution/`
(live broker path). Both require their own dedicated, tested, reversible migration
plan — not a bundled move alongside the lower-risk modules.

## Explicit Non-Recommendation

This document does not conclude that Phase 2 extraction should start. Per the
constraint given for this analysis: no code changes, no file moves, no refactoring.
The next decision — whether and when to begin moving any of the above — is a
separate, explicit call to make later.
