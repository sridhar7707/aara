\# SENTINEL EXTRACTION PLAN



\## Purpose



Extract the existing Sentinel capabilities from the AI Trading System into the AARA Sentinel Intelligence Engine without breaking existing functionality.



This is an extraction, not a rewrite.



\---



\# Current State



The repository currently contains:



\- Trading Intelligence

\- Sentinel Intelligence capabilities

\- Shared infrastructure



The goal is:



CURRENT SYSTEM



&#x20;       |

&#x20;       |

&#x20;       v



AARA PLATFORM



&#x20;       |

&#x20;       +-----------------------------+

&#x20;       |                             |



Sentinel Intelligence Engine     AARA Trading Intelligence



\---



\# Extraction Principles



1\. Preserve existing behavior.

2\. Move one bounded capability at a time.

3\. Maintain tests after every migration.

4\. Never remove functionality during extraction.

5\. Commit after every successful milestone.



\---



\# Sentinel Engine Ownership



Sentinel owns:



\## Decision Intelligence



Sources:



sentinel/backend/domain/decision.py



sentinel/backend/services/decision\_service.py





Destination:



sentinel\_engine/domain/

sentinel\_engine/services/





\---



\## Evidence System



Sources:



sentinel/backend/domain/evidence.py



sentinel/backend/services/evidence\_service.py





Destination:



sentinel\_engine/evidence/

sentinel\_engine/services/





\---



\## Event System



Sources:



sentinel/backend/events/





Destination:



sentinel\_engine/events/





Includes:



\- event model

\- event writer

\- event types

\- hash chain





\---



\## Ledger



Sources:



ledger/





Destination:



sentinel\_engine/ledger/





Includes:



\- immutable records

\- hashing

\- integrity verification

\- reproducibility





\---



\## Governance



Sources:



sentinel/backend/services/governance\_service.py



sentinel/backend/services/risk\_governor\_service.py





Destination:



sentinel\_engine/governance/





\---



\## Projections



Sources:



sentinel/backend/projections/





Destination:



sentinel\_engine/projections/





\---



\# Trading Intelligence Ownership



Trading owns:



\## Strategy



Source:



bot/strategy/





Destination:



applications/trading\_intelligence/strategy/





Includes:



\- XGBoost

\- LSTM

\- ensemble

\- regime classifier

\- sentiment

\- RL agent





\---



\## Execution



Source:



bot/execution/





Destination:



applications/trading\_intelligence/execution/





Includes:



\- Alpaca

\- paper execution

\- broker interfaces





\---



\## Capital



Source:



bot/capital/





Destination:



applications/trading\_intelligence/capital/





\---



\## Backtesting



Source:



backtest/





Destination:



applications/trading\_intelligence/backtesting/





\---



\# First Extraction Milestone



Do NOT move code yet.



First milestone:



Create the new Sentinel Engine package structure.



Target:



sentinel\_engine/



&#x20;   domain/

&#x20;   events/

&#x20;   ledger/

&#x20;   governance/

&#x20;   evidence/

&#x20;   projections/

&#x20;   repositories/

&#x20;   services/

&#x20;   tests/





No existing files move during this milestone.



\---



\# Validation



Before any extraction:



Run existing tests:



pytest





Capture baseline:



\- number of tests

\- passing tests

\- failures



\---



\# Rollback Strategy



Every extraction step requires:



git commit



Example:



git commit -m "Extract Sentinel event system"



\---



\# Current Status



Completed:



\[x] Architecture



\[x] Inventory



\[x] Migration mapping



\[x] Dependency analysis

\[x] Sentinel package skeleton (Phase 0)

\[x] Baseline tests captured (see Baseline Test Snapshot below)

\[x] Event system extraction (Phases 1-7: domain, events, evidence, governance,
     ledger, projections, repositories, services, adapters — 82 sentinel_engine
     tests passing)

\[x] Phase 2A: boundary, event-model, gap-analysis, and ledger-integration-options
     design (docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md,
     TRADING_INTELLIGENCE_EVENT_MODEL.md,
     docs/analysis/TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md,
     TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md)

\[x] ADR-001 through ADR-004 recorded (see docs/decisions/)


---

# Baseline Test Snapshot

Date:
2026-08-04

Environment:

Python:
3.9.0

Pytest:
8.4.2


Results:

Tests collected: 1208

Passed: 1162

Skipped: 46

Failed: 0

Errors: 0


Runtime:

84.85 seconds


Status:

BASELINE HEALTHY

Migration may begin.

---


Next:

Phase 3 — Product Development. Concrete ledger storage adapters and bot
integration adapters are explicitly **not** part of Phase 3's initial scope —
per ADR-004, that work is deferred until Phase 1A validation completes and
ADR-004's decision criteria are met. See
docs/decisions/ADR-004-sentinel-ledger-ownership-strategy.md.

---

# Sentinel Engine Extraction Status

## Phase 0: Architecture boundary created

Status: COMPLETE

## Phase 1: Core Decision/Event Contracts

Status: COMPLETE

Implemented:

- Decision domain model
- Event contract
- Event type vocabulary

## Phase 2: Evidence and Governance Contracts

Status: COMPLETE

Implemented:

- Evidence contract
- Policy contract
- Approval contract

## Phase 3: Ledger and Projection Contracts

Status: COMPLETE

Implemented:

- LedgerStore abstraction contract
- DecisionProjection read model contract

## Phase 4: Repository Adapters

Status: COMPLETE

Implemented:

- LedgerRepository (storage-backend-independent facade over LedgerStore)
- ProjectionRepository abstraction contract

## Phase 5: Sentinel Engine Services Layer

Status: COMPLETE

Implemented:

- DecisionService
- EvidenceService
- GovernanceService

## Phase 6: Sentinel Engine Application Boundary

Status: COMPLETE

Implemented:

- SentinelEngine (single entry point coordinating DecisionService, EvidenceService, GovernanceService)

Validation:

- 69 sentinel_engine tests passing

## Phase 7: Sentinel Engine Adapters

Status: COMPLETE

Implemented:

- decision_adapter (sentinel_engine/adapters/decision_adapter.py) — translation
  boundary from plain dict data into the Decision contract, zero bot/ imports

Validation:

- 82 sentinel_engine tests passing

## Phase 2A: Boundary, Event Model & Ledger Design

Status: COMPLETE

Implemented (documentation/design only — no code, no protected paths touched):

- docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md — ownership boundary between
  sentinel_engine and future applications/trading_intelligence/
- docs/analysis/TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md — field-level
  comparison of bot/trust_ledger data against Decision/Event/EventType contracts
- docs/platform/TRADING_INTELLIGENCE_EVENT_MODEL.md — resolves the
  DECISION_CREATED/DECISION_EXECUTED split, rejected-candidate handling,
  portfolio-scoped risk model, and outcome lifecycle
- docs/platform/TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md —
  three ledger-ownership architectures compared (Trading-Intelligence-owned,
  Sentinel-canonical, dual-ledger), no option chosen
- docs/decisions/ADR-003-aara-identity-and-product-access.md — multi-product
  identity/access requirement recorded, implementation deferred
- docs/decisions/ADR-004-sentinel-ledger-ownership-strategy.md — ledger
  ownership choice (Option A/B/C) formally deferred until Phase 1A validation
  completes; ADR-002 protections preserved unchanged

Validation:

- 82 sentinel_engine tests passing (unchanged from Phase 7 — this phase was
  documentation only)

Next:

- Phase 3 — Product Development (see "Current Status" below; concrete storage
  adapters and bot integration remain explicitly deferred per ADR-004, not part
  of Phase 3's initial scope)

