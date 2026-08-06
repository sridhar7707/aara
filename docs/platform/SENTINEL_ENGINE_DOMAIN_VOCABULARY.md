# Sentinel Engine Domain Vocabulary

**Status:** Reference — captured during ADR-008 analysis, prior to `sentinel/`
archival.
**Authorizes:** Nothing. See §4.

## 1. Purpose and Relationship

This document exists to preserve vocabulary discovered in the `sentinel/`
scaffold before that package is archived per
[ADR-008](../decisions/ADR-008-sentinel-scaffold-disposition.md), so the
vocabulary remains discoverable in a committed location rather than only
inside a package about to be moved out of the active tree.

The vocabulary below sits at different points in the platform hierarchy
established by [ADR-007](../decisions/ADR-007-aara-platform-hierarchy.md):

```
AARA Systems
    |
    └── Sentinel Intelligence Engine
           |
           ├── AARA Trading Intelligence (Product #1)
           ├── AARA Wealth Intelligence (Product #2)
           └── (future products)
```

- **AARA Systems** — the parent platform/company brand. Owns nothing in this
  vocabulary directly; it is realized through the engine and products beneath
  it.
- **Sentinel Intelligence Engine** (`sentinel_engine/`, per
  [ADR-001](../decisions/ADR-001-sentinel-engine-structure.md)) — the
  reusable, product-agnostic intelligence layer. Vocabulary that describes
  concepts true regardless of which product is consuming the engine belongs
  here.
- **Products** (e.g. `applications/trading_intelligence/`) — customer-facing
  applications built on the engine. Vocabulary that only makes sense in the
  context of one product's domain (e.g. a portfolio's drawdown percentage)
  belongs here, not in the engine.

This document records vocabulary; it does not decide where implementation
code should live beyond what is already stated below, and it does not
implement anything itself.

## 2. Source

- `sentinel/backend/domain/enums.py` — the original code location of all five
  enums catalogued below. That file is scaffolding only (every consumer in
  `sentinel/` raises `NotImplementedError`); the enums themselves have design
  value independent of that scaffolding's fate.
- [ADR-008: Sentinel Scaffold Disposition](../decisions/ADR-008-sentinel-scaffold-disposition.md)
  — the decision record that identified this vocabulary as worth preserving
  ahead of archiving `sentinel/`, and the source of the classification below.

## 3. Vocabulary Classification

### `GovernanceAction`

| | |
|---|---|
| **Current source** | `sentinel/backend/domain/enums.py` — `APPROVE_DECISION`, `DEFER_DECISION`, `DECLINE_DECISION`, `ESCALATE_REVIEW` |
| **Proposed future home** | `sentinel_engine/` domain/governance layer — would type `sentinel_engine/governance/approval.py`'s `Approval.status`, which is an untyped `str` today |
| **Status** | Direct, ready adoption. No conflicting vocabulary exists elsewhere; fills a real, identified gap. |

### `RiskGovernorState`

| | |
|---|---|
| **Current source** | `sentinel/backend/domain/enums.py` — `NORMAL`, `WARNING`, `DEFENSIVE` (drawdown beyond `DEFENSIVE` is a Governance Integrity BREACH event, not a 4th state, per the original module's docstring) |
| **Proposed future home** | `sentinel_engine/` domain/governance layer, for the state enum itself |
| **Engine/product ownership split** | The *state* (`NORMAL`/`WARNING`/`DEFENSIVE`) is product-agnostic and belongs in the engine. The *triggering logic* — concrete drawdown-percentage threshold checks, as sketched in `sentinel/backend/services/risk_governor_service.py`'s `check_threshold(drawdown_pct)` — is portfolio/trading-specific and belongs in `applications/trading_intelligence/`, consistent with `TRADING_INTELLIGENCE_BOUNDARY.md`'s existing pattern of a Trading-Intelligence-owned risk adapter feeding engine-level state. |

### `DecisionState`

| | |
|---|---|
| **Current source** | `sentinel/backend/domain/enums.py` — `IDENTIFIED`, `EVALUATED`, `GOVERNED`, `APPROVED`, `DISPATCHED`, `EXECUTED`, `REVIEWED`, `CLOSED` (8-stage lifecycle) |
| **Relationship to `EventType`** | Adjacent, not equal, to `sentinel_engine/events/event_types.py`'s `EventType` (`CANDIDATE_EVALUATED`, `DECISION_CREATED`, `RISK_EVALUATED`, `DECISION_EXECUTED`, `DECISION_OUTCOME_RECORDED`). Both describe a decision's progress, at different granularity and with different vocabulary — `GOVERNED` and `REVIEWED` have no `EventType` counterpart. |
| **Explicitly unresolved** | No code destination is chosen. Adoption requires a prior reconciliation decision (extend `EventType`, keep both vocabularies at different granularities with an explicit mapping, or some other resolution) — not decided by this document or by ADR-008. |

### `SentinelRole`

| | |
|---|---|
| **Current source** | `sentinel/backend/domain/enums.py` — `INVESTOR`, `ADVISOR`, `RISK_OFFICER`, `COMPLIANCE_OFFICER`, `ADMINISTRATOR`. Self-marked in the original file as "Placeholder enum. Not enforced in Phase 2A (no RBAC, no auth)." |
| **Difference from ADR-003 roles** | [ADR-003](../decisions/ADR-003-aara-identity-and-product-access.md) defines a separate role model — `Trading Intelligence User`, `Wealth Intelligence User`, `AARA Super User / Platform Administrator` — answering "which product can this user access" (product entitlement). `SentinelRole` answers a different question: "in what governance capacity is this user acting on a decision" (e.g. approving, as a risk officer vs. an advisor). Neither vocabulary subsumes the other. |
| **Explicitly unresolved** | No code destination is chosen. Placing `SentinelRole` in `applications/platform/identity/` or anywhere else would create a second, unreconciled role taxonomy alongside ADR-003's until a reconciliation decision is made (e.g. additive layers — product entitlement plus governance capacity — or a merged model). Documentation only until then. |

### `OperationalMode`

| | |
|---|---|
| **Current source** | `sentinel/backend/domain/enums.py` — `RESEARCH`, `PAPER`, `SUPERVISED`, `GOVERNED_AUTOMATION` (the last marked "Future value; not implemented in Phase 2A" in the original file) |
| **Future governance vocabulary** | No equivalent exists in `sentinel_engine/` or `applications/platform/` today. Adjacent to, but not the same as, `bot/`'s paper-vs-live execution distinction — this enum describes a governance-supervision mode (how tightly decisions are supervised), not the trading execution backend. Carried forward as a placeholder for future engine governance work; nothing consumes it yet, and there is no existing conflicting vocabulary to reconcile. |

## 4. Explicit Statement

**This document does not authorize implementation, migration, or package
movement.** It is a reference record of vocabulary discovered during ADR-008
analysis. No enum, class, or value described above has been created, moved,
or wired into `sentinel_engine/`, `applications/`, or any other package by
this document. Any future adoption requires its own implementation work,
and — for `DecisionState` and `SentinelRole` — a prior reconciliation
decision, neither of which this document performs.

## 5. References

- [ADR-001: Sentinel Engine Package Structure](../decisions/ADR-001-sentinel-engine-structure.md)
- [ADR-003: AARA Identity and Product Access Model](../decisions/ADR-003-aara-identity-and-product-access.md)
- [ADR-007: AARA Platform Hierarchy](../decisions/ADR-007-aara-platform-hierarchy.md)
- [ADR-008: Sentinel Scaffold Disposition](../decisions/ADR-008-sentinel-scaffold-disposition.md)
