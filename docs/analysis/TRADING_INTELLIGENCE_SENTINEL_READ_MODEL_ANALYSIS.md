# Trading Intelligence ↔ Sentinel Engine Read Model Analysis

**Status:** Design analysis — Phase 2A (Sentinel Read-Only Integration Analysis).
Documentation only. No code changes accompany this document — `sentinel_engine/`
and `applications/trading_intelligence/` were reviewed (read-only) but not
modified; `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`, `database/`,
`ledger/` were not touched at all. Confirmed via `git status` before and after.

**Authority:** ADR-001, ADR-002, ADR-004, `TRADING_INTELLIGENCE_BOUNDARY.md`,
`TRADING_INTELLIGENCE_EVENT_MODEL.md`,
`AARA_TRADING_INTELLIGENCE_IMPLEMENTATION_ROADMAP.md`.

**Reviewed (read-only, unchanged):** every file in `sentinel_engine/` (excluding
`tests/`) and `applications/trading_intelligence/` (the skeleton created in the
prior milestone — `__init__.py` files and empty `contracts/`/`adapters/`/
`projections/`/`services/` subpackages only, still no implementation).

**Important framing:** `sentinel_engine`'s `LedgerStore` and `ProjectionRepository`
have no backend implementation (ADR-004 defers this). Everything below is a
design analysis of what *would* be safe/possible once a backend exists — not a
description of working data access today. There is currently nothing real to
read.

---

## 1. What Sentinel Engine Capabilities Are Safe to Expose

| Capability | Contract | Read accessor | Safe to expose read-only? |
|---|---|---|---|
| Decisions | `sentinel_engine.domain.decision.Decision`, `projections.DecisionProjection` | `ProjectionRepository.get(decision_id)`, `DecisionService.get_projection(decision_id)` | Yes — `Decision`/`DecisionProjection` are frozen dataclasses; the get-accessors are pure reads |
| Evidence | `sentinel_engine.evidence.evidence.Evidence` | `EvidenceService.get_evidence_for_decision(decision_id)` | Yes — already verified to return a copy, not the internal list (`test_get_evidence_for_decision_returns_a_copy_not_the_internal_list`) |
| Governance | `sentinel_engine.governance.policy.Policy`, `approval.Approval` | `GovernanceService.get_policy(id)`, `is_policy_enabled(id)`, `get_approval(decision_id)` | Yes, **if only these getters are exposed** — `GovernanceService` also has `register_policy`/`record_approval` (writes) on the same object; a reader must not expose the whole service, only its getters (see Section 4) |
| Projections | `DecisionProjection` | `ProjectionRepository.get()` | Yes — this is the layer designed for read access in the first place |
| Events | `sentinel_engine.events.event.Event`/`EventType` | `LedgerRepository.get_events()` | Technically yes (no mutation), but **broader than the other four** — it returns the entire ledger unfiltered, not one decision's data. Safe from a write-hazard standpoint; over-scoped for a per-decision consumer. Flagged, not resolved. |

No sentinel_engine object exposes a way to mutate state through what would be a
"reader" — the risk is over-exposure of read surface (Events), not accidental
write access, **as long as readers are built to wrap only the specific
getter methods above, not entire service objects** (Section 4 explains why this
matters concretely for Governance).

## 2. Future Read-Only Interfaces (Not Implemented)

Four proposed interfaces — signatures only, no implementation, no code file
created for any of them:

- **`TradingIntelligenceDecisionReader`** — `get_decision(decision_id) ->
  DecisionProjection | None`. Wraps `ProjectionRepository.get()` only — never
  `DecisionService`, to structurally avoid `create_decision()` (a write) being
  reachable through the same object.
- **`TradingIntelligenceEvidenceReader`** — `get_evidence(decision_id) ->
  list[Evidence]`. Wraps `EvidenceService.get_evidence_for_decision()` only.
- **`TradingIntelligenceRiskReader`** — **cannot be fully specified today.** No
  `RiskEvaluation` contract exists in `sentinel_engine` (Section 4). At best this
  would wrap `LedgerRepository.get_events()` filtered to
  `event_type == EventType.RISK_EVALUATED`, reading an untyped `Event.payload`
  dict rather than a typed object.
