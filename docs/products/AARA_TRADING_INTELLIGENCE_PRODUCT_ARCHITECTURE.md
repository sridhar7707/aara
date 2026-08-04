# AARA Trading Intelligence Product Architecture

**Status:** Product definition — Phase 3 (Product Development Planning), item 4.
Documentation only. No `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`,
`database/`, `ledger/`, or `sentinel_engine/` file was touched. No code, no
adapters, no migrations, no extraction. This document defines the product; it
does not implement it.

**Shared foundations (not recreated here):** `AARA_UI_UX_DESIGN_SYSTEM.md`,
`AARA_PLATFORM_USER_EXPERIENCE.md`, `AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md`.
Where this document needs a platform-level concept (shell, switcher,
entitlements, design principles), it references those documents rather than
restating or re-deciding them.

**Trading Intelligence architecture inputs:** `TRADING_INTELLIGENCE_BOUNDARY.md`,
`TRADING_INTELLIGENCE_EVENT_MODEL.md`,
`TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md`,
`TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md`, ADR-002, ADR-003, ADR-004,
`AARA_ARCHITECTURE_AUTHORITY.md`.

---

## 1. Product Vision

**Purpose within AARA:** Product #1, per `AARA_ARCHITECTURE_AUTHORITY.md`'s
Product Model — medium-term investing intelligence: portfolio decisions, trade
evaluation, risk management, paper trading validation, eventual broker
integration.

**Relationship to Sentinel Engine:** consumes `sentinel_engine`'s Decision/Event/
Evidence/Governance contracts through adapters, one-way — Trading Intelligence
depends on Sentinel Engine; Sentinel Engine never depends on Trading Intelligence
(`TRADING_INTELLIGENCE_BOUNDARY.md` Migration Principles, unchanged here).

**Human-governed intelligence philosophy:** applies `AARA_UI_UX_DESIGN_SYSTEM.md`'s
four design principles (evidence over emotion, explainability first, governance
visible, human-controlled intelligence) specifically to trading: every decision
this product surfaces is explainable and evidence-backed, and no decision
executes without the governance path already documented in
`TRADING_INTELLIGENCE_EVENT_MODEL.md`.

## 2. Product Scope

- **Portfolio decision intelligence** — signal generation through to a recorded
  decision, per `TRADING_INTELLIGENCE_BOUNDARY.md`'s Trading Intelligence
  Responsibilities (signal generation, strategy evaluation, portfolio decisions).
- **Evidence-backed decisions** — every decision traces to evidence (today:
  `candidate_event_id`, `market_context`, `model_outputs`, per
  `TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md` Section 1; construction of a
  formal `evidence_reference` remains an open question, Section 11).
- **Risk intelligence** — the portfolio-scoped risk model defined in
  `TRADING_INTELLIGENCE_EVENT_MODEL.md` Section 7 (`RISK_EVALUATED`, many
  decisions per cycle sharing one risk reference).
- **Governance** — constitution-rule enforcement (`bot/trust_ledger/constitution.py`'s
  six rules today) and the role model in Section 4.
- **Performance learning** — the outcome lifecycle defined in
  `TRADING_INTELLIGENCE_EVENT_MODEL.md` Section 9 (BUY-scoped
  `DECISION_OUTCOME_RECORDED`).

## 3. Explicit Non-Goals

- **Autonomous trading** — matches `AARA_ARCHITECTURE_AUTHORITY.md`'s Product
  Model: "not auto-execution-as-identity."
- **Market prediction** — matches the same source: "not market prediction as
  the product pitch."
- **High-frequency trading** — matches the same source: "not day trading."
- **Replacing human approval** — matches Design Principle "human-controlled
  intelligence" (Section 1) and `CLAUDE_AARA_MIGRATION.md`'s "recommendations
  are not automatic actions" framing, applied here specifically: no workflow in
  this document proposes removing a human decision point from the trading path.

## 4. User Roles

Unchanged from ADR-003 — no new role, no reinterpretation:

| Role | Trading Intelligence access |
|---|---|
| Trading Intelligence User | Full workspace access |
| Wealth Intelligence User | No access (different product) |
| AARA Super User / Platform Administrator | Full workspace access + cross-product/admin |

**No authentication implementation** — matches ADR-003 exactly: no schema, no
middleware, no user database. This table describes intended access, not a
built mechanism.

## 5. Trading Intelligence Workspace

