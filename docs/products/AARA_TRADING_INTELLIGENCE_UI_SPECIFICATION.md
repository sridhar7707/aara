# AARA Trading Intelligence UI Specification

**Status:** Screen-level specification — Phase 3 (Product Development Planning),
item 5. Documentation only. No `bot/`, `dashboard/`, `scheduler/`,
`.github/workflows/`, `database/`, `ledger/`, or `sentinel_engine/` file was
touched. Defines the future UI; does not implement it.

**Authority:** `AARA_UI_UX_DESIGN_SYSTEM.md`,
`AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`,
`AARA_PLATFORM_USER_EXPERIENCE.md`, `AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md`,
`TRADING_INTELLIGENCE_BOUNDARY.md`, `TRADING_INTELLIGENCE_EVENT_MODEL.md`,
ADR-002. This document does not redecide anything those establish — it applies
them at screen granularity.

---

## 1. Workspace Overview

Six screens, unchanged from `AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`
Section 5: Morning Brief, Decision Center, Portfolio Intelligence, Risk
Intelligence, Performance & Learning, Settings.

## 2. Screen Responsibilities

### Morning Brief

- **Purpose:** single-glance daily summary before/at market open.
- **User questions answered:** What happened since yesterday? What does today's
  candidate set look like? What should I know before the market opens?
- **Required information:** portfolio snapshot, market mood/regime, today's
  candidate screening summary, overnight news relevant to holdings.
- **Future Sentinel Engine inputs:** `DecisionProjection` summaries for recent
  decisions; `Evidence` summaries for today's candidates — neither wired today.
- **Current data source (real, verified):** `dashboard/components/brief.py`,
  `executive_summary.py`, `market_mood.py`, `news.py`.

### Decision Center

- **Purpose:** review and evaluate individual trading decisions.
- **User questions answered:** What did the system decide, and why? What
  evidence supports it? Is anything pending approval?
- **Required information:** decision list, per-decision evidence, risk context
  at decision time, approval/constitution-check status.
- **Future Sentinel Engine inputs:** `Decision`, `Event` (`DECISION_CREATED`/
  `DECISION_EXECUTED`), `Evidence`, `Approval` — `decision_adapter` exists for
  `Decision`; nothing else in this list is wired.
- **Current data source (real, verified):** `dashboard/components/decision.py`,
  `decision_bar.py`, `decision_quality.py`, `pending_approvals.py`, `thesis.py`,
  `counterfactual.py`, `loss_explanation.py`.

### Portfolio Intelligence

- **Purpose:** understand current holdings, allocation, and capital deployment.
- **User questions answered:** What do I own? How is capital allocated? What's
  my current exposure?
- **Required information:** positions, capital pool state, allocation breakdown.
- **Future Sentinel Engine inputs:** **none proposed.** Portfolio state is a
  Trading-Intelligence-owned concept (`TRADING_INTELLIGENCE_BOUNDARY.md` Section 7
  Data Ownership) — no Sentinel-side portfolio contract exists or is proposed
  here.
- **Current data source (real, verified):** `dashboard/components/portfolio.py`,
  `capital.py`, `rebalance.py`; backing data in `bot/capital/pool.py`'s
  `capital_pools`/`capital_ledger`.

### Risk Intelligence

- **Purpose:** understand the current risk-governor state and its rationale.
- **User questions answered:** Is the system in a defensive posture, and why?
  What position sizing does that imply?
- **Required information:** current state (`NORMAL`/`WARNING`/`DEFENSIVE`),
  trigger reason, recommended vs. actual position sizing.
- **Future Sentinel Engine inputs:** `RISK_EVALUATED` — portfolio-scoped, not
  per-decision, per `TRADING_INTELLIGENCE_EVENT_MODEL.md` Section 7. A UI
  surfacing this must not imply a per-decision risk score that doesn't exist.
- **Current data source (real, verified):** `dashboard/components/risk.py`;
  backing data in `bot/trust_ledger/risk.py`'s `risk_evaluation_events`.

### Performance & Learning

- **Purpose:** understand historical performance and what the system has
  learned.
- **User questions answered:** How has the strategy performed? What worked,
  what didn't? What's the attribution?
- **Required information:** outcome history, attribution breakdown, model
  confidence calibration.
- **Future Sentinel Engine inputs:** `DECISION_OUTCOME_RECORDED` — BUY-scoped
  only, per `TRADING_INTELLIGENCE_EVENT_MODEL.md` Section 9; a UI must not imply
  every decision gets an outcome.
- **Current data source (real, verified):** `dashboard/components/attribution.py`,
  `weekly_summary.py`, `trust_scorecard.py`, `signal_history.py`, `timeline.py`,
  `recommendation_history.py`; backing data in `bot/trust_ledger/outcomes.py`'s
  `decision_outcome_events`.

### Settings

- **Purpose:** configure user/system preferences.
- **User questions answered:** How do I control trading parameters,
  notifications, preferences?
- **Required information:** user settings, thresholds, notification
  preferences.
- **Future Sentinel Engine inputs:** **none proposed.** This is a
  Trading-Intelligence/product-layer concern, not a Sentinel governance concern —
  flagged as explicitly out of Sentinel's scope, not silently assumed either way.
