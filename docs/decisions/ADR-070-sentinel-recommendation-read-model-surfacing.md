# ADR-070 — Sentinel Recommendation Read-Model Surfacing

**Status:** Accepted — scope limited to the read-side propagation architecture
in §2–§10 and the display-semantics rules in §6–§9; see `## Acceptance`. Per
ADR-058 D2, this ADR is authoritative once it is tracked on the default branch
with `Status: Accepted` and landed under the repository's applicable write/merge
controls — carried by the commit that lands this acceptance (recorded in the
Status Log). **Acceptance authorizes the architecture, not an implementation** —
the Sprint 3 implementation is a separate subsequent batch bound by §3, §13,
§15 and §16, and authorizes nothing outside this ADR's defined scope.
**Date Proposed:** 2026-09-09
**Date Accepted:** 2026-09-09
**Decision Type:** Architecture / Governance — read-side propagation of two
already-ratified fields (`Decision.action_source`, `Evidence.polarity`) into the
Trading Intelligence read models, plus provenance-gated Decision Center display
semantics. No new intelligence, no persistence backend, no execution, no
approval, no `bot/` change, no ADR-002 exception.
**Related ADRs:** ADR-001, ADR-002, ADR-004, ADR-044, ADR-058, ADR-064,
ADR-065, ADR-066, ADR-067, ADR-068, ADR-069.

---

## 1. Context

### 1.1 What Sprint 2 (ADR-066 → ADR-069) produced

- **ADR-066** ratified `EvidencePolarity {SUPPORTING, CONTRADICTING}`,
  `Evidence.polarity`, the `ActionSource`/`DecisionAction` vocabulary family,
  and the optional `Decision` fields as **inert representation only**.
- **ADR-067** established the causal `Decision` lifecycle: one `decision_id`
  minted pre-gate, one shared **process-local, in-memory** composition pair
  (`sentinel_engine/composition/decision_lifecycle.py`), one
  `DecisionProjection` walking
  `DECISION_CREATED → EVIDENCE_ATTACHED → GOVERNANCE_EVALUATED → DECISION_EXECUTED`.
- **ADR-068 (B1)** made `evidence_adapter.to_evidence_records()` populate each
  `MODEL_OUTPUT` record's `polarity` by a pure, signal-only map
  (`BUY → SUPPORTING`, `SELL → CONTRADICTING`, `HOLD`/other `→ None`).
  Classification only — no aggregation (ADR-068 §3.9).
- **ADR-069 (B2)** authorized `recommendation_adapter.recommend_entry_action()`
  to apply a single fixed three-model unanimity rule and author
  `Decision.action ∈ {BUY, WAIT}` with `Decision.action_source = "SENTINEL"`
  (fallback → `("BUY", "STRATEGY")`). Zero execution / approval / sizing
  effect. ADR-069 §7 fixes `WAIT` as an **inert label**; §9 fixes
  `Decision.confidence` as an **uncalibrated ensemble model score**; §17 and
  §17.1 flag that surfacing `action = "WAIT"` and `action_source` into
  `applications/trading_intelligence` UI copy is *"a separate
  `applications/trading_intelligence` concern, not authorized or required
  here."* **ADR-070 is that separate concern.**

### 1.2 The gap — verified against HEAD `eda3bad`

The write side already carries both new fields in its event payloads:

| Field | Written at | Verified |
|---|---|---|
| `action_source` | `DECISION_CREATED` event payload | `sentinel_engine/services/decision_service.py::create_decision()` payload key `"action_source"` (alongside `"symbol"`, `"action"`) |
| `polarity` | `EVIDENCE_ATTACHED` event payload | `sentinel_engine/services/evidence_service.py::associate_evidence()` payload key `"polarity"` (alongside `"data"`) |

The read side does **not** carry either:

- `sentinel_engine/projections/decision_projection.py::DecisionProjection` has
  eight fields; `action_source` is not among them. `advance_status()`
  (`projection_repository.py`) only ever `replace(...)`s `status` / `updated_at`.
- `sentinel_engine/queries/decision_query.py::EvidenceSummary` is deliberately
  narrow (`evidence_id`, `evidence_type`, `source`, `attached_at`) — no
  `polarity`, no `data`.
- `applications/trading_intelligence/contracts/decision_contract.py::DecisionContract`
  and `.../projections/decision_view.py::DecisionView` carry no `action_source`.
- `applications/trading_intelligence/projections/evidence_entry.py::EvidenceEntry`
  carries no `polarity`.
- No Decision Center view-model surface distinguishes a Sentinel-authored
  recommendation from an interpreted strategy decision, renders a `WAIT`
  abstention, or attaches the uncalibrated-score qualifier to a displayed
  `confidence`.

Consequently the B1/B2 intelligence is invisible to any human, and would
remain invisible even if ADR-004 selected a persistent backend tomorrow,
because the contracts do not express it.

### 1.3 Persistence is out of scope and stays out

`ProjectionRepository` has **no concrete backend** anywhere in the repository;
ADR-004 defers that choice. Every existing `sentinel_engine` and
`applications/trading_intelligence` read-side test exercises in-memory fakes
(`_InMemoryProjectionRepository`, `_InMemoryLedgerStore`). ADR-070 changes none
of this and selects no ADR-004 option (§11).

## 2. Decision

Authorize, and only this:

1. **Propagate `Decision.action_source`** from the `DECISION_CREATED` event
   payload into `DecisionContract` and `DecisionView` as one additive optional
   field, read via the already-optional `DecisionQuery` collaborator on
   `SentinelProjectionDecisionSource` (§10 seam decision). Value preserved
   exactly: `"SENTINEL"`, `"STRATEGY"`, or `None`. Never fabricated.
