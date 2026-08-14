# ADR-021: Portfolio-Level Hygiene — Future Portfolio Intelligence (Classification Only, Implementation Deferred)

**Status:** Accepted — Implementation Deferred
**Date:** 2026-08-14
**Decision Type:** Architecture / Governance — Placement Classification Only
**Related ADRs:** ADR-002, ADR-004, ADR-011, ADR-015, ADR-016, ADR-019, ADR-020

---

## 1. Context / Problem

A read-only architecture/governance audit (2026-08-14, the same audit that
produced [ADR-019](ADR-019-asset-universe-screening-funnel.md) and
[ADR-020](ADR-020-sell-intelligence.md)) identified Portfolio-Level Hygiene
— cross-position reasoning about concentration, correlation overlap, and
capital efficiency across the whole book, as distinct from any single
decision — as a third gap: a capability with no contract, no code, and no
architectural placement anywhere in this repository.

**In code, what exists today is deterministic, per-check, not
cross-portfolio reasoning:**

- **Concentration** — `bot/risk/risk_manager.py::RiskManager.sector_check()`
  blocks a new BUY when `held_in_sector >= MAX_SECTOR_POSITIONS` for a
  symbol's `SECTOR_MAP` entry (a single-symbol gate, evaluated at buy time
  only). Separately, `bot/core/recommendation_portfolio.py::get_portfolio_health()`
  computes a 0–100 Portfolio Health Score whose Diversification component
  (25 of 100 points) is driven by `_max_sector_conc()`, the single worst
  sector's weight — a point-weighted heuristic, not a warning/recommendation
  mechanism, and read-only against already-open positions.
- **Correlation overlap** — `bot/_main_positions.py::_passes_correlation_gate(symbol, positions, bars_map)`
  blocks a new BUY when any held position's daily-return correlation with
  the candidate exceeds `CORRELATION_THRESHOLD` (a config constant), wired
  into the entry gate sequence in `bot/_main_cycle.py` (Gate 7 —
  Correlation). This is a single new-candidate-vs-existing-holdings check
  at buy time, not a pruning recommendation over already-held pairs.
- **Capital efficiency** — `bot/capital/pool.py::CapitalPool` (a frozen
  dataclass: `id`, `name`, `allocated_amount`, `available_cash`,
  `invested_amount`, `reserve`, `realized_profit`, `profit_withdrawn`, with
  computed properties `tradeable_cash`, `total_value`, `withdrawable_profit`)
  and `compute_tradeable_capital()` track and gate available capital
  deterministically. `get_portfolio_health()`'s Cash score component (20 of
  100 points, driven by `_cash_pct()`) is the closest existing analog to a
  capital-efficiency signal, but it scores idle-cash-as-safety-buffer, not
  deployment efficiency, and produces no recommendation of any kind.

All three are real, live, production code inside `bot/`, protected by
[ADR-002](ADR-002-bot-runtime-protection.md).

**In the frozen, non-binding architecture reference**
(`docs/architecture/DECISION_INTELLIGENCE_ARCHITECTURE.md`, gitignored,
Tier-4 per `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`), the closest
analogs are Stage 4 ("Capital Allocation" — a per-decision Capital Pool
check and position-sizing formula, not a portfolio-wide hygiene pass) and
Stage 9 ("Position Management" — per-position stop/target monitoring, not
cross-position concentration/correlation reasoning). No stage, in this or
any document, describes reasoning across the whole portfolio about
concentration, correlation overlap, or capital efficiency as a distinct
advisory capability.

**In `sentinel_engine/`:** `sentinel_engine.domain.decision.Decision`
(`sentinel_engine/domain/decision.py`) is a frozen dataclass —
`decision_id`, `symbol`, `action`, `timestamp`, `confidence`,
`evidence_reference`, `risk_reference` — scoped to a single decision, with
no portfolio-level or cross-position field of any kind.
`sentinel_engine.events.event_types.EventType`
(`sentinel_engine/events/event_types.py`) currently has eight members
(`CANDIDATE_EVALUATED`, `DECISION_CREATED`, `EVIDENCE_ATTACHED`,
`GOVERNANCE_EVALUATED`, `APPROVAL_RECORDED`, `RISK_EVALUATED`,
`DECISION_EXECUTED`, `DECISION_OUTCOME_RECORDED`) — all scoped to a single
decision's lifecycle; none represents a portfolio-wide hygiene warning or
recommendation. `sentinel_engine/ledger/ledger.py`'s `LedgerStore` remains
an abstract interface with no backend, per
[ADR-004](ADR-004-sentinel-ledger-ownership-strategy.md).

`docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md` §6 ("Future Adapter
Responsibilities") names four undesigned future adapters (Candidate, Risk,
Execution, Outcome). **None of the four is Portfolio-Hygiene-specific.**
The Risk adapter is scoped to translating `bot/risk/risk_manager.py`'s
existing per-decision output into `RISK_EVALUATED` — a single-decision
event, not a cross-portfolio one. As with
[ADR-020](ADR-020-sell-intelligence.md), no existing placeholder names this
capability.

No `InvestmentDecision` class exists anywhere in this repository. This ADR
uses only the real, existing names:
`sentinel_engine.domain.decision.Decision` and `bot/capital/pool.py::CapitalPool`.

## 2. Governing Authority

Per `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`, Architecture Decision
Records are Tier-2 authority, superseding any conflicting document below
them (Tier-3 `docs/platform/`/`docs/implementation/` docs; Tier-4 gitignored
`docs/architecture/*` drafts). That document's conflict-resolution rule
applies here directly: *"A new document that conflicts with an existing
authoritative doc does not silently coexist with it. Write a new ADR...
that references both and states which wins and why."* This ADR references
ADR-002, ADR-004, ADR-011, ADR-015, ADR-016, ADR-019, and ADR-020, states
that it does not conflict with any of them, and states precisely what new
ground it covers that none of them already decided: a placement
classification for Portfolio-Level Hygiene — cross-position concentration,
correlation-overlap, and capital-efficiency reasoning — that no prior ADR
names.

## 3. Decision

This ADR establishes, for future architecture only, where a Portfolio
Hygiene capability — if and when it is built — would belong, and records
what it conceptually is, without designing it:

1. **Portfolio Hygiene is classified as a future `sentinel_engine/` Core
   advisory capability**, not a Trading Intelligence product-specific
   mechanism, evaluated under the same
   [ADR-015](ADR-015-sentinel-engine-core-boundary.md) §7 classification
   test already applied to Stage 3 deep evaluation
   ([ADR-019](ADR-019-asset-universe-screening-funnel.md)) and Sell
   Intelligence (ADR-020).
