# AARA Trading Intelligence — MVP Scope Decision

**Status:** Scope decision. Documentation only. No code, UI, or database
change was created. No ADR was resolved; no ownership boundary was changed.
`applications/trading_intelligence/`, `sentinel_engine/`, `ledger/`, `bot/`,
`dashboard/`, `scheduler/`, `.github/workflows/`, `database/` untouched,
confirmed via `git status` before and after.

**Authority:** `AARA_TRADING_INTELLIGENCE_MVP_EXPERIENCE_DESIGN.md`,
`AARA_TRADING_INTELLIGENCE_DECISION_CENTER_CAPABILITY_MODEL.md`,
`AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`,
`AARA_PLATFORM_SHELL_ARCHITECTURE.md`,
`ADR-003-aara-identity-and-product-access.md`,
`ADR-004-sentinel-ledger-ownership-strategy.md`. This document does not
re-derive their findings — it converts them into a single, final scope
statement. Where `AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` predates
work this session already completed (its Section 6/10 still say "no code
exists" for `applications/trading_intelligence/`), this document uses the
current, verified state instead, not the stale claim.

---

## 1. MVP Goal

**The single user problem this MVP solves:** let a Trading Intelligence user
see, for each decision the system recorded, exactly what it decided —
symbol, action, confidence, and when — and open any one decision to see that
same information again in full. Nothing more.

Deliberately excluded from the goal statement itself, not just deferred as
scope: *why* a decision was made. Evidence, risk, and governance context
answer "why" (per
`AARA_TRADING_INTELLIGENCE_DECISION_CENTER_CAPABILITY_MODEL.md` Section 1),
and none of the three is real enough today to include in a truthful MVP goal
(Section 3).

## 2. Included Capability: Decision Center

What exists, verified directly against
`applications/trading_intelligence/ui/decision_center/`, real and tested
(77 tests: 49 in `applications/trading_intelligence/tests`, 28 in
`applications/trading_intelligence/ui/tests`):

- **Decision list** — `DecisionListArea`, populated by
  `DecisionCenterController.load_decisions()` /
  `.load_screen()` via `DecisionQueryService.list_decision_views()`. Empty
  state ("No decisions recorded yet.") included.
- **Decision detail** — `DecisionDetailArea`, populated by
  `.load_decision_detail()` / `.load_screen(selected_id=...)`, defaulting to
  the first listed decision when no selection is given.
- **Status** — `DecisionView.status`, displayed as-is on the list;
  `DecisionDetailArea.status_display` on detail (underscore-to-title-case
  formatting, e.g. `"DECISION_CREATED"` → `"Decision Created"`).
- **Confidence** — `DecisionView.confidence`, displayed as-is on the list;
  `DecisionDetailArea.confidence_display` on detail (formatted as a rounded
  percentage, e.g. `0.78` → `"78%"`).
- **Timestamp** — `DecisionView.updated_at`, displayed as-is on the list;
  `DecisionDetailArea.timestamp_display` on detail (formatted
  `"%Y-%m-%d %H:%M UTC"`).

This is the entire included capability. `symbol` and `action` are also
present on `DecisionView` (not separately called out by this task, but part
of the same, already-real field set).

## 3. Excluded Capabilities

Each explicitly deferred, with the specific reason it isn't part of this
MVP — not a vague "later," a cited, concrete blocker:

- **Portfolio** — no code exists anywhere under
  `applications/trading_intelligence/`; no `sentinel_engine` contract is even
  proposed for it (`AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`
  Section 7 confirms Trading Intelligence, not Sentinel, owns portfolio
  context).
- **Risk Intelligence** — no `sentinel_engine` risk contract exists at all;
  the largest single gap found across every capability analyzed this
  session (`AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md`
  Section 1).
- **Evidence Intelligence UI** — `Evidence` contract exists, but no
  Trading-Intelligence-side reader exists, and the cardinality question
  (single `evidence_reference` vs. the full list
  `EvidenceService.get_evidence_for_decision()` returns) is unresolved
  (`AARA_TRADING_INTELLIGENCE_EVIDENCE_DESIGN.md` Section 4). Building
  against it now would mean guessing.
- **Governance Intelligence UI** — `Approval`'s shape (one record per
  decision) doesn't match the real audit data
  (`constitution_enforcement_events`, six rows per decision); using it as-is
  would misrepresent the real data
  (`AARA_TRADING_INTELLIGENCE_GOVERNANCE_INTELLIGENCE_DESIGN.md` Section 3).
- **Authentication implementation** — `AuthenticationProvider` is an
  abstract interface with zero concrete implementations; per `ADR-003`,
  implementation "begins only after product boundaries stabilize," which
  this ADR explicitly states has not yet happened for identity/access
  generally.
