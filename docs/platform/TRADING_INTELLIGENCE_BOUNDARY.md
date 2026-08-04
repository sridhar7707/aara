# Trading Intelligence Boundary

**Status:** Draft — target-state description, not an implementation plan.
**Scope:** Documents boundaries only. No code moves, import changes, or
refactors accompany this document (see ADR-002).

## Purpose

Define what "Aara Trading Intelligence" (Product #1, per `CODEBASE_MIGRATION_MATRIX.md`
and `ADR-001`) owns versus what belongs to the Sentinel Intelligence Engine
(`sentinel_engine/`), ahead of any future `applications/trading_intelligence/`
extraction (Phase 2, still not started — see ADR-002).

## 1. Sentinel Engine Responsibilities

**`sentinel_engine` is the intelligence foundation, not the trading application.**
It owns governance, evidence, decision-lifecycle contracts, and audit — it does not
generate trading signals, place orders, or manage capital. Verified against current
code (`sentinel_engine/`, 82 tests passing, zero real data flowing through any of
it today):

| Capability | Module | What exists |
|---|---|---|
| Decision model | `domain/decision.py` | `Decision` — frozen dataclass: `decision_id`, `symbol`, `action`, `timestamp`, `confidence`, `evidence_reference`, `risk_reference` |
| Event model | `events/event.py`, `event_types.py` | `Event` (`event_id`, `event_type`, `created_at`, `payload`); `EventType` enum: `CANDIDATE_EVALUATED`, `DECISION_CREATED`, `RISK_EVALUATED`, `DECISION_EXECUTED`, `DECISION_OUTCOME_RECORDED` |
| Evidence model | `evidence/evidence.py` | `Evidence` — `evidence_id`, `evidence_type`, `source`, `data`, `collected_at` |
| Governance model | `governance/policy.py`, `approval.py` | `Policy` (`policy_id`, `name`, `description`, `enabled`); `Approval` (`approval_id`, `decision_id`, `status`, `approved_by`, `timestamp`) |
| Ledger abstraction | `ledger/ledger.py` | `LedgerStore(ABC)` — abstract `append`/`read_all`, no backend implemented |
| Projections | `projections/decision_projection.py` | `DecisionProjection` read model (Decision's fields plus `status`, `updated_at`) |
| Repositories | `repositories/` | `LedgerRepository` (concrete, wraps any `LedgerStore`); `ProjectionRepository(ABC)` |
| Services | `services/` | `DecisionService`, `EvidenceService`, `GovernanceService`, `SentinelEngine` facade |
| Adapters | `adapters/decision_adapter.py` | `to_decision(dict) -> Decision`, validates 7 required fields, zero `bot` imports |

## 2. Trading Intelligence Responsibilities

**Current implementation:** `bot/`, `scheduler/`.
**Future target:** `applications/trading_intelligence/` (does not exist yet — no
directory has been created, per ADR-002; this is a target, not a plan to create it
now).

Responsibilities, mapped to what currently implements them:

| Responsibility | Current owner |
|---|---|
| Signal generation | `bot/strategy/` (XGBoost, LSTM, RL, ensemble, regime classification, sentiment, macro) |
| Strategy evaluation | `bot/strategy/signal_gate.py`, `bot/strategy/ensemble.py` |
| Portfolio decisions | `bot/main.py`, `bot/_main_cycle.py` (cycle orchestration) |
| Capital management | `bot/capital/pool.py` |
| Risk management | `bot/risk/risk_manager.py` |
| Execution orchestration | `bot/execution/` (broker integration, paper/live executor selection) |
| Operational trading workflows | `bot/main.py`, `bot/_main_*.py`, `scheduler/` (dispatcher, session manager, startup/trading/shutdown jobs — confirmed a live, independent entry point per ADR-002, not legacy/unused) |

`bot/trust_ledger/` (candidate/decision/outcome tracking) sits conceptually between
the two sides — per `CODEBASE_MIGRATION_MATRIX.md` it is a **Sentinel-side**
extraction candidate (→ `sentinel_engine/evidence/`), not a Trading Intelligence
one, despite living under `bot/` today.

## 3. Shared Contracts

Documenting what exists, not what's integrated:

- **`Decision` dataclass** (`sentinel_engine/domain/decision.py`) — the only
  decision-shaped contract that exists. Nothing in `bot/` constructs one today.
- **`Event`/`EventType`** (`sentinel_engine/events/`) — five event types with no
  emitters yet.
- **`Evidence`** (`sentinel_engine/evidence/evidence.py`) — no producer exists yet.
- **`Approval`/governance model** (`sentinel_engine/governance/`) — no caller exists
  yet.

**Conceptual alignment, not integration:** `sentinel_engine`'s `EventType`
vocabulary —

```
CANDIDATE_EVALUATED
DECISION_CREATED
RISK_EVALUATED
DECISION_EXECUTED
DECISION_OUTCOME_RECORDED
```

— aligns conceptually with `bot/trust_ledger/`'s existing candidate → decision →
risk → outcome lifecycle (`candidates.py`, `decisions.py`, `risk.py`, `outcomes.py`).
**No integration exists.** `bot/trust_ledger/` writes directly to
`data/trust_ledger.db`; it does not construct `sentinel_engine.events.event.Event`
objects, and nothing translates between the two today. This is a structural
observation about vocabulary overlap, not a claim that wiring has happened.

## 4. Event Ownership

**Future proposal — not implemented.** No event in this table is emitted by
anything today; this is proposed future ownership only.

| Event type | Proposed owner | Status |
|---|---|---|
| `CANDIDATE_EVALUATED` | Trading Intelligence screening layer (`bot/strategy/` / `scripts/screen_universe.py`) | Future proposal — not implemented |
| `DECISION_CREATED` | Trading Intelligence orchestration (`bot/main.py` / `scheduler/trading_job.py`) | Future proposal — not implemented |
| `RISK_EVALUATED` | Trading Intelligence risk layer (`bot/risk/risk_manager.py`) | Future proposal — not implemented |
| `DECISION_EXECUTED` | Trading Intelligence execution layer (`bot/execution/`) | Future proposal — not implemented |
| `DECISION_OUTCOME_RECORDED` | Trading Intelligence outcome tracking (`bot/trust_ledger/outcomes.py` or successor) | Future proposal — not implemented |

## 5. Data Ownership

**Trading Intelligence owns:**
- Trading databases (`trades.db`, `trading_bot.db`, `bot/db/` caches)
- Model artifacts (`models/saved/*`, HF-synced)
- Execution records (operational trade log, `bot/db/trade_log.py`)

**Sentinel Engine owns:**
- Decision lifecycle contracts (`Decision`, `Event`)
- Evidence (`Evidence`)
- Governance (`Policy`, `Approval`)
- Projections (`DecisionProjection`)

**Explicitly unknown — not decided by this document:**
- What implements `sentinel_engine/ledger/`'s `LedgerStore` backend. None exists
  today; only the abstract interface.
- The relationship between the top-level `ledger/` package (hash-chain,
  integrity, reproducibility — currently imported directly by `bot/main.py`) and
  `sentinel_engine/ledger/`. `CODEBASE_MIGRATION_MATRIX.md` names top-level
  `ledger/` as the eventual `sentinel_engine/ledger/` backend, but no such wiring
  exists.
- The relationship between `data/trust_ledger.db` (written today by
  `bot/trust_ledger/connection.py`) and any future Sentinel-side ledger — whether
  it migrates, is replayed, or coexists is not decided.

## 6. Future Adapter Responsibilities

**Existing:** `sentinel_engine/adapters/decision_adapter.py` — `to_decision(dict)`.
The only adapter that exists.

**Future possibilities (not designed, not implemented, requires future ADR/design):**
- Candidate adapter — would translate screening output into `Evidence`/`CANDIDATE_EVALUATED`.
- Risk adapter — would translate `bot/risk/risk_manager.py` output into `RISK_EVALUATED`.
- Execution adapter — would translate `bot/execution/` results into `DECISION_EXECUTED`.
- Outcome adapter — would translate `bot/trust_ledger/outcomes.py` (or successor)
  into `DECISION_OUTCOME_RECORDED`.

None of these four are designed. Naming them here is scope identification, not a
commitment to build them, and not a specification of their shape.

## 7. Migration Principles

- Trading Intelligence depends on Sentinel Engine. Sentinel Engine never depends on
  Trading Intelligence — the dependency direction is one-way, and is already true
  today (zero coupling in either direction, verified in `BOT_DEPENDENCY_MAP.md`).
- Adapters are the only mechanism permitted to cross the boundary. Nothing in
  `sentinel_engine` imports `bot`/`scheduler` types directly, and nothing in
  `bot`/`scheduler` imports `sentinel_engine` types directly.
- ADR-002 protection remains active: `bot/`, `dashboard/`, `scheduler/`,
  `.github/workflows/`, `database/`, top-level `ledger/` stay frozen until a
  dedicated, scoped ADR authorizes a specific change.
- No runtime migration occurs from this document. This is a boundary description,
  not an execution plan.

## 8. Current vs Future Architecture

**Current:**

```
bot/
 |
 +-- strategy
 +-- risk
 +-- execution
 +-- trust_ledger

scheduler/
 |
 +-- dispatcher (sole cron entry point, per its own docstring)
 +-- trading_job / startup_job / shutdown_job
```

No connection to `sentinel_engine/` exists from either.

**Future (target, not built):**

```
applications/trading_intelligence/
 |
 adapters
 |
 v
sentinel_engine/
 |
 +-- domain / events / evidence / governance / ledger / projections
```

## Current Boundary Reality (Not Target — What Actually Exists Today)

- **Zero code coupling** between `sentinel_engine/` and `bot/`/`scheduler/` in either
  direction (verified in `BOT_DEPENDENCY_MAP.md`). Trading Intelligence, as it
  exists today, has no dependency on the engine and vice versa.
- `sentinel_engine/adapters/decision_adapter.py` (`to_decision(data: dict)`) is the
  only boundary-shaped code that exists — it's a one-sided translation function, not
  a live bridge. It was built with zero `bot` imports by design (ADR from the
  extraction plan), so it doesn't create coupling on its own.
- There is currently no mechanism by which anything Trading Intelligence does
  produces a `sentinel_engine.domain.decision.Decision`, records a
  `sentinel_engine.events.event.Event`, or writes to any `sentinel_engine` ledger.
  Trading's own audit trail today is `bot/trust_ledger/` + the top-level `ledger/`
  package, entirely separate from `sentinel_engine/ledger/`.

## 9. Unresolved Decisions

- Does existing `bot` lifecycle data fit Sentinel contracts?
- What implements `LedgerStore`?
- Relationship between top-level `ledger/` and Sentinel ledger?
- Migration/replay strategy for `trust_ledger.db`?
- Incremental event adoption vs. all events?
- Ownership of future adapters?

## Non-Goals

- Not deciding whether/when Phase 2 extraction begins.
- Not specifying the concrete dict schema `decision_adapter.to_decision()` expects
  beyond what's already in its code (`decision_id`, `symbol`, `action`, `timestamp`,
  `confidence`, `evidence_reference`, `risk_reference`) — whether `bot/`'s actual data
  shapes cleanly into that today is unverified and out of scope for this document.