2. **Propagate `Evidence.polarity`** from the `EVIDENCE_ATTACHED` event payload
   into `EvidenceEntry` as one additive optional field, read via
   `SentinelEvidenceSource`'s existing `timeline.events` payload read (the same
   mechanism it already uses for `Evidence.data`). Value preserved exactly:
   `"SUPPORTING"`, `"CONTRADICTING"`, or `None`. Never aggregated.
3. **Establish provenance-gated Decision Center display semantics** (§6–§9) as a
   decision of record: the recommendation-terminology rule, the `WAIT`
   inert-label rule, the uncalibrated-confidence qualifier rule, and the
   per-model polarity display rule — expressed in
   `applications/trading_intelligence/ui/decision_center/` view-model code
   (framework-independent dataclasses / display strings; `dashboard/` untouched).

No `sentinel_engine` domain, projection, query, event, or service contract is
changed by this ADR (§10). No `bot/` file is changed (§8). No ADR-002 exception
is created or required.

## 3. Scope

**In scope — authorized by this ADR (design only; implementation is a later
batch bound by §15):**

- The two additive optional fields in §2.1 / §2.2 on the three
  `applications/trading_intelligence` read models named there.
- The read-adapter mapping changes in `SentinelProjectionDecisionSource` and
  `SentinelEvidenceSource` needed to populate them from existing event
  payloads.
- The Decision Center view-model / display-semantics rules in §6–§9.
- The test contract in §15.

**Out of scope — not authorized, not touched:**

- Any change to `DecisionProjection`, `DecisionQuery` / its summary
  dataclasses, `Decision`, `Evidence`, `EvidencePolarity`, `ActionSource`,
  `DecisionAction`, any service, any event type, any `DecisionState` /
  `ApprovalStatus` member (§13).
- `DecisionCenterQuery` / `DecisionCenterView` / `MorningBriefQuery` /
  `MorningBrief` and the Morning Brief UI surface — a parallel
  `sentinel_engine`-internal read path not on the Decision Center adapter
  chain; adding `action_source` there is a `sentinel_engine` contract change
  and is deferred as optional future consistency work (§17).
- Any `bot/`, `dashboard/`, `scheduler/`, `database/`, `ledger/`,
  `.github/workflows/` change (§8, §12).
- Any persistence backend / ADR-004 option (§11).
- Everything in §14.

## 4. Field propagation rules

### 4.1 `action_source`

- Source of truth: the `DECISION_CREATED` event payload key `"action_source"`
  (written by `DecisionService.create_decision()`).
- Path: `DecisionQuery.get_decision_timeline(decision_id).events` → the single
  `DECISION_CREATED` event → `payload.get("action_source")` →
  `DecisionContract.action_source` → `DecisionView.action_source`.
- Type: `Optional[str] = None` on both contracts.
- Preservation: the string is carried **verbatim**. No normalization, no
  defaulting to `"STRATEGY"`, no inference from `action`. Absent key or absent
  `DecisionQuery` collaborator → `None`.
- Legality: exactly the three states ADR-069 §8.4 fixed — `"SENTINEL"`,
  `"STRATEGY"`, `None`. A read model that encounters any other value passes it
  through unchanged (it is display data, not a branch key) but the view model
  (§6) treats anything other than `"SENTINEL"` / `"STRATEGY"` as `None`-equivalent
  ("legacy / unknown / unspecified").

### 4.2 `polarity`

- Source of truth: the `EVIDENCE_ATTACHED` event payload key `"polarity"`
  (written by `EvidenceService.associate_evidence()`).
- Path: `DecisionQuery.get_decision_timeline(decision_id).events` → each
  `EVIDENCE_ATTACHED` event → `payload.get("polarity")`, keyed to the matching
  `timeline.evidence` summary by `evidence_id` (identical to how
  `SentinelEvidenceSource._data_by_evidence_id()` already keys `data`) →
  `EvidenceEntry.polarity`.
- Type: `Optional[str] = None` on `EvidenceEntry`.
- Preservation: carried **verbatim** per evidence record. No aggregation, no
  net value, no count, no derived field (§9, §13). Absent key → `None`.

### 4.3 Historical compatibility

`payload.get(...)` returns `None` for every pre-B1 / pre-B2 event; every new
field defaults to `None`. **No `DecisionProjection`, `decision_events` row,
`EVIDENCE_ATTACHED` event, or historical record is rewritten, backfilled, or
migrated.** A decision or evidence record created before Sprint 2 surfaces as
`action_source = None` / `polarity = None` forever, and the view model renders
that as the honest "legacy / unknown" / "polarity unavailable" state.

## 5. (reserved — see §10 for the seam decision)

## 6. Recommendation terminology

The Decision Center view model applies exactly this rule, and no other, when
choosing how to describe a decision:

```
action_source == "SENTINEL"   → "Sentinel recommendation"
action_source == "STRATEGY"   → "interpreted strategy decision"
action_source is None (or any other value)
                              → "interpreted strategy decision"
                                 (legacy / unknown / unspecified provenance)
```

- The label **"Sentinel recommendation"** is reachable **only** through
  `action_source == "SENTINEL"`. It is never applied on the strength of a
  `Decision` merely existing, a `DecisionProjection` merely existing, a
  non-`None` `confidence`, or attached evidence.
- This distinction must survive **every** mapping layer: event payload →
  `DecisionContract` → `DecisionView` → view model → any rendered string. A
  guard test asserts it at each hop (§15).