- **`TradingIntelligenceGovernanceReader`** (proposed, not named in the task but
  a natural fourth given Section 1's findings) — `get_policy(id)`,
  `is_policy_enabled(id)`, `get_approval(decision_id)`. Wraps only
  `GovernanceService`'s three getters, explicitly excluding `register_policy`/
  `record_approval`.

None of these four exist as code anywhere. This section names them and their
intended read-only scope only.

## 3. Are Existing Sentinel Engine Contracts Sufficient?

- **Decision / Evidence / Governance:** yes, sufficient for a reader as
  specified above — the underlying dataclasses and read-accessor methods
  already exist and are tested (82 tests).
- **Risk:** **no.** There is no `Risk`/`RiskEvaluation` dataclass in
  `sentinel_engine` anywhere. `EventType.RISK_EVALUATED` exists as an enum
  value, but the data it would carry is an untyped `dict` inside `Event.payload`
  — a `TradingIntelligenceRiskReader` today could only return a generic `Event`,
  not a strongly-typed risk object, unlike every other reader in Section 2.
- **Events (generic):** sufficient as a mechanism, but not as a per-category
  typed interface — every event type shares one `Event` shape with an untyped
  payload. This is a design tradeoff already implicit in `sentinel_engine`'s
  existing structure, not a new finding, but it's the reason the Risk reader
  specifically can't be typed today.

## 4. Missing Contracts

- **A `RiskEvaluation` domain object.** Should conceptually mirror what
  `TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md` Section 1 already documented
  from `bot/trust_ledger/risk.py`'s real `risk_evaluation_events` row shape
  (`from_state`, `to_state`, `trigger_reason`, `recommended_position_size`,
  `actual_position_size`) — and should be portfolio-scoped, not decision-scoped,
  matching the design already settled in `TRADING_INTELLIGENCE_EVENT_MODEL.md`
  Section 7. Not created by this document — a missing-contract finding only.
- **A corresponding risk repository/service**, parallel to
  `LedgerRepository`/`ProjectionRepository`/`DecisionService`, does not exist
  either — there is nowhere for a `RiskEvaluation` to be stored or retrieved
  even if the dataclass existed.
- **A structural read-only boundary.** Today, "read-only access" to Decisions or
  Governance means *calling only some methods* of `DecisionService`/
  `GovernanceService` by convention — nothing prevents a caller holding a
  `GovernanceService` reference from also calling `register_policy()`. The four
  proposed readers in Section 2 are a design response to this (wrap the
  narrowest object, e.g. `ProjectionRepository` instead of `DecisionService`),
  but no enforcement mechanism (e.g. a `Protocol` restricting the interface)
  exists in code today. Flagged as a design gap, not solved here.

## 5. First Read-Only Milestone

Given the findings above, the narrowest, best-grounded starting point is
**`TradingIntelligenceDecisionReader`**:

- Wraps `ProjectionRepository.get(decision_id) -> DecisionProjection | None`
  only — the one capability with zero missing-contract gap (Section 3), an
  existing typed return value, and no write method reachable through the same
  object.
- **This is a design milestone, not a working-code milestone.** Since
  `ProjectionRepository` has no backend (ADR-004), defining this reader's
  interface produces no retrievable data yet regardless of implementation
  status. The milestone is: agree on the interface shape now; implement it only
  once a `ProjectionRepository` backend exists, which itself waits on ADR-004's
  Phase 1A gate.
- Evidence and Governance readers are reasonable next candidates once the
  Decision reader's pattern is validated; the Risk reader cannot proceed until
  the missing `RiskEvaluation` contract (Section 4) is designed separately.

## Constraints Confirmed

- No `bot` or `dashboard` import appears anywhere in this document's proposals
  — every reader wraps only `sentinel_engine` objects.
- No database change, adapter implementation, or migration was made or
  proposed as ready-to-build; everything in Sections 2 and 5 is named, not
  implemented.
