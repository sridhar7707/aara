# ADR-068 — Sentinel B1 Deterministic Evidence Polarity (Interpretation-Only Classification)

**Status:** Accepted — scope limited to the deterministic, signal-only
evidence-polarity classification in §3 (see `## Acceptance`). The Architecture
Owner acceptance act (Phase 2B — ADR-068 Explicit Acceptance, 2026-09-04) is
recorded in `## Acceptance` and is distinct from, and prior to, any landing
step. ADR-058 D2 is **not yet satisfied** — this file is not yet tracked on the
default branch; ADR-068 becomes authoritative once it is landed on `main` with
`Status: Accepted` under the repository's applicable write/merge controls.
Acceptance authorizes the B1 architecture in §3 only; the B1 implementation is a
separate subsequent batch bound by §4 and §12.
**Date Proposed:** 2026-09-09
**Date Accepted:** 2026-09-04
**Decision Type:** Architecture / Governance — narrow authorization of one deterministic representation step (population of an already-ratified optional field), no recommendation intelligence, no `bot/` change, no ADR-002 exception
**Related ADRs:** ADR-001, ADR-002, ADR-009, ADR-011, ADR-012, ADR-013, ADR-014, ADR-020, ADR-034, ADR-036, ADR-043, ADR-045, ADR-047, ADR-048, ADR-049, ADR-050, ADR-058, ADR-065, ADR-066, ADR-067

---

## 1. Context

The Phase 2 Recommendation Intelligence architecture audit and the Phase 2A
Recommendation Authority audit (both read-only, against HEAD
`1658f5590afecc2c1f72f1962dc03068d6818196`) established a split of the
preferred direction "Sentinel becomes the recommendation-formation layer" into
two stages with a hard authority boundary between them:

- **B1 — Recommendation interpretation / representation.** Sentinel consumes an
  already-produced ensemble signal plus the evidence it already receives, and
  produces the canonical `Decision` representation ADR-067 already creates —
  adding only *objective, deterministic representation*, never judgment.
- **B2 — Recommendation judgment / authority.** Sentinel independently reasons
  about evidence and may select, override, or withhold an action; weight or
  aggregate evidence; compute its own confidence or an uncertainty value;
  generate a thesis or counterfactual; select a horizon; or feed outcomes into
  calibration. **B2 is out of scope for this ADR entirely.**

Repository facts verified for this ADR (read-only, HEAD as above):

- `bot/strategy/ensemble.py::ensemble_signal()` → `action_to_int()` produces the
  entry action; the entry path reaches `_handle_entry()` only when
  `action == 1` (BUY). `bot/_main_trust_decisions.py::EntryDecisionRecorder.__init__()`
  then constructs one `sentinel_engine.domain.decision.Decision` with
  `action = "BUY"` (a literal — ADR-067 §3.A / §6), `confidence = final_confidence`
  (the existing `ensemble_confidence()` weighted average — `bot/_main_trust_decisions.py:130`,
  `:168`), and the six optional `Decision` fields left at their `None` defaults.
- The three `MODEL_OUTPUT` `Evidence` records are built by
  `sentinel_engine/adapters/evidence_adapter.py::to_evidence_records(model_outputs)`
  from the dict `bot/strategy/model_output_adapter.py::build_model_outputs(...)`
  produces. `_REQUIRED_MODELS = ("xgboost", "lstm", "finbert")`. Each record:
  `evidence_id = uuid4()`, `evidence_type = "MODEL_OUTPUT"`,
  `source ∈ {"xgboost", "lstm", "finbert"}`,
  `data = dict(model_outputs[model])` (carrying `signal`, `confidence`,
  `metadata`), `collected_at = datetime.now(timezone.utc)`,
  `polarity = None` (domain default; the adapter never sets it — consistent
  with ADR-066 §7).