- ADR-068 §3.1's mandate ("interpreted strategy decision, never Sentinel
  recommendation") remains in force for every `action_source != "SENTINEL"`
  decision. ADR-070 lifts it **only** for `action_source == "SENTINEL"`,
  exactly as ADR-069 §17 anticipated.

## 7. WAIT semantics

A Sentinel-authored `WAIT` (`action == "WAIT"` with
`action_source == "SENTINEL"`) means, and is displayed as, exactly:

> **Sentinel does not concur at this time.**

It is **informational and inert**. The view model and any surface built on it
**must not**:

- present it as a rejection, a block, or an execution veto;
- present it as, or wire it to, a schedule, timer, reminder, notification,
  alert, or badge that decays / refreshes;
- trigger, offer, or imply re-evaluation, a retry, or a "check back later"
  affordance;
- imply Sentinel predicts, expects, or forecasts a future `BUY`;
- render an urgency cue (countdown, "act now", pulsing, colour-as-alarm).

`WAIT` is a calm, static statement about the present evidence. It carries no
tense beyond "at this time". Guard tests assert the absence of every affordance
above (§15).

## 8. Confidence semantics

`Decision.confidence` (surfaced as `DecisionContract.confidence` /
`DecisionView.confidence`) **remains** the value ADR-069 §9 fixed: the existing
`ensemble_confidence(...)` output — an **uncalibrated ensemble model score**.

- ADR-070 does not recompute, rescale, calibrate, reinterpret, threshold, or
  relabel it, and introduces no second confidence value.
- Any surface that displays it **must keep the qualifier available** — the
  displayed value is accompanied (inline, tooltip, or adjacent caption) by
  wording to the effect of *"uncalibrated ensemble model score"*.
- The following words **must not** appear as a description of this value in any
  Decision Center surface: *probability*, *probability of success / of a win /
  of correctness*, *calibrated confidence*, *likelihood*, *certainty*,
  *recommendation confidence*, *Sentinel's confidence*. A guard test greps the
  view-model output strings for these (§15).
- This holds **especially** on a surface that also shows
  `action_source == "SENTINEL"` — a `SENTINEL` badge next to a percentage must
  not read as "Sentinel is X% sure".

## 9. Evidence polarity semantics

The view model may expose, per `MODEL_OUTPUT` evidence record, exactly one of:

```
polarity == "SUPPORTING"      → "this model supported the BUY"
polarity == "CONTRADICTING"   → "this model contradicted the BUY"
polarity is None              → "polarity unavailable"
```

It **must not** compute, store, or display any of:

- a count of supporting models; a count of contradicting models;
- a majority / minority determination; a "k of n" figure;
- a unanimity flag or unanimity score;
- a net polarity, aggregate polarity, or polarity total;
- an evidence score; a confidence derived from evidence; a corroboration
  score; a weighted-evidence value; a voting result / tally.

Each record's polarity is rendered **in isolation**, mirroring ADR-068 §3.9's
classification-only boundary. The B2 three-model unanimity rule stays
authoritative and private to `recommendation_adapter` under ADR-069; ADR-070
surfaces only the already-computed per-record `polarity` values, never the
predicate or its inputs. A guard test asserts no aggregate/derived value is
produced (§15).

## 10. Read-side seam decision

**Decision: carry `action_source` from the `DECISION_CREATED` event payload,
read through the existing optional `DecisionQuery` collaborator on
`SentinelProjectionDecisionSource` — NOT as a new field on `DecisionProjection`.
Carry `polarity` from the `EVIDENCE_ATTACHED` event payload through
`SentinelEvidenceSource`'s existing `timeline.events` read — NOT as a new field
on `EvidenceSummary`.**

### 10.1 Why this seam

- **Zero `sentinel_engine` contract change.** Both values are *already* in the
  event payloads. `SentinelProjectionDecisionSource.__init__` *already* accepts
  an optional `DecisionQuery` and *already* consults it in `_to_contract()`
  (for `approval_status`, via `_latest_approval_status()`), on both the
  `get_decision()` and `list_decisions()` paths. `SentinelEvidenceSource`
  *already* reads `EVIDENCE_ATTACHED` payloads from `timeline.events` (for
  `Evidence.data`, via `_data_by_evidence_id()`). Adding `action_source` /
  `polarity` extraction is the identical move in each case.
- **Consistent with the dominant established pattern.** Three of the four
  Trading Intelligence read adapters (`SentinelEvidenceSource`,
  `SentinelGovernanceSource`, `SentinelAuditSource`) read decision context from
  `DecisionQuery.get_decision_timeline()`. `sentinel_engine`'s own
  `DecisionCenterQuery` already derives `symbol` and `action` for its view by
  reading the `DECISION_CREATED` event's payload out of the timeline — the
  exact treatment proposed here for `action_source`, its sibling birth field.
- **Projection integrity.** `DecisionProjection` is a *lifecycle-state* read
  model; its only mutation path (`advance_status`) changes `status` /
  `updated_at` and nothing else. `action_source` is decision-birth data that
  the projection's own lifecycle never touches. Keeping it off the projection
  keeps the projection a pure "where is this decision now" record. (`action` /
  `symbol` / `confidence` already sit on the projection; that is a pre-existing
  redundancy, not a pattern this ADR chooses to extend.)
- **Historical compatibility.** No `DecisionProjection(...)` construction site
  — production (`DecisionService.create_decision`) or the many in-memory test
  fakes — needs to change. A legacy `DECISION_CREATED` event with no
  `action_source` key yields `None` with no special handling.