2. Portfolio Hygiene's capital-efficiency dimension is placement-eligible
   only **once a durable, chosen ledger/capital representation exists at
   the engine level** — a choice
   [ADR-004](ADR-004-sentinel-ledger-ownership-strategy.md) explicitly
   defers (Option A/B/C) and
   [ADR-011](ADR-011-phase-1-applicability-scope-for-decision-intelligence-architecture.md)
   explicitly excludes from Phase 1 ("Phase 1 does not adopt a
   `sentinel_engine`-native Capital Pool merely because the long-term
   architecture contains one"). Until one of those is resolved, Portfolio
   Hygiene's capital-efficiency dimension has no engine-side capital
   concept to reason over.
3. Existing deterministic concentration/correlation/capital mechanisms
   (`RiskManager.sector_check()`, `_passes_correlation_gate()`,
   `bot/capital/pool.py::CapitalPool`, `get_portfolio_health()`) are
   unaffected, unchanged, and remain the current, sole, production
   mechanisms governing these concerns.

**This ADR is a placement/classification decision only. It is not an
implementation or refactoring authorization. It moves no file, changes no
import, creates no contract, designs no schema, and alters no behavior.**
This mirrors the scope discipline of ADR-015, ADR-016, ADR-019, and
ADR-020.

## 4. Portfolio Hygiene Capability Classification

Applying ADR-015's five-part classification test (§7) to Portfolio Hygiene,
at the concept level only — no contract exists to test against code:

1. **Consumers:** none today — no Portfolio Hygiene code or contract exists
   anywhere. `sector_check()`, `_passes_correlation_gate()`,
   `get_portfolio_health()`, and `CapitalPool` are separate, deterministic,
   unrelated mechanisms (see §6).
2. **Vocabulary:** "concentration warning," "correlation-overlap pruning,"
   and "capital-efficiency recommendation" are generic decision-lifecycle
   vocabulary, consistent with `Decision`/`Evidence` naming already in
   `sentinel_engine/`, not product-branded terms.
3. **Behavior:** if built, its responsibility would be reading a
   portfolio's existing decisions/positions and evidence to produce a
   cross-position, advisory reassessment — genuine engine-level behavior
   per ADR-015 §6, not product presentation/workflow, and not a
   deterministic per-symbol threshold check (which is what
   `sector_check()`/`_passes_correlation_gate()` already are).
4. **Portability:** cross-portfolio hygiene reasoning is not inherently
   trading-specific; the same reasoning shape could plausibly serve Wealth
   Intelligence's account-aggregation/portfolio-health scope, consistent
   with the platform's one-engine/multiple-products model.
5. **Coupling if retained:** none assessed — nothing is retained or moved
   by this ADR.

Per ADR-015 §7, scoring "generic/engine-level" on vocabulary and behavior
makes Portfolio Hygiene a **candidate for Core, transitional pending
design** — the same category ADR-019 assigned Stage 3 deep evaluation and
ADR-020 assigned Sell Intelligence, and the same "Transitional, leaning
toward future Core" language ADR-015 itself used for
`morning_brief_query.py` and `decision_center_query.py`. This ADR does not
finalize that classification; it records directional placement for a
future contract-design ADR to build against.

**Explicit non-invention:** this ADR does not invent an `InvestmentDecision`
class, a `PortfolioAdvisory` class, a scoring formula, a threshold, an
event type, or an API. It uses only `sentinel_engine.domain.decision.Decision`
and `bot/capital/pool.py::CapitalPool` by name, as the real objects a future
Portfolio Hygiene capability would presumably reason about — without
adding any field to either.

## 5. The Three Future Evaluation Dimensions

The following three dimensions describe conceptual intent only. No field
shape, scoring method, threshold, or algorithm is specified for any of
them; specifying any of these is explicitly out of scope (§11).

| Dimension | Conceptual meaning | Current analog (deterministic, unrelated) |
|---|---|---|
| **Concentration warnings** | Is the portfolio, as a whole, overweight a sector, symbol, or theme, beyond a single buy-time gate? | `RiskManager.sector_check()` (single-symbol, buy-time only) and `get_portfolio_health()`'s Diversification component (`_max_sector_conc()`, a score contribution, not a standalone warning) |
| **Correlation-overlap pruning** | Do existing held positions overlap enough, pairwise or in aggregate, that trimming one would reduce risk without proportionally reducing exposure? | `_passes_correlation_gate()` (buy-time-only, new-candidate-vs-existing-holdings; no pairwise or aggregate reasoning over already-held positions exists) |
| **Capital-efficiency recommendations** | Is capital deployed effectively across the portfolio (e.g. idle cash, over-reserved capital, uneven position sizing), as distinct from whether a single buy is affordable? | `CapitalPool.tradeable_cash`/`total_value` (deterministic balance tracking, no recommendation) and `get_portfolio_health()`'s Cash score (`_cash_pct()`, a safety-buffer score, not an efficiency recommendation) |

## 6. Boundary Between Current `bot/` Behavior and Future Sentinel Capability

This ADR draws an explicit line between what exists today and what is
classified, not built, by this ADR:

**Existing, unchanged, production (`bot/`, frozen by ADR-002):**
- Buy-time, single-symbol concentration gate —
  `RiskManager.sector_check()` (`SECTOR_MAP`, `MAX_SECTOR_POSITIONS`).
- Buy-time, single-symbol correlation gate —
  `_passes_correlation_gate()` (`CORRELATION_THRESHOLD`), Gate 7 in
  `bot/_main_cycle.py`'s entry gate sequence.
- Deterministic capital tracking — `bot/capital/pool.py::CapitalPool`,
  `compute_tradeable_capital()`.
- Deterministic point-weighted Portfolio Health Score —
  `bot/core/recommendation_portfolio.py::get_portfolio_health()`, combining
  VIX, sector concentration, cash percentage, momentum, and win rate into a
  single 0–100 score and letter grade.

**Future, undesigned, classified only by this ADR (`sentinel_engine/`
Core candidate):**
- Portfolio Hygiene — reasoning across the whole portfolio's held
  positions and their recorded decisions/evidence to produce
  concentration warnings, correlation-overlap pruning suggestions, and
  capital-efficiency recommendations, as distinct from any single buy-time
  gate or point-weighted score.

The two categories answer different questions: the existing mechanisms
answer "does this one new buy, or this one snapshot, cross a threshold?";
the future, classified-only capability would answer "is the portfolio, as
a whole, structured well?" This ADR does not merge, replace, deprecate, or
alter the first category in any way.

## 7. Relationship to ADR-002

This ADR touches no ADR-002-protected file. It does not authorize, propose,
or imply any change to `bot/` (including
`bot/risk/risk_manager.py`, `bot/_main_positions.py`, `bot/_main_cycle.py`,
`bot/capital/pool.py`, `bot/core/recommendation_portfolio.py`, or any other
file), `dashboard/`, `scheduler/`, `.github/workflows/*.yml`, `database/`,
or top-level `ledger/`. **This ADR does not create an ADR-002 exception.**
`sector_check()`, `_passes_correlation_gate()`, `CapitalPool`, and
`get_portfolio_health()` stay exactly as ADR-002 protects them, unchanged,
regardless of this classification.

## 8. Relationship to ADR-011 — Capital Pool Non-Reopening

**This ADR does not reopen, alter, narrow, or expand
[ADR-011](ADR-011-phase-1-applicability-scope-for-decision-intelligence-architecture.md)'s
Phase 1 applicability scope in any way**, specifically its ruling that
"Phase 1 does not adopt a `sentinel_engine`-native Capital Pool merely
because the long-term architecture contains one," and that "existing
`bot/` `CapitalPool` behavior (`bot/_main_cycle.py`) remains governed
independently, under its existing authority (ADR-002), and is unaffected."

- This ADR does **not** make a `sentinel_engine`-native Capital Pool a
  Phase 1 requirement or deliverable.
- This ADR does **not** authorize implementation of any engine-side capital
  representation, in Phase 1 or otherwise.
- Portfolio Hygiene's capital-efficiency dimension, as classified here, is
  placement-eligible **only once** such a representation is separately
  authorized — which this ADR does not create, schedule, or accelerate.
- `bot/capital/pool.py::CapitalPool` remains completely unchanged, per §6
  and §7 above.

## 9. Relationship to ADR-004 — Ledger-Ownership Non-Reopening

**This ADR does not reopen, choose among, narrow, or expand
[ADR-004](ADR-004-sentinel-ledger-ownership-strategy.md)'s deferred
Option A/B/C ledger-ownership choice.** ADR-004 remains the sole,
unchanged, Tier-2 authority on when and how that choice is made.

- Any future Portfolio Hygiene implementation that would emit ledger
  events (e.g. a concentration-warning or pruning-recommendation event) is
  contingent on a `sentinel_engine/ledger/` backend existing — which
  `LedgerStore` today does not (abstract only, per ADR-004's Context). This
  ADR does not create, imply, or accelerate that backend.
- This ADR does not select Option A, B, or C on ADR-004's behalf, and does
  not alter any of ADR-004's stated Future Decision Criteria.
- Consistent with ADR-004 itself, this ADR does not require Phase 1A's
  validation window to have closed before this classification exists — it
  only requires that closure (or an amendment to ADR-004) before any
  Portfolio Hygiene *implementation* touching the ledger could proceed.

## 10. Relationship to ADR-015, ADR-016, ADR-019, and ADR-020

**ADR-015:** This ADR applies, but does not amend,
`docs/decisions/ADR-015-sentinel-engine-core-boundary.md`'s Sentinel Engine
Core boundary rule and classification test (§6–§7) to a new subject —
Portfolio Hygiene — that ADR-015 did not address. ADR-015 classified four
specific, already-existing modules; this ADR classifies zero existing
modules and one not-yet-designed future capability. This ADR does not
reclassify any of ADR-015's four modules and does not alter its Core
boundary rule.

**ADR-016:** This ADR follows the same governance pattern ADR-016 used —
naming a concept, classifying it, and explicitly deferring implementation
without designing a contract. This ADR does not reference or depend on
ADR-016's specific subject (`ConstitutionRuleCheck`), only its pattern.

**ADR-019 and ADR-020:** This ADR is the third sibling of
`docs/decisions/ADR-019-asset-universe-screening-funnel.md` and
`docs/decisions/ADR-020-sell-intelligence.md`, produced by the same
2026-08-14 governance audit. ADR-019 classified deep Sentinel evaluation
of candidates not yet held; ADR-020 classified Sell Intelligence for
positions already held, individually; this ADR classifies Portfolio
Hygiene — reasoning across *all* held positions together — as a third,
cross-position counterpart, under the same classification test and the
same undesigned-contract discipline. This ADR does not amend ADR-019 or
ADR-020, and does not alter either of their classifications.

**Stage-numbering disambiguation:** consistent with ADR-019 §4 and
ADR-020 §9, this ADR does not introduce, reuse, or extend any "Stage N"
numbering of its own. Its references to `DECISION_INTELLIGENCE_ARCHITECTURE.md`'s
Stage 4 ("Capital Allocation") and Stage 9 ("Position Management") in §1
are descriptive citations of that document's own numbering, not this ADR's
numbering, and this ADR takes no position on how Portfolio Hygiene relates
to that document's Stage 1–12 lifecycle.

## 11. Non-Authorization

**This ADR is classification/placement-only. It authorizes no source-code
change, schema change, test change, contract design, adapter creation,
composition-root change, scoring formula, threshold, event type, API, or
behavior change of any kind.**

Specifically, this ADR does not authorize:

- Any change to `bot/` (including `bot/risk/risk_manager.py`,
  `bot/_main_positions.py`, `bot/_main_cycle.py`, `bot/capital/pool.py`,
  `bot/core/recommendation_portfolio.py`, or any other file), `dashboard/`,
  `scheduler/`, `.github/workflows/*.yml`, `database/`, or top-level
  `ledger/`.
- Any ADR-002 exception, of any scope.
- Any change to `sentinel_engine/` — no new file, no new class, no new
  `EventType` member, no new adapter, no modification of
  `sentinel_engine.domain.decision.Decision` or any other existing
  contract.
- Designing, naming, or specifying a Portfolio Hygiene contract, schema,
  scoring formula, threshold, or data shape in any form.
- Any reopening, narrowing, or expansion of ADR-011's Phase 1 applicability
  scope, including its Capital Pool non-goal.
- Any reopening, choice, or amendment of ADR-004's deferred Option A/B/C
  ledger-ownership decision.
- Any change to current concentration, correlation, or capital-allocation
  behavior — `sector_check()`, `_passes_correlation_gate()`,
  `CORRELATION_THRESHOLD`, `MAX_SECTOR_POSITIONS`, `CapitalPool`, or
  `get_portfolio_health()` scoring.
- **Any authorization to automatically rebalance, trim, prune, or otherwise
  act on any position or the portfolio as a whole.** Portfolio Hygiene, if
  ever built, would remain subject to this platform's human-governance
  principle (per `docs/AI_AGENT_GUIDELINES.md` §1: "the platform surfaces
  evidence and recommendations; it does not execute trades autonomously")
  — this ADR does not decide or alter that principle, only notes it
  applies.
- Any modification to `TRADING_INTELLIGENCE_BOUNDARY.md`,
  `docs/architecture/DECISION_INTELLIGENCE_ARCHITECTURE.md`, or any other
  existing document.
- Any modification to ADR-002, ADR-004, ADR-011, ADR-015, ADR-016,
  ADR-019, ADR-020, or any other existing ADR.
- Creation of any ADR beyond this one — no `ADR-022` or later is created
  or implied by this ADR.
- Invention of an `InvestmentDecision` class or any other new domain type.
- Any change to `applications/trading_intelligence/` or
  `applications/wealth_intelligence/`.
- Any commitment to a timeline, phase, or priority for building Portfolio
  Hygiene.

**Implementation of any part of Portfolio Hygiene — including its contract
design and the engine-side capital/ledger representation its
capital-efficiency dimension depends on — will occur later, if and when
undertaken, as a separately governed change, after the current product
work is finished. This ADR neither schedules nor blocks that future work;
it only records where it would belong.**

## 12. Deferred Implementation / Future Change Requirements

**Implementation pointer:** as with ADR-020, and unlike ADR-019's
already-named Candidate adapter, **no existing document names a
placeholder for Portfolio Hygiene.** The closest adjacent placeholder —
the Risk adapter in `TRADING_INTELLIGENCE_BOUNDARY.md` §6 — is scoped to a
single decision's `RISK_EVALUATED` translation, not cross-portfolio
reasoning, and is not repurposed by this ADR. **The implementation
location for Portfolio Hygiene therefore remains to be designed by a
future ADR.** That future ADR would need to address, at minimum:

- Whether Portfolio Hygiene's contract is a new `sentinel_engine/` module,
  and where within `sentinel_engine/`'s existing package structure (per
  [ADR-001](ADR-001-sentinel-engine-structure.md)) it would live.
- Whether a new `EventType` member (e.g. representing a portfolio-level
  warning or recommendation) is needed, alongside the eight that exist
  today, and how it would relate to ADR-004's still-deferred ledger
  backend.
- Whether/how Portfolio Hygiene requires an engine-side capital/ledger
  representation, and how that interacts with ADR-004's Option A/B/C
  choice and ADR-011's Capital Pool non-goal — this ADR does not resolve
  either.
- Whether `TRADING_INTELLIGENCE_BOUNDARY.md` should be amended (a separate
  action; not performed here) to name a fifth or sixth future adapter for
  this purpose.
- Whether/how Portfolio Hygiene's output would interact with, but not
  replace, the existing deterministic `sector_check()` /
  `_passes_correlation_gate()` / `get_portfolio_health()` mechanisms (§6)
  — this ADR does not decide whether they would run side-by-side, whether
  one would inform the other, or any other integration shape.

None of the above is designed, decided, or authorized by this ADR.

## 13. Consequences

### Positive

- Gives a name and a directional Core-vs-Product classification to a
  capability (cross-portfolio concentration/correlation/capital-efficiency
  reasoning) that previously had no architectural home anywhere in this
  repository.
- Clearly separates existing deterministic, buy-time/single-symbol
  mechanisms (unchanged, still governing) from a distinct future
  cross-portfolio reasoning capability.
- Provides a citable classification for any future ADR designing Portfolio
  Hygiene's contract, consistent with ADR-015's, ADR-019's, and ADR-020's
  precedent.
- Keeps ADR-011's Phase 1 scope and ADR-004's deferred ledger-ownership
  choice untouched and unambiguous, and states explicitly why Portfolio
  Hygiene's capital-efficiency dimension is contingent on both.
- Completes the three-part classification set from the 2026-08-14
  governance audit (ADR-019, ADR-020, ADR-021).

### Negative

- Portfolio Hygiene remains entirely undesigned; this ADR resolves only
  directional placement, not shape, contract, or timeline.
- No implementation pointer exists yet — a future ADR must both design the
  contract and decide where it lives.
- Portfolio Hygiene's capital-efficiency dimension depends on two separate
  unresolved decisions (ADR-004's ledger-ownership choice and any future
  engine-side capital representation), making it the most contingent of
  the three classified capabilities.

## 14. Acceptance Criteria

This ADR may be considered accepted only when:

- It names ADR-002, ADR-004, ADR-011, ADR-015, ADR-016, ADR-019, and
  ADR-020.
- It classifies Portfolio Hygiene as a future `sentinel_engine/` Core
  candidate, without designing its contract.
- It names and distinguishes the three evaluation dimensions
  (concentration warnings, correlation-overlap pruning, capital-efficiency
  recommendations) at the conceptual level only.
- It clearly separates existing deterministic `bot/` concentration,
  correlation, and capital mechanisms from the future classified-only
  capability.
- It explicitly states it does not reopen or alter ADR-011's Capital Pool
  non-goal.
- It explicitly states it does not reopen, choose among, or amend ADR-004's
  deferred ledger-ownership decision.
- It does not create an ADR-002 exception.
- It does not modify `TRADING_INTELLIGENCE_BOUNDARY.md` or any other
  existing document or ADR.
- It does not invent an `InvestmentDecision` class or any scoring
  formula/threshold/event contract/API.
- It does not authorize automatic rebalancing, trimming, or pruning of any
  position or the portfolio as a whole.
- It does not create any further ADR.
- It states the implementation location remains to be designed, since no
  existing placeholder names it.
- It leaves all implementation to future, separately governed work.