- `Evidence.data["signal"]` is produced by
  `bot/strategy/model_output_adapter.py`:
  `_prob_signal(prob)` → `"BUY"` if `prob > 0.5`, `"SELL"` if `prob < 0.5`,
  `"HOLD"` if `prob == 0.5` (applied to the **raw** `xgb_prob` and the **raw**
  `lstm_prob`); `_sentiment_signal(score)` → `"BUY"` if `score > 0.0`,
  `"SELL"` if `score < 0.0`, `"HOLD"` if `score == 0.0`. That module's own
  docstring labels these as "a documented, explicitly-labeled *informational*
  threshold (0.5 for XGB/LSTM probabilities, 0.0 for sentiment's [-1,+1] scale)
  — it is NOT the ensemble's actual trading decision."
- The LSTM indeterminate band `_LSTM_INDETERMINATE_LO = 0.45` /
  `_LSTM_INDETERMINATE_HI = 0.55` is defined in `bot/strategy/ensemble.py` and
  consumed **only** by `_lstm_is_indeterminate()` → `_reweight_score()` /
  `ensemble_signal()`, to transfer LSTM's weight to XGB in the blended ensemble
  score. It **never** touches `model_outputs`, the `lstm` `Evidence` record,
  `Decision.confidence`, or `ensemble_confidence()`.
- `metadata["is_degraded"]` (bool) and `metadata["val_loss"]` are carried on the
  `lstm` `Evidence` record's `data`. `is_degraded` is a model reliability /
  quality flag, not a directional signal.
- `to_evidence_records()` has exactly two callers: the production entry path
  (`bot/_main_trust_decisions.py:94`, inside `record_decision_safe()`), and the
  ADR-043 one-shot offline diagnostic (`scripts/project_one_trust_ledger_decision.py:219`).
- `EvidenceService.associate_evidence()` already includes
  `"polarity": evidence.polarity` in the `EVIDENCE_ATTACHED` event payload
  (`sentinel_engine/services/evidence_service.py:43`). Today it always carries
  `None`. No `EventType`, `DecisionState`, payload field, or schema needs to
  change for a non-`None` polarity to flow end to end.

ADR-066 (Accepted, landed `a7c65cb`) ratified `EvidencePolarity{SUPPORTING,
CONTRADICTING}` and `Evidence.polarity` as **inert representation only** and
explicitly deferred *operative* polarity population and use to separate
governance (ADR-066 §3.3, §6, §7, §10). ADR-067 (Accepted, landed `d7e64a4`)
established the causal `Decision` lifecycle and explicitly left the optional
`Decision` fields — and evidence polarity — unset, with recommendation
formation named a non-goal (ADR-067 §6, §14). **This ADR is the narrow
separate authorization both point to, for B1 and B1 only.**

## 2. Problem

The Phase 2A audit found that the only thing preventing the pre-gate `Decision`
from being an honest, structured *representation* of the strategy's
recommendation — as opposed to a bare record — is that `Evidence.polarity` is
never populated: the decision record cannot show, per model, whether that
model's own output agreed or disagreed with the BUY action being represented.
ADR-066 §3 of the P0 contract it cites requires that "both supporting and
contradicting evidence must be present in the decision record."

Populating `polarity` is a real production behavior change (evidence records
that previously carried `None` would carry a value), and ADR-066 §10 reserved
"operative `EvidencePolarity` use" for a separate governed decision. No
Accepted ADR authorizes writing a polarity value in production. This ADR grants
exactly that, bounded to a deterministic classification with no downstream use,
and nothing more.

## 3. Decision

Authorize **B1 deterministic evidence-polarity classification**, exactly as
specified in §3.1–§3.12, and nothing else.

### 3.1 B1 purpose and terminology

B1 adds one capability: for each `MODEL_OUTPUT` `Evidence` record attached to a
pre-gate causal `Decision`, classify whether that record's already-computed
directional `signal` **agrees or disagrees with the action the `Decision`
represents** (always `"BUY"` on the entry path), and record that as the
record's `EvidencePolarity`.

This is *interpretation / representation*, not judgment. During B1 the
production `Decision` is an **"interpreted strategy decision"**: Sentinel's
structured representation of a recommendation the upstream strategy / ensemble
authored. It **must not** be described, in code comments, documentation,
logs, UI copy, or product material, as a **"Sentinel recommendation."** The
upstream strategy / ensemble remains the sole author of the action.

### 3.2 Action preservation

`Decision.action` is copied, unchanged, from the upstream strategy decision. On
the entry path this is the literal `"BUY"` (`DecisionAction.BUY`), exactly as
ADR-067 §3.A / §6 established. **B1 has no authority to change, suppress,
replace, veto, or withhold the action, and B1 introduces no code path that
could.** B1 does not create a `Decision` for any symbol or cycle that did not
already reach the existing entry decision path.

### 3.3 Confidence preservation

`Decision.confidence` remains the existing `final_confidence` value —
`ensemble_confidence(xgb_prob, lstm_prob, sentiment, macro_score)`, an
**uncalibrated weighted average of model scores** — passed through byte-for-byte
unchanged. B1 does **not** recompute, rescale, calibrate, reinterpret, or
adjust it, and B1 writes no separate confidence value anywhere.

`Decision.confidence` under B1 is, semantically, an **uncalibrated ensemble
model score**. It is **not**:

- a probability of correctness / probability the trade wins,
- a calibrated confidence,
- a "Sentinel confidence" or any Sentinel-formed assessment.

Any surface that displays it must describe it accordingly.

### 3.4 Deterministic polarity rule

For each `MODEL_OUTPUT` `Evidence` record, `polarity` is a **pure deterministic
function of that record's own already-existing `Evidence.data["signal"]`
value**, relative to the fixed action `"BUY"` the `Decision` represents:

```
Evidence.data["signal"] == "BUY"   ->  EvidencePolarity.SUPPORTING
Evidence.data["signal"] == "SELL"  ->  EvidencePolarity.CONTRADICTING
Evidence.data["signal"] == "HOLD"  ->  None   (see §3.6)
```

No other input is consulted. **No new threshold, no new deadband, no
reinterpretation of any model's signal is authorized.** Specifically:

- The LSTM ensemble-internal indeterminate band `[0.45, 0.55]` **must not** be
  used. It belongs only to ensemble-score reweighting and is not part of the
  `MODEL_OUTPUT` `Evidence` path.
- `lstm` `metadata["is_degraded"]` **must not** be used for polarity. It is a
  reliability / quality flag, not a directional polarity rule.
  Degraded-model / reliability intelligence is deferred to future work.
- The `signal` semantics defined in `bot/strategy/model_output_adapter.py`
  (`_prob_signal` at 0.5, `_sentiment_signal` at 0.0) **remain authoritative
  and unchanged**; B1 consumes their output, it does not redefine them.

### 3.5 MODEL_OUTPUT scope

Polarity is assigned to **exactly the three existing `MODEL_OUTPUT` `Evidence`
records** and no others:

- `xgboost`
- `lstm`
- `finbert`

B1 creates **no additional `Evidence` records**. B1 does **not** classify
regime, macro, technical gates, relative strength, portfolio context, risk
context, or any other data as evidence, and does **not** promote any of them
into an `Evidence` record. B1 does not read or classify `market_context`,
`portfolio_snapshot`, or `risk_checks`.

### 3.6 HOLD / neutral handling

`Evidence.data["signal"] == "HOLD"` — the exact-midpoint outcome
(`prob == 0.5` for xgb/lstm, `score == 0.0` for finbert) already produced by the
existing helpers — maps to **`polarity = None`** (field left unset). This is
the repository's own, already-defined neutral condition; B1 introduces no other
neutral condition and no band around the midpoint. `None` is a legitimate
terminal polarity value for a record and carries no further meaning.

### 3.7 Evidence provenance preservation

For every `MODEL_OUTPUT` `Evidence` record, `evidence_id`, `evidence_type`
(`"MODEL_OUTPUT"`), `source`, `data` (including `signal`, `confidence`,
`metadata` and everything within — SHAP drivers, `is_degraded`, `val_loss`,
`raw_score`, `headlines`), and `collected_at` are **byte-for-byte unchanged**
from pre-B1. `polarity` is the **only** field whose populated value changes
(from always-`None` to `SUPPORTING` / `CONTRADICTING` / `None` per §3.4).
`to_evidence_records()`'s existing required-field validation, three-record
output, unique-id generation, timezone-aware `collected_at`, and shallow-copy
independence of `data` are all preserved.

### 3.8 Decision optional-field preservation

Every one of the six optional `Decision` fields remains at its `None` default
on every B1-produced `Decision`:

- `uncertainty` — remains `None`
- `thesis` — remains `None`
- `counterfactual` — remains `None`
- `horizon` — remains `None`
- `desired_allocation` — remains `None`
- `minimum_viable_allocation` — remains `None`

B1 populates none of them, reads none of them to derive anything, and
authorizes no methodology for any of them.

### 3.9 Classification-only boundary

Polarity under B1 is **classification only**. B1 does **not**, and any
implementation claiming this ADR's authority for the following is out of scope:

- produce a net / combined polarity,
- count supporting sources, count contradicting sources,
- assign weights to sources,
- compute an evidence score of any kind,
- apply corroboration or independence logic,
- influence `Decision.action`,
- influence `Decision.confidence`,
- influence `RiskManager` or any risk evaluation,
- influence execution, order sizing, or order routing,
- influence the `GovernanceService.evaluate_policy()` result or its handling.

Each `Evidence` record's `polarity` is computed and stored in isolation from
every other record's.

### 3.10 Domain / event / state boundary

B1 adds:

- **no** new `EventType` member (polarity flows through the existing
  `EVIDENCE_ATTACHED` payload field, which already exists),
- **no** new `DecisionState` member,
- **no** new `ApprovalStatus` member,
- **no** new domain type, dataclass, enum, or `Evidence` / `Decision` field
  (`EvidencePolarity`, `Evidence.polarity`, and the `DecisionAction` vocabulary
  are all already ratified by ADR-066),
- **no** new identity or correlation identifier — the single `decision_id`
  from ADR-067 remains the only lifecycle identity,
- **no** `Recommendation` class, object, service, or "Risk Governor".

### 3.11 Bot / execution / governance boundary

B1 changes **nothing** in `bot/`. It makes no change to `RiskManager`,
`PaperExecutor`, `AlpacaClient`, `bot/execution/factory.py`, `bot/main.py`,
`EntryContext`, `_handle_entry()`'s gate sequence, model inference, or
`bot/strategy/ensemble.py`. It requires **no ADR-002 boundary exception**.

`RiskManager.approve_buy()` remains the sole execution-blocking risk gate,
receiving byte-for-byte identical arguments and consuming zero Sentinel input.
`PaperExecutor` remains the sole execution authority. B1 calls no executor,
constructs no `Approval`, calls neither `GovernanceService.register_policy()`
nor `GovernanceService.record_approval()`, wires no governance verdict into any
production path, and grants Sentinel **no approval authority and no execution
authority**.

### 3.12 B1 invariants and required tests

A B1 implementation authorized by this ADR must prove the invariants in the
**B1 Invariants** section below. The test plan is written at implementation
time, not here; §12 states the verification requirements it must satisfy.

## 4. Implementation boundary

- **Preferred seam:**
  `sentinel_engine/adapters/evidence_adapter.py::to_evidence_records()` — it
  already receives `model_outputs`, already computes each record's
  `data["signal"]`, and already constructs each `Evidence(...)`. Setting
  `polarity=` there, from the record's own `signal`, per §3.4, is entirely
  inside `sentinel_engine/` and needs no `bot/` change and no ADR-002
  exception. (An equivalent `sentinel_engine`-internal seam that classifies the
  same `Evidence.data["signal"]` value without a second signal representation
  is a permissible alternative; the `to_evidence_records()` seam is preferred.)
- The implementation **may** use the already-existing `model_outputs` signal
  value / the resulting `Evidence.data["signal"]`.
- The implementation **must not** import any `bot/strategy/` helper (including
  `_prob_signal`, `_sentiment_signal`, `build_model_outputs`, or the
  `_LSTM_INDETERMINATE_*` constants) into `sentinel_engine/`. It reads the
  resulting `signal` string, which is already the Sentinel-side copy.
- The implementation **must not** introduce a second directional / signal
  representation of any model output.
- The implementation **must not** modify `bot/`, model inference, ensemble
  behavior, `ensemble_confidence()`, `RiskManager`, or execution.
- The ADR-043 offline diagnostic (`scripts/project_one_trust_ledger_decision.py`),
  which also calls `to_evidence_records()`, will surface polarity in its
  diagnostic projection output. This is acceptable and harmless: that script
  performs no weighting, scoring, or authority logic. ADR-043's separate
  one-shot pair is otherwise unaffected and not consolidated.
- Implementation occurs on an isolated branch/worktree, not directly on `main`.
  The full `sentinel_engine/tests` and `tests/` suites, and
  `scripts/verify_single_write_path.py`, must pass before and after.

## 5. B1 → B2 boundary

B1 is **representation**. **B2 begins at the first act of Sentinel judgment.**
Any of the following is B2 and is **not** authorized by this ADR — each
requires its own separate governance:

- selecting an action,
- overriding an upstream action,
- withholding an action because Sentinel disagrees (as distinct from the
  ADR-067 §9 failure-isolation `try/except` catching a genuine error),
- emitting `WAIT`,
- emitting `BUY_MORE`,
- weighting or aggregating evidence; counting / netting / scoring evidence;
  corroboration logic,
- producing a distinct Sentinel recommendation confidence,
- computing an `uncertainty` value or methodology,
- generating a `thesis` or `counterfactual`,
- selecting a `horizon`,
- position sizing / allocation (`desired_allocation`,
  `minimum_viable_allocation`, or any sizing algorithm),
- calibration or learning (feeding outcomes back into confidence, weights, or
  polarity).

Crossing this line is the point at which the production `Decision` could first
be honestly called a "Sentinel recommendation." Until then it is an interpreted
strategy decision (§3.1).

## 6. Explicit non-goals

This ADR does **not** authorize, imply, prepare for, or partially enable any of
the following:

- a `Recommendation` class / object / service;
- Sentinel action selection; action override; action withholding;
- `WAIT`; `BUY_MORE`; any `SELL` / exit-path `Decision`; position lifecycle;
- evidence weighting; evidence aggregation; evidence counting / netting;
  evidence scoring; corroboration or independence logic;
- any confidence methodology; any recalibration or reinterpretation of
  `Decision.confidence`;
- any uncertainty methodology or value;
- thesis generation; conviction modelling; counterfactual generation;
- horizon selection, enforcement, expiry, or re-evaluation;
- allocation or position-sizing logic of any kind;
- calibration; a learning / feedback loop; Investment Memory;
- `GovernanceService.register_policy()`;
- `GovernanceService.record_approval()` production wiring;
- any operative `GovernanceService` approval; acting on the
  `evaluate_policy()` result;
- any Sentinel approval authority; any Sentinel authority over
  `RiskManager.approve_buy()`;
- any Sentinel execution authority; any change to `RiskManager`,
  `PaperExecutor`, `AlpacaClient`, `bot/execution/factory.py`;
- any `bot/` change; any `bot/main.py` / `EntryContext` / `_handle_entry()`
  change;
- any ADR-002 boundary exception;
- any new `EventType`, `DecisionState`, or `ApprovalStatus` member;
- any new identity or correlation identifier;
- any second directional / signal representation of a model output;
- any change to model inference or `bot/strategy/ensemble.py`;
- any persistence, ledger backend, or ADR-004 option selection;
- any modification to
  `sentinel_engine/tests/test_recommendation_governance_lifecycle.py`.

## 7. Relationship to ADR-066

ADR-066 (Accepted, landed `a7c65cb`) ratified `EvidencePolarity{SUPPORTING,
CONTRADICTING}` and the additive `Evidence.polarity` field as **inert
representation and vocabulary only**. ADR-066 §3.3 states polarity "is **not** a
weighting, a score, a corroboration rule, or an input to any recommendation or
decision authority." ADR-066 §7 states that ADR-012's `to_evidence_records()`
"signature, behavior, and MODEL_OUTPUT shape are not changed by [ADR-066], and
**no polarity value is introduced into that path**." ADR-066 §10 lists
"Operative `EvidencePolarity` use — weighting, scoring, corroboration rules" as
**deferred work requiring separate governance**.

**ADR-068 is that separate, narrow authorization** — and only for the
non-weighting, non-scoring, non-corroboration part: deterministic *classification*
of a single `Evidence` record from its own `signal`, with no aggregation and no
downstream use (§3.9). ADR-066 was correct and remains authoritative; it
deliberately deferred this step rather than deciding it. **ADR-068 does not
claim ADR-066 was wrong, does not supersede it, and does not modify it.** The
`EvidencePolarity` vocabulary and `Evidence.polarity` field ADR-068 populates
are exactly the ones ADR-066 ratified, unchanged.

## 8. Relationship to ADR-067

ADR-067 (Accepted, landed `d7e64a4`) established the causal `Decision`
lifecycle: a pre-gate `Decision` with a stable `decision_id` threaded through
the Trust Ledger write, evidence association, governance evaluation, and
execution-outcome reporting, so one `DecisionProjection` walks
`DECISION_CREATED → EVIDENCE_ATTACHED → GOVERNANCE_EVALUATED → DECISION_EXECUTED`.
ADR-067 §6 states it "defines **no** confidence mathematics, sizing algorithm,
thesis evaluation, conviction model, horizon enforcement, or evidence
weighting" and that "the optional `Decision` fields (`horizon`, `thesis`,
etc.) may be left `None`; nothing populates or evaluates them." ADR-067 §14
names "a new `Recommendation` class/service" and every reasoning capability as
non-goals.

**ADR-068 authorizes only the deterministic representation step of §3** — it
populates `Evidence.polarity` from each model's own already-computed `signal`.
It does **not** authorize recommendation formation, Sentinel judgment, or any
capability ADR-067 §14 lists as a non-goal. The causal identity, lifecycle,
shared composition pair, and failure-isolation discipline ADR-067 established
are unchanged; polarity flows through ADR-067's existing `EVIDENCE_ATTACHED`
step with no new event, state, or identity.

## 9. Relationship to ADR-011 / ADR-020 / ADR-045 / ADR-050

### ADR-011 — adjacency, not conflict
ADR-011 (Accepted) established that Stage-3 structured Thesis / Conviction and
Stage-11/12 Investment Memory are not a Phase-1 dependency and that "future
expansion … requires its own separate, governed decision." ADR-068 leaves
`Decision.thesis` and `Decision.counterfactual` at `None` (§3.8) and authorizes
no thesis, conviction, memory, or learning capability. No conflict; ADR-011 is
not superseded, amended, or reinterpreted.

### ADR-020 — adjacency, not conflict
ADR-020 ("Sell Intelligence", Accepted — Implementation Deferred) reserves
`holding_horizon` and exit-decision intelligence for future authorized work.
ADR-068 leaves `Decision.horizon` at `None` (§3.8), authorizes no horizon
selection or enforcement, and touches no exit path. No conflict; ADR-020 is not
superseded, amended, or reinterpreted.

### ADR-045 — prohibition unchanged
ADR-045 §3 prohibits operative Phase-1A `Policy` registration and
`GovernanceService.record_approval()` wiring in the production trust-decision
path. **ADR-068 does not alter, weaken, or create any exception to that
prohibition.** Nothing in §3 registers a policy, constructs an `Approval`,
calls `record_approval()`, acts on an `evaluate_policy()` result, or wires any
governance evaluation into a production path.

### ADR-050 — precedent followed
ADR-068 follows ADR-050's / ADR-066's "recognize and stabilize a narrow,
bounded step without claiming prior ratification and without introducing new
runtime design" pattern. Unlike a pure no-op it authorizes one real behavior
change (a previously always-`None` field now carries a value), stated openly
here. It freezes no string or constant as architectural vocabulary beyond the
`EvidencePolarity` members ADR-066 already ratified, and establishes no general
cross-product architecture. The Constitution rules (ADR-047/048/049/050/051)
remain advisory and non-blocking; ADR-068 adds no new authority and makes no
governance verdict consequential.

## 10. Alternatives considered

1. **Do nothing — leave `polarity` always `None`.** Rejected: the decision
   record cannot show per-model agreement/disagreement with the represented
   action, which the audits identified as the single missing representation
   element. Deferring indefinitely blocks every honest "evidence for and
   against" product surface with no offsetting benefit.
2. **Classify using the LSTM `[0.45, 0.55]` indeterminate band and/or a
   sentiment deadband** (as an earlier draft of the polarity rule proposed).
   Rejected by the Architecture Owner: the band is ensemble-score-internal and
   is not part of the `MODEL_OUTPUT` `Evidence` path, and no sentiment deadband
   exists in the repository. Using either would import an ensemble-internal
   threshold into the evidence path or invent a new one, reinterpreting a
   model's signal. The authoritative rule is signal-only (§3.4).
3. **Use `lstm` `metadata["is_degraded"]` to force `None`.** Rejected by the
   Architecture Owner for B1: `is_degraded` is a reliability/quality flag, not a
   directional polarity rule. Degraded-model / reliability intelligence is
   deferred to future work.
4. **Weight or aggregate polarities into a net supporting/contradicting
   assessment.** Rejected: that is evidence weighting / scoring — B2 judgment,
   explicitly deferred by ADR-066 §10 and out of scope here (§3.9, §5).
5. **Introduce a `Recommendation` type to hold the interpreted decision.**
   Rejected: `Decision` already carries every needed field (ADR-066-ratified);
   a second type forks identity and lifecycle and is an ADR-067 §14 non-goal.
6. **Implement the classification in `bot/`** (e.g. in `build_model_outputs`
   or `record_decision_safe`). Rejected: it would require an ADR-002 exception
   for no benefit; the `sentinel_engine`-internal `to_evidence_records()` seam
   already has everything needed (§4).

## 11. Risks

- **Misreading polarity as judgment.** A populated `polarity` could be mistaken
  — in code, docs, or product copy — for Sentinel having reasoned about the
  evidence. Mitigation: §3.1 terminology ("interpreted strategy decision", not
  "Sentinel recommendation"); §3.9 classification-only boundary; §5 B1→B2
  boundary; the B1 invariants.
- **Scope creep toward aggregation.** Once per-record polarity exists, a "2 of
  3 support" count is a small code step away. Mitigation: §3.9 and invariant 8
  forbid any net/count/weight/score; verification (§12) must include a guard
  test that no aggregate is computed.
- **Confidence mislabelling.** Surfaces might present `Decision.confidence` as a
  calibrated probability now that the record looks more "reasoned." Mitigation:
  §3.3 fixes the semantic label; invariant 4 fixes the value.
- **Divergence of the `signal` midpoint semantics.** If
  `bot/strategy/model_output_adapter.py`'s `_prob_signal` / `_sentiment_signal`
  thresholds ever change, B1's polarity changes with them — which is correct
  (B1 consumes, does not redefine), but must be understood. Mitigation: §3.4
  names those helpers as authoritative and unchanged by this ADR.
- **ADR-043 diagnostic output shape.** The offline diagnostic will start
  emitting polarity. Mitigation: §4 accepts this explicitly; it performs no
  weighting/scoring/authority logic.

## 12. Verification requirements

An implementation authorized by this ADR must, before it can be proposed for
acceptance of the *implementation*, demonstrate:

1. Every B1 invariant below holds, each with a direct test.
2. `polarity` is a pure function of `Evidence.data["signal"]` per §3.4 —
   property/parametrised test over `{"BUY", "SELL", "HOLD"}` and, defensively,
   an unexpected value (which must yield `None`, never raise into the trade
   path).
3. Exactly three `MODEL_OUTPUT` records exist; each is classified
   independently; no fourth record and no aggregate/count/score field is
   produced anywhere — guard test.
4. `Decision.action`, `Decision.confidence`, and all six optional `Decision`
   fields are unchanged / `None` on a full `_handle_entry()` run — assertion
   test.
5. `Evidence` `evidence_id` / `evidence_type` / `source` / `data` /
   `collected_at` are identical to pre-B1 for the same inputs; only `polarity`
   differs — snapshot/assertion test.
6. `RiskManager.approve_buy()` receives byte-for-byte identical arguments;
   blocking behavior unchanged — test.
7. `GovernanceService.register_policy()` and `record_approval()` are never
   invoked across a full `_handle_entry()` — guard tests.
8. Polarity-classification failure or unavailability leaves pre-B1 lifecycle
   behavior byte-for-byte intact, with `polarity` remaining `None` — test
   (invariant 20).
9. `sentinel_engine/tests/test_package_imports.py` passes unchanged; no `bot`
   import is added to `sentinel_engine/`.
10. `scripts/verify_single_write_path.py` passes unchanged.
11. Existing ADR-009 / ADR-012 / ADR-036 evidence tests and ADR-065 reporting
    tests pass unchanged.
12. `sentinel_engine/tests/test_recommendation_governance_lifecycle.py` is
    untouched.

## 13. Status / acceptance process

This ADR is `Status: Proposed — DRAFT / NOT ACCEPTED`. Per ADR-058 D4,
authoring it records a proposal only; it is non-authoritative until it is
tracked on the default branch with `Status: Accepted` and landed under the
repository's applicable write/merge controls (ADR-058 D2).

**Acceptance is a separate, explicit Architecture Owner act**, in a later
batch, not performed here. Acceptance of this ADR authorizes the B1
*architecture* in §3; the B1 *implementation* is a further separate batch bound
by §4 and §12. There is no `## Acceptance` section in this draft and no claim
of acceptance anywhere in it.

If this ADR is later superseded, a superseding ADR marks it
`Superseded by ADR-0NN`. If the §3 implementation has been landed under it,
rollback is: revert the `to_evidence_records()` (or equivalent seam) change so
`polarity` is again always `None`, and remove the ADR-068 tests — a
single-commit revert with no schema, migration, persistence, `bot/`,
`RiskManager`, or execution cleanup (none is touched).

---

## B1 Invariants

A B1 implementation authorized by this ADR must prove all of the following:

1. **Action preservation** — `Decision.action` equals the upstream strategy
   action for that symbol/cycle (always `"BUY"` on the entry path). Sentinel
   never substitutes, overrides, suppresses, withholds, or manufactures a
   different action.
2. **No manufactured decisions** — no `Decision` is created for any symbol or
   cycle that did not already reach the existing entry decision path
   (`action_to_int(...) == 1`).
3. **No disagreement veto** — `create_decision()` is never withheld because of
   evidence content or polarity; only the ADR-067 §9 failure-isolation
   `try/except` may skip it, and only on a genuine error.
4. **Confidence identity** — `Decision.confidence` equals the existing
   `final_confidence` (`ensemble_confidence(...)` output) byte-for-byte; B1
   does not recompute, rescale, calibrate, reinterpret, or adjust it, and
   writes no separate confidence value.
5. **Polarity purity** — each record's `polarity` is a deterministic function
   **only** of that record's own already-existing `Evidence.data["signal"]`
   value; no other input (no probability re-thresholding, no band, no
   `is_degraded`, no other record, no aggregate) is consulted.
6. **Polarity mapping** — `signal == "BUY"` → `SUPPORTING`;
   `signal == "SELL"` → `CONTRADICTING`; `signal == "HOLD"` → `None`.
7. **Scope** — exactly the three `MODEL_OUTPUT` records (`xgboost`, `lstm`,
   `finbert`) are in scope; no additional `Evidence` record is created; no
   non-model data is classified as evidence.
8. **No aggregation** — B1 computes no net polarity, no supporting count, no
   contradicting count, no evidence score, and applies no corroboration or
   weighting logic; each record's `polarity` is computed and stored in
   isolation.
9. `Decision.uncertainty` remains `None` on every B1-produced decision.
10. `Decision.thesis` remains `None` on every B1-produced decision.
11. `Decision.counterfactual` remains `None` on every B1-produced decision.
12. `Decision.horizon` remains `None` on every B1-produced decision.
13. `Decision.desired_allocation` remains `None` on every B1-produced decision.
14. `Decision.minimum_viable_allocation` remains `None` on every B1-produced
    decision.
15. **One identity** — the single `decision_id` from ADR-067 remains the sole
    causal-lifecycle identity; no second identifier is introduced.
16. **Evidence provenance intact** — `evidence_id`, `evidence_type`, `source`,
    `data` (all contents), and `collected_at` are unchanged from pre-B1;
    `polarity` is the only field whose populated value changes.
17. **No new type** — no new domain type, `EventType`, `DecisionState`,
    `ApprovalStatus`, `Evidence` / `Decision` field, `Recommendation` type, or
    correlation identifier is added.
18. **RiskManager unchanged** — `RiskManager.approve_buy()` receives
    byte-for-byte identical arguments and remains the sole execution-blocking
    risk gate, consuming zero Sentinel input.
19. **No approval/execution change** — no approval or execution behavior is
    changed; `register_policy()` and `record_approval()` are never invoked in
    the production path; the `evaluate_policy()` result is still discarded at
    the call site.
20. **Failure safety** — if polarity classification is unavailable or fails,
    pre-B1 lifecycle behavior remains byte-for-byte intact and `polarity`
    remains `None`; classification never blocks, delays, retries, or alters the
    gate sequence, `risk.approve_buy()`, `client.buy()`, or the Trust Ledger
    write.

---

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-09-04
**Accepted By:** Architecture Owner (explicit act performed directly in this
conversation — Phase 2B — ADR-068 Explicit Acceptance — not inferred from the
Phase 2B draft, from any implementation, or from any other source).

The Architecture Owner explicitly accepts ADR-068 **exactly as drafted**. This
acceptance ratifies the ADR-068 text as authored in the Phase 2B draft; only
the header status/date lines, this `## Acceptance` section, and the Status Log
entry below were altered to perform the acceptance. No substantive Context,
Problem, Decision (§3.1–§3.12), Implementation boundary (§4), B1 → B2 boundary
(§5), Non-goals (§6), ADR-relationship (§7–§9), Alternatives (§10), Risks
(§11), Verification (§12), or **B1 Invariants** content was changed.

### Accepted scope — exactly, and only

Deterministic, **signal-only** evidence-polarity classification of the three
existing `MODEL_OUTPUT` `Evidence` records (`xgboost`, `lstm`, `finbert`)
attached to a pre-gate causal `Decision`, using solely each record's own
already-existing `Evidence.data["signal"]` value:

```
Evidence.data["signal"] == "BUY"   ->  EvidencePolarity.SUPPORTING
Evidence.data["signal"] == "SELL"  ->  EvidencePolarity.CONTRADICTING
Evidence.data["signal"] == "HOLD"  ->  None
```

`polarity` is the only `Evidence` field whose populated value changes (from
always-`None`); it flows through the existing `EVIDENCE_ATTACHED` payload field
with no schema, event, state, or identity change.

### Explicitly excluded by this acceptance

- **No LSTM ensemble `[0.45, 0.55]` indeterminate band** is used for polarity —
  that band is ensemble-score-internal and is not part of the `MODEL_OUTPUT`
  `Evidence` path.
- **No `lstm` `metadata["is_degraded"]` polarity rule** — it is a
  reliability / quality flag, not a directional signal; degraded-model /
  reliability intelligence is deferred to future work.
- **No new threshold and no new deadband** — the `signal` semantics in
  `bot/strategy/model_output_adapter.py` (`_prob_signal` at 0.5,
  `_sentiment_signal` at 0.0) remain authoritative and unchanged.
- **No evidence aggregation, weighting, scoring, counting, netting, or
  corroboration logic.**
- **No modification of `Decision.action`** — copied unchanged from the upstream
  strategy decision; B1 has no authority to change, suppress, replace, veto, or
  withhold it.
- **No modification of `Decision.confidence`** — the existing uncalibrated
  ensemble model score, passed through unchanged; it is not a probability of
  correctness, a calibrated confidence, or a Sentinel confidence.
- **`Decision.uncertainty`, `thesis`, `counterfactual`, `horizon`,
  `desired_allocation`, `minimum_viable_allocation` all remain `None`.**
- **No `Recommendation` class/object/service; no "Risk Governor".**
- **No new `EventType`, `DecisionState`, `ApprovalStatus`, domain type,
  `Evidence` / `Decision` field, or correlation identifier.**
- **No `bot/` change; no `bot/main.py` / `EntryContext` / `_handle_entry()`
  change; no ADR-002 boundary exception.**
- **No `Policy` registration; no `record_approval()` production wiring; no
  operative `GovernanceService` approval; no acting on the `evaluate_policy()`
  result.**
- **No Sentinel approval authority; no Sentinel execution authority; no change
  to `RiskManager`, `PaperExecutor`, `AlpacaClient`, or
  `bot/execution/factory.py`.** `RiskManager.approve_buy()` remains the sole
  execution-blocking risk gate, consuming zero Sentinel input.
- **No change to model inference or `bot/strategy/ensemble.py`; no second
  directional / signal representation of any model output.**
- **No persistence, ledger backend, or ADR-004 option selection.**
- **No modification to
  `sentinel_engine/tests/test_recommendation_governance_lifecycle.py`.**

Every item in §6 (Explicit non-goals) remains **non-authorized**, restated here
because acceptance does not expand it. During B1 the production `Decision` is an
**"interpreted strategy decision"**, never a **"Sentinel recommendation"**; the
upstream strategy / ensemble remains the sole author of the action. **B2 —
the first act of Sentinel judgment (§5)** — is not authorized by this
acceptance and requires its own separate governance.

### Implementation

Acceptance authorizes the **B1 architecture in §3 only**. The **B1
implementation must occur in a separate subsequent batch**, on an isolated
branch/worktree, bound by §4 (Implementation boundary) and §12 (Verification
requirements), and must prove every one of the 20 B1 Invariants. No
implementation is performed or authorized by this acceptance step.

The date rollover during this work (system clock 2026-09-09) does not change the
`Date Accepted` the Architecture Owner specified for this act (2026-09-04).

---

## Status Log

**Proposed — DRAFT / NOT ACCEPTED — 2026-09-09 (Phase 2B).** Deterministic B1
polarity boundary draft. Authored as a draft-only task following the Phase 2
Recommendation Intelligence audit, the Phase 2A Recommendation Authority audit,
and the Phase 2B read-only repository verification (which corrected the earlier
proposed polarity rule to signal-only after finding the LSTM `[0.45, 0.55]`
band is ensemble-internal and no sentiment deadband exists). The Architecture
Owner decided the polarity rule for this draft: classification is based solely
on the existing `Evidence.data["signal"]` value —
`BUY → SUPPORTING`, `SELL → CONTRADICTING`, `HOLD → None` — with no additional
threshold, no deadband, no use of the LSTM ensemble indeterminate band, and no
use of `lstm metadata["is_degraded"]`. No production code, test, or other ADR
was modified in producing this draft; no `docs/platform/` governance file,
`docs/REQUIREMENTS.md`, or `tests/req_snapshots/req_state.json` was touched;
`sentinel_engine/tests/test_recommendation_governance_lifecycle.py` was not
touched; nothing was staged, committed, or pushed. This ADR is not accepted and
authorizes no implementation.

**Accepted — 2026-09-04 (Phase 2B — ADR-068 Explicit Acceptance).** Explicit
Architecture Owner acceptance; implementation deferred. The ADR-068 text was
accepted exactly as drafted; `Status` now reads `Accepted`, scoped exactly to
the deterministic signal-only polarity classification in §3
(`BUY → SUPPORTING`, `SELL → CONTRADICTING`, `HOLD → None`), with the LSTM
ensemble `[0.45, 0.55]` band and `lstm metadata["is_degraded"]` explicitly
excluded from polarity and every §6 non-goal remaining non-authorized. Only the
header status/date lines, the `## Acceptance` section, and this Status Log entry
were altered to perform the acceptance; no substantive Decision, invariant,
implementation-boundary, non-goal, or B1 → B2 boundary content changed. No
production code or test was modified; no other ADR was modified; no
`docs/platform/` governance file, `docs/REQUIREMENTS.md`, or
`tests/req_snapshots/req_state.json` was touched;
`sentinel_engine/tests/test_recommendation_governance_lifecycle.py` was not
touched; nothing was staged, committed, or pushed. ADR-058 D2 is not yet
satisfied (this file is not yet tracked on the default branch); ADR-068 becomes
authoritative when landed on `main`. The B1 implementation is a separate
subsequent batch bound by §4 and §12. The date rollover during this
conversation (system clock 2026-09-09) does not change the `Date Accepted` the
Architecture Owner specified (2026-09-04).
