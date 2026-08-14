# ADR-020: Sell Intelligence — Future Exit Decision Intelligence (Classification Only, Implementation Deferred)

**Status:** Accepted — Implementation Deferred
**Date:** 2026-08-14
**Decision Type:** Architecture / Governance — Placement Classification Only
**Related ADRs:** ADR-002, ADR-004, ADR-011, ADR-015, ADR-016, ADR-019

---

## 1. Context / Problem

A read-only architecture/governance audit (2026-08-14, the same audit that
produced [ADR-019](ADR-019-asset-universe-screening-funnel.md)) identified
Sell Intelligence — reasoning about whether an existing holding's original
buy rationale still holds — as a second gap: a capability with no contract,
no code, and no architectural placement anywhere in this repository.

**In code, what exists today is deterministic, not reasoning-based:**

- `bot/core/recommendation_engine.py::get_sell_analysis(symbol, d)` computes
  a 0–100 point score from four independently-weighted deterministic
  inputs — position-size concentration (`pos_w`, points for exceeding
  10%/15%/25%/50% thresholds), unrealized profit (`unreal_pct`, points for
  exceeding 10%/25%/50%/100% gain), a single AI ensemble confidence float
  read from the last BUY row or latest signal (`ens`, points for falling
  below 0.65/0.60/0.50), and drawdown (points for `unreal_pct` breaching
  -5%/-7%/-10%/-15%/-25%/-40%) — then maps the summed score to a
  `HOLD`/`WATCH`/`TRIM`/`SELL`/`EXIT` label and a `trim_pct`. This is
  point-weighted arithmetic over already-computed numbers, not a reasoning
  process — it does not read or represent *why* the original decision was
  made, only current price/size/confidence state. `docs/REQUIREMENTS.md`
  (BUG-001) records this function as having previously underscored extreme
  concentration, corroborating that it is a maintained heuristic, not a
  frozen contract.
- `bot/risk/risk_manager.py::RiskManager` implements independent,
  deterministic exit/risk gates: `check_stop_loss()` and
  `check_trailing_stop()` (price-threshold exits, `STOP_LOSS_PCT`),
  `check_portfolio_drawdown()` (`PORTFOLIO_DRAWDOWN_LIMIT_PCT`
  circuit breaker), `check_daily_loss()` / `check_weekly_loss()`
  (time-windowed loss circuit breakers), and `sector_check()` (sector
  concentration limit). None of these evaluate *why* a position was
  opened — they evaluate current price/portfolio state against fixed
  thresholds.

Both are real, live, production code inside `bot/`, protected by
[ADR-002](ADR-002-bot-runtime-protection.md).

**In the frozen, non-binding architecture reference**
(`docs/architecture/DECISION_INTELLIGENCE_ARCHITECTURE.md`, gitignored,
Tier-4 per `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`), Stage 9
("Position Management") only covers mechanical monitoring — stop-loss,
profit-target, and time-based exit triggers on an already-open position, the
same category of mechanism `RiskManager` already implements. That document's
Stage 3 ("Thesis Formation") is the only place `thesis` (`hypothesis`,
`expected_outcome`, `invalidation_trigger`, `holding_horizon`) and
`conviction` (a 0–100 composite score with named components) are defined —
and only for the original BUY decision, not for reassessing an existing
holding. No stage, in this or any document, describes reasoning about
whether an existing thesis still holds. Per
[ADR-011](ADR-011-phase-1-applicability-scope-for-decision-intelligence-architecture.md),
this structured Thesis/Conviction concept is confirmed unimplemented in
production: `trades.db.decision_log.thesis` is 0/18 rows populated.

