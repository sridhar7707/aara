# AARA Trading Intelligence

**Status:** Application boundary skeleton only. No adapters, services, or data
connections are implemented. This package currently contains no behavior.

## What this is

AARA Product #1, per `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`'s Product
Model and `docs/products/AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`.
Medium-term investing intelligence: portfolio decisions, trade evaluation, risk
management, paper trading validation, eventual broker integration.

## What this is not

- **It does not own the Sentinel Intelligence Engine.** `sentinel_engine/` is a
  separate, independent package (`docs/decisions/ADR-001-sentinel-engine-structure.md`).
  This package consumes it; it does not contain it, extend it, or fork it.
- **It does not replace `bot/` yet.** `bot/` remains the live production trading
  runtime — real scheduled trades, an active Phase 1A validation window,
  protected under `docs/decisions/ADR-002-bot-runtime-protection.md`. Nothing in
  this package reads from, writes to, or imports `bot/`, `dashboard/`, or
  `scheduler/`.

## Dependency Rules

**Allowed:**

```
trading_intelligence -> sentinel_engine
```

**Forbidden:**

```
sentinel_engine -> trading_intelligence
trading_intelligence -> bot runtime (bot/, scheduler/)
trading_intelligence -> dashboard runtime (dashboard/)
```

These rules match `docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md`'s Migration
Principles: the dependency direction is one-way, and today it is not even
exercised — `sentinel_engine` and `bot`/`scheduler` have zero code coupling in
either direction (per `docs/analysis/BOT_DEPENDENCY_MAP.md`), and this package
introduces none either.

## Structure

| Directory | Purpose | Status |
|---|---|---|
| `contracts/` | Trading-Intelligence-specific data contracts, distinct from `sentinel_engine`'s own contracts | Placeholder only — no contracts defined |
| `adapters/` | Read-only translation from `bot/`-shaped data into `sentinel_engine` contracts (candidate, risk, execution, outcome — per `docs/platform/TRADING_INTELLIGENCE_EVENT_MODEL.md` Section 6) | Placeholder only — no adapters implemented. `sentinel_engine/adapters/decision_adapter.py` already exists on the Sentinel Engine side and is not duplicated here. |
| `projections/` | Trading-Intelligence-specific read models, if any prove necessary beyond `sentinel_engine.projections.DecisionProjection` | Placeholder only — no projections defined |
| `services/` | Internal services (signal/screening, decision-orchestration, execution — conceptually parallel to `sentinel_engine`'s `DecisionService`/`EvidenceService`/`GovernanceService` pattern) | Placeholder only — no services implemented |

## Roadmap

See `docs/implementation/AARA_TRADING_INTELLIGENCE_IMPLEMENTATION_ROADMAP.md` for
what comes after this skeleton, and which future steps require their own ADR or
are blocked by Phase 1A validation (`docs/decisions/ADR-004-sentinel-ledger-ownership-strategy.md`).
