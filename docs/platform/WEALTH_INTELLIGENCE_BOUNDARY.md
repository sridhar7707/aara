# Wealth Intelligence Boundary

**Status:** Draft — target-state description, not an implementation plan.
**Scope:** Documents boundaries only. No code moves, import changes, or
refactors accompany this document (per `ADR-024`, which authorizes only
directional decisions, and consistent with `docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md`'s
own scope discipline).

**Authority:** `ADR-015` (module classification), `ADR-022` (product-facing
UI ownership), `ADR-024` (directional disposition of the four `ADR-015`-classified
modules — this document is the boundary artifact `ADR-024` §2.5 requires
before or alongside implementation of §2.1/§2.2/§2.4). Structurally mirrors
`docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md` (Product #1's boundary
document), per `ADR-015` §12's citation of it as structural precedent.

## Purpose

Define what "Aara Wealth Intelligence" (Product #2, per
`CODEBASE_MIGRATION_MATRIX.md` and `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`)
owns versus what belongs to the Sentinel Intelligence Engine
(`sentinel_engine/`), recording `ADR-024`'s directional dispositions in the
same structured, durable format Trading Intelligence already has. This
document authorizes no implementation — it records direction only, exactly
as `ADR-024` itself does.

## 1. Sentinel Engine Responsibilities

**`sentinel_engine` is the intelligence foundation, not the Wealth product
application.** Verified against current code:

| Capability | Module | What exists |
|---|---|---|
| Decision model | `domain/decision.py` | `Decision` — frozen dataclass, shared across both products |
| Event model | `events/event.py`, `event_types.py` | `Event`, `EventType` — shared across both products |
| Evidence model | `evidence/evidence.py` | `Evidence` — shared |
| Governance model | `governance/policy.py`, `approval.py` | `Policy`, `Approval` — shared |
| Ledger abstraction | `ledger/ledger.py` | `LedgerStore(ABC)` — abstract, no backend implemented (`ADR-004` deferred) |
| Projections | `projections/decision_projection.py` | `DecisionProjection` — shared |
| Repositories | `repositories/` | `LedgerRepository`, `ProjectionRepository(ABC)` — shared |
| Shared decision query | `queries/decision_query.py` | `DecisionQuery` — confirmed imported by **both** product bootstraps today (`applications/trading_intelligence/bootstrap.py` and `applications/wealth_intelligence/bootstrap.py`); genuinely Core, not disposed of by `ADR-024` (out of its scope) |
| Decision-activity aggregation query | `queries/morning_brief_query.py` | `MorningBriefQuery`/`MorningBrief` — per `ADR-024` §2.2, **directionally Core** (engine-level, product-neutral behavior), but its current name and shape remain Wealth-flavored; **no rename or relocation is authorized yet** (`ADR-024` §7.2) |
| Decision Center read query | `queries/decision_center_query.py` | `DecisionCenterQuery`/`DecisionCenterView` — per `ADR-024` §2.3, remains in the engine, **not promoted to a shared canonical query**; duplicated in spirit by Trading Intelligence's own independent Decision Center implementation; may only converge through a future ADR |

**Physically resident in `sentinel_engine/` today, but directionally
product code per `ADR-024` (not yet relocated — no move authorized by this
document or by `ADR-024` itself):**

| Module | Current path | `ADR-024` direction |
|---|---|---|
| `InvestorWorkspaceFacade` | `sentinel_engine/application/investor_workspace.py` | Directionally Wealth product code (`ADR-024` §2.1) |
| `InvestorPresenter` | `sentinel_engine/presentation/investor_presenter.py` | Directionally Wealth product code (`ADR-024` §2.4, relocation authorized in direction only) |

Both packages (`sentinel_engine/application/`, `sentinel_engine/presentation/`)
contain exactly one substantive module each today — if/when a future
implementation change relocates these two, both packages become empty
except for their (currently empty) `__init__.py`; that is an implementation
detail for a future change, not decided here.

