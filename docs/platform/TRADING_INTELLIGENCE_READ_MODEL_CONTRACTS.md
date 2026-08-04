# Trading Intelligence Read Model Contracts

**Status:** Contract design — Phase 2B. Documentation only. No code was created
or modified. `sentinel_engine/` and `applications/trading_intelligence/` were
not touched — this document designs contracts against them, it does not
implement anything in either. `bot/`, `dashboard/`, `scheduler/`,
`.github/workflows/`, `database/`, `ledger/` untouched, confirmed via `git
status` before and after.

**Authority:** ADR-001, ADR-002, ADR-003, ADR-004, `TRADING_INTELLIGENCE_BOUNDARY.md`,
`TRADING_INTELLIGENCE_EVENT_MODEL.md`,
`TRADING_INTELLIGENCE_SENTINEL_READ_MODEL_ANALYSIS.md` — this document formalizes
that analysis into contract shapes; it doesn't revisit its findings.

---

## 1. Decision Read Contract

- **Input:** `decision_id: str`
- **Output:** `DecisionProjection | None` — `decision_id`, `symbol`, `action`,
  `status`, `confidence`, `evidence_reference`, `risk_reference`, `updated_at`.
  Already exists, already tested (`sentinel_engine/projections/decision_projection.py`).
- **Ownership:** Sentinel Engine owns the `DecisionProjection` contract and its
  backing store (once one exists). Trading Intelligence reads through the
  contract only — it never constructs, mutates, or persists a
  `DecisionProjection` directly.
- **Data lifecycle:** created by `DecisionService.create_decision()` →
  persisted via `ProjectionRepository.save()` → updated only through that same
  write path (not through any read contract) → read via
  `ProjectionRepository.get()` (today) or a future
  `TradingIntelligenceDecisionReader` (proposed, per the read-model analysis).
- **Future implementation location:** unresolved by this document. The
  existing `applications/trading_intelligence/` skeleton's `adapters/` was
  scoped for the *opposite* direction — translating `bot/`-shaped data *into*
  Sentinel contracts (write path) — not for reading Sentinel data back out. The
  closest existing placeholder is `services/` (a reader is conceptually a
  narrow query service), but no subpackage was purpose-built for this. Flagged
  as an open question (Section 7 / future work), not decided here, and not
  resolved by modifying the skeleton — out of scope for this task.

## 2. Evidence Read Contract

- **Evidence retrieval model:** `get_evidence_for_decision(decision_id: str) ->
  list[Evidence]` — already exists (`EvidenceService.get_evidence_for_decision`),
  already returns a copy, not the internal list.
- **Relationship to decisions:** looser than it first appears. `Evidence` itself
  carries no `decision_id` field — the association is external, held in
  `EvidenceService`'s own `decision_id -> list[Evidence]` mapping via
  `associate_evidence()`. This means a decision can have **multiple** `Evidence`
  records, while `Decision.evidence_reference` is a **single** string field.
  **Not previously flagged this precisely:** a read contract must decide
  whether `evidence_reference` means "the one referenced evidence item" or
  whether the real read path is "all evidence associated with this decision"
  (a list, via `get_evidence_for_decision`) — these are two different contracts
  with the same name in different documents. Not resolved here; recorded as a
  design question for whoever builds this.
- **Ownership boundaries:** Sentinel Engine owns the `Evidence` contract and its
  association-to-decision logic. Trading Intelligence would eventually be the
  *producer* of the raw material behind evidence (candidate screening results,
  market context, model outputs — per `TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md`),
  but the `Evidence` record and its storage belong to Sentinel Engine, not to
  Trading Intelligence.

## 3. Risk Read Contract

**The gap, restated precisely (from `TRADING_INTELLIGENCE_SENTINEL_READ_MODEL_ANALYSIS.md`
Section 3-4):** no `Risk`/`RiskEvaluation` dataclass exists in `sentinel_engine`.
`EventType.RISK_EVALUATED` exists as an enum value only; the data behind it
would live in an untyped `Event.payload` dict, not a typed contract.

**Proposed future contract shape (documentation only — no file created, no
class defined):**