- **ADR-044 / ADR-004 boundary.** `DecisionProjection` is the contract ADR-004's
  future persistent `ProjectionRepository` backend will have to implement.
  Not adding a field to it keeps that future surface exactly as ADR-067 left
  it. The event payload, by contrast, is already the carrier of record for
  `symbol` / `action` / `action_source` and needs no widening.
- **Testability.** Identical to the existing `approval_status` and
  `Evidence.data` tests: construct a real `DecisionQuery` over in-memory
  `LedgerRepository` / `ProjectionRepository` fakes, write a `DECISION_CREATED`
  / `EVIDENCE_ATTACHED` event, assert the field arrives. No persistence, no new
  fixture shape.

### 10.2 Rejected alternative — `action_source` on `DecisionProjection`

Add `action_source: Optional[str] = None` to `DecisionProjection`, set it in
`DecisionService.create_decision()`, let `SentinelProjectionDecisionSource` read
it in the same `ProjectionRepository.get()` call.

Rejected because:

- It is a genuine Tier-2 `sentinel_engine` read-contract change; by the
  ADR-066 precedent (additive optional fields on `Decision` / `Evidence`
  required ADR-066 to ratify) it would need its own ratification and would
  enlarge the contract ADR-004's backend must satisfy.
- It forces an edit to every `DecisionProjection(...)` construction site,
  production and test.
- It puts decision-birth data on a lifecycle-state model whose mutation path
  never maintains it.
- Its one ergonomic advantage (no `DecisionQuery` dependency in the adapter)
  is already void: the adapter consults `DecisionQuery` for `approval_status`
  regardless.

### 10.3 Rejected alternative — new `DecisionQuery` decision-level summary

Add `action_source` (and a per-evidence `polarity`) to `DecisionQuery`'s output
— e.g. a new `DecisionSummary` dataclass or new fields on `EvidenceSummary` /
`DecisionTimeline`.

Rejected for Sprint 3 because it is still a `sentinel_engine` read-contract
change for no benefit the payload read does not already provide: `DecisionQuery`
already exposes the raw `events` list with full payloads, and both
`DecisionCenterQuery` and `SentinelEvidenceSource` already demonstrate reading
birth/attachment fields straight from those payloads. If raw-payload extraction
later proliferates across many consumers, promoting these two values to typed
`DecisionQuery` summary fields is a reasonable **future** `sentinel_engine`
cleanup — with its own ADR — but it is not needed to surface them once.

## 11. Persistence boundary

ADR-070 **does not** select, design, implement, or imply a persistent
`ProjectionRepository` or `LedgerStore`. The ADR-067 process-local, in-memory
composition pair is unchanged. Sprint 3's read contracts are, and must remain,
fully exercisable against the in-memory / fake sources every existing read-side
test already uses. Running the Decision Center against a real persistent
projection source is **not** a Sprint 3 deliverable and remains blocked by
ADR-004 (§16, §17).

## 12. UI boundary

ADR-070 authorizes **only** view-model / display-semantics code inside
`applications/trading_intelligence/ui/decision_center/` (framework-independent
dataclasses and display strings, the existing pattern in `screen.py`).

It does **not** authorize: any `dashboard/` (Gradio) change; a trading
dashboard redesign; polling; a notification, alert, or messaging system;
timers; `WAIT` scheduling; any compulsive-checking, streak, refresh-to-see-more,
or "new since you last looked" mechanism; flashing or animated prices / P&L;
countdowns; or any FOMO / urgency device. The Decision Center surface stays
**calm, explicit, and evidence-oriented** — a static drill-down, not a monitor.

## 13. Architectural constraints (what Sprint 3 must not change)

- `RiskManager.approve_buy()` as the sole execution-blocking gate, consuming
  zero Sentinel input.
- `PaperExecutor` as the sole execution authority; `bot/execution/factory.py`
  untouched.
- The single ADR-067 `decision_id` / one `Decision` / one `DecisionProjection`
  / one lifecycle. No second identity, no new correlation identifier.
- The B2 action-selection rule (ADR-069 three-model unanimity) and the B1
  polarity rule (ADR-068 signal-only map) — unchanged and not re-derived on
  the read side.
- `Decision.confidence` semantics — uncalibrated ensemble score (§8).
- ADR-045 §3 — no operative `Policy` registration / `record_approval()`;
  `evaluate_policy()`'s result stays discarded.
- Evidence write semantics — `to_evidence_records()` signature, three-record
  output, every `Evidence` field, and the `EVIDENCE_ATTACHED` payload —
  byte-for-byte.
- No new `EventType`, `DecisionState`, or `ApprovalStatus` member; no new
  domain type, enum, or `Evidence` / `Decision` / `DecisionProjection` field.
- No `sentinel_engine → bot` import; no `bot/` change; no ADR-002 exception; no
  `.github/workflows/*` change.
- No ADR-004 persistence selection.
- Provenance stays three-state (`SENTINEL` / `STRATEGY` / `None`); historical
  records are never rewritten.

## 14. Explicit non-goals

This ADR does **not** authorize, imply, prepare for, or partially enable:

- Any recommendation quality, correctness, hit-rate, or outcome-scoring
  measurement.
- Any calibration, `uncertainty` value or methodology, or `confidence`
  recompute / relabel.
- Any generated `thesis` / `counterfactual` / explanation prose.
- Any new evidence type, evidence source, or non-`MODEL_OUTPUT` evidence.
- Any evidence aggregation, counting, netting, scoring, weighting, voting, or
  corroboration value (§9).
- Any portfolio-aware, risk-aware, or `market_context`-aware recommendation
  context.