**In `sentinel_engine/`:** `sentinel_engine.domain.decision.Decision`
(`sentinel_engine/domain/decision.py`) is a frozen dataclass —
`decision_id`, `symbol`, `action`, `timestamp`, `confidence`,
`evidence_reference`, `risk_reference` — with no thesis, conviction, or
invalidation field of any kind.
`sentinel_engine.events.event_types.EventType`
(`sentinel_engine/events/event_types.py`) currently has eight members
(`CANDIDATE_EVALUATED`, `DECISION_CREATED`, `EVIDENCE_ATTACHED`,
`GOVERNANCE_EVALUATED`, `APPROVAL_RECORDED`, `RISK_EVALUATED`,
`DECISION_EXECUTED`, `DECISION_OUTCOME_RECORDED`) — none represents a
sell/exit reassessment of an existing holding.

`docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md` §6 ("Future Adapter
Responsibilities") names four undesigned future adapters (Candidate, Risk,
Execution, Outcome). **None of the four is Sell-Intelligence-specific.**
The Risk adapter is scoped to translating `bot/risk/risk_manager.py`'s
existing deterministic output into `RISK_EVALUATED` — the same mechanical
category audited above, not thesis-reassessment reasoning. This differs
from [ADR-019](ADR-019-asset-universe-screening-funnel.md), where a
"Candidate adapter" placeholder already existed to point to; no equivalent
placeholder exists for Sell Intelligence.

No `InvestmentDecision` class exists anywhere in this repository. This ADR
uses only the real, existing name: `sentinel_engine.domain.decision.Decision`.

## 2. Governing Authority

Per `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`, Architecture Decision
Records are Tier-2 authority, superseding any conflicting document below
them (Tier-3 `docs/platform/`/`docs/implementation/` docs; Tier-4 gitignored
`docs/architecture/*` drafts). That document's conflict-resolution rule
applies here directly: *"A new document that conflicts with an existing
authoritative doc does not silently coexist with it. Write a new ADR...
that references both and states which wins and why."* This ADR references
ADR-002, ADR-004, ADR-011, ADR-015, ADR-016, and ADR-019, states that it
does not conflict with any of them, and states precisely what new ground it
covers that none of them already decided: a placement classification for
Sell Intelligence — reasoning about whether an existing holding's original
rationale still holds — that no prior ADR names.

## 3. Decision

This ADR establishes, for future architecture only, where a Sell
Intelligence capability — if and when it is built — would belong, and
records what it conceptually is, without designing it:

1. **Sell Intelligence is classified as a future `sentinel_engine/` Core
   decision-intelligence capability**, not a Trading Intelligence
   product-specific mechanism — it is the exit-side counterpart to Stage 3
   deep Sentinel evaluation classified in
   [ADR-019](ADR-019-asset-universe-screening-funnel.md) §3–§5, evaluated
   under the same [ADR-015](ADR-015-sentinel-engine-core-boundary.md) §7
   classification test.
2. Sell Intelligence is placement-eligible only **once the structured
   decision concepts it depends on exist** — chiefly structured Thesis and
   Conviction, which
   [ADR-011](ADR-011-phase-1-applicability-scope-for-decision-intelligence-architecture.md)
   confirms are **not** a current Phase 1 requirement or deliverable. Until
   those concepts exist, Sell Intelligence has nothing to reason over.
3. Existing deterministic exit/risk mechanisms
   (`bot/core/recommendation_engine.py::get_sell_analysis()`,
   `bot/risk/risk_manager.py::RiskManager`) are unaffected, unchanged, and
   remain the current, sole, production sell/exit logic.

**This ADR is a placement/classification decision only. It is not an
implementation or refactoring authorization. It moves no file, changes no
import, creates no contract, designs no schema, and alters no behavior.**
This mirrors the scope discipline of ADR-015 (Sentinel Engine core boundary
classification), ADR-016 (contract-shape classification, implementation
deferred), and ADR-019 (screening-funnel placement classification).

## 4. Sell Intelligence Capability Classification

Applying ADR-015's five-part classification test (§7) to Sell Intelligence,
at the concept level only — no contract exists to test against code:

