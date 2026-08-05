# AARA Trading Intelligence — Decision Center Capability Model

**Status:** Synthesis design document. Documentation only. No code was
created or modified. `applications/trading_intelligence/`, `sentinel_engine/`,
`ledger/`, `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`,
`database/` untouched, confirmed via `git status` before and after. No
contract, adapter, or UI component was created.

**Authority:** `AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md`,
`AARA_TRADING_INTELLIGENCE_EVIDENCE_DESIGN.md`,
`AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md`,
`AARA_TRADING_INTELLIGENCE_GOVERNANCE_INTELLIGENCE_DESIGN.md`,
`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`. This document synthesizes
those five; it does not re-derive or re-decide any finding they already
made. Where a fact below depends on the current state of real code
(`applications/trading_intelligence/`), it was re-verified directly for this
document, not assumed from the prior documents alone — current test suite:
159 passing (`applications/trading_intelligence/tests` 49,
`applications/trading_intelligence/ui/tests` 28, `sentinel_engine/tests` 82).

---

## 1. Decision Center Purpose

**User problem solved**, per `AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`
Section 2's own framing, not restated differently here: *"What did the system
decide, and why? What evidence supports it? Is anything pending approval?"*
Decision Center exists to answer those three questions for one decision at a
time, not to summarize the portfolio.

**Investor workflow:** browse a list of decisions → select one → see that
decision's full context. The "full context" is exactly the three siblings
Section 2 below defines — evidence, risk, governance — each independently
answering one of the three questions above. This is a drill-down workflow,
not a monitoring one: the user starts broad (a list) and moves narrow (one
decision, fully explained).