- Any position sizing, allocation, or Kelly logic.
- Any `WAIT` scheduling, timer, re-evaluation, notification, or "future BUY"
  implication (§7).
- Any broader action authoring, action override, or `SELL` / `BUY_MORE` /
  exit-path `Decision`.
- Any `GovernanceService.register_policy()` / `record_approval()` wiring, any
  operative approval, any acting on `evaluate_policy()`.
- Any Sentinel approval or execution authority; any change to `RiskManager`,
  `PaperExecutor`, `AlpacaClient`, `bot/execution/factory.py`, `bot/main.py`,
  `EntryContext`, or `_handle_entry()`.
- Autonomy; live / Robinhood execution; brokerage integration.
- Any persistent `ProjectionRepository` / `LedgerStore` / ADR-004 option.
- Any `dashboard/` change; any polling / alerting / vigilance mechanism (§12).
- Any change to `DecisionCenterQuery` / `DecisionCenterView` /
  `MorningBriefQuery` / the Morning Brief surface (§17).
- Any modification to
  `sentinel_engine/tests/test_recommendation_governance_lifecycle.py` — it
  remains deferred and untouched.

## 15. Test contract (categories; written and run at implementation, not now)

**Field propagation**
1. `action_source` written to a `DECISION_CREATED` payload as `"SENTINEL"` /
   `"STRATEGY"` reaches `DecisionContract.action_source` and
   `DecisionView.action_source` unchanged, via `get_decision()` and
   `list_decisions()`.
2. Absent `action_source` key → `None`. Absent `DecisionQuery` collaborator →
   `None` (backward-compatible construction, mirrors the existing
   `approval_status is None` test).
3. `polarity` written to an `EVIDENCE_ATTACHED` payload as `"SUPPORTING"` /
   `"CONTRADICTING"` / `None` reaches the matching `EvidenceEntry.polarity`
   unchanged; keyed correctly by `evidence_id` across multiple records.
4. Absent `polarity` key → `None` (mirrors the existing "no `data` key" test).
5. No historical event, `DecisionProjection`, or `decision_events` row is
   written, mutated, or backfilled by any read path — the existing
   "never calls a write operation" / "only calls get, never save" guards
   extended to the new fields.

**Terminology**
6. The view model labels a decision "Sentinel recommendation" **iff**
   `action_source == "SENTINEL"`; `"STRATEGY"` and `None` (and any other value)
   yield "interpreted strategy decision".
7. The distinction is asserted at each hop: payload → contract → view → view
   model output string.

**WAIT**
8. `action == "WAIT"` + `action_source == "SENTINEL"` renders the exact
   "Sentinel does not concur at this time" statement.
9. Guard: a `WAIT` decision produces no schedule, timer, notification, retry
   affordance, re-evaluation hook, urgency cue, or "future BUY" wording in the
   view-model output; `"WAIT"` is never rendered as a rejection reason.

**Confidence**
10. Every view-model surface that emits `confidence` also emits the
    uncalibrated-ensemble-score qualifier.
11. Guard: the view-model output strings contain none of the forbidden words in
    §8 as a description of `confidence`.

**Polarity display**
12. Per-model polarity renders exactly the three §9 phrasings, one per record,
    in isolation.
13. Guard: no count, majority, unanimity flag/score, net polarity, evidence
    score, corroboration score, weighted value, or vote tally is computed,
    stored, or emitted anywhere in the read/view path.

**Boundary / non-execution**
14. No touched read/view module imports `bot`, `alpaca`, an executor,
    `RiskManager`, or `dashboard` — AST/import guard, extending the existing
    lifecycle-import guard style.
15. `sentinel_engine/tests/test_package_imports.py` and the
    `applications/trading_intelligence` package-import guard pass unchanged
    (no `sentinel_engine` file changed).
16. `scripts/verify_single_write_path.py` passes unchanged.

**Regression**
17. Full `sentinel_engine/tests` and `applications/trading_intelligence/tests`
    (and `ui/tests`) suites pass with zero regressions; every existing
    `SentinelProjectionDecisionSource` / `SentinelEvidenceSource` /
    Decision Center test still passes (new fields are additive and default to
    `None` / absent).

## 16. Completion criteria (Sprint 3)

**🟢 SPRINT 3 — COMPLETE** when all hold:

- `action_source` survives the read path (`DECISION_CREATED` payload →
  `DecisionContract` → `DecisionView`), value-exact, with a direct test.
- `Evidence.polarity` survives the read path (`EVIDENCE_ATTACHED` payload →
  `EvidenceEntry`), value-exact per record, with a direct test.
- Optional / legacy values remain optional: absent → `None`, never fabricated,
  no backfill, no historical rewrite — tested.
- "Sentinel recommendation" terminology is provenance-gated on
  `action_source == "SENTINEL"` at every layer — guard-tested.
- `WAIT` has explicit inert semantics (the fixed statement; no
  schedule/timer/notification/re-evaluation/future-BUY implication) —
  guard-tested.
- `confidence` retains its uncalibrated-ensemble-score semantics and qualifier
  everywhere it is displayed; no forbidden wording — guard-tested.
- No evidence aggregation of any kind is introduced — guard-tested.
- No execution, approval, risk, or governance authority is introduced.
- No persistence backend is selected; the contracts pass their tests against
  in-memory / fake sources.
- No `sentinel_engine` contract file is changed; no `bot/` file is changed; no
  ADR-002 exception is required.
- Full relevant test suites are green, zero regressions.
- ADR-070 is `Status: Accepted` and landed (ADR-058 D2).