1. **Consumers:** none today — no Sell Intelligence code or contract exists
   anywhere. `get_sell_analysis()` and `RiskManager` are separate,
   deterministic, unrelated mechanisms (see §6).
2. **Vocabulary:** "thesis invalidation," "conviction degradation," and
   "alpha exhaustion" are generic decision-lifecycle vocabulary, consistent
   with `Decision`/`Evidence` naming already in `sentinel_engine/`, not
   product-branded terms.
3. **Behavior:** if built, its responsibility would be reading evidence and
   an existing decision's recorded thesis/conviction to produce a reasoned
   reassessment — genuine engine-level behavior per ADR-015 §6, not
   product presentation/workflow, and not a deterministic threshold check
   (which is what `get_sell_analysis()`/`RiskManager` already are).
4. **Portability:** thesis-reassessment reasoning is not inherently
   trading-specific; the same reasoning shape could plausibly serve Wealth
   Intelligence or future products, consistent with the platform's
   one-engine/multiple-products model.
5. **Coupling if retained:** none assessed — nothing is retained or moved
   by this ADR.

Per ADR-015 §7, scoring "generic/engine-level" on vocabulary and behavior
makes Sell Intelligence a **candidate for Core, transitional pending
design** — the same category ADR-019 assigned to Stage 3 deep evaluation,
and the same "Transitional, leaning toward future Core" language ADR-015
itself used for `morning_brief_query.py` and `decision_center_query.py`.
This ADR does not finalize that classification; it records directional
placement for a future contract-design ADR to build against.

**Explicit non-invention:** this ADR does not invent an `InvestmentDecision`
class, a `SellDecision` class, a scoring formula, a threshold, an event
type, or an API. It uses only `sentinel_engine.domain.decision.Decision` by
name, as the real object a future Sell Intelligence capability would
presumably reason about — without adding any field to it.

## 5. The Four Future Evaluation Dimensions

The following four dimensions describe conceptual intent only. No field
shape, scoring method, threshold, or algorithm is specified for any of
them; specifying any of these is explicitly out of scope (§10).