- A `RiskEvaluation` object mirroring the real data already documented in
  `TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md` Section 1 from
  `bot/trust_ledger/risk.py`'s actual `risk_evaluation_events` row: an
  identifier, `evaluated_at`, `from_state`, `to_state`, `trigger_reason`,
  `recommended_position_size`, `actual_position_size`.
- **Portfolio-scoped, not decision-scoped** — matching
  `TRADING_INTELLIGENCE_EVENT_MODEL.md` Section 7's already-settled design (many
  decisions in a cycle share one risk reference).
- Proposed read shape: `get_latest_risk_evaluation() -> RiskEvaluation | None`
  and/or `get_risk_evaluation(risk_reference: str) -> RiskEvaluation | None`
  (matching `Decision.risk_reference`'s pointer semantics).

**No implementation accompanies this proposal.** This section documents a gap
and a candidate shape; it does not create `sentinel_engine/domain/risk.py` or
any equivalent.

## 4. Governance Read Contract

- **Policy visibility:** `get_policy(policy_id: str) -> Policy | None`,
  `is_policy_enabled(policy_id: str) -> bool` — already exist
  (`GovernanceService`).
- **Approval visibility:** `get_approval(decision_id: str) -> Approval | None` —
  already exists (`GovernanceService`).
- **Audit requirements:** these three getters are themselves the audit-relevant
  surface — reading `Policy`/`Approval` state is how governance becomes visible
  in the UI (per `AARA_UI_UX_DESIGN_SYSTEM.md`'s "governance visible" principle
  and the Decision Center screen in
  `AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`). No separate "audit of the
  audit-viewing" mechanism is proposed — reading governance state doesn't
  itself need auditing, since it can't mutate anything (Section 5).

## 5. Read-Only Boundary Rules

**Allowed:**
- Query (get-by-id: `ProjectionRepository.get()`, `GovernanceService.get_policy()`,
  `get_approval()`, `EvidenceService.get_evidence_for_decision()`)
- Projection access (`DecisionProjection` reads)
- Analytics/aggregate views — **not yet designed anywhere**; noted as an allowed
  future category, not a proposed contract

**Forbidden:**
- Mutation of any kind
- Policy changes (`GovernanceService.register_policy()`)
- Ledger writes (`LedgerRepository.save_event()`, `ProjectionRepository.save()`)
- Execution actions — nothing in `sentinel_engine` performs execution today, but
  stated explicitly: no future reader built from this document may become a
  path through which Trading Intelligence's execution concern routes. Reading
  and executing must remain structurally separate.

Every contract in Sections 1-4 was chosen specifically because it maps to an
existing *getter*, never a full service object — this is how "read-only" stays
true structurally, not just by naming convention (per the read-model analysis's
Section 4 finding that no enforcement mechanism exists in code today; this
document doesn't add one either, it just consistently picks the narrowest
existing accessor).

## 6. Backend Independence

Explicitly preserved, not touched by this document:

- **ADR-004's ledger ownership deferral remains fully in force.** Nothing here
  selects Option A, B, or C from
  `TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md`.
- **No storage assumption is made anywhere in this document.** Every contract
  above is defined against `sentinel_engine`'s existing abstract interfaces
  (`ProjectionRepository(ABC)`, `LedgerRepository` wrapping any `LedgerStore`),
  which are already backend-agnostic by construction (ADR-001). This document
  adds no dependency on a concrete backend existing.

## 7. First Implementation Candidate

The **Decision Read Contract** (Section 1) is the first candidate:

- Zero missing-contract gap, unlike Risk (Section 3).
- Its underlying `DecisionProjection` object is already built and tested (82
  tests), unlike a hypothetical `RiskEvaluation`.
- Its ownership and data lifecycle are already fully defined (Section 1).

**But implementation does not begin from this conclusion.** It waits until a
backend/read-model strategy is approved — i.e., until ADR-004's deferred ledger
ownership decision is made and its Phase 1A-completion criteria are satisfied.
This document identifies the smallest future milestone; it does not authorize
starting it.

---

## Constraints Confirmed

No adapter, service, or import was created. `applications/trading_intelligence/`
and `sentinel_engine/` were not modified — this document analyzes and proposes
contract shapes in prose only.
