# AARA Trading Intelligence

**Status:** Runnable application. Decision Center (`ui/decision_center/`) is
the one implemented screen, wired end-to-end to a real Sentinel Engine read
path through this package's own adapters/query services (see the Structure
table below). Bootstrap (`bootstrap.py`) seeds a handful of deterministic,
illustrative decisions in memory -- there is no persistent backend, live
trading, real market data, or production-readiness claim behind it; see
`ui/decision_center/README.md` for exactly what is and isn't built.

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
| `contracts/` | Trading-Intelligence-specific data contracts (`DecisionContract`, `TradingIntelligenceReadError`), distinct from `sentinel_engine`'s own contracts | Implemented |
| `adapters/` | Read-only adapters wrapping `sentinel_engine`'s `ProjectionRepository`/`DecisionQuery` (`SentinelProjectionDecisionSource`, `SentinelEvidenceSource`, `SentinelGovernanceSource`) | Implemented, read-only. No production adapter exists yet for `bot/`-shaped candidate/execution/outcome data (per `docs/platform/TRADING_INTELLIGENCE_EVENT_MODEL.md` Section 6) -- only the Decision Center read path above. |
| `projections/` | Trading-Intelligence-owned read models for the UI (`DecisionView`, `EvidenceEntry`, `GovernanceEntry`, `ApprovalEntry`) | Implemented |
| `services/` | Query-service boundary between adapters and the UI controller (`DecisionQueryService`, `DecisionEvidenceQueryService`, `DecisionGovernanceQueryService`) | Implemented |

## Roadmap

See `docs/implementation/AARA_TRADING_INTELLIGENCE_IMPLEMENTATION_ROADMAP.md` for
product surfaces beyond Decision Center (Portfolio Intelligence, Risk
Intelligence, and the rest of `docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`'s
screen list -- today, navigation-bar-only placeholders with no screen or
backing code), and for the persistent-backend decision still gated by
`docs/decisions/ADR-004-sentinel-ledger-ownership-strategy.md`.
