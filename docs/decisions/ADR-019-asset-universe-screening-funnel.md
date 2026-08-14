# ADR-019 — Asset Universe Ingestion & 3-Stage Screening Funnel (Classification / Placement Only, Implementation Deferred)

**Status:** Accepted — Implementation Deferred
**Date:** 2026-08-14
**Decision Type:** Architecture / Governance — Placement Classification Only
**Related ADRs:** ADR-001, ADR-002, ADR-011, ADR-015

---

## 1. Context

A read-only architecture/governance audit (2026-08-14) traced how asset
screening exists today, in code and in documentation, ahead of any decision
about a "3-stage funnel."

**In documentation:** `docs/architecture/DECISION_INTELLIGENCE_ARCHITECTURE.md`
(gitignored, Tier-4/non-binding per `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`)
defines Stage 1 as a single "Opportunity Detection" stage — market signal
evaluation, candidate screening filters (volume, liquidity, data quality),
and thesis-trigger checks, all in one undifferentiated step. No 3-stage
funnel (broad screening → quantitative shortlist → deep intelligence
evaluation) exists in any tracked or untracked document today.

**In code:** the current asset-screening implementation lives entirely in
Trading Intelligence's product territory, all inside `bot/`, frozen by
[ADR-002](ADR-002-bot-runtime-protection.md):

- `scripts/screen_universe.py` and `scripts/_screener_helpers.py` — the
  screening entry points.
- `bot/strategy/` — signal generation (XGBoost, LSTM, RL, ensemble, regime
  classification, sentiment, macro) that downstream stages of screening and
  decisioning consume.
- The 10-gate Entry Gate Suite (per `docs/REQUIREMENTS.md`: VIX halt /
  regime / volume / 15-min RSI / RS / open-order / earnings / correlation /
  wash-sale / stop re-entry + Kelly sizing) — deterministic filtering,
  already in production.

