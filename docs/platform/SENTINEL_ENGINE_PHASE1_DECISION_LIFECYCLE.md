# Sentinel Engine Phase 1: Governed Decision Lifecycle

**Status:** Architecture guidance — an implementation contract, not an
implementation. This document contains no code and authorizes no change by
itself; it defines what Phase 1 must build against
[ADR-001](../decisions/ADR-001-sentinel-engine-structure.md)'s existing
`sentinel_engine/` structure.
**Date:** 2026-08-06
**Scope:** The first complete, governed decision lifecycle inside
`sentinel_engine/`.

## 1. Objective

Enable one complete governed decision lifecycle, end to end, through
`sentinel_engine/` alone:

```
Decision → Evidence → Governance Evaluation → Approval → Ledger Event → Projection → Query
```

**Current state:** only the `Decision → Ledger Event → Projection → Query`
segment exists today, in `DecisionService.create_decision()`. `Evidence`
attachment (`EvidenceService`) and governance/approval recording
(`GovernanceService`) exist as isolated, in-memory-only domain services —
neither writes to the ledger, neither updates the decision's projection, and
neither is wired to a repository of any kind. Phase 1's objective is closing
that gap: making evidence attachment, governance evaluation, and approval
each a first-class, ledgered step in the same decision's lifecycle, so a
single `decision_id` accumulates a complete, queryable audit trail.

## 2. Domain Concepts

All concepts below already exist in `sentinel_engine/`. Phase 1 introduces
**no new domain entity classes**. The only new domain vocabulary Phase 1 may
require is additional `EventType` enum members (see §3) — these are event
labels, not new domain classes.

| Concept | Location | Current shape |
|---|---|---|
| `Decision` | `sentinel_engine/domain/decision.py` | Frozen dataclass: `decision_id`, `symbol`, `action`, `timestamp`, `confidence`, `evidence_reference`, `risk_reference` |
| `Evidence` | `sentinel_engine/evidence/evidence.py` | Frozen dataclass: `evidence_id`, `evidence_type`, `source`, `data`, `collected_at` |
| `Policy` | `sentinel_engine/governance/policy.py` | Frozen dataclass: `policy_id`, `name`, `description`, `enabled` |
| `Approval` | `sentinel_engine/governance/approval.py` | Frozen dataclass: `approval_id`, `decision_id`, `status`, `approved_by`, `timestamp` |
| `Event` / `EventType` | `sentinel_engine/events/event.py`, `event_types.py` | Frozen `Event` dataclass (`event_id`, `event_type`, `created_at`, `payload`); `EventType` is a `str` enum currently holding `CANDIDATE_EVALUATED`, `DECISION_CREATED`, `RISK_EVALUATED`, `DECISION_EXECUTED`, `DECISION_OUTCOME_RECORDED` |
| `LedgerStore` | `sentinel_engine/ledger/ledger.py` | Abstract: `append(event)`, `read_all()` |
| `DecisionProjection` | `sentinel_engine/projections/decision_projection.py` | Frozen dataclass: `decision_id`, `symbol`, `action`, `status`, `confidence`, `evidence_reference`, `risk_reference`, `updated_at` |

`Policy` and `Approval` are existing concepts under the umbrella term
"Governance" used in §3–§4; no separate `Governance` class exists or is
introduced.

## 3. Event Flow

| Step | Requested name | Classification | Phase 1 requirement |
|---|---|---|---|
| 1 | `DecisionCreated` | Existing — maps directly to `EventType.DECISION_CREATED` | None. Already implemented in `DecisionService.create_decision()`. |
| 2 | `EvidenceAttached` | **New** `EventType` member required | `EvidenceService.associate_evidence()` must write this event via `LedgerRepository`, in addition to its current in-memory association. |
| 3 | `GovernanceEvaluated` | **New** `EventType` member required | A governance evaluation step (see §4, `governance_service.py`) must write this event, recording the `Policy` outcome against the decision. |
| 4 | `ApprovalRecorded` | **New** `EventType` member required | `GovernanceService.record_approval()` must write this event via `LedgerRepository`, in addition to its current in-memory recording. |
| 5 | `EventWritten` | Mechanical, not a distinct `EventType` | This is `LedgerRepository.save_event()` itself — the persistence action common to steps 1–4, not a fifth event type. Documented as a flow step because every one of steps 1–4 must actually reach the ledger, not just update in-memory state. |
| 6 | `ProjectionUpdated` | Mechanical, not a distinct `EventType` | This is `ProjectionRepository.save()` — `DecisionProjection` must be re-saved (upserted by `decision_id`) after each of steps 2–4, advancing its `status` field, not just at creation. |

