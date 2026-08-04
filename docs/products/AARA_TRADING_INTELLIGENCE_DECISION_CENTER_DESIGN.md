# AARA Trading Intelligence — Decision Center Design

**Status:** Screen design — Phase 3D, the first Trading Intelligence user
experience to be fully specified. Documentation only. No UI, adapter, or
service code was created or modified. `bot/`, `dashboard/`, `scheduler/`,
`.github/workflows/`, `database/`, `ledger/`, `sentinel_engine/` untouched,
confirmed via `git status` before and after.

**Authority:** `AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`,
`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`,
`TRADING_INTELLIGENCE_SENTINEL_READ_INTEGRATION_DESIGN.md`,
`TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md`,
`TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md`.

---

## 1. Purpose

Decision Center is the primary intelligence review workspace — the single
place a user goes to understand what the system decided and why. Per
`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`'s existing definition: review
and evaluate individual trading decisions, answering "what did the system
decide, and why? What evidence supports it? Is anything pending approval?"
This document does not redefine that purpose — it specifies the screen in
enough detail to build from later.

## 2. User Roles

Per ADR-003, unchanged:

| Role | Decision Center access |
|---|---|
| Trading Intelligence User | Full access |
| AARA Super User / Platform Administrator | Full access, plus cross-product/admin context |
| Wealth Intelligence User | No access — different product |

No authentication implementation exists. This table describes intended access,
not a built mechanism, consistent with every prior document.

## 3. Data Model

**Available today (real, tested code — 29 `applications/trading_intelligence/tests`
passing, 82 `sentinel_engine/tests` passing, none connected to real data):**

- `DecisionContract` (`contracts/decision_contract.py`) — `decision_id`,
  `symbol`, `action`, `status`, `confidence`, `evidence_reference`,
  `risk_reference`, `updated_at`.
- `DecisionView` (`projections/decision_view.py`) — the UI-facing subset:
  `decision_id`, `symbol`, `action`, `status`, `confidence`, `updated_at`
  (deliberately excludes the two reference fields — see Section 4).
- The plumbing that would produce these from real Sentinel data —
  `SentinelProjectionDecisionSource`, `DecisionQueryService` — is built and
  tested, but not wired to any real backend (`ProjectionRepository` has none).

**Future (not built, no contract exists yet for some of these):**

- **Evidence details** — `sentinel_engine.evidence.Evidence` exists, but no
  Trading-Intelligence-side reader/adapter has been built, and the cardinality
  question (`evidence_reference` singular vs. `get_evidence_for_decision()`
  list) from `TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md` Section 2 is still
  open.
- **Risk context** — no `RiskEvaluation` contract exists anywhere in
  `sentinel_engine` (per that same document's Section 3). This is a bigger gap
  than Evidence: there's no data model to build a reader against yet, not just
  a missing reader.
- **Governance approval** — `sentinel_engine.governance.Approval` exists, but
  `approval_events` (the underlying ledger table) has zero writers anywhere in
  `bot/trust_ledger/`, per `TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md`'s
  finding. Even a working reader would have nothing real to read.
- **Outcome tracking** — `DECISION_OUTCOME_RECORDED` exists as an `EventType`
  value; no Trading-Intelligence-side contract or reader exists for it.

## 4. Screen Layout

- **Decision list** — a scannable list of `DecisionView` items (symbol,
  action, status, confidence, updated_at). The only part of this screen with a
  real, complete data model today.
- **Decision detail** — expands one decision, showing the full
  `DecisionContract` (including `evidence_reference`/`risk_reference` as raw
  pointer values until Sections below resolve them into real content).
- **Evidence section** — future; populated once an Evidence reader/adapter is
  built (Section 3).
- **Risk section** — future; blocked on the missing `RiskEvaluation` contract
  itself, not just a missing reader.
- **Governance section** — future; doubly blocked — needs a Governance reader
  *and* a real `approval_events` writer, neither of which exists.

## 5. Component Mapping

Per `AARA_UI_UX_DESIGN_SYSTEM.md`'s verified component table:

| Screen element | Component | Status |
|---|---|---|
| Decision list | `sentinel/frontend/components/decision_card.py` | Real, verified |
| Decision detail | `decision_card.py` (expanded) | Real, verified |
| Evidence section | `evidence_card.py` | Real, verified — but no data to feed it yet |
| Risk section | `risk_governor_badge.py` | Real, verified, but this is a **badge**, not a full panel — a dedicated "risk section" layout doesn't exist as a component and would need new design once the `RiskEvaluation` contract exists |
| Governance section | `governance_badge.py`, `approval_controls.py`, `audit_fingerprint.py`, `chain_timeline.py` | All real, verified — `approval_controls.py` specifically relevant here though not named in earlier UI-spec drafts |

## 6. Data Flow

```
Sentinel
   (sentinel_engine.services.DecisionService.create_decision)
        |
        v
Projection
   (ProjectionRepository -> DecisionProjection)
        |
        v
Trading Intelligence Adapter
   (SentinelProjectionDecisionSource -> DecisionContract)
        |
        v
Query Service
   (DecisionQueryService -> DecisionView)
        |
        v
UI
   (Decision Center — not yet built)
```

Every arrow above except the last is real, tested code (`applications/trading_intelligence/adapters/sentinel_projection_decision_source.py`,
`services/decision_query_service.py`). None of it is connected to a real
`ProjectionRepository` backend.

## 7. Empty / Mock States

- **No decisions exist:** the decision list shows an empty state. Note a real
  gap surfaced while writing this: `DecisionQueryService` today only exposes
  `get_decision_view(decision_id)` — a single lookup. There is no "list all
  decisions" method anywhere (`ProjectionRepository` itself only has
  `get`/`save`, no query-all). A decision *list* screen cannot be built against
  today's contracts without adding one — flagged here, not silently assumed to
  already exist.
- **No evidence exists:** the evidence section shows an empty state; the
  decision remains fully viewable without it — evidence is supplementary, not
  blocking, per Design Principle "evidence over emotion" not meaning "no
  evidence, no decision shown."
- **No risk contract exists:** this is not an empty-state case — there's no
  data model to represent "empty" risk data against. Phase 1 (Section 8) would
  need a placeholder ("Risk Intelligence — coming soon") rather than a true
  empty state, which implies a working-but-unpopulated data path that doesn't
  exist here.

## 8. Implementation Phases

**Phase 1: Mock UI.** Build the Decision Center screen shell using hardcoded
`DecisionView` objects, no real service wiring. Validates layout and component
choices (Sections 4-5) without any data-integration risk. No dependency on
ADR-004.

**Phase 2: Connect `DecisionQueryService`.** Wire the mock UI to the real
`DecisionQueryService` + `SentinelProjectionDecisionSource` chain. Two
preconditions, stated plainly: (a) a real `ProjectionRepository` backend must
exist, which is ADR-004's deferred decision — or, for a non-production demo
only, an in-memory backend could be used the same way the adapter's own tests
already do; (b) the "list all decisions" gap (Section 7) must be resolved
first, since the decision list screen specifically depends on it.

**Phase 3: Add evidence/risk/governance.** The most blocked of the three
phases — requires the Evidence cardinality question resolved, the
`RiskEvaluation` contract designed and built (it doesn't exist), and either a
real `approval_events` writer or an explicit decision to leave the governance
section permanently empty until one exists.

**No UI was implemented by this document.**

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `sentinel_engine/`, or any
protected path was created or modified.
