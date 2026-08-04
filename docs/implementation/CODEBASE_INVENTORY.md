Project Overview
This repository contains a modular algorithmic trading and autonomous portfolio management system (featuring the Sentinel architecture and governance framework). It incorporates live/paper execution interfaces, decision ledgers with hash-chain integrity, a robust analytics and backtesting engine, and a rich multi-component dashboard interface.

Directory Structure & Core Modules
Root Configuration & Documentation
ARCHITECTURE.md, SETUP.md, README.md: Core system architecture, setup instructions, and project documentation.

config.py, .env / .env.example: Application configurations and environment variables.

requirements.txt, requirements_space.txt: Python dependency manifests.

*.db: Local SQLite databases handling trades, state tracking, and logs (trades.db, trading_bot.db, etc.).

1. bot/ — Trading Bot Core & Strategy Pipeline
main.py & Sub-modules (_main_*.py): Core orchestration loop, market synchronization, candidate generation, and execution handling.

capital/: Capital pool management (pool.py).

core/: Safety guards, error logging, and recommendation engines (api_guard.py, recommendation_engine.py).

db/: Macro caching, risk states, and trade logging.

decision/: Daily action generators.

eval/: Ablation testing, loaders, and evaluation metrics.

execution/: Broker integration layers including Alpaca API clients, paper execution, and supervised runners (alpaca_client.py, paper_executor.py).

monitor/: Telegram alerting, dashboard background data synchronizers, and rendering modules.

risk/: Risk management controls (risk_manager.py).

strategy/: Prediction models and signals (Ensemble, LSTM, XGBoost, Reddit sentiment analysis, market regime classification, and reinforcement learning agents).

trust_ledger/: Cryptographic trust tracking, candidate ledgers, constitution rules, and risk metrics.

2. sentinel/ — Governance & Backend Infrastructure
backend/:

api/: Routers and endpoints for admin operations, approvals, decisions, evidence tracking, governance, and portfolio oversight.

domain/: Business domain models (broker accounts, capital management, decisions, evidence, and user context).

events/: Event-driven architecture components, hash-chain verification, and event writers.

projections/: Read-model projections for decisions, governance status, and portfolio health.

repositories/: Data access layers for events, evidence, and projections.

services/: Core governance workflows, approval gates, risk governor logic, and evidence processing.

frontend/:

components/: Modular UI building blocks (audit fingerprints, chain timelines, decision/evidence cards, governance badges, health scores).

workspaces/: High-level analytical views (Chain of Custody, Decision History, Governance Review, Portfolio Health, Tax Intelligence).

tests/: Unit, integration, and acceptance tests covering Sentinel APIs and services.

3. dashboard/ — User Interface & Visualizations
app.py: Main dashboard application entry point.

components/: Feature-rich widgets including AI panels, attribution, decision trees, loss explanations, market mood, portfolio health, trade journals, and trust scorecards.

*.py (builders, charts, data, http_endpoints, layout, registry): Layout generation, metric builders, and API routing.

4. analytics/ & backtest/
analytics/: Calibration utilities, compliance auditing, experiment tracking, improvement proposals, market regime views, and performance scorecards.

backtest/: Simulation engine (engine.py) and performance metrics (metrics.py).

5. database/ & ledger/
database/: DuckDB schemas, SQLite-to-DuckDB migration sync jobs, query metrics, and repository wrappers.

ledger/: Immutable ledger logic, hash hashing, domain models, integrity verification, and reproducibility controls.

6. scheduler/
dispatcher.py, health_monitor.py, market_calendar.py, trading_job.py: Time-based task schedulers, market-hour synchronization, and health checks.

7. scripts/ & tools/
scripts/: Operational utilities for architecture reviews, backtest gates, confidence checks, data downloads, model training (Hugging Face integration), screening, and system validation.

tools/validators/: Comprehensive test-suite integrity checkers, brand system validations, and code-scan validators.

8. tests/
Comprehensive test suite covering baseline components, Phase 1A/1B/2 features, integration pipelines, UI responsiveness, and invariant verifications.