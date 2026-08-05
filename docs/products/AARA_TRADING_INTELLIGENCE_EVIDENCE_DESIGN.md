# AARA Trading Intelligence — Evidence Design

**Status:** Design proposal. Documentation only. No code was created or
modified. `applications/trading_intelligence/`, `sentinel_engine/`, `ledger/`,
`bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`, `database/`
untouched, confirmed via `git status` before and after.

**Authority:** `TRADING_INTELLIGENCE_EVENT_MODEL.md`, `TRADING_INTELLIGENCE_BOUNDARY.md`,
`AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md`. Where those documents
already settled a question relevant to evidence, this document cites the
finding rather than re-deriving it. Where they left a question open, Section 4
restates it precisely rather than silently resolving it.

---

## 1. Current Evidence State

### Existing contracts

- **`sentinel_engine.evidence.evidence.Evidence`** (`sentinel_engine/evidence/evidence.py`)
  — the only evidence contract that exists anywhere in this codebase. A frozen
  dataclass with five fields: `evidence_id: str`, `evidence_type: str`,
  `source: str`, `data: Dict[str, Any]`, `collected_at: datetime`.
  `evidence_type` and `source` are plain strings — no enum, no constrained
  vocabulary is enforced in code today.
- **`Decision.evidence_reference: str`** (`sentinel_engine/domain/decision.py`)
  and its read-model counterpart **`DecisionProjection.evidence_reference: str`**
  (`sentinel_engine/projections/decision_projection.py`) — a single string
  pointer field, not a collection.
- **`applications.trading_intelligence.contracts.decision_contract.DecisionContract.evidence_reference: str`**
  (`applications/trading_intelligence/contracts/decision_contract.py`) — passed
  through 1:1 from `DecisionProjection.evidence_reference` by
  `SentinelProjectionDecisionSource._to_contract()`. No transformation, no
  evidence-specific handling.
- **`applications.trading_intelligence.projections.decision_view.DecisionView`**
  — deliberately excludes `evidence_reference` (and `risk_reference`). Its own
  docstring states why: per `AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`,
  evidence is shown in a separate panel, not embedded in the decision card.
- **No evidence-specific contract exists in `applications/trading_intelligence/`.**
  There is no `EvidenceContract`, `EvidenceView`, or equivalent anywhere under
  `applications/trading_intelligence/contracts/` or `projections/` today.

### Existing services

- **`sentinel_engine.services.evidence_service.EvidenceService`**
  (`sentinel_engine/services/evidence_service.py`) — the only evidence-handling
  service that exists. In-memory only, no persistence, no repository behind
  it:
  - `associate_evidence(decision_id: str, evidence: Evidence) -> None` —
    appends to a private `Dict[str, List[Evidence]]`.
  - `get_evidence_for_decision(decision_id: str) -> List[Evidence]` — returns
    a **copy** of the list (`list(...)`), never the internal reference.
  - `Evidence` itself carries no `decision_id` field. The association between
    a decision and its evidence is external, held only in this service's own
    dictionary — not a property of `Evidence` or `Decision`.
- **No reader or adapter exists in `applications/trading_intelligence/`.**
  Nothing under `applications/trading_intelligence/adapters/` or `services/`
  calls `EvidenceService` today. `SentinelProjectionDecisionSource` only reads
  `DecisionProjection` (via `ProjectionRepository`); it has no path to
  `EvidenceService` at all.
- **No producer exists anywhere.** Nothing in `bot/`, `scheduler/`, or
  `applications/trading_intelligence/` constructs an `Evidence` object or
  calls `associate_evidence()`. `TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md`
  Section 2 states Trading Intelligence would eventually be the *producer* of
  the raw material behind evidence (candidate screening results, market
  context, model outputs) — that production path is not designed, let alone
  built.

### Current limitations

- **Decision Center has no evidence section today.** Verified directly:
  `applications/trading_intelligence/ui/decision_center/screen.py` defines
  only `DecisionListArea` and `DecisionDetailArea` — no `EvidenceArea` or
  equivalent exists. `AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md`
  Section 4 already named this as "future; populated once an Evidence
  reader/adapter is built" — still true, unchanged by this document.
