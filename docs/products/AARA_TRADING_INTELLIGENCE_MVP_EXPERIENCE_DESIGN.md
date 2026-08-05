# AARA Trading Intelligence — MVP Experience Design

**Status:** Design proposal. Documentation only. No code, UI component, or
database change was created. `applications/trading_intelligence/`,
`sentinel_engine/`, `ledger/`, `bot/`, `dashboard/`, `scheduler/`,
`.github/workflows/`, `database/` untouched, confirmed via `git status`
before and after. Ledger ownership (`ADR-004`) is not resolved by this
document.

**Authority:** `AARA_TRADING_INTELLIGENCE_DECISION_CENTER_CAPABILITY_MODEL.md`,
`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`,
`AARA_PLATFORM_SHELL_ARCHITECTURE.md`,
`ADR-004-sentinel-ledger-ownership-strategy.md`. Every "available today"
claim below was re-verified directly against real code for this document
(directory listings, test counts), not carried forward from the prior
documents without checking.

---

## 1. MVP User Journey

```
Login
  |
  v
Trading Intelligence workspace
  |
  v
Decision Center
  |
  v
Review decisions
  |
  v
Inspect evidence/risk/governance placeholders
```

Each step, stated honestly against what exists today rather than what the
journey implies:

- **Login** — **does not exist as working code.**
  `applications.platform.identity.authentication_provider.AuthenticationProvider`
  is an abstract interface with zero concrete implementations anywhere in
  this codebase (verified directly) — per
  `AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 6, the authentication
  provider itself is still an open decision (Google OAuth / managed
  provider / internal service).
- **Trading Intelligence workspace** — the shell's navigation concept
  (`AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 2) names three screens
  under it: Decision Center, Portfolio, Risk. The shell itself
  (`ShellBuilder`, `NavigationBuilder`) is built and tested, but nothing
  routes a real user into it — `ShellBuilder.build()` depends on
  `AuthenticationProvider`, which has no implementation (previous bullet).
  This step is a routing *concept*, not a working transition, today.
- **Decision Center** — the only one of the three workspace screens with
  real code: `applications/trading_intelligence/ui/decision_center/`,
  verified to exist; `Portfolio` and `Risk` have no corresponding
  directories anywhere under `applications/trading_intelligence/ui/`
  (confirmed directly — only `decision_center/` and `tests/` exist there).
  Section 2 below treats this asymmetry as the central fact of the MVP.
- **Review decisions** — real and tested: `DecisionListArea`, populated via
  `DecisionCenterController.load_screen()` →
  `DecisionQueryService.list_decision_views()`.