| Dimension | Conceptual meaning | Current analog (deterministic, unrelated) |
|---|---|---|
| **Thesis invalidation** | Has the original stated rationale for the position been contradicted by new evidence? | None exists — no thesis is recorded in production (`decision_log.thesis`: 0/18 rows, per ADR-011) |
| **Conviction degradation** | Has confidence in the original decision declined over time, distinct from a point-in-time price move? | `get_sell_analysis()`'s single-snapshot `ens` (AI ensemble confidence) check is the closest existing analog, but it re-reads a stored float; it does not track degradation over time or reason about *why* confidence changed |
| **Risk / policy breach** | Has the position violated a governance or constitution rule, as distinct from a price-based stop? | `bot/trust_ledger/constitution.py::check_and_log()` (six rule checks per decision, per ADR-016's context) and `RiskManager`'s deterministic gates are the closest existing analogs — both are rule/threshold checks, not intelligence reasoning |
| **Alpha exhaustion** | Has the original expected catalyst/edge already played out, independent of current price or loss/gain? | None exists — no catalyst-tracking or edge-decay mechanism exists in `bot/` or `sentinel_engine/` today |

## 6. Boundary Between Current `bot/` Behavior and Future Sentinel Capability

This ADR draws an explicit line between what exists today and what is
classified, not built, by this ADR:

**Existing, unchanged, production (`bot/`, frozen by ADR-002):**
- Mechanical stop/target/time-based exits — `RiskManager.check_stop_loss()`,
  `RiskManager.check_trailing_stop()`.
- Deterministic portfolio-level risk/concentration/drawdown controls —
  `RiskManager.check_portfolio_drawdown()`, `RiskManager.check_daily_loss()`,
  `RiskManager.check_weekly_loss()`, `RiskManager.sector_check()`.
- Deterministic point-weighted sell scoring —
  `recommendation_engine.get_sell_analysis()`, which combines
  position-size, unrealized P&L, a single confidence snapshot, and
  drawdown into a `HOLD`/`WATCH`/`TRIM`/`SELL`/`EXIT` label.

**Future, undesigned, classified only by this ADR (`sentinel_engine/`
Core candidate):**
- Sell Intelligence — reasoning about whether the *original decision
  rationale* (thesis, conviction, expected catalyst) still holds, using
  evidence and the decision's own recorded history, not a fresh snapshot
  of price/size/confidence alone.

The two categories answer different questions: the existing mechanisms
answer "has price/portfolio state crossed a threshold?"; the future,
classified-only capability would answer "does the reason I bought this
still hold?" This ADR does not merge, replace, deprecate, or alter the
first category in any way.

## 7. Relationship to ADR-002

This ADR touches no ADR-002-protected file. It does not authorize, propose,
or imply any change to `bot/` (including
`bot/core/recommendation_engine.py`, `bot/risk/risk_manager.py`, or any
other file), `dashboard/`, `scheduler/`, `.github/workflows/*.yml`,
`database/`, or top-level `ledger/`. **This ADR does not create an ADR-002
exception.** `get_sell_analysis()` and `RiskManager`'s existing gates stay
exactly as ADR-002 protects them, unchanged, regardless of this
classification.

## 8. Relationship to ADR-011

**This ADR does not reopen, alter, narrow, or expand
[ADR-011](ADR-011-phase-1-applicability-scope-for-decision-intelligence-architecture.md)'s
Phase 1 applicability scope in any way.** ADR-011 remains the sole,
unchanged, Tier-2 authority on what current Phase 1 `sentinel_engine/`
implementation work requires. Specifically:

- This ADR does **not** make structured Thesis or structured Conviction a
  Phase 1 requirement. ADR-011's ruling — "Phase 1 does not require Stage
  3's structured Thesis or Conviction" — stands unchanged.
- This ADR does **not** authorize implementation of Thesis or Conviction,
  in Phase 1 or otherwise. Section 10 (Non-Authorization) makes this
  explicit.
- Sell Intelligence, as classified here, is placement-eligible **only once**
  structured Thesis/Conviction exist — which this ADR does not create,
  schedule, or accelerate. This ADR is therefore, by its own logic,
  necessarily further out than the concepts ADR-011 already deferred.
- Current deterministic `bot/risk/` and `recommendation_engine.py` exit
  mechanisms remain completely unchanged, per §6 and §7 above.
- Any future implementation of Sell Intelligence, Thesis, or Conviction
  requires its own, separately governed decision/architecture change — this
  ADR does not pre-authorize any of it.

## 9. Relationship to ADR-015, ADR-016, and ADR-019

**ADR-015:** This ADR applies, but does not amend,
`docs/decisions/ADR-015-sentinel-engine-core-boundary.md`'s Sentinel Engine
Core boundary rule and classification test (§6–§7) to a new subject — Sell
Intelligence — that ADR-015 did not address. ADR-015 classified four
specific, already-existing modules; this ADR classifies zero existing
modules and one not-yet-designed future capability. This ADR does not
reclassify any of ADR-015's four modules and does not alter its Core
boundary rule.

**ADR-016:** This ADR follows the same governance pattern ADR-016 used —
naming a concept, classifying it, and explicitly deferring implementation
without designing a contract. This ADR does not reference or depend on
ADR-016's specific subject (`ConstitutionRuleCheck`), only its pattern.

**ADR-019:** This ADR is the direct sibling of
`docs/decisions/ADR-019-asset-universe-screening-funnel.md`, produced by the
same 2026-08-14 governance audit. ADR-019 classified Stage 3 "deep Sentinel
Intelligence evaluation" of *candidates not yet held* as a future
`sentinel_engine/` Core capability; this ADR classifies Sell Intelligence —
reasoning about positions *already held* — as its exit-side counterpart,
under the same classification test and the same undesigned-contract
discipline. Per ADR-019 §4's numbering disambiguation, ADR-019's Stage
1/2/3 numbering is local to the screening funnel only; this ADR does not
reuse or extend that numbering, and does not use "Stage" numbering of its
own. This ADR does not amend ADR-019 and does not alter its classification
of Stage 1/2/3.

**Stage 3 disambiguation:** references to "Stage 3" in this ADR span two
distinct and unrelated numbering systems — `DECISION_INTELLIGENCE_ARCHITECTURE.md`'s
Stage 1–12 lifecycle, where Stage 3 is Thesis Formation (§1), and ADR-019's
locally-scoped screening-funnel Stage 1/2/3, where Stage 3 is deep Sentinel
evaluation (§3, above); this ADR adopts neither numbering system as its own
and takes no position on how the two relate to each other.

## 10. Non-Authorization

**This ADR is classification/placement-only. It authorizes no source-code
change, schema change, test change, contract design, adapter creation,
composition-root change, scoring formula, threshold, event type, API, or
behavior change of any kind.**

Specifically, this ADR does not authorize:

- Any change to `bot/` (including `bot/core/recommendation_engine.py`,
  `bot/core/recommendation_portfolio.py`, `bot/risk/risk_manager.py`, or
  any other file), `dashboard/`, `scheduler/`, `.github/workflows/*.yml`,
  `database/`, or top-level `ledger/`.
- Any ADR-002 exception, of any scope.
- Any change to `sentinel_engine/` — no new file, no new class, no new
  `EventType` member, no new adapter, no modification of
  `sentinel_engine.domain.decision.Decision` or any other existing
  contract.
- Designing, naming, or specifying a Sell Intelligence contract, schema,
  scoring formula, threshold, or data shape in any form.
- Implementation of structured Thesis or structured Conviction, in Phase 1
  or any other phase.
- Any change to current sell/exit behavior, current stop-loss/trailing-stop
  logic, current portfolio drawdown or concentration gates, or current
  `get_sell_analysis()` scoring.
- Any authorization to automatically sell, trim, or otherwise act on any
  position. Sell Intelligence, if ever built, would remain subject to this
  platform's human-governance principle (per
  `docs/AI_AGENT_GUIDELINES.md` §1: "the platform surfaces evidence and
  recommendations; it does not execute trades autonomously") — this ADR
  does not decide or alter that principle, only notes it applies.
- Any modification to `TRADING_INTELLIGENCE_BOUNDARY.md`,
  `docs/architecture/DECISION_INTELLIGENCE_ARCHITECTURE.md`, or any other
  existing document.
- Any modification to ADR-002, ADR-004, ADR-011, ADR-015, ADR-016,
  ADR-019, or any other existing ADR.
- Any reopening, narrowing, or expansion of ADR-011's Phase 1 applicability
  scope.
- Creation of `ADR-021` (Portfolio Hygiene) or any other ADR — that remains
  separate, future, independently governed work, not created or
  pre-authorized here.
- Invention of an `InvestmentDecision` class or any other new domain type.
- Any change to `applications/trading_intelligence/` or
  `applications/wealth_intelligence/`.
- Any commitment to a timeline, phase, or priority for building Sell
  Intelligence.

**Implementation of any part of Sell Intelligence — including its contract
design and the Thesis/Conviction structure it depends on — will occur
later, if and when undertaken, as a separately governed change, after the
current product work is finished. This ADR neither schedules nor blocks
that future work; it only records where it would belong.**

## 11. Deferred Implementation / Future Change Requirements

**Implementation pointer:** unlike ADR-019, which pointed to an
already-named placeholder (the "Candidate adapter" in
`TRADING_INTELLIGENCE_BOUNDARY.md` §6), **no existing document names a
placeholder for Sell Intelligence.** The closest adjacent placeholders —
the Risk adapter and Outcome adapter in `TRADING_INTELLIGENCE_BOUNDARY.md`
§6 — are scoped to different, already-deterministic concerns (translating
`RiskManager`'s existing gate output, and post-close outcome recording,
respectively) and are not repurposed by this ADR. **The implementation
location for Sell Intelligence therefore remains to be designed by a
future ADR.** That future ADR would need to address, at minimum:

- Whether Sell Intelligence's contract is a new `sentinel_engine/`
  module (e.g. an `adapters/` or `services/` addition, following the
  `evidence_adapter.py` precedent set by
  [ADR-012](ADR-012-sentinel-engine-evidence-intake-for-bot-model-outputs.md)),
  and where within `sentinel_engine/`'s existing package structure (per
  [ADR-001](ADR-001-sentinel-engine-structure.md)) it would live.