**🟡 SPRINT 3 — COMPLETE WITH EXPLICIT DEFERMENT** when all of the above hold
**except** that rendering the surfaced fields inside a *running* UI against a
*real persistent projection source* is explicitly deferred — because ADR-004
still prevents a persistent `ProjectionRepository`. The read/view pipe is
complete and tested end-to-end against in-memory fakes; live data flow is
handed to the ADR-004 sprint. This is a legitimate close, not a shortfall.

## 17. Future work (explicitly outside ADR-070)

- ADR-004 persistent `ProjectionRepository` / `LedgerStore` selection and the
  wiring of a real source into the Decision Center bootstrap.
- Recommendation quality / outcome scoring / hit-rate measurement (would join
  ADR-065 `DECISION_EXECUTED` outcomes to recommendations).
- Confidence calibration; an `uncertainty` value or methodology.
- Portfolio-aware / risk-aware recommendation context.
- Position sizing / allocation.
- Richer thesis / explanation generation.
- New evidence types or sources.
- Broader action authoring; approval integration; autonomy;
  vigilance / watchfulness; brokerage integration.
- Optional `sentinel_engine` consistency cleanup: promoting `action_source` /
  per-evidence `polarity` to typed `DecisionQuery` summary fields, and adding
  `action_source` to `DecisionCenterView` / the Morning Brief surface — each
  with its own ADR.

## 18. Rejected alternatives

1. **`action_source` on `DecisionProjection`.** Rejected — §10.2: a
   `sentinel_engine` contract change, construction-site churn, decision-birth
   data on a lifecycle-state model, no ergonomic gain.
2. **New `DecisionQuery` decision-level summary / widened `EvidenceSummary`.**
   Rejected for Sprint 3 — §10.3: still a `sentinel_engine` contract change; the
   raw-payload read already suffices and matches existing precedent. Viable as
   a future cleanup with its own ADR.
3. **Label every `Decision` a "Sentinel recommendation".** Rejected — violates
   ADR-068 §3.1 and ADR-069 §17; would imply Sentinel authority over
   strategy-authored and legacy decisions. §6 gates the label on
   `action_source == "SENTINEL"`.
4. **Show an aggregate "N of 3 models agree" / unanimity indicator.** Rejected —
   evidence aggregation, deferred by ADR-066 §10 and ADR-068 §3.9; ADR-069
   already exposes the *result* (the authored `action`), which is the honest
   summary. §9 forbids any aggregate.
5. **Relabel `confidence` as a calibrated probability now that a `SENTINEL`
   badge is shown.** Rejected — ADR-069 §9; the value is unchanged and
   uncalibrated. §8 fixes the qualifier and forbids the wording.
6. **Give `WAIT` a "re-evaluates in …" / "check back" affordance.** Rejected —
   ADR-069 §7 / §14 make `WAIT` an inert label; a timer is vigilance/FOMO,
   explicitly out of scope. §7 / §12.
7. **Wire a real `ProjectionRepository` so the Decision Center shows live
   data.** Rejected — ADR-004-gated; §11. Sprint 3 is the contract layer, not
   the persistence layer.
8. **Bundle the Morning Brief surface.** Rejected — separate
   `sentinel_engine`-internal read path (`DecisionCenterQuery` /
   `MorningBriefQuery`); pulling it in means a `sentinel_engine` contract
   change and widens the sprint. Deferred (§17).

## 19. Acceptance criteria

This ADR may be considered **Accepted** only when the Architecture Owner
confirms, in writing, through the ADR-058 D2/D4 mechanism (tracked on the
default branch, `Status: Accepted`, landed under applicable write/merge
controls), that:

- The capability is exactly §2: propagate `action_source` and `Evidence.polarity`
  through the read side value-exact, plus provenance-gated Decision Center
  display semantics — no new intelligence, persistence, execution, approval, or
  governance authority.
- The read-side seam is §10: both values read from existing event payloads via
  `DecisionQuery` — **no** `DecisionProjection` field, **no** `DecisionQuery`
  summary-contract change, **no** `sentinel_engine` contract change at all.
  Alternatives §10.2 / §10.3 are rejected for this sprint.
- The terminology rule (§6), `WAIT` inert-label rule (§7), uncalibrated-
  confidence rule (§8), and per-model polarity rule (§9, no aggregation) are
  binding on the implementation.
- Historical records are never rewritten; all new fields are
  `Optional[...] = None` (§4.3).
- The persistence boundary (§11) and UI boundary (§12) hold; no ADR-004 option
  is selected.
- No `bot/` change and no ADR-002 exception (§8, §13). If implementation review
  finds either is actually required, implementation **stops** and the conflict
  is reported for a scope decision — it is not absorbed silently.
- The §15 test contract and §16 completion criteria (including the legitimacy
  of the 🟡 deferred close while ADR-004 blocks a real projection source) are
  binding.
- `sentinel_engine/tests/test_recommendation_governance_lifecycle.py` and the
  unrelated working-tree items (`docs/REQUIREMENTS.md`,
  `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`,
  `tests/req_snapshots/req_state.json`) remain untouched.

Acceptance authorizes the **architecture only**. Implementation is a further
separate batch bound by §3, §13, §15, and §16, on an isolated branch/worktree,
with the full `sentinel_engine/tests` and `applications/trading_intelligence`
suites green before and after.

---

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-09-09
**Accepted By:** Architecture Owner (explicit act — Sprint 3, Finalize and
Accept ADR-070 — not inferred from the design draft, from any implementation, or
from any other source).