- **Inspect evidence/risk/governance placeholders** — **does not exist, not
  even as an empty placeholder.** Verified directly:
  `applications/trading_intelligence/ui/decision_center/screen.py` defines
  only `DecisionListArea` and `DecisionDetailArea` — no `EvidenceArea`,
  `RiskArea`, or `GovernanceArea`, empty or otherwise. `DecisionView` (what
  the screen actually renders from) excludes `evidence_reference`/
  `risk_reference` entirely; even the raw, unresolved pointer strings aren't
  shown in the real UI today. This step, as literally stated, is not part
  of the current MVP — Section 5 treats closing this specific gap as a
  measurable, not-yet-met success criterion, without proposing to build it
  here (out of this document's scope).

## 2. MVP Screens

Per this task's instruction, defining **only what exists** — this section
does not design Portfolio or Risk, because there is nothing to design
around; it states that fact precisely instead.

### Decision Center

Real code exists: `applications/trading_intelligence/ui/decision_center/`
— `screen.py`, `mock_data.py`, `controller.py`, plus the full supporting
chain (`contracts/`, `projections/`, `services/`, `adapters/`). 77 tests pass
across `applications/trading_intelligence/tests` (49) and
`applications/trading_intelligence/ui/tests` (28), re-verified for this
document.

### Portfolio

**No code exists anywhere under `applications/trading_intelligence/`** —
confirmed directly, no `portfolio/` directory, no contract, no screen model,
no mock data provider. It exists only as: (a) a name in the shell's
navigation tree (`AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 2); (b) the
current, separate, protected `dashboard/components/portfolio.py`/`capital.py`/
`rebalance.py` (a different product surface entirely, per
`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` Section 2's "Current data
source" listing — not part of this MVP). Per that same UI specification
document, **no Sentinel Engine input is even proposed** for this screen:
"Portfolio state is a Trading-Intelligence-owned concept... no Sentinel-side
portfolio contract exists or is proposed here."

### Risk

**No code exists anywhere under `applications/trading_intelligence/`** —
same as Portfolio, confirmed directly. This is the standalone "Risk
Intelligence" workspace screen from
`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` Section 2 (portfolio-scoped
risk-governor state), shortened to "Risk" in the shell's navigation tree —
**not** the same thing as "Risk Intelligence" as a Decision Center
*capability*, which
`AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md` already analyzed at
length as a separate, narrower, decision-scoped concept. Real backing data
exists elsewhere (`bot/risk/risk_manager.py`,
`bot/trust_ledger/risk.py`'s `risk_evaluation_events`,
`dashboard/components/risk.py`) but none of it is wired into
`applications/trading_intelligence/` in any form.

### Per-screen classification

| Screen | Available today | Requires mock data | Requires future backend |
|---|---|---|---|
| Decision Center | Decision list + detail, fully wired and tested end-to-end (contract → adapter → service → controller → screen) | Yes, to show anything at all — see Section 4 | A real `ProjectionRepository` implementation (blocked by `ADR-004`); any Evidence/Risk/Governance panel |
| Portfolio | Nothing | Yes, entirely — no contract or screen model exists to even seed mock data into | Everything — no Sentinel-side contract is proposed for this screen at all |
| Risk | Nothing (in `applications/trading_intelligence/`) | Yes, entirely | Everything — no `sentinel_engine` risk contract exists (per `AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md` Section 1, the largest gap of any capability analyzed this session) |

## 3. Data Strategy

**Production data:**
- **Not connected.** `ProjectionRepository` (the interface the entire
  Decision Center read chain depends on) has zero concrete implementations
  anywhere in this codebase — verified directly; all 82 `sentinel_engine`
  tests exercise it exclusively against in-memory fakes.
- **Blocked by `ADR-004`.** The ledger-ownership choice (Option A/B/C — how
  `sentinel_engine`'s ledger relates to `bot/trust_ledger/`/top-level
  `ledger/`) is explicitly deferred until Phase 1A's 30-day live-validation
  window completes and is reviewed. No production data path can be built
  before that choice is made, per `ADR-004`'s own decision framework — this
  document does not attempt to resolve it.

**Demo/test data:**
- **Allowed, and already built.** Two real, already-existing mechanisms —
  not proposed here, both delivered by already-completed work: `mock_data.py`
  (`applications/trading_intelligence/ui/decision_center/mock_data.py`),
  explicitly kept available for demos and structurally prevented from being
  a production dependency (`test_controller_does_not_import_mock_data`);
  and `InMemoryProjectionRepository`
  (`applications/trading_intelligence/tests/fakes.py`), test-only
  infrastructure proving the real service chain composes correctly. Either
  is a legitimate way to show a working Decision Center screen today —
  neither implies real data.

## 4. MVP Success Criteria

A user can:

- **Enter workspace** — **not yet achievable end-to-end.** Requires Login
  (Section 1), which has no implementation. Achievable only by bypassing
  authentication entirely (e.g., constructing a `DecisionCenterController`
  directly, as every test in this codebase already does) — not a real user
  journey.
- **View decisions** — **achievable today**, using demo/test data (Section
  3): `DecisionListArea` via `mock_data.build_mock_screen()` or a populated
  `InMemoryProjectionRepository`.
- **Inspect decision details** — **achievable today**, same data-source
  caveat: `DecisionDetailArea`, fully formatted (confidence/status/timestamp
  display).
- **Understand why a decision exists** — **not achievable today.**
  `DecisionDetailArea` shows the decision's own fields (symbol, action,
  confidence) but nothing behind `evidence_reference`/`risk_reference` — per
  Section 1, `DecisionView` excludes them entirely. A user can see *what*
  was decided, not *why*, matching
  `AARA_TRADING_INTELLIGENCE_DECISION_CENTER_CAPABILITY_MODEL.md` Section
  6's finding precisely.
- **See future intelligence areas** — **not achievable today, not even as a
  placeholder.** No `EvidenceArea`/`RiskArea`/`GovernanceArea` exists in
  `screen.py`, empty or otherwise. This is the clearest, most concrete gap
  between the MVP as it exists and the journey Section 1 describes — closing
  it is future work, not something this document builds.

**Stated plainly:** of the five criteria above, two are achievable today
(with demo/test data only), one is blocked purely on identity/authentication
work, and two require capability work this document does not undertake
(Sections 2-3 of `AARA_TRADING_INTELLIGENCE_DECISION_CENTER_CAPABILITY_MODEL.md`
already named exactly what each would need).

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `sentinel_engine/`,
`ledger/`, `bot/`, `dashboard/`, or any other protected path was created or
modified. No UI component, contract, or database change was created. Ledger
ownership (`ADR-004`) is not resolved by this document. This document only
reads and cites existing code and prior documentation.