- **Cardinality mismatch, not yet resolved.** `Decision.evidence_reference`
  is a single string; `EvidenceService.get_evidence_for_decision()` returns a
  list. These are two different shapes of "a decision's evidence" documented
  in different places, and nothing in this codebase has decided which one a
  future read contract should expose. Restated precisely in Section 4.
- **The Sentinel component catalog's assumed evidence shape does not match
  `Evidence`'s actual fields.** `docs/architecture/SENTINEL_COMPONENT_CATALOG.md`'s
  `EvidenceCard` component (data source verified directly in that file)
  expects: `evidence_id`, `type`, `provider`, `provider_version`,
  `data_as_of`, `recorded_at`, `confidence`, `confidence_interval`. The real
  `Evidence` dataclass has: `evidence_id`, `evidence_type`, `source`, `data`,
  `collected_at`. Only `evidence_id` matches by name. `provider`/
  `provider_version` have no counterpart (would presumably live inside the
  untyped `data` dict, unconfirmed). `data_as_of`/`recorded_at` are two
  timestamps where `Evidence` has one (`collected_at`). `confidence`/
  `confidence_interval` have no counterpart in `Evidence` at all — nothing
  indicates whether confidence-bearing evidence would store this in `data`
  or whether `Evidence` itself is missing fields the catalog already assumes
  exist. This is a real, currently-unreconciled gap between a UI component
  spec and the domain contract it would need to render — not a decision this
  document makes, only a discrepancy this document records precisely so it
  isn't silently assumed away later.
- **`sentinel/frontend/components/evidence_card.py`'s `render()` is a stub**
  (`raise NotImplementedError`) — verified directly. There is no working
  evidence rendering code anywhere in this codebase today, mock or real.
- **No authentication or entitlement enforcement exists.** The component
  catalog's `EvidenceCard` permissions model (Section 3 below) has no backing
  implementation — `applications.platform.identity.AuthenticationProvider`
  and `applications.platform.entitlements.EntitlementChecker` are abstract
  interfaces only (per ADR-003), with zero concrete implementations anywhere
  in this codebase.

## 2. Evidence Display Model

### Decision → evidence relationship

The real, verified relationship is **external and one-to-many**, not a field
on either side:

```
Decision (evidence_reference: str, singular pointer)
        |
        v
EvidenceService._evidence_by_decision: Dict[decision_id, List[Evidence]]
        |
        v
Evidence (no decision_id field at all)
```

`EvidenceService` is the only place this relationship is recorded, and it
associates a decision with a **list** of `Evidence` objects, not one. Whether
`Decision.evidence_reference` is meant to point at one particular `Evidence`
record (e.g., a summary or primary item) within that list, or is a
vestigial/placeholder field that predates the list-shaped association model,
is not resolved anywhere in this codebase. Section 4 restates this as an open
question rather than assuming an answer.

### Evidence categories

`Evidence.evidence_type` is an unconstrained `str` in code — no enum exists.
The only concrete category vocabulary that appears anywhere is
`SENTINEL_COMPONENT_CATALOG.md`'s `EvidenceCard` visual spec: `MODEL_OUTPUT`,
`FUNDAMENTAL`, `TECHNICAL`, `SENTIMENT`, `EXTERNAL` (used there as a "type
icon" selector). These five values are a UI-catalog convention, not a
type-checked contract — nothing prevents `evidence_type` from holding any
other string today, and no validation exists at the `Evidence` construction
site (there is no construction site — nothing builds one).

### Timestamps

`Evidence` has exactly one timestamp field: `collected_at: datetime`. The
component catalog's `EvidenceCard` spec wants two — `data_as_of` (when the
underlying data was true) and `recorded_at` (when the evidence record was
captured) — a real distinction for model-output evidence, where a model might
run on data from an earlier point in time. `Evidence.collected_at` does not
state which of the two it represents; both readings are plausible from the
field name alone, and this document does not pick one.

### Source attribution