The Architecture Owner explicitly accepts ADR-070 and its defined read-side
boundary. This acceptance ratifies the ADR-070 text as authored in the Sprint 3
design draft; only the header status/date lines, this `## Acceptance` section,
and the Status Log entry below were altered to perform the acceptance. No
substantive Context, Decision (§2), Scope (§3), Field-propagation (§4),
terminology (§6), WAIT (§7), confidence (§8), polarity (§9), seam (§10),
persistence-boundary (§11), UI-boundary (§12), constraints (§13), non-goal
(§14), test-contract (§15), completion-criteria (§16), or rejected-alternatives
(§18) content was weakened or expanded.

### Accepted scope — exactly, and only

- **The read-side seam in §10.** `action_source` and `Evidence.polarity` are
  carried from the existing `DECISION_CREATED` / `EVIDENCE_ATTACHED` event
  payloads through `DecisionQuery.get_decision_timeline()` and the existing
  Trading Intelligence read adapters:

  ```
  action_source:
    DECISION_CREATED payload
        -> DecisionQuery timeline (events)
        -> SentinelProjectionDecisionSource (via its already-optional DecisionQuery)
        -> DecisionContract.action_source
        -> DecisionView.action_source

  polarity:
    EVIDENCE_ATTACHED payload
        -> DecisionQuery timeline (events)
        -> SentinelEvidenceSource (its existing timeline.events payload read)
        -> EvidenceEntry.polarity
  ```

  **Neither field is added to `DecisionProjection`.** **No `DecisionQuery`
  summary contract (`EvidenceSummary`, `GovernanceEvaluationSummary`,
  `ApprovalSummary`, `DecisionTimeline`) is widened.** **No `sentinel_engine`
  domain, projection, query, event, or service contract is changed by this
  ADR.** Rejected alternatives §10.2 (`DecisionProjection` field) and §10.3
  (new `DecisionQuery` summary) are rejected for this sprint.

- **The three additive optional fields** — `DecisionContract.action_source`,
  `DecisionView.action_source`, `EvidenceEntry.polarity` — each
  `Optional[str] = None`, value carried verbatim, never fabricated.

- **`action_source` semantics (§4.1, §6):** `"SENTINEL"` → the decision may be
  described as a **"Sentinel recommendation"**; `"STRATEGY"`, `None`, or any
  other value → **"interpreted strategy decision"** (legacy / unknown /
  unspecified for `None`). The gate is `action_source == "SENTINEL"` and
  nothing else, at every mapping layer.

- **`Evidence.polarity` semantics (§4.2, §9):** `"SUPPORTING"` /
  `"CONTRADICTING"` / `None`, carried verbatim per evidence record, rendered in
  isolation as "this model supported the BUY" / "this model contradicted the
  BUY" / "polarity unavailable". **No aggregation** — no count, majority,
  unanimity flag/score, net/aggregate polarity, evidence score, corroboration
  score, weighted value, or vote tally is computed, stored, or displayed.

- **`WAIT` semantics (§7):** a Sentinel-authored `WAIT` renders exactly
  **"Sentinel does not concur at this time."** and is **inert** — no rejection,
  no execution veto, no schedule, no timer, no notification, no re-evaluation
  or retry affordance, no implication that Sentinel predicts a future `BUY`.

- **Confidence semantics (§8):** `Decision.confidence` remains the
  **uncalibrated ensemble model score** (ADR-069 §9), unchanged and not
  relabelled; the qualifier accompanies every displayed value; the words
  *probability*, *probability of success / correctness*, *calibrated
  confidence*, *likelihood*, *certainty*, *recommendation confidence*,
  *Sentinel's confidence* must not describe it.

- **Persistence boundary (§11):** Sprint 3 selects, designs, and implements
  **no** persistent `ProjectionRepository` / `LedgerStore`. The ADR-067
  process-local in-memory composition pair is unchanged. The Sprint 3
  contracts and view-model semantics are independently testable against the
  in-memory / fake read sources every existing read-side test already uses.
  The absence of production persistence does **not** make the Sprint 3
  capability incomplete, and ADR-004 is **not** a Sprint 3 prerequisite. A
  real persistent projection source remains an ADR-004 / future-sprint
  decision.

- **UI boundary (§12):** only view-model / display-semantics code inside
  `applications/trading_intelligence/ui/decision_center/`. No `dashboard/`
  change; no polling, notification, alert, timer, `WAIT` scheduling,
  compulsive-checking, "new since last look", flashing price/P&L, countdown,
  or FOMO / urgency mechanism. The surface stays calm, explicit, and
  evidence-oriented.

- **Sprint 3 may modify** `applications/trading_intelligence/` read
  contracts, view models, adapters, and Decision Center UI presentation as
  necessary. **Sprint 3 must not modify** `bot/`, `dashboard/`, `scheduler/`,
  `database/`, `ledger/`, `.github/workflows/`, or any `sentinel_engine`
  domain / projection / query / event / service contract.

- **The §15 test contract and §16 completion criteria** are binding on the
  implementation batch. Intended closure is **🟢 SPRINT 3 — COMPLETE** when the
  approved read-side contracts, adapters, view-model semantics, tests, and UI
  presentation are implemented and verified against the existing in-memory /
  fake read sources; a real persistent production data path is **not** required
  for Sprint 3 closure. If a truly unavoidable implementation dependency is
  discovered during implementation, it is reported then for a scope decision —
  not assumed now.

### Not authorized by this acceptance