Steps 5 and 6 are **outcomes**, not new event types: every ledgered step
(1–4) must be followed by a ledger write and a projection update. Treating
them as separate `EventType` values would conflate the event with its own
persistence side effect.

## 4. Service Responsibilities

| Service | Current responsibility | Phase 1 addition |
|---|---|---|
| `decision_service.py` | Creates a `Decision`, writes `DECISION_CREATED`, saves the initial `DecisionProjection`. Already depends on `LedgerRepository` and `ProjectionRepository`. | None required — this is the reference pattern the other three services must follow. |
| `evidence_service.py` | Associates `Evidence` with a `decision_id` in an in-memory dict only. No repository dependency exists today. | Must gain a `LedgerRepository` dependency; `associate_evidence()` must write `EVIDENCE_ATTACHED` and update the decision's `DecisionProjection` status via `ProjectionRepository`. |
| `governance_service.py` | Registers/reads `Policy`; records/reads `Approval` in in-memory dicts only. No repository dependency exists today. | Must gain a `LedgerRepository` dependency (and `ProjectionRepository`, for status updates). Needs a governance-evaluation entry point (naming TBD at implementation time) that writes `GOVERNANCE_EVALUATED`; `record_approval()` must write `APPROVAL_RECORDED`. |
| `sentinel_engine.py` | Pure coordination facade: forwards calls to the three services, injects nothing itself, makes no persistence decisions. | None required structurally — continues to expose the same facade pattern for whatever new entry points `evidence_service.py`/`governance_service.py` gain (e.g. a governance-evaluation call), without owning any repository logic itself. |

## 5. Repository Boundaries

| Repository | Current contract | Phase 1 usage |
|---|---|---|
| `ledger_repository.py` (`LedgerRepository` over `LedgerStore`) | `save_event(event)`, `get_events()`. Append-only, backend-agnostic. | Becomes the single write path for all four ledgered steps (`DECISION_CREATED`, `EVIDENCE_ATTACHED`, `GOVERNANCE_EVALUATED`, `APPROVAL_RECORDED`), used by `decision_service.py`, `evidence_service.py`, and `governance_service.py` alike. No new methods required. |
| `projection_repository.py` (abstract `save`/`get`) | Currently called once, at decision creation. | Must be called again after each subsequent ledgered step, with a newly-constructed `DecisionProjection` (frozen dataclass — an update means building a new instance with the advanced `status`/`updated_at` and re-`save()`-ing it, keyed by the same `decision_id`). No interface change required; concrete adapters must treat `save()` as an upsert. |

Neither repository's abstract interface needs to change. This is an
*additional-caller*, not an *additional-method*, integration.

## 6. Success Criteria

Phase 1 is complete when a single test, using only `sentinel_engine/`
components, can:

1. Create a `Decision` and receive a `DECISION_CREATED` event.
2. Attach `Evidence` to that decision and observe an `EVIDENCE_ATTACHED`
   event in the ledger.
3. Evaluate governance against a registered `Policy` and observe a
   `GOVERNANCE_EVALUATED` event in the ledger.
4. Record an `Approval` and observe an `APPROVAL_RECORDED` event in the
   ledger.
5. Confirm, via `LedgerRepository.get_events()`, that all four events exist
   for that `decision_id`, in order.
6. Query the decision's current `DecisionProjection` via
   `SentinelEngine.get_decision_projection()` (or the underlying service) and
   observe its `status` reflecting the most recent step, not just
   `DECISION_CREATED`.

No concrete backend (SQLite, HuggingFace, or otherwise) is required to meet
this criterion — as with `test_decision_service.py` today, in-memory fakes of
`LedgerStore` and `ProjectionRepository` are sufficient.

## 7. Out of Scope

Phase 1 does **not** include, and no Phase 1 work should introduce:

- AI models (XGBoost, LSTM, or any other)
- LLMs or LLM-based reasoning
- Predictions or forecasting of any kind
- Trading strategies or signal generation
- Broker execution or order placement

This phase is governance-first infrastructure: it proves that a decision can
be created, evidenced, evaluated, approved, and queried with a complete
audit trail — independent of what generates the decision or what (if
anything) ever executes on it.
