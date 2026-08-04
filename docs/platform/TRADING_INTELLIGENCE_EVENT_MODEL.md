# Trading Intelligence Event Model

**Status:** Design proposal — establishes the event contract, not an implementation.
**Scope:** Documentation only. No code changes, no adapters built, no `bot/`
modifications, no `sentinel_engine/` modifications. Confirmed via `git status` on
all protected paths before and after this document was written.

**Builds on:** `TRADING_INTELLIGENCE_BOUNDARY.md` (ownership boundary),
`TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md` (field-level findings this design
resolves). Where the gap analysis left a question as "decision to make later," this
document makes that call — as design, not as authorization to implement it.

---

## 1. Trading Intelligence Internal Events

Events that originate in and stay within Trading Intelligence's own operational
domain — not proposed to cross into `sentinel_engine` at all, at least not yet:

| Event | Current source |
|---|---|
| Screening pipeline runs (including symbols that never became candidates) | `scripts/screen_universe.py` |
| Raw model inference (XGB/LSTM/RL individual outputs, ensemble internals) | `bot/strategy/` |
| Order mechanics (placement, retries, `wait_for_fill` polling, broker API responses) | `bot/execution/` |
| Capital pool bookkeeping (`deposit`/`buy`/`sell`/`withdrawal`) | `bot/capital/pool.py` `capital_ledger` |
| Data quality / health observations (`HEALTHY`/`DEGRADED`/`DOWN`) | `bot/trust_ledger/data_quality.py` |
| Constitution rule checks (6 per decision) | `bot/trust_ledger/constitution.py` |

These stay internal by default. Section 5 states which of them are proposed to
**never** cross, versus which are candidates for a future, explicit promotion.

## 2. Sentinel Engine Events

The event vocabulary already built (`sentinel_engine/events/event_types.py`), with
no bot-side emitter yet for any of them:

```
CANDIDATE_EVALUATED
DECISION_CREATED
RISK_EVALUATED
DECISION_EXECUTED
DECISION_OUTCOME_RECORDED
```

This document does not add new `EventType` values (that would be a
`sentinel_engine/` code change, out of scope here) — Section 6 flags two
candidates for a *future* addition, explicitly marked as proposed, not decided.

## 3. Events Owned By Each Subsystem

| Event / concept | Owner | Crosses boundary? |
|---|---|---|
| Candidate screening result | Trading Intelligence | Yes → `CANDIDATE_EVALUATED` |
| Decision (any action, any outcome) | Trading Intelligence | Yes → `DECISION_CREATED` |
| Execution confirmation | Trading Intelligence | Yes → `DECISION_EXECUTED` (only when a decision actually executes) |
| Portfolio risk-governor state | Trading Intelligence | Yes → `RISK_EVALUATED` (portfolio-scoped — see Section 7) |
| Position outcome (closed BUY) | Trading Intelligence | Yes → `DECISION_OUTCOME_RECORDED` |
| Constitution rule checks | Trading Intelligence | Not yet — candidate for future `EventType` addition (Section 6) |
| Data quality / health | Trading Intelligence | No — stays internal (Section 5) |
| Capital ledger (deposit/buy/sell/withdrawal) | Trading Intelligence | No — stays internal (Section 5) |
| Raw model internals, order mechanics | Trading Intelligence | No — stays internal (Section 5) |
| `Decision`/`Event`/`Evidence`/`Policy`/`Approval` contracts | Sentinel Engine | N/A — Sentinel-owned by definition |
| Ledger/projection storage | Sentinel Engine | N/A — Sentinel-owned by definition |

## 4. Translation Boundaries

- **Direction is one-way**, per `TRADING_INTELLIGENCE_BOUNDARY.md`'s Migration
  Principles: Trading Intelligence produces data in a plain-dict shape; adapters in
  `sentinel_engine/adapters/` translate it into contracts. `sentinel_engine` never
  imports or reaches into Trading Intelligence.