Every §14 non-goal remains non-authorized, restated because acceptance does not
expand it: no new intelligence; no recommendation quality / outcome scoring /
calibration; no `uncertainty` value or methodology; no generated `thesis` /
`counterfactual` / explanation prose; no new evidence type or source; no
evidence aggregation of any kind; no portfolio- / risk- / `market_context`-aware
recommendation context; no sizing or allocation; no `WAIT` scheduling / timer /
notification / re-evaluation / future-BUY implication; no broader action
authoring or override; no `SELL` / `BUY_MORE` / exit-path `Decision`; no
`register_policy()` / `record_approval()` wiring, operative approval, or acting
on `evaluate_policy()`; no Sentinel approval or execution authority; no change
to `RiskManager`, `PaperExecutor`, `AlpacaClient`, `bot/execution/factory.py`,
`bot/main.py`, `EntryContext`, or `_handle_entry()`; no autonomy, live /
Robinhood execution, or brokerage integration; no persistent
`ProjectionRepository` / `LedgerStore` / ADR-004 option selection; no
`ProjectionRepository` wiring; no `dashboard/` change; no polling / alerting /
vigilance mechanism; no new `EventType`, `DecisionState`, or `ApprovalStatus`
member; no new domain type, enum, or `Evidence` / `Decision` /
`DecisionProjection` field; no `Recommendation` class / object / service; no
historical backfill or record rewrite; no `sentinel_engine → bot` import; no
ADR-002 exception; no `.github/workflows/*` change; no modification to ADR-068,
ADR-069, `DecisionCenterQuery` / `DecisionCenterView` / `MorningBriefQuery` /
the Morning Brief surface, or
`sentinel_engine/tests/test_recommendation_governance_lifecycle.py`.

### Authoritative status and next step

ADR-070 is now **authoritative** (ADR-058 D2: tracked on `main`,
`Status: Accepted`, landed under the repository's direct-to-`main` flow by the
commit recorded in the Status Log). **Sprint 3 implementation may proceed — as a
separate subsequent batch — only within the scope defined above**, on an
isolated branch/worktree, with the full `sentinel_engine/tests` and
`applications/trading_intelligence` suites green before and after. This
acceptance authorizes nothing outside ADR-070.

---

## Status Log

**Proposed — DRAFT / NOT ACCEPTED — 2026-09-09 (Sprint 3 design).** Drafted as a
design-only artifact following the Sprint 3 discovery pass, which found that
B1 (`Evidence.polarity`, ADR-068) and B2 (`Decision.action_source`, ADR-069)
write both fields into the `EVIDENCE_ATTACHED` / `DECISION_CREATED` event
payloads but no read model carries them, and no Decision Center surface
distinguishes a Sentinel-authored recommendation, renders a `WAIT` abstention,
or qualifies a displayed `confidence`. The read-side seam was investigated
against the current code: both values are already in the event payloads;
`SentinelProjectionDecisionSource` already consults an optional `DecisionQuery`
(for `approval_status`) and `SentinelEvidenceSource` already reads
`EVIDENCE_ATTACHED` payloads (for `Evidence.data`), so surfacing the two new
fields requires **no `sentinel_engine` contract change** — the
`DecisionProjection`-field alternative and the `DecisionQuery`-summary
alternative are rejected (§10). No production code, test, or other ADR was
modified in producing this draft; ADR-068 and ADR-069 were not modified; no
`docs/platform/` governance file, `docs/REQUIREMENTS.md`, or
`tests/req_snapshots/req_state.json` was touched; nothing was staged, committed,
or pushed. This ADR is not accepted and authorizes no implementation.

**Accepted + Landed — 2026-09-09 (Sprint 3 — Finalize and Accept ADR-070).** The
Architecture Owner explicitly accepted ADR-070 in the form the Sprint 3 design
draft produced, and it was landed on the default branch `main` in the same
commit ("docs: accept and land ADR-070 recommendation read-model surfacing").
`Status` now reads `Accepted`, scoped exactly to the read-side propagation
architecture in §2–§10 and the display-semantics rules in §6–§9: `action_source`
(`SENTINEL` → "Sentinel recommendation"; `STRATEGY` / `None` / unknown →
"interpreted strategy decision") and `Evidence.polarity`
(`SUPPORTING` / `CONTRADICTING` / `None`, no aggregation) carried from the
existing `DECISION_CREATED` / `EVIDENCE_ATTACHED` event payloads through
`DecisionQuery` and the existing Trading Intelligence read adapters into
`DecisionContract` / `DecisionView` / `EvidenceEntry`; `WAIT` = the inert
statement "Sentinel does not concur at this time." with no veto / scheduling /
notification / re-evaluation / future-BUY implication; `confidence` unchanged as
an uncalibrated ensemble model score with no calibrated-probability language.
**Neither field is added to `DecisionProjection`; no `DecisionQuery` summary
contract is widened; no `sentinel_engine` contract is changed.** No execution or
approval authority; no `RiskManager` / `bot/` change; no ADR-002 exception; no
ADR-004 persistence selection; no `ProjectionRepository` wiring; no new
`EventType` / `DecisionState`; no historical backfill; no new `Recommendation`
class. With this commit ADR-058 D2's three conditions are met — tracked on
`main`, `Status: Accepted`, landed under applicable write/merge controls — and
ADR-070 is authoritative. Sprint 3 implementation is a separate subsequent batch
bound by §3, §13, §15 and §16, independently testable against the existing
in-memory / fake read sources; a real persistent `ProjectionRepository` remains
an ADR-004 / future-sprint decision and is not a Sprint 3 prerequisite. No
production code, test, or UI file was modified; ADR-068 and ADR-069 were not
modified; `docs/REQUIREMENTS.md`, `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`,
`tests/req_snapshots/req_state.json`, and
`sentinel_engine/tests/test_recommendation_governance_lifecycle.py` were not
touched or staged. Only this file changed in the accepting/landing commit.