`Evidence.source: str` is a single field. The component catalog wants
`provider` + `provider_version` separately (e.g., "XGBoost" / "v2.1"). Today,
a single `source` string would need to encode both (e.g., `"XGBoost v2.1"`)
or the version would need to live inside the untyped `data` dict — neither
approach is specified anywhere, and this document does not choose one.

## 3. UI Impact

### Decision Center evidence section

Per `AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md` Section 4/8, the
evidence section is scoped to that design's **Phase 3** — the most blocked of
its three phases, requiring the cardinality question resolved (Section 4
below) before a reader can even be shaped. This document does not move that
phase forward; it narrows what Phase 3 would need to resolve first.

If built, the natural shape (not a commitment — a description of what the
existing pieces already imply) would extend `DecisionDetailArea` with an
additional area, following the same pattern `screen.py` already uses for
`DecisionListArea`/`DecisionDetailArea`: framework-independent, no rendering
engine, populated by the controller from a query-service call — mirroring
exactly how `DecisionQueryService`/`SentinelProjectionDecisionSource` already
supply `DecisionView` data today (see prior Phase 5A work).

### Evidence timeline concept

Worth distinguishing precisely from an existing, differently-scoped
component: `docs/architecture/SENTINEL_COMPONENT_CATALOG.md`'s
`ChainOfCustodyTimeline` is **decision-lifecycle-scoped** — a fixed 5-step
journey sourced from `decision.timeline`, not from a decision's evidence
records. An "evidence timeline" in the sense this task means — a
chronological ordering of the (possibly multiple) `Evidence` records
associated with one decision, sorted by `collected_at` — is a different,
narrower concept that has no corresponding component or contract anywhere in
this codebase today. Nothing here proposes building one; this section only
notes that conflating the two would be a mistake, since `ChainOfCustodyTimeline`
already exists as a name and could be reached for by mistake.

### Audit visibility

The component catalog's `EvidenceCard` defines a three-tier visibility model:
Investor (provenance + summary only, payload hidden), Advisor (full payload),
Analyst (full payload + features + calibration). This is a real, documented
design intent, but it has **no enforcement path today** — it would depend on
`EntitlementChecker` (interface only, no implementation) to determine which
tier a given user falls into, and on a role concept that does not yet exist
in `applications.platform.identity.User`. Until both exist, any evidence
section Decision Center builds would either show everything or show nothing —
partial, role-filtered evidence visibility is not achievable with what exists
in this codebase today.

## 4. Unresolved Decisions

- **Single `evidence_reference` vs. multiple evidence records.** Restated
  precisely from `TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md` Section 2,
  still unresolved: `Decision.evidence_reference` is one string;
  `EvidenceService.get_evidence_for_decision()` returns a list. A future read
  contract must decide whether "a decision's evidence" means the single
  referenced item or the full associated list — these are two different
  contracts with overlapping names in different documents today, and nothing
  in code picks between them.
- **Ownership of evidence retrieval.** No subpackage in
  `applications/trading_intelligence/` was purpose-built for reading Sentinel
  data back out — `adapters/` was scoped for the opposite direction (bot-shaped
  data → Sentinel contracts), and `services/` currently only holds
  `DecisionQueryService`. Whether a future evidence reader lives in
  `services/`, a new `adapters/`-sibling package, or elsewhere is the same
  open question `TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md` Section 1
  already flagged for the Decision Read Contract, now also true for evidence.
  Not decided here.
- **Future Sentinel integration.** Two separate gaps, not one: (a) no
  `Evidence` producer exists anywhere — Trading Intelligence is proposed as
  the eventual producer of the raw material behind evidence, per
  `TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md` Section 2, but that
  production path is undesigned; (b) even once evidence exists, the
  `EvidenceCard` component's assumed field shape (Section 1) does not match
  `Evidence`'s actual fields, so a future adapter would need to either extend
  `Evidence`, encode extra fields into its untyped `data` dict, or the
  component's spec would need to change — this document does not choose
  among those options.

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `sentinel_engine/`,
`ledger/`, or any other protected path was created or modified. This document
only reads and cites existing code and prior documentation.
