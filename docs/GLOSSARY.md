# TradeGenius AI — Glossary

Last updated: 2026-09-18

Single lookup table for domain vocabulary spanning the trading bot (`bot/`) and the Sentinel
Intelligence Engine (`sentinel_engine/`). This glossary does not redefine terms that already have a
canonical, ratified definition elsewhere — it points to that source instead, so there is exactly one
place each term is actually defined.

## Trading Bot Terms (`bot/`)

| Term | Meaning |
|---|---|
| **Regime** | The market condition classification a symbol is currently in — `TRENDING_UP`, `RANGING`, etc. Computed by `bot/strategy/regime_classifier.py`; used to weight which signals the ensemble trusts. |
| **Signal** | A directional prediction from one model (XGBoost, LSTM, RL agent) before ensembling — a probability or score, not yet a trade decision. |
| **Ensemble** | `bot/strategy/ensemble.py` — the weighted blend of the XGB, LSTM, and sentiment/macro signals into a single BUY/HOLD/SELL call. |
| **Signal gate / entry gate** | `bot/strategy/signal_gate.py` — the 10-gate filter a candidate BUY must pass (regime, correlation, sentiment, macro, etc.) before it reaches risk management. See ADR-052 for the retrain-time equivalent (backtest quality gate). |
| **Risk gate** | Any check in `bot/risk/risk_manager.py` that can block or resize a trade: daily/weekly loss limits, PDT guard, drawdown circuit breaker, Kelly position sizing, stop-loss check. |
| **Kelly sizing** | Position-sizing method in `risk_manager.py` that scales position size to edge/confidence rather than a fixed dollar amount. |
| **PDT (Pattern Day Trader) guard** | Regulatory gate enforcing `PDT_MAX_DAY_TRADES` for accounts under $25K (R-005, `RISK_REGISTER.md`). |
| **Drawdown circuit breaker** | Halts new buys once portfolio drawdown from its high crosses the risk-appetite limit in `RISK_REGISTER.md`. |
| **VIX halt** | New-buy halt triggered when VIX ≥ 28 (existing positions still exit normally each cycle). |
| **Backtest quality gate** | The check a retrained model must pass (walk-forward backtest metrics vs. `SUCCESS_METRICS.md` targets) before it can be promoted to production. Ratified in ADR-052; see `TEST_STRATEGY.md` §3. |
| **HALT_TRADING** | Emergency manual override — presence of the `data/HALT_TRADING` file pauses the trading cycle without touching the GitHub Actions schedule. See `RUNBOOK.md`. |

## Decision Intelligence Terms (`sentinel_engine/`)

These terms have a ratified, binding definition in ADR-066 and `docs/platform/SENTINEL_ENGINE_DOMAIN_VOCABULARY.md` — this row set is a pointer, not a restatement, since the ADR is the actual authority and can change under a future ADR without this file going stale.

| Term | One-line orientation | Authoritative source |
|---|---|---|
| **Decision** | A recommendation object (`DecisionAction`, `Horizon`, optional thesis/allocation fields) — a recommendation label, never an executable order. | ADR-066 §3.1, §3.4 |
| **Evidence** | A single supporting or contradicting data point attached to a Decision (`EvidencePolarity`). | ADR-066 §3.3, §3.5 |
| **Ledger / Trust Ledger** | The authoritative event record `bot/trust_ledger/` writes to and `sentinel_engine/` projections read from. Ownership is explicitly deferred, not yet decided. | ADR-004 |
| **Projection** | A derived, read-only view rebuilt from the ledger's event record — never a second source of truth. | `AI_AGENT_GUIDELINES.md` §3 |
| **Capability API** | The verb-based interface (`analyze` / `explain` / `remember` / `evaluate` / `recommend`) products call on the engine instead of reaching into its internals. | `SENTINEL_ENGINE_BOUNDARY_AND_API_CONTRACTS.md` |
| **Sentinel Engine** | The shared, product-agnostic intelligence layer beneath both AARA products — the platform's one core, not a peer of the products it serves. Does not own customer data (see `SECURITY.md` §1's boundary diagram for the bot-layer equivalent). | ADR-001, ADR-007, ADR-015, `SENTINEL_ENGINE_DOMAIN_VOCABULARY.md` |
| **Recommendation** | The as-yet-unresolved causal link between a Decision and what `bot/` actually does — explicitly **not yet authorized**; a Decision today has no live effect on execution. | ADR-066 §6 |

## Governance Terms

| Term | Meaning |
|---|---|
| **ADR (Architecture Decision Record)** | A binding decision once `Status: Accepted`. `Status: Proposed` is not yet authoritative. See `docs/decisions/`. |
| **Frozen document** | An architecture document that must not be silently edited — only via a dated addendum or a narrowly-scoped ADR exception. |
| **Canonical document** | The one document `docs/DOCUMENT_INDEX.md` names as authoritative for a given area; other documents on the same topic are supporting references, not competing authorities. |

## Scope Note

This glossary does not exhaustively re-derive every term in the 70+ ADRs or the platform/product
docs — it covers the terms a new reader hits first in `ARCHITECTURE.md`, `RISK_REGISTER.md`, and the
Decision/Evidence contracts. For anything not listed here, `docs/DOCUMENT_INDEX.md` §4 gives the
reading order to find the canonical source.