- **Real ledger connection** — `ProjectionRepository` has zero concrete
  implementations anywhere; `ADR-004` explicitly defers the ledger-ownership
  choice (Option A/B/C) until Phase 1A's 30-day live-validation window
  completes and is reviewed. This document does not revisit or shorten that
  deferral.

## 4. Data Strategy

**Demo mode: allowed.** Two mechanisms already exist, both delivered by
already-completed work, neither invented here: `mock_data.py`
(`applications/trading_intelligence/ui/decision_center/mock_data.py`,
structurally prevented from being a production dependency) and
`InMemoryProjectionRepository`
(`applications/trading_intelligence/tests/fakes.py`). Either produces a
fully working `DecisionCenterScreen` today.

**Production mode: blocked by `ADR-004`.** No real `ProjectionRepository`
backend exists. `ADR-004`'s criterion 1 (Phase 1A's window must complete and
be reviewed) and criterion 3 (a tested dry run against real `trust_ledger`
data, which has never happened) both remain unmet. This document does not
resolve `ADR-004` and does not propose a timeline for when production mode
becomes available — that is `ADR-004`'s decision to make, not this one's.

## 5. MVP User Journey

**Only what actually exists today, verified directly — not the aspirational
Login → Workspace → Decision Center flow described in
`AARA_TRADING_INTELLIGENCE_MVP_EXPERIENCE_DESIGN.md` Section 1, which itself
already states most of that flow doesn't exist as working code.**

The real, working journey today is a **data/service flow, not a browser
flow** — there is no rendering framework wired to
`DecisionCenterScreen`/`DecisionListArea`/`DecisionDetailArea` at all; they
are plain, framework-independent dataclasses
(`AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md` Section 4's own
description, still accurate). What genuinely works, provable by running the
test suite:

```
Construct a data source
  (mock_data.build_mock_screen(), or
   SentinelProjectionDecisionSource(InMemoryProjectionRepository())
     -> DecisionQueryService -> DecisionCenterController)
        |
        v
Call .load_screen(decision_ids, selected_id=...)
        |
        v
Receive a DecisionCenterScreen
  (DecisionListArea + DecisionDetailArea, fully populated)
```

No login step, no workspace navigation, no rendered page exists in this
flow. A truthful MVP user journey today ends at "a screen model exists and
is correct," not at "a user sees a screen" — Section 7 names closing that
gap as future work, not something this document claims is already done.

## 6. Implementation Readiness Matrix

| Capability | Current State | Can Build Now | Blocked By |
|---|---|---|---|
| Decision list | Real, tested, wired end-to-end | Already built | — |
| Decision detail | Real, tested, wired end-to-end | Already built | — |
| Portfolio | No code anywhere | No | No `sentinel_engine` contract proposed; ownership not decided |
| Risk Intelligence | No `sentinel_engine` contract | No | Missing contract (new `sentinel_engine/` code needs its own ADR, per `ADR-001`); which of four non-unified risk models is authoritative is undecided |
| Evidence Intelligence UI | Contract exists, no reader | No | Cardinality decision unresolved; no reader/adapter exists |
| Governance Intelligence UI | Contract exists, wrong shape | No | Needs a new contract matching `constitution_enforcement_events`; needs its own ADR |
| Authentication | Interface only, zero implementations | No | `ADR-003`: implementation gated on product boundaries stabilizing |
| Real ledger connection | No backend implementation | No | `ADR-004`: deferred until Phase 1A validation window completes |
| Rendering/UI framework | No technology chosen | No | Open decision, `AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 6 — not resolved by this document |

## 7. First Implementation Milestone

**The smallest next coding milestone that requires no new contract, no new
ADR, and no ownership-boundary change:** add explicit placeholder areas to
`DecisionCenterScreen` for evidence, risk, and governance — each honestly
representing "not yet available," not real data. This is narrower than any
excluded capability in Section 3: it renders the *absence* of evidence/
risk/governance content, never evidence/risk/governance content itself, so
it does not implement any of the three excluded UI capabilities.

This would close the one concrete gap
`AARA_TRADING_INTELLIGENCE_MVP_EXPERIENCE_DESIGN.md` Section 4 already
named as unmet ("see future intelligence areas" — not achievable today, not
even as a placeholder), using the same framework-independent-dataclass, TDD
pattern this codebase already follows for `DecisionListArea`/
`DecisionDetailArea`. It is a definition of the next milestone, not an
implementation of it — no file under any protected or in-scope path was
changed to produce this section.

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `sentinel_engine/`,
`ledger/`, `bot/`, `dashboard/`, or any other protected path was created or
modified. No UI component or code was created. No ADR was resolved; `ADR-003`
and `ADR-004` remain exactly as deferred as before this document. No
ownership boundary was changed. This document only reads and cites existing
code and prior documentation.