- **Current data source (real, verified):** `dashboard/components/settings.py`;
  backing data in `database/user_settings.py`.

## 3. Component Mapping

Verified against real files (`sentinel/frontend/components/`,
`dashboard/design_system.py`) — nothing below is invented unless explicitly
marked **(future, undesigned)**:

| UI concept | Existing component | Verified |
|---|---|---|
| Decision cards | `sentinel/frontend/components/decision_card.py` | Yes |
| Evidence cards | `sentinel/frontend/components/evidence_card.py` | Yes |
| Risk indicators | `sentinel/frontend/components/risk_governor_badge.py` | Yes |
| Governance indicators | `sentinel/frontend/components/governance_badge.py` | Yes |
| Health scores | `sentinel/frontend/components/health_score.py` | Yes |
| Chain/audit timeline | `sentinel/frontend/components/chain_timeline.py`, `audit_fingerprint.py` | Yes — not requested by name but relevant to Decision Center's evidence trail |
| Approval controls | `sentinel/frontend/components/approval_controls.py` | Yes — not requested by name |
| Model agreement indicator | `sentinel/frontend/components/model_agreement.py` | Yes — not requested by name |
| Charts | `dashboard/design_system.py`'s `PLOTLY_LAYOUT` theme | Yes, but this is the *current* Trading Intelligence charting reference, not a Sentinel-side component |
| Morning Brief summary card | **(future, undesigned)** | No dedicated component exists in either `dashboard/` or `sentinel/frontend/` for a Sentinel-sourced brief — today's `brief.py` is not a reusable component, it's page content |
| Portfolio Intelligence components | **(future, undesigned)** | No Sentinel-side component proposed, consistent with Section 2's "no Sentinel inputs" finding for this screen |

## 4. Data Readiness

| Screen | Classification | Why |
|---|---|---|
| Morning Brief | Available today (current `dashboard/` implementation) / Mock-future for a Sentinel-sourced version | No candidate/evidence adapter exists beyond `decision_adapter` |
| Decision Center | Available today (current) / Available later for `Decision`+`Event` (adapter exists for `Decision`) / Mock-future for `Approval` display (no writer exists anywhere — `approval_events` is schema-only, per `TRADING_INTELLIGENCE_SENTINEL_LEDGER_INTEGRATION_OPTIONS.md`'s finding) |
| Portfolio Intelligence | Available today (current) / **Mock-future** for any Sentinel-mediated version — no contract even proposed |
| Risk Intelligence | Available today (current) / Available later for `RISK_EVALUATED` (event type exists, not wired) |
| Performance & Learning | Available today (current) / Available later for `DECISION_OUTCOME_RECORDED` (event type exists, outcome adapter named but not designed) |
| Settings | Available today (current) only — no Sentinel relationship proposed, not applicable to the later/mock categories |

## 5. Current Dashboard Relationship

**Current:** `dashboard/` — real, protected under ADR-002, unmodified by this
document. Every "current data source" cited in Section 2 is a real file in this
tree today.

**Future:** Trading Intelligence application surface (`applications/trading_intelligence/`,
per `AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` Section 6) — not created,
no timeline proposed.

**No `dashboard/` file was moved or modified to produce this document** —
confirmed via `git status` before and after.

## 6. Sentinel Engine Integration Points

Future, read-only consumption only — no implementation:

- **Decisions** — reading `DecisionProjection` (the read-model layer, via
  `ProjectionRepository.get()`), not raw ledger rows. Matches the "derived views
  only" principle already established for governance-facing UI.
- **Events** — reading `Event`/`EventType` history for a decision's audit trail
  (Decision Center's evidence/chain-timeline view), not writing new events from
  the UI.
- **Evidence** — reading `Evidence` records once a producer exists (none does
  today — see Section 4).
- **Projections** — `DecisionProjection` is the only projection that exists;
  no Portfolio- or Risk-specific projection has been proposed (Sections 2/3).

All four are described as future read paths. None is implemented, wired, or
scheduled by this document.

## 7. UX Principles

Applies `AARA_UI_UX_DESIGN_SYSTEM.md`'s four principles (evidence over emotion,
explainability first, governance visible, human-controlled intelligence)
directly — not restated in depth here. Concretely for this specification: every
screen in Section 2 either cites a current real data source or explicitly marks
itself future/mock, rather than presenting undecided functionality as if it
already existed — the specification-level expression of "evidence over emotion."

## 8. Open Decisions

Preserved from prior documents, not resolved here:

- **Dashboard decoupling** — `DASHBOARD_DEPENDENCY_REDUCTION_PLAN.md`'s three
  options, no option chosen.
- **Identity integration** — how/when this UI's screens actually enforce ADR-003's
  role visibility; no authentication mechanism exists.
- **Adapter timing** — when candidate/risk/execution/outcome adapters
  (`TRADING_INTELLIGENCE_EVENT_MODEL.md` Section 6) get designed and built, given
  ADR-004 defers related ledger work until Phase 1A completes.
- **Ledger ownership** — Option A/B/C, per ADR-004, still deferred.