**Why this is different from a trading dashboard — stated precisely, not as
a marketing claim:** the current `dashboard/` already has real,
decision-explanation-oriented components today — `decision.py`, `thesis.py`,
`counterfactual.py`, `loss_explanation.py`, `pending_approvals.py`
(`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` Section 2's own "current
data source" list). Decision Center is **not** the first place decisions get
explained. The actual differences, verified against real code:

1. **Data path, not just presentation.** `dashboard/`'s components query
   `bot/trust_ledger/`-backed SQLite directly through `dashboard/data.py`.
   Decision Center's data path is `Sentinel → Projection →
   SentinelProjectionDecisionSource → DecisionQueryService → UI`
   (`AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md` Section 6) — a
   contract-mediated, adapter-bounded path, per
   `TRADING_INTELLIGENCE_BOUNDARY.md`'s one-way-boundary principle. The
   dashboard's version is direct and ad hoc; Decision Center's is typed and
   structurally decoupled from `bot/`.
2. **Framework-independent, testable models.** `DecisionListArea`/
   `DecisionDetailArea`/`DecisionCenterScreen`
   (`applications/trading_intelligence/ui/decision_center/screen.py`) are
   plain, frozen dataclasses with no rendering engine — verified directly.
   `dashboard/`'s components are Gradio-coupled HTML-string renderers. This
   is a reusability property (the same screen model could back a different
   rendering layer later), not a claim that today's dashboard is worse at
   explaining decisions.
3. **Governance-shaped by design intent, not retrofitted.** Decision
   Center's data model is built to eventually surface the same
   immutable, hash-chained audit trail `AARA_TRADING_INTELLIGENCE_GOVERNANCE_INTELLIGENCE_DESIGN.md`
   found already exists (`constitution_enforcement_events`) — the intent is
   an auditable decision record, not a live operational metric surface.
   Whether that intent is realized yet is answered honestly in Section 6:
   as of today, it is not.

## 2. Decision Object Model

```
Decision
    |
    +-- Evidence Intelligence      (AARA_TRADING_INTELLIGENCE_EVIDENCE_DESIGN.md)
    |
    +-- Risk Intelligence          (AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md)
    |
    +-- Governance Intelligence    (AARA_TRADING_INTELLIGENCE_GOVERNANCE_INTELLIGENCE_DESIGN.md)
```

One structural note the three prior documents didn't need to state
side-by-side, but which matters once they're read together: **each sibling
is at a different, non-comparable maturity level**, not three equally-blocked
features. Section 4 makes this precise; stated at a glance here:

| Sibling | Real, tested code today |
|---|---|
| Decision (the trunk) | Yes — full end-to-end wiring, 159 tests |
| Evidence Intelligence | Contract exists, zero wiring |
| Risk Intelligence | No `sentinel_engine` contract exists at all |
| Governance Intelligence | Contract exists but doesn't fit the real data |

## 3. User Experience Flow

An illustrative walk-through, not a new specification — each stage cites
what's real versus proposed rather than presenting the whole flow as built:

**Morning — review decisions.** The user opens Decision Center and sees a
decision list. This stage is **real and tested today**:
`DecisionCenterController.load_screen()` →
`DecisionQueryService.list_decision_views()` → `DecisionListArea`. Empty
state ("No decisions recorded yet.") is also real and tested.

**Investigation — understand evidence.** The user selects a decision and
wants to know what evidence supports it. Per
`AARA_TRADING_INTELLIGENCE_EVIDENCE_DESIGN.md` Section 3, this stage is
**not built**: `DecisionDetailArea` today exposes only
`evidence_reference` as an opaque string (the raw pointer, unresolved into
any real `Evidence` content) — there is no evidence panel, and the
cardinality question (one referenced item vs. the full associated list) is
still open.

**Risk review — evaluate risk.** The user wants to know what risk state the
decision was made under. Per
`AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md` Sections 2-3, this
stage is **not built and has no contract to build against** — `risk_reference`
is likewise an opaque string today, and even conceptually, "decision risk"
can only ever mean the shared, cycle-scoped `RISK_EVALUATED` state (many
decisions per cycle share one `risk_reference`), never a per-decision score.

**Trust — inspect governance trail.** The user wants to know whether the
decision was checked, and by what rules. Per
`AARA_TRADING_INTELLIGENCE_GOVERNANCE_INTELLIGENCE_DESIGN.md` Sections 1-2,
the underlying data this stage would need — `constitution_enforcement_events`'
six-rule-per-decision explanation trail — is real and already written by
`bot/trust_ledger/constitution.py`, but **no reader or contract exists** to
bring it into Decision Center, and the Phase 1A "advisory only, no real
approval workflow" caveat must not be misrepresented if it ever is built.

## 4. Capability Maturity

### Evidence

- **Available now:** `sentinel_engine.evidence.Evidence` contract (5 fields);
  `EvidenceService.associate_evidence()`/`get_evidence_for_decision()`
  (in-memory); `Decision.evidence_reference`/`DecisionContract.evidence_reference`
  passed through end-to-end, unresolved (a string, not a panel).
- **Missing pieces:** the cardinality decision (singular reference vs. list,
  per `AARA_TRADING_INTELLIGENCE_EVIDENCE_DESIGN.md` Section 4); any
  Trading-Intelligence-side reader/adapter; any `Evidence` producer anywhere
  in `bot/`; an `EvidenceArea` in `screen.py`; reconciliation between
  `EvidenceCard`'s assumed field shape and `Evidence`'s real fields.

### Risk

- **Available now:** real, live enforcement (`bot/risk/risk_manager.py`);
  a real, hash-chained, currently-written `risk_evaluation_events` table
  (Phase 1A observation mode); a real dashboard display
  (`dashboard/components/risk.py`); `Decision.risk_reference`/
  `DecisionContract.risk_reference` passed through end-to-end, unresolved.
- **Missing pieces:** **no `sentinel_engine` risk contract exists at all** —
  the largest single gap of the three siblings; no reader, no adapter;
  unresolved ownership among the four non-unified risk models
  (`AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md` Section 1); a
  `RiskArea` in `screen.py`.

### Governance

- **Available now:** `sentinel_engine.governance.Policy`/`Approval`
  contracts and `GovernanceService` (in-memory, no real backing data); a
  real, hash-chained, currently-written `constitution_enforcement_events`
  table with a genuine human-readable explanation trail
  (`bot/trust_ledger/constitution.py`).
- **Missing pieces:** `Approval`'s shape doesn't fit the real data — it's a
  single record per decision, while the real audit trail is six rows per
  decision, one per constitution rule
  (`AARA_TRADING_INTELLIGENCE_GOVERNANCE_INTELLIGENCE_DESIGN.md` Section 3);
  `approval_events` (the table `Approval` would naturally map to) has zero
  writers and isn't even decision-scoped; no reader/adapter exists for
  `constitution_enforcement_events`; a `GovernanceArea` in `screen.py`.

## 5. Implementation Boundaries

**Can implement now, using existing contracts:** nothing beyond what already
exists — the current decision list/detail flow (Section 3's "Morning"
stage), already built and tested. None of the three intelligence panels
qualifies, for three different reasons: Evidence has a contract but no
reader and an unresolved cardinality question; Risk has no contract at all;
Governance has a contract, but using it as-is would misrepresent the real
data (wrong cardinality, wrong table). Building any of the three "using only
existing contracts" would mean guessing at exactly the questions the prior
three documents named as open.

**Requires new contracts:**
- Risk — a `RiskEvaluation`-shaped `sentinel_engine` contract does not exist
  and would need to be designed and added.
- Governance — a contract matching `constitution_enforcement_events`' real
  six-rows-per-decision shape does not exist; `Approval` cannot be
  repurposed for it without changing what it models.
- Evidence is the one exception — its contract already exists; what it
  needs first is a cardinality decision, not a new contract.

**Blocked by:**
- **ADR decisions** — any new `sentinel_engine` contract requires its own
  ADR (`sentinel_engine/` is protected, per `ADR-001`); any
  reader/adapter touching `bot/trust_ledger/`, `ledger/`, or `database/`
  crosses the one-way boundary and touches protected paths, gated the same
  way `ADR-004` gates ledger-integration work generally (its criterion 6:
  "whichever option is chosen gets its own ADR... before any implementation
  work begins").
- **Phase 1A validation** — `risk_evaluation_events` and
  `constitution_enforcement_events` are both Phase 1A observation-mode data
  whose own correctness is still being measured (win rate, trade count,
  data-integrity record, per `ADR-004`'s criterion 1). Surfacing either as
  finished, authoritative UI content before that window closes and is
  reviewed would misrepresent unvalidated data as settled — the same finding
  both the Risk and Governance documents already made independently.

## 6. MVP Decision Center

**What the first user can actually see today, stated plainly — no invented
future capability:**

- A **decision list**: symbol, action, status, confidence, last-updated —
  real, tested (`DecisionListArea`, via `DecisionQueryService.list_decision_views()`).
- Selecting a decision shows a **decision detail** view: the same fields
  plus formatted confidence/status/timestamp display strings — real, tested
  (`DecisionDetailArea`).
- `evidence_reference` and `risk_reference` appear only as **raw, opaque
  string values** on the underlying `DecisionContract` — `DecisionView` (what
  the list/detail screens actually render from) deliberately excludes them
  entirely. There is no evidence panel, risk panel, or governance panel. A
  user cannot see *why* a decision was made, only *what* it was.
- An **empty state** ("No decisions recorded yet.") when no decisions exist.
- `mock_data.py` remains available for demos but is not part of this real
  data path (confirmed: `controller.py` has zero import of it, structurally
  enforced by a dedicated test).

**The one fact that matters most here, and must not be glossed over:**
**there is no real data behind any of this yet.** `ProjectionRepository` —
the interface the entire chain reads through — has zero concrete
implementations anywhere in this codebase; per `ADR-004`, all 82
`sentinel_engine` tests exercise it against in-memory fakes only, "never
against real `trust_ledger` data." The only thing populating this pipeline
today is test code (`InMemoryProjectionRepository` in
`applications/trading_intelligence/tests/fakes.py`) and, separately,
`mock_data.py` for demos. **The MVP, as it stands, is a complete and tested
UI pipe with nothing real flowing through it** — not a partially-populated
screen, an empty one, by construction, until `ADR-004`'s deferred ledger
backend choice is made. This is the honest state of "what the first user can
actually see": today, in a real deployment, nothing — the list would render
its empty state forever.

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `sentinel_engine/`,
`ledger/`, `bot/`, `dashboard/`, or any other protected path was created or
modified. No contract, adapter, or UI component was created. This document
only reads and cites existing code and the four prior design documents.
