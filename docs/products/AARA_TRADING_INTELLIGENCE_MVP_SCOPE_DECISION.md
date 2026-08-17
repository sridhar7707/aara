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
(326 tests: 181 in `applications/trading_intelligence/tests`, 145 in
`applications/trading_intelligence/ui/tests`):

**Implemented — real code, real rendering, decision-specific:**

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
- **Evidence** — `EvidenceEntry` record cards (`evidence_type`/`source`/
  `attached_at`), read via `SentinelEvidenceSource`/
  `DecisionEvidenceQueryService`, including ADR-037's evidence metadata
  disclosure (`shap_drivers`/`is_degraded`/`val_loss`/`raw_score`/
  `headlines`).
- **Why?/Rationale summary** — a real, per-decision sentence derived from
  already-loaded evidence (`evidence_type`/`source`), not a fabricated
  thesis; falls back to a static disclosure when no evidence exists.
- **Risk context placeholder** — a static, decision-independent disclosure
  ("Risk context not yet available") added by the UI-completion roadmap's
  Slice 1. Presentation only — see Section 3 for why this is not Risk
  Intelligence.

**Implemented but illustrative — real code, real rendering, but backed by
Sentinel Engine's own seed data, not real production data:**

- **Governance & Policy, Approval, Audit Trail** — `GovernanceEntry`/
  `ApprovalEntry`/`AuditEntry`, read via `SentinelGovernanceSource`/
  `DecisionGovernanceQueryService` and `SentinelAuditSource`. These render
  Sentinel Engine's own internal `GovernanceService`/`Policy`/`Approval`
  domain (real code, per `ADR-012`), populated by `bootstrap.py`'s
  deterministic in-memory seed decisions — **not** the real
  `constitution_enforcement_events`/`approval_events` production audit
  source `AARA_TRADING_INTELLIGENCE_GOVERNANCE_INTELLIGENCE_DESIGN.md`
  analyzes (Section 3 keeps this distinction explicit).

`symbol` and `action` are also present on `DecisionView` (not separately
called out by this task, but part of the same, already-real field set). None
of the above implies real persistence or real production authentication —
both remain exactly as excluded as Section 3 states.

## 3. Excluded Capabilities

Each explicitly deferred, with the specific reason it isn't part of this
MVP — not a vague "later," a cited, concrete blocker:

- **Portfolio** — no code exists anywhere under
  `applications/trading_intelligence/`; no `sentinel_engine` contract is even
  proposed for it (`AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`
  Section 7 confirms Trading Intelligence, not Sentinel, owns portfolio
  context).
- **Real Risk Intelligence** — no `sentinel_engine` risk contract exists at
  all; still the largest single gap found across every capability analyzed
  in this product (`AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md`
  Section 1). The UI's static "Risk context not yet available" disclosure
  (Section 2) is a decision-independent placeholder string, not a
  `RiskEvaluation` contract, reader, or any risk data of any kind — it must
  not be read as Risk Intelligence existing.
- **Evidence Intelligence UI** — implemented (Section 2): a real
  Trading-Intelligence-side reader (`SentinelEvidenceSource`) exists and is
  rendered, including ADR-037 evidence metadata. The cardinality concern
  originally named here (single `evidence_reference` vs. the full list
  `EvidenceService.get_evidence_for_decision()` returns) turned out moot —
  the built reader never dereferences `evidence_reference` at all; it reads
  `DecisionQuery.get_decision_timeline()`'s event stream directly, mirroring
  `SentinelAuditSource`'s existing pattern.
- **Governance Intelligence UI (real production source)** — remains
  excluded exactly as before: `Approval`'s shape (one record per decision)
  still doesn't match the real audit data (`constitution_enforcement_events`,
  six rows per decision); using it as-is would still misrepresent the real
  data (`AARA_TRADING_INTELLIGENCE_GOVERNANCE_INTELLIGENCE_DESIGN.md`
  Section 3). What the UI now renders (Section 2) is a separate thing —
  Sentinel Engine's own internal, illustrative `GovernanceService`/`Policy`/
  `Approval` domain, not `constitution_enforcement_events` — and does not
  close this exclusion.
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

**Section 2's now-broader rendered feature set changes nothing about this
posture.** Evidence, governance/approval/audit, the Why summary, and the
Risk placeholder all run through the same in-memory, illustrative seed data
`bootstrap.py` already produces — none of them implies a real production
backend exists, and Production mode above remains exactly as blocked.

## 5. MVP User Journey

**Only what actually exists today, verified directly.**