- **One adapter per event category**, not one general-purpose translator —
  `decision_adapter.to_decision()` already establishes this pattern. Section 6-9
  describe the shape each future adapter would need, without building them.
- **Translation happens at well-defined points**, not scattered: candidate
  screening conclusion, decision-write time, execution-confirmation time,
  cycle-end risk classification, and outcome-write time — matching the five points
  `bot/trust_ledger/` already writes at today.
- **No adapter invents data.** Per the gap analysis, `evidence_reference` and
  `risk_reference` construction depend on decisions made in Sections 6-7 below, not
  on an adapter guessing a value that doesn't exist upstream.

## 5. Events That Must NOT Cross The Boundary

- **Raw broker/execution mechanics** — order IDs, retry counts, `wait_for_fill`
  polling detail, raw broker API responses. Not governance-relevant; only the
  distilled outcome (symbol, action, fill price, timestamp) belongs in
  `DECISION_EXECUTED`'s payload.
- **Raw ML model internals** — individual XGB/LSTM/RL probability outputs, feature
  vectors, ensemble internals beyond the final `confidence` value. Proprietary
  strategy detail; `sentinel_engine` needs the decision and its confidence, not the
  model internals that produced it.
- **`data_quality_events`** — per that module's own docstring, "an operational
  health log, not an immutable decision-evidence record." Stays Trading
  Intelligence-internal; not a candidate for `EventType` promotion.
- **`capital_ledger` raw entries** — exact dollar amounts, account balances,
  deposit/withdrawal history. Consistent with the data-privacy boundary principle
  already established (`sentinel_engine` does not own raw financial account data,
  only abstracted state) — if capital context is ever needed by Sentinel Engine, it
  should be a derived value (e.g., `sizing_base`, already present in
  `risk_evaluation_events`), not the raw ledger.
- **Broker credentials / API tokens** — never applicable to any Sentinel Engine
  contract; not a design question.

## 6. Rejected Candidate Handling

Bot has **two distinct rejection points**, not one:

1. **Pre-decision rejection** — a candidate is screened but never reaches a
   decision at all (`data_available=False`, `required_models_available=False`, or
   evaluation never concludes). Only a `candidate_evaluation_events` row exists.
   **Design:** this produces `CANDIDATE_EVALUATED` only. No `DECISION_CREATED`
   follows, because bot itself never writes a `decision_events` row for it.

2. **Post-evaluation rejection** — a decision *was* made (action `HOLD`/`REJECT`),
   recorded as `decision_events.event_type = "QUALIFIED_REJECTION"`. **Design:**
   this produces `DECISION_CREATED` (a decision was genuinely made and recorded),
   but **never** `DECISION_EXECUTED` (nothing executed) and **never**
   `DECISION_OUTCOME_RECORDED` (no position was opened, so there's nothing to
   close).

This resolves the gap analysis's open question about `decision_events`' single-row
model: **every `decision_events` row produces exactly one `DECISION_CREATED`.
`DECISION_EXECUTED` is additionally emitted if and only if
`event_type == "EXECUTED"`.** This is a direct, non-lossy mapping of bot's existing
two-value `event_type` field — not a reinterpretation of it.

## 7. Portfolio-Level Risk Evaluation Model

The gap analysis found `risk_evaluation_events` has no `decision_id`/`asset`
column — it's written once per cycle, not once per decision. **Design decision:**
do not force risk evaluation into a decision-scoped shape it doesn't have.

- `RISK_EVALUATED` stays portfolio-scoped, matching reality: one event per cycle
  (`from_state`, `to_state`, `trigger_reason`, `recommended_position_size`,
  `actual_position_size`), not one per decision.
- **`Decision.risk_reference` is many-to-one**: every decision made within a given
  cycle references that cycle's single `RISK_EVALUATED` event (its `event_id`).
  Multiple decisions in the same cycle share the same `risk_reference` — this is
  correct, not a collision, because they were genuinely all made under the same
  risk-governor state.