## 2. Wealth Intelligence Product Responsibilities

**Current implementation:** `applications/wealth_intelligence/` —
`bootstrap.py`, `main.py`, `ui/investor_workspace.py`. Deployed to its own
Hugging Face Space (`ksri77/aara-wealth-intelligence`, per `ADR-023`), 18
tests passing. Runs with no seed data — its `bootstrap.py` constructs
fresh, empty `_InMemoryLedgerStore`/`_InMemoryProjectionRepository`
instances with no equivalent of Trading Intelligence's `_seed_decisions()`
call, so the deployed Space currently shows an empty workspace on every
load (confirmed during deployment verification; not a defect, a
consequence of `ADR-004`'s deferred backend).

Responsibilities, mapped to what currently implements them:

| Responsibility | Current owner |
|---|---|
| Investor workspace UI (Gradio) | `applications/wealth_intelligence/ui/investor_workspace.py` |
| Application composition | `applications/wealth_intelligence/bootstrap.py` (the one place that constructs `sentinel_engine` repositories, services, and the read-side object graph for this product) |
| Runtime entry point | `applications/wealth_intelligence/main.py` |
| Investor-facing view-model mapping | `InvestorPresenter` — directionally this product's own responsibility (`ADR-024` §2.4), physically still in `sentinel_engine/presentation/` today |
| Investor-facing read-access facade | `InvestorWorkspaceFacade` — directionally this product's own responsibility (`ADR-024` §2.1), physically still in `sentinel_engine/application/` today |

**`ADR-024` disposition summary for the four `ADR-015`-classified modules**
(directional only — no code moved by this document):

| Module | `ADR-015` classification | `ADR-024` direction |
|---|---|---|
| `investor_presenter.py` | B — Product-specific | Wealth product code; relocation authorized in direction only |
| `investor_workspace.py` | C — Transitional | Wealth product code; not genericized |
| `morning_brief_query.py` | C — Transitional, leaning toward future Core | Generic Core; stays in `sentinel_engine/`; no rename/move authorized yet |
| `decision_center_query.py` | C/D — Transitional, leaning toward future Core | Duplication stands; not promoted to shared/canonical; may only converge via a future ADR |

## 3. Shared Contracts

- **`Decision`, `Event`/`EventType`, `Evidence`, `Approval`, `DecisionState`, `ApprovalStatus`**
  (`sentinel_engine/domain/`, `events/`, `evidence/`, `governance/`) — the
  same domain contracts Trading Intelligence's own boundary document names,
  genuinely shared, not product-specific.
- **`DecisionQuery`** (`sentinel_engine/queries/decision_query.py`) — the
  one query confirmed shared between both products' bootstraps today.
- **`MorningBriefQuery`/`MorningBrief`** — directionally shared per
  `ADR-024` §2.2, but Trading Intelligence does not consume it today; the
  "shared" status is a disposition, not yet an integration fact. Its actual
  computed fields (`total_decisions`, `decisions_by_status`,
  `pending_governance_count`, `pending_approval_count`, `recent_decisions`)
  are decision-lifecycle-status aggregates — this is a narrower claim than
  "matches Trading Intelligence's own 'Morning Brief' screen concept,"
  which per `AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` is primarily
  portfolio/market-context content; only a partial, currently-unwired
  overlap exists ("`DecisionProjection` summaries for recent decisions").
- **`DecisionCenterQuery`/`DecisionCenterView`** — explicitly **not**
  shared per `ADR-024` §2.3. Trading Intelligence's own Decision Center
  read path (`applications/trading_intelligence/adapters/{sentinel_evidence_source,sentinel_governance_source,sentinel_projection_decision_source}.py`)
  is independent and unaffected.

**No integration exists** between `sentinel_engine`'s domain vocabulary and
any external data source for Wealth Intelligence — unlike Trading
Intelligence, Wealth Intelligence has no `bot/`-side analog at all; it
consumes `sentinel_engine` directly and exclusively, with no third data
source to reconcile.

## 4. Data Ownership

**Sentinel Engine owns:**
- Decision lifecycle contracts (`Decision`, `Event`)
- Evidence (`Evidence`)
- Governance (`Policy`, `Approval`)
- Projections (`DecisionProjection`)

**Wealth Intelligence owns:** no distinct data store of its own today.
Unlike Trading Intelligence (which owns trading databases, model
artifacts, and execution records under `bot/`/`database/`), Wealth
Intelligence has no equivalent operational data anywhere in this
repository — its `bootstrap.py` constructs its own private, empty,
in-memory `LedgerStore`/`ProjectionRepository` pair, structurally
identical in shape to Trading Intelligence's own placeholder repositories
but a **separate instance**, not shared runtime state between the two
products' deployed Spaces.

**Explicitly unknown — not decided by this document:**
- What implements `sentinel_engine/ledger/`'s `LedgerStore` backend for
  either product. None exists today; only the abstract interface
  (`ADR-004`, still deferred).
- Whether Wealth Intelligence will ever have its own operational data
  source analogous to Trading Intelligence's `bot/`-side data, or whether
  it remains purely a read surface over `sentinel_engine`.
- Whether `investor_presenter.py`/`investor_workspace.py`'s eventual
  relocation changes anything about data ownership (it should not — they
  are read/presentation code, not data stores — but this document does not
  formally rule on it).

## 5. Migration Principles

- Wealth Intelligence depends on Sentinel Engine. Sentinel Engine never
  depends on Wealth Intelligence — the dependency direction is one-way,
  consistent with `ADR-015` §6 rule 5 and `ADR-001`'s package-structure
  boundary. Verified today: `applications/wealth_intelligence/bootstrap.py`
  imports five `sentinel_engine` modules; nothing in `sentinel_engine`
  imports `applications/wealth_intelligence`.
- Two of the four `ADR-015`-classified modules currently violate the
  "engine owns no product-specific presentation code" principle
  (`ADR-007`'s stated boundary, `ADR-022`'s accepted UI-ownership
  decision) by physically residing in `sentinel_engine/`. `ADR-024`
  records the direction to correct this; **this document does not correct
  it** — no file is moved, renamed, or refactored here, consistent with
  `ADR-024`'s own non-authorization.
- Adapters/facades remain the only mechanism permitted to cross the
  boundary once relocation occurs — the same principle
  `TRADING_INTELLIGENCE_BOUNDARY.md` §7 already states for Product #1.
- No runtime migration occurs from this document. This is a boundary
  description, not an execution plan.

## 6. Unresolved Decisions

- Exact destination module path for `investor_presenter.py` and
  `investor_workspace.py` if/when relocated (`ADR-024` §7.1, §7.5).
- New name and exact module location for the generalized
  `morning_brief_query.py` (`ADR-024` §7.2) — no rename is currently
  authorized or required.
- Whether `decision_center_query.py` and Trading Intelligence's
  independent Decision Center read path ever converge into one shared
  query — explicitly gated on a future ADR (`ADR-024` §2.3), not decided
  here.
- Any timeline for implementing `ADR-024` §2.1, §2.2, or §2.4's directions
  (`ADR-024` §7.6 — none set).
- What implements `LedgerStore`/`ProjectionRepository` backends for either
  product (`ADR-004`, unresolved, gates real data for both products
  identically).
- Whether Wealth Intelligence will ever seed illustrative demo data
  (mirroring Trading Intelligence's `_seed_decisions()`) or remain
  intentionally empty until a real backend exists — not addressed by any
  ADR to date.

---

## Constraints Confirmed

No file under `sentinel_engine/`, `applications/`, `dashboard/`, `bot/`, or
any other path was created, moved, or modified to produce this document.
No ADR was modified. This document only reads and cites existing code and
`ADR-015`/`ADR-022`/`ADR-024`.
