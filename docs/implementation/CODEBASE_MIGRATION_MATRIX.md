# CODEBASE MIGRATION MATRIX

**Project:** AARA Platform Migration  
**Source Repository:** ai-trading-bot  
**Purpose:** Controlled extraction of Sentinel Intelligence Engine and separation of product boundaries.

---

# Migration Philosophy

This is NOT a rewrite.

The existing system becomes the foundation of AARA.

Migration strategy:

Current AI Trading System

        |

        v

Extract Sentinel Intelligence Engine

        |

        +---------------------------+
        |                           |

Aara Trading Intelligence     Aara Wealth Intelligence

(Product #1)                  (Product #2)

---

# Migration Status Legend

| Status | Meaning |
|---|---|
| KEEP | Remains in current product |
| MOVE | Direct extraction |
| SPLIT | Requires separation |
| REFACTOR | Requires redesign |
| ARCHIVE | Preserve but no active development |

---

# 1. Sentinel Intelligence Engine Candidates

## sentinel/

Current:

sentinel/

Future:

sentinel_engine/

Status:

MOVE


Reason:

Already contains:

- governance
- events
- projections
- evidence
- approval workflows
- decision tracking


Migration:

Extract as independent intelligence platform.

---

## bot/trust_ledger/

Future:

sentinel_engine/evidence/

Status:

MOVE


Reason:

Trust ledger is a platform capability.

Used by:

- Trading Intelligence
- Wealth Intelligence
- Future AARA products


---

## bot/risk/

Future:

sentinel_engine/governance/risk/

Status:

REFACTOR


Reason:

Risk intelligence applies beyond trading.


---

## database/

Future:

sentinel_engine/storage/

Status:

SPLIT


Move:

- event storage
- evidence storage
- projections


Remain:

- trading operational data


---

## ledger/

Future:

sentinel_engine/ledger/

Status:

MOVE


Reason:

Immutable decision history is a Sentinel capability.

---

# 2. AARA Trading Intelligence

Future location:

applications/trading_intelligence/


---

## bot/execution/

Status:

MOVE


Destination:

applications/trading_intelligence/execution/


Contains:

- broker integrations
- Alpaca clients
- paper execution
- order handling


---

## bot/strategy/

Status:

MOVE


Destination:

applications/trading_intelligence/strategy/


Contains:

- XGBoost
- LSTM
- ensemble models
- market regime
- reinforcement learning


---

## bot/capital/

Status:

MOVE


Destination:

applications/trading_intelligence/capital/


Purpose:

AARA Research Capital Management


---

## backtest/

Status:

MOVE


Destination:

applications/trading_intelligence/backtesting/


---

## scheduler/

Status:

MOVE


Destination:

applications/trading_intelligence/scheduler/


Reason:

Trading schedules are product-specific.

---

# 3. Dashboard Migration

Current:

dashboard/


Status:

SPLIT


---

Trading UI:

Destination:

applications/trading_intelligence/ui/


Includes:

- trading views
- positions
- strategy dashboards
- performance


---

Sentinel UI:

Destination:

sentinel_engine/admin_ui/


Includes:

- governance views
- audit history
- decision chains
- evidence views


---

# 4. Analytics Migration

Current:

analytics/


Status:

SPLIT


---

Sentinel Analytics:

Move:

- calibration
- decision quality
- governance metrics


Destination:

sentinel_engine/analytics/


---

Trading Analytics:

Move:

- strategy performance
- backtesting metrics
- trade attribution


Destination:

applications/trading_intelligence/analytics/

---

# 5. Tools and Scripts

Current:

scripts/

tools/


Status:

DEFER


Reason:

Do not migrate utilities until core architecture stabilizes.

---

# Migration Execution Order

## Phase 1

Create new folders.

No code movement.

Status:

NOT STARTED


---

## Phase 2

Extract Sentinel modules.

Order:

1. events
2. ledger
3. evidence
4. governance
5. projections
6. reasoning


---

## Phase 3

Move Trading Intelligence modules.

Order:

1. execution
2. strategy
3. capital
4. backtesting
5. scheduler


---

## Phase 4

Split dashboard.

---

## Phase 5

Validate:

- Existing tests pass
- Trading application runs
- Sentinel runs independently
- No feature regression


---

# Migration Rule

Every migration must:

1. Preserve behavior
2. Add tests
3. Create git commit
4. Update IMPLEMENTATION_MASTER_ROADMAP.md

---

# Current Status

Completed:

[x] Architecture definition

[x] Implementation roadmap

[x] Codebase inventory


Next:

[ ] Create migration branches

[ ] Create new folder structure

[ ] Begin Sentinel extraction