- Whether a new `EventType` member (e.g. representing a sell
  reassessment) is needed, alongside the eight that exist today.
- How Thesis and Conviction — themselves unbuilt, per ADR-011 — would need
  to be structured before Sell Intelligence has anything to reason over.
- Whether `TRADING_INTELLIGENCE_BOUNDARY.md` should be amended (a separate
  action; not performed here) to name a fifth future adapter for this
  purpose, alongside its existing four.
- Whether/how Sell Intelligence's output would interact with, but not
  replace, the existing deterministic `RiskManager`/`get_sell_analysis()`
  gates (§6) — this ADR does not decide whether the two would run
  side-by-side, whether one would inform the other, or any other
  integration shape.

None of the above is designed, decided, or authorized by this ADR.

## 12. Consequences

### Positive

- Gives a name and a directional Core-vs-Product classification to a
  capability (reasoning about whether an existing position's rationale
  still holds) that previously had no architectural home anywhere in this
  repository.
- Clearly separates existing deterministic exit/risk mechanisms (unchanged,
  still governing) from a distinct future reasoning capability, reducing
  the risk that a future change conflates the two.
- Provides a citable classification for any future ADR designing Sell
  Intelligence's contract, consistent with ADR-015's and ADR-019's
  precedent.
- Keeps ADR-011's Phase 1 scope untouched and unambiguous, and states
  explicitly why Sell Intelligence is further out than the Thesis/Conviction
  work ADR-011 already deferred.