- This requires that the risk evaluation for a cycle happens (and its event_id is
  known) before any decision in that cycle is finalized, which already matches
  `bot/main.py`'s cycle ordering (risk evaluation recorded at cycle end today —
  see `bot/main.py:442`'s `record_risk_evaluation_safe` call; the *reference* would
  need the risk state to be known at decision-time, not cycle-end, which is a
  sequencing question for whoever eventually designs the adapter, not resolved by
  this document).

## 8. Execution Lifecycle Model

Conceptual state machine (field names for the execution payload are **not**
finalized — the gap analysis flagged that `alpaca_client.py`/`paper_executor.py`'s
actual fill-dict shape was not read; this document does not invent it):

```
decision_events row written (action=BUY/SELL, event_type=EXECUTED)
        |
        v
DECISION_CREATED  (always, per Section 6)
        |
        v
Executor.buy() / Executor.sell() called  [Trading Intelligence-internal, Section 5]
        |
        v
wait_for_fill() confirms                 [Trading Intelligence-internal, Section 5]
        |
        v
DECISION_EXECUTED (payload: symbol, action, distilled fill data — exact fields TBD)
```

`DECISION_EXECUTED`'s payload should carry only the distilled result (what
executed, at what price, when) — not the order mechanics that produced it, per
Section 5. Finalizing exact field names requires reading the executor
implementations first (gap analysis recommendation #5) — explicitly deferred, not
guessed here.

## 9. Outcome Lifecycle Model

Matches `bot/trust_ledger/outcomes.py`'s existing (asymmetric, intentional) design
exactly — not a new model:

```
DECISION_EXECUTED (BUY)  →  position opens
        |
        (time passes, zero or more other decisions occur)
        |
DECISION_EXECUTED (SELL) →  a separate, independent decision/event pair
        |
        v
DECISION_OUTCOME_RECORDED
   decision_id → the ORIGINAL BUY's decision_id, not the SELL's
   payload: gross_return, net_return, holding_period_days, cost_breakdown
```

**Design constraints, stated explicitly:**
- Only `BUY` decisions ever receive a `DECISION_OUTCOME_RECORDED` event. `SELL`
  decisions get their own `DECISION_CREATED`/`DECISION_EXECUTED` pair but never
  their own outcome — they *trigger* the original BUY's outcome instead.
  `HOLD`/`REJECT`/`QUALIFIED_REJECTION` decisions never receive one either (no
  position was ever opened).
  - This means a `Decision` (the BUY) can have an `Event` referencing it
  (`DECISION_OUTCOME_RECORDED`) written well after the `Decision` itself was
  created — the outcome is not part of the same transaction as the decision, and
  may not exist at all if the position is still open.

## Summary — What This Document Resolves vs. Leaves Open

**Resolved (design decisions made here):**
- `DECISION_CREATED`/`DECISION_EXECUTED` split (Section 6)
- Pre- vs. post-evaluation rejection handling (Section 6)
- `RISK_EVALUATED` stays portfolio-scoped; `risk_reference` is many-to-one (Section 7)
- Outcome asymmetry (BUY-only, deferred-in-time) (Section 9)
- What must never cross the boundary (Section 5)

**Explicitly left open:**
- Exact `DECISION_EXECUTED` payload field names (requires reading
  `alpaca_client.py`/`paper_executor.py` — not done in this pass)
- Whether constitution-enforcement events get promoted to a new `EventType` (Section 3/5)
- `evidence_reference` construction (FK-passthrough vs. synthesized `Evidence` —
  still open per the gap analysis, not addressed by this document)
- The cycle-ordering question in Section 7 (risk state known before vs. at decision time)

None of the above requires touching `bot/`, `scheduler/`, or any protected path —
all remaining work is `sentinel_engine/`-side design (new dataclasses, possible
`EventType` additions, adapter functions), still subject to its own future ADR
before implementation begins.