Refines `AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md` Section 3's mapping. Two
changes from that document, stated explicitly rather than silently applied:
**"Investor Evolution" is dropped** (it had no capability grounding — see that
document's Open Decisions, still unresolved, not resolved by dropping it here);
**"Risk Intelligence" is separated out** as its own workspace section, since it
has real grounding (`dashboard/components/risk.py`, the risk model in Section 2)
that the earlier combined mapping didn't call out individually.

| Workspace section | Grounding |
|---|---|
| Morning Brief | `dashboard/components/brief.py`, `executive_summary.py` |
| Decision Center | `dashboard/components/decision.py`, `decision_bar.py`, `decision_quality.py`, `pending_approvals.py`, `thesis.py`, `counterfactual.py`, `loss_explanation.py` |
| Portfolio Intelligence | `dashboard/components/portfolio.py`, `capital.py`, `rebalance.py` |
| Risk Intelligence | `dashboard/components/risk.py`; conceptually the portfolio-scoped risk model (Section 2) |
| Performance & Learning | `dashboard/components/attribution.py`, `weekly_summary.py`, `trust_scorecard.py`, `signal_history.py`, `timeline.py`, `recommendation_history.py` |
| Settings | `dashboard/components/settings.py` |

Design principles and component patterns (cards, evidence panels, risk
indicators) are defined in `AARA_UI_UX_DESIGN_SYSTEM.md` and not restated here.

## 6. Current Capability Mapping

**Current** (real, protected under ADR-002, unmodified by this document):
- `dashboard/` — the workspace's de facto UI implementation today.
- `bot/` — signal generation, execution, capital, risk, orchestration.
- `scheduler/` — the second live trading-trigger path (per `BOT_DEPENDENCY_MAP.md`'s
  corrected finding), not legacy.

**Future** (target namespace, per `CODEBASE_MIGRATION_MATRIX.md`/ADR-001 — not
created, no file movement proposed by this document):
- `applications/trading_intelligence/`

No file movement is proposed here. This section names the target, consistent
with prior documents; it does not schedule or begin the move.

## 7. Sentinel Engine Relationship

Restates the ownership boundary already established in
`TRADING_INTELLIGENCE_BOUNDARY.md` Sections 1-2 — not redefined here:

**Trading Intelligence owns:**
- Trading domain intelligence (signal generation, strategy evaluation)
- Portfolio context (capital, positions, risk state)
- Trading workflows (orchestration, execution, scheduling)

**Sentinel Engine owns:**
- Decisions (`sentinel_engine.domain.decision.Decision`)
- Events (`sentinel_engine.events.event.Event`, `EventType`)
- Evidence (`sentinel_engine.evidence.evidence.Evidence`)
- Governance (`sentinel_engine.governance.policy.Policy`, `approval.Approval`)
- Projections (`sentinel_engine.projections.decision_projection.DecisionProjection`)

Zero code coupling exists between the two today, in either direction (unchanged
finding from `BOT_DEPENDENCY_MAP.md`).

## 8. Data and Ledger Boundaries

Per ADR-004 — **no ledger ownership option is selected by this document.**

- `TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md` compares three
  architectures (Trading-Intelligence-owned, Sentinel-canonical, dual-ledger);
  this document does not choose among them.
- ADR-004 formally defers that choice until Phase 1A validation completes and
  its decision criteria are met.
- This product's data today lives in `bot/trust_ledger/` (`data/trust_ledger.db`)
  and the top-level `ledger/` package, both protected under ADR-002 and
  untouched by this document.

## 9. User Workflows

Illustrative, not a UI spec — each ties to real grounding, not invented
functionality:

- **Review intelligence briefing** — Morning Brief (Section 5); a daily
  single-glance summary.
- **Evaluate a decision** — Decision Center; list-to-detail pattern per
  `AARA_UI_UX_DESIGN_SYSTEM.md` Section 4, decision card → evidence panel → risk
  indicator.
- **Review evidence** — the evidence panel pattern (`evidence_card.py`-grounded,
  per the design system document), backed by whatever evidence data exists for
  that decision (Section 2's "evidence-backed decisions").
- **Review risk** — Risk Intelligence section; the portfolio-scoped risk state
  (`RISK_EVALUATED`, Section 2), not a per-decision risk score (that scope
  mismatch is documented, not resolved, in `TRADING_INTELLIGENCE_EVENT_MODEL.md`
  Section 7).
- **Review historical outcomes** — Performance & Learning section; the BUY-scoped
  outcome lifecycle (`DECISION_OUTCOME_RECORDED`, Section 2).

## 10. Implementation Roadmap

**Completed:**
- Architecture — `sentinel_engine/` contracts (domain, events, evidence,
  governance, ledger interface, projections, repositories, services, adapters),
  82 tests passing.
- Contracts — `Decision`, `Event`/`EventType`, `Evidence`, `Policy`/`Approval`,
  `decision_adapter`.
- Documentation — this document plus every input listed at the top: boundary,
  event model, gap analysis, ledger options, four ADRs, platform UX, navigation,
  design system.

**Future (not started, not scheduled by this document):**
- Application layer — `applications/trading_intelligence/` (Section 6), no code
  exists.
- Adapters — candidate/risk/execution/outcome adapters beyond the existing
  `decision_adapter` (per `TRADING_INTELLIGENCE_EVENT_MODEL.md` Section 6), not
  designed in detail, not built.
- UI implementation — the workspace described in Section 5, not built; `dashboard/`
  remains the real implementation, protected and unchanged.
- Safe integration — gated by ADR-002 (any `bot/`/`scheduler/`/`dashboard/`
  change needs its own dedicated ADR) and ADR-004 (ledger ownership choice
  deferred until Phase 1A completes).

## 11. Open Decisions

Preserved, not resolved:

- **Dashboard decoupling** — `DASHBOARD_DEPENDENCY_REDUCTION_PLAN.md`'s three
  options (facade, Sentinel projections, defer), no option chosen.
- **Adapter design** — candidate/risk/execution/outcome adapters named but not
  designed (`TRADING_INTELLIGENCE_EVENT_MODEL.md` Section 6); exact
  `DECISION_EXECUTED` payload fields still require reading
  `alpaca_client.py`/`paper_executor.py` (`TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md`
  recommendation #5, not done).
- **Ledger ownership** — Option A/B/C, deferred per ADR-004 until Phase 1A
  validation completes and its criteria are met.
- **Missing capabilities** — "Investor Evolution" (Section 5) has no capability
  grounding anywhere in the codebase; remains unresolved, not invented.