The real, working journey today is a genuine rendered browser page, not
just a data/service flow — `applications/trading_intelligence/ui/
decision_center/gradio_view.py`'s `DecisionCenterUI` is a fully wired
Gradio `Blocks` application, launched by `main.py`:

```
bootstrap.build_application()
  -> DecisionCenterController (query_service, evidence_query_service,
                                governance_query_service, audit_source)
  -> DecisionCenterUI(controller, decision_ids)
main.py: DecisionCenterUI.build().launch()
  -> a real Gradio Blocks page: decision list, decision detail, evidence,
     governance & policy, approval, audit trail, Why? summary, Risk
     placeholder, refresh, mouse/keyboard row selection
```

This supersedes the earlier claim that `DecisionCenterScreen`/
`DecisionListArea`/`DecisionDetailArea` have no rendering framework wired to
them and that no rendered page exists — both were true when originally
written (per `AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md` Section
4's pre-build description) and are false now; `gradio_view.py` did not exist
at the time.

**No login step and no real, multi-workspace navigation still exist** — the
shell's nav bar shows "Decision Center" as the only active item; Portfolio
Intelligence and Risk Intelligence remain non-interactive "Coming Soon"
labels, and no `AuthenticationProvider` implementation is wired to any real
credential. A truthful MVP user journey today is "a user opens the app and
sees a real Decision Center page," not the aspirational Login → Workspace →
Decision Center flow `AARA_TRADING_INTELLIGENCE_MVP_EXPERIENCE_DESIGN.md`
Section 1 describes, which still doesn't exist as working code.

## 6. Implementation Readiness Matrix

| Capability | Current State | Can Build Now | Blocked By |
|---|---|---|---|
| Decision list | Real, tested, wired end-to-end | Already built | — |
| Decision detail | Real, tested, wired end-to-end | Already built | — |
| Portfolio | No code anywhere | No | No `sentinel_engine` contract proposed; ownership not decided |
| Real Risk Intelligence | No `sentinel_engine` contract | No | Missing contract (new `sentinel_engine/` code needs its own ADR, per `ADR-001`); which of four non-unified risk models is authoritative is undecided |
| Risk placeholder (static UI disclosure) | Real, tested, wired end-to-end | Already built | — (not Risk Intelligence; see Section 3) |
| Evidence Intelligence UI | Real, tested, wired end-to-end, including ADR-037 metadata | Already built | — |
| Governance Intelligence UI (Sentinel-domain, illustrative) | Real, tested, wired end-to-end | Already built | — |
| Governance Intelligence UI (real `constitution_enforcement_events` source) | No reader, wrong contract shape | No | Needs a new contract matching `constitution_enforcement_events`; needs its own ADR |
| Authentication | Interface only, zero implementations | No | `ADR-003`: implementation gated on product boundaries stabilizing |
| Real ledger connection | No backend implementation | No | `ADR-004`: deferred until Phase 1A validation window completes |
| Rendering/UI framework | Gradio 4.44.1, chosen and shipped (`gradio_view.py`) | Already built | — |

`AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 6's "open decision" this row
previously cited concerns the platform-wide shell technology choice across
all AARA products, not Trading Intelligence's own Decision Center, which
already ships on Gradio.

## 7. First Implementation Milestone

**Status: superseded — completed, then exceeded.** The milestone originally
named here — add explicit placeholder areas to `DecisionCenterScreen` for
evidence, risk, and governance, each honestly representing "not yet
available" — has shipped. For evidence and governance, the actual result
went further than a placeholder: both are now real, rendered content
(Section 2), not an absence-only disclosure. What has actually shipped,
verified directly:

- Decision Center rendering (`gradio_view.py`, a real Gradio `Blocks`
  application — see Section 5).
- Evidence rendering, including ADR-037 evidence metadata.
- Governance & Policy, Approval, and Audit Trail rendering (Sentinel-domain,
  illustrative — see Sections 2 and 3).
- A derived, per-decision Why?/Rationale summary.
- The Risk section's placeholder: a static, decision-independent disclosure
  — the one piece of the original milestone that shipped exactly as
  originally scoped (an absence-only placeholder, since no `RiskEvaluation`
  contract exists).

This document does not name a next milestone — that is a separate, future
scope decision, not a correction to this one.

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `sentinel_engine/`,
`ledger/`, `bot/`, `dashboard/`, or any other protected path was created or
modified. No UI component or code was created. No ADR was resolved; `ADR-003`
and `ADR-004` remain exactly as deferred as before this document. No
ownership boundary was changed. This document only reads and cites existing
code and prior documentation.