### Negative

- Sell Intelligence remains entirely undesigned; this ADR resolves only
  directional placement, not shape, contract, or timeline.
- No implementation pointer exists yet (unlike ADR-019's Candidate
  adapter) — a future ADR must both design the contract and decide where
  it lives.
- Sell Intelligence's dependency on unbuilt Thesis/Conviction structure
  means it cannot be implemented before that separate, larger body of work
  is separately authorized.
- One related topic from the same governance audit (Portfolio Hygiene,
  `ADR-021`) remains fully unaddressed and is not created by this ADR.

## 13. Acceptance Criteria

This ADR may be considered accepted only when:

- It names ADR-002, ADR-004, ADR-011, ADR-015, ADR-016, and ADR-019.
- It classifies Sell Intelligence as a future `sentinel_engine/` Core
  candidate, without designing its contract.
- It names and distinguishes the four evaluation dimensions (thesis
  invalidation, conviction degradation, risk/policy breach, alpha
  exhaustion) at the conceptual level only.
- It clearly separates existing deterministic `bot/` sell/exit/risk
  mechanisms from the future classified-only capability.
- It explicitly states it does not reopen or alter ADR-011's Phase 1 scope,
  and does not make Thesis/Conviction a Phase 1 requirement.
- It does not create an ADR-002 exception.
- It does not modify `TRADING_INTELLIGENCE_BOUNDARY.md` or any other
  existing document or ADR.
- It does not invent an `InvestmentDecision` class or any scoring
  formula/threshold/event contract/API.
- It does not authorize automated selling or trimming of any position.
- It does not create `ADR-021`.
- It states the implementation location remains to be designed, since no
  existing placeholder names it.
- It leaves all implementation to future, separately governed work.