**In `sentinel_engine/`:** no candidate-screening or asset-universe contract
exists. `docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md` §6 ("Future Adapter
Responsibilities") already names a **Candidate adapter** — "would translate
screening output into `Evidence`/`CANDIDATE_EVALUATED`" — as one of four
adapters that are explicitly "not designed, not implemented, requires future
ADR/design." `sentinel_engine.events.event_types.EventType.CANDIDATE_EVALUATED`
already exists as an enum member (per `sentinel_engine/events/event_types.py`,
confirmed in `TRADING_INTELLIGENCE_BOUNDARY.md` §1), but nothing emits it —
`TRADING_INTELLIGENCE_BOUNDARY.md` §4 lists its proposed owner as "Trading
Intelligence screening layer... Future proposal — not implemented."

No `InvestmentDecision` class exists anywhere in this repository. The real,
existing decision-lifecycle objects are `sentinel_engine.domain.decision.Decision`
(engine-side, frozen dataclass: `decision_id`, `symbol`, `action`, `timestamp`,
`confidence`, `evidence_reference`, `risk_reference`) and
`bot/trust_ledger/decisions.py` (product-side, frozen by ADR-002, the live
production writer of decision rows). This ADR uses only these real names.

`applications/trading_intelligence/` exists as a built skeleton (contracts,
projections, services, adapters, Decision Center UI) but is not fed by
`bot/`; no screening code has been moved or extracted into it. Its eventual
role as Trading Intelligence's product home is unaffected by, and not
accelerated by, this ADR.

## 2. Governing Authority

Per `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`, Architecture Decision
Records are Tier-2 authority, superseding any conflicting document below
them (Tier-3 `docs/platform/`/`docs/implementation/` docs; Tier-4 gitignored
`docs/architecture/*` drafts). That document's conflict-resolution rule
applies here directly: *"A new document that conflicts with an existing
authoritative doc does not silently coexist with it. Write a new ADR... that
references both and states which wins and why."* This ADR is written under
that rule — it references ADR-001, ADR-002, ADR-011, and ADR-015, states
that it does not conflict with any of them, and states precisely what new
ground it covers that none of them already decided: a placement
classification for a 3-stage screening funnel that no prior ADR names.

## 3. Decision Summary

This ADR establishes, for future architecture only, where a 3-stage asset
screening funnel — if and when it is built — would belong:

1. **Stage 1 (broad deterministic screening/filtering)** and **Stage 2
   (quantitative/factor shortlisting)** are classified as **Trading
   Intelligence product territory** — extensions of the existing
   `scripts/screen_universe.py` / `bot/strategy/` / Entry Gate Suite
   pattern, and eventually `applications/trading_intelligence/` once Phase 2
   extraction begins under its own, separately governed ADR-002 exception.
2. **Stage 3 (deep Sentinel Intelligence evaluation)** is classified as a
   **future `sentinel_engine/` Core candidate**, per the classification test
   `docs/decisions/ADR-015-sentinel-engine-core-boundary.md` §7 establishes,
   corresponding to the already-named but undesigned "Candidate adapter" in
   `TRADING_INTELLIGENCE_BOUNDARY.md` §6.

**This ADR is a placement/classification decision only. It is not an
implementation or refactoring authorization. It moves no file, changes no
import, creates no contract, and alters no behavior.** This mirrors the
scope discipline of ADR-015 (Sentinel Engine core boundary classification)
and ADR-016 (contract-shape classification, implementation deferred).

## 4. Stage Definitions (Documentation Only)

These definitions describe proposed future terminology and boundary intent.
They do not specify field shapes, contracts, or implementations.

| Stage | Description | Territory |
|---|---|---|
| **Stage 1 — Broad deterministic screening/filtering** | Coarse universe reduction by hard, deterministic filters (liquidity, volume, data quality, halt/regime status) — the same category of filter already implemented by `scripts/screen_universe.py` and the Entry Gate Suite. | Trading Intelligence product (existing `bot/`, future `applications/trading_intelligence/`) |
| **Stage 2 — Quantitative/factor shortlisting** | Ranking or shortlisting the Stage-1-reduced set by quantitative/factor signals — the same category of output already produced by `bot/strategy/`'s model ensemble and factor scoring. | Trading Intelligence product (existing `bot/`, future `applications/trading_intelligence/`) |
| **Stage 3 — Deep Sentinel Intelligence evaluation** | Evidence-driven, model-reasoning evaluation of the Stage-2 shortlist, analogous in spirit to the engine's existing `Decision`/`Evidence`/`Governance` contracts. **No contract, schema, or implementation is designed by this ADR.** | Future `sentinel_engine/` Core candidate (undesigned) |

**Numbering disambiguation:** the "Stage 1/2/3" numbering above is a local
scheme for this screening-funnel concept only. It is independent of, and
must not be confused with, `docs/architecture/DECISION_INTELLIGENCE_ARCHITECTURE.md`'s
Stage 1–12 decision lifecycle, in which Stage 3 is Thesis Formation, Stage
11 is Investment Memory, and Stage 12 is Feedback to Future Decisions. This
ADR takes no position on whether or how its own Stage 1/2/3 numbering
relates to that document's Stage 1–12 numbering.

## 5. Classification Test Applied to Stage 3 (per ADR-015 §7)

Applying ADR-015's five-part test to Stage 3 candidate evaluation, at the
concept level only (no contract exists to test against code):

1. **Consumers:** none today — no Stage 3 code or contract exists anywhere.
2. **Vocabulary:** "deep intelligence evaluation of a candidate" is
   generic/decision-lifecycle vocabulary, not product-branded — consistent
   with `Decision`/`Evidence` naming already in `sentinel_engine/`, not with
   product-specific terms like Wealth Intelligence's "Investor"/"Morning
   Brief" (per ADR-015 §8).
3. **Behavior:** if built, its responsibility would be reading evidence and
   producing a reasoned evaluation — genuine engine-level behavior per
   ADR-015 §6's classification rule, not product presentation/workflow.
4. **Portability:** an evidence-driven evaluation capability is not
   inherently trading-specific; the same reasoning shape could plausibly
   serve Wealth Intelligence or future products, consistent with the
   platform's one-engine/multiple-products model (`AARA_ARCHITECTURE_AUTHORITY.md`
   §"Product model").
5. **Coupling if retained:** none assessed — nothing is retained or moved by
   this ADR.

Per ADR-015 §7, scoring "generic/engine-level" on vocabulary and behavior
makes Stage 3 a **candidate for Core, transitional pending design** — the
same "Transitional, leaning toward future Core" classification ADR-015 used
for `morning_brief_query.py` and `decision_center_query.py`. This ADR does
not finalize that classification; it records the directional placement for
a future contract-design ADR to build against.

Stages 1 and 2 are not subjected to this test: their existing implementation
(`scripts/screen_universe.py`, `bot/strategy/`) already carries
trading-specific vocabulary, product-branded gate logic, and direct
`bot/`-internal coupling — unambiguously Product territory under ADR-015's
same rule (§6.4: "Product-specific... workflows belong outside
`sentinel_engine/`").

## 6. Relationship to ADR-001

`docs/decisions/ADR-001-sentinel-engine-structure.md` establishes
`sentinel_engine/` as a separate package, independent of `bot/`,
`dashboard/`, and `database/`, giving "cleaner isolation for multiple future
products... consuming one shared engine." This ADR is consistent with, and
does not amend, ADR-001: if Stage 3 is ever built, ADR-001 already dictates
it would live inside `sentinel_engine/`'s existing package structure, not a
new top-level package. This ADR does not decide Stage 3's internal module
location within `sentinel_engine/` (e.g. `adapters/`, `services/`) — that is
future contract-design work.

## 7. Relationship to ADR-002

This ADR touches no ADR-002-protected file. It does not authorize, propose,
or imply any change to `bot/` (including `scripts/screen_universe.py`,
`bot/strategy/`, or the Entry Gate Suite), `dashboard/`, `scheduler/`,
`.github/workflows/*.yml`, `database/`, or top-level `ledger/`. **This ADR
does not create an ADR-002 exception.** Stages 1 and 2 remaining classified
as Trading Intelligence product territory does not change their current
physical location inside `bot/`, which stays exactly as ADR-002 protects it,
unchanged, until a future, separately governed ADR-002 exception or the
eventual Phase 2 extraction (per `CODEBASE_MIGRATION_MATRIX.md`, itself
gated by ADR-002).

## 8. Relationship to ADR-011 — Explicit Non-Reopening

**This ADR does not reopen, alter, narrow, or expand ADR-011's Phase 1
applicability scope in any way.**
`docs/decisions/ADR-011-phase-1-applicability-scope-for-decision-intelligence-architecture.md`
remains the sole, unchanged, Tier-2 authority on what current Phase 1
`sentinel_engine/` implementation work requires. ADR-011 states that Phase 1
does not require Stage 3's structured Thesis or Conviction, Stage 11's
Investment Memory, Stage 12's feedback loop, or a `sentinel_engine`-native
Capital Pool. This ADR does not require, imply, schedule, or accelerate any
of those either. Stage 3 "deep Sentinel Intelligence evaluation," as
classified here, is **future/target architecture, not a Phase 1
requirement** — exactly the same status ADR-011 already assigns to
Thesis/Conviction structure. This ADR introduces no new Phase 1 obligation
of any kind.

## 9. Relationship to ADR-015

This ADR applies, but does not amend, `docs/decisions/ADR-015-sentinel-engine-core-boundary.md`'s
Sentinel Engine Core boundary rule and classification test (§6–§7) to a new
subject — Stage 3 candidate evaluation — that ADR-015 did not address.
ADR-015 classified four specific, already-existing modules
(`investor_presenter.py`, `investor_workspace.py`, `morning_brief_query.py`,
`decision_center_query.py`); this ADR classifies zero existing modules and
one not-yet-designed future capability. This ADR does not reclassify any of
ADR-015's four modules and does not alter its Core boundary rule.

## 10. Deferred Implementation / Implementation Pointer

`docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md` §6 ("Future Adapter
Responsibilities") already names the correct future location for the
boundary-crossing side of Stage 3:

> "Candidate adapter — would translate screening output into
> `Evidence`/`CANDIDATE_EVALUATED`."

This ADR designates that already-named, already-undesigned Candidate
adapter as the eventual home for Stage 3's `bot`/`applications/trading_intelligence`
→ `sentinel_engine` boundary crossing, once a future ADR designs its
contract — following the same pattern by which
[ADR-012](ADR-012-sentinel-engine-evidence-intake-for-bot-model-outputs.md)
later designed the previously-named-but-undesigned Evidence translation
boundary. **This ADR does not modify `TRADING_INTELLIGENCE_BOUNDARY.md`.**
It only records, for future reference, that this ADR is the governance
record that first assigns architectural direction to that already-named
placeholder.

`sentinel_engine.events.event_types.EventType.CANDIDATE_EVALUATED` already
exists as an enum member with no emitter. A future contract-design ADR for
the Candidate adapter would be the natural point to decide whether Stage 3
evaluation is what finally emits it — this ADR does not decide that either.

## 11. Non-Authorization

**This ADR is classification/placement-only. It authorizes no source-code
change, schema change, test change, contract design, adapter creation,
composition-root change, or behavior change of any kind.**

Specifically, this ADR does not authorize:

- Any change to `bot/` (including `scripts/screen_universe.py`,
  `scripts/_screener_helpers.py`, `bot/strategy/`, or the Entry Gate Suite),
  `dashboard/`, `scheduler/`, `.github/workflows/*.yml`, `database/`, or
  top-level `ledger/`.
- Any ADR-002 exception, of any scope.
- Any change to `sentinel_engine/` — no new file, no new class, no new
  `EventType` member, no new adapter, no modification of
  `sentinel_engine.domain.decision.Decision` or any other existing
  contract.
- Designing, naming, or specifying the Stage 3 contract, schema, or data
  shape in any form.
- Creation, modification, or wiring of the Candidate adapter named in
  `TRADING_INTELLIGENCE_BOUNDARY.md` §6.
- Any modification to `TRADING_INTELLIGENCE_BOUNDARY.md`,
  `docs/architecture/DECISION_INTELLIGENCE_ARCHITECTURE.md`, or any other
  existing document.
- Any modification to ADR-001, ADR-002, ADR-011, ADR-015, or any other
  existing ADR.
- Any reopening, narrowing, or expansion of ADR-011's Phase 1 applicability
  scope.
- Creation of `ADR-020` (Sell Intelligence), `ADR-021` (Portfolio Hygiene),
  or any other ADR — those remain separate, future, independently governed
  work, not created or pre-authorized here.
- Invention of an `InvestmentDecision` class or any other new domain type.
- Any change to `applications/trading_intelligence/` or
  `applications/wealth_intelligence/`.
- Any commitment to a timeline, phase, or priority for building Stage 3.

**Implementation of any part of the 3-stage funnel — including Stage 3's
contract design — will occur later, if and when undertaken, as a separately
governed change, after the current product work is finished. This ADR
neither schedules nor blocks that future work; it only records where it
would belong.**

## 12. Future Change Requirements

Any of the following require their own, separate, future ADR — none are
authorized here:

- Designing Stage 3's contract (fields, evidence shape, evaluation output
  shape).
- Designing and implementing the Candidate adapter named in
  `TRADING_INTELLIGENCE_BOUNDARY.md` §6.
- Wiring an emitter for `EventType.CANDIDATE_EVALUATED`.
- Formally splitting the current single-stage screening implementation
  (`scripts/screen_universe.py`) into distinct Stage 1 / Stage 2 code paths.
- Extracting Stage 1/2 screening code into
  `applications/trading_intelligence/` (gated by ADR-002's existing "Lifting
  This Protection" checklist).
- `ADR-020` (Sell Intelligence) and `ADR-021` (Portfolio Hygiene), covering
  the two other topics identified in the 2026-08-14 governance audit — both
  remain unstarted and are not created by this ADR.
- Updating `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`'s document-roles
  table to register this ADR.

## 13. Consequences

### Positive

- Gives a name and a directional home to a screening-funnel concept that
  previously existed only as an undifferentiated single stage in a
  non-binding, gitignored document.
- Resolves, for future governance, which parts of the funnel are Product
  territory versus future Core territory, without requiring the Stage 3
  contract to be designed first.
- Provides a citable classification for any future ADR designing the
  Candidate adapter or Stage 3 contract, consistent with ADR-015's
  precedent.
- Keeps ADR-011's Phase 1 scope untouched and unambiguous.

### Negative

- Stage 3 remains entirely undesigned; this ADR resolves only its
  directional placement, not its shape.
- The existing single-stage screening implementation is not reorganized —
  Stage 1/Stage 2 remain conceptually, not physically, distinguished until
  a future change.
- Two related topics from the same governance audit (Sell Intelligence,
  Portfolio Hygiene) remain fully unaddressed.

## 14. Acceptance Criteria

This ADR may be considered accepted only when:

- It names ADR-001, ADR-002, ADR-011, and ADR-015.
- It classifies Stage 1 and Stage 2 as Trading Intelligence product
  territory.
- It classifies Stage 3 as a future `sentinel_engine/` Core candidate,
  without designing its contract.
- It explicitly states it does not reopen or alter ADR-011's Phase 1 scope.
- It does not create an ADR-002 exception.
- It does not modify `TRADING_INTELLIGENCE_BOUNDARY.md` or any other
  existing document or ADR.
- It does not invent an `InvestmentDecision` class.
- It does not create ADR-020 or ADR-021.
- It leaves all implementation to future, separately governed work.
