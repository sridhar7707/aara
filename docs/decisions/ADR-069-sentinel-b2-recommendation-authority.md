# ADR-069 — Sentinel B2 Recommendation Authority (Minimum Deterministic Concur/Abstain)

**Status:** Accepted — scope limited to the B2 architecture in §3–§13 and the
**B2 Invariants** (§20); see `## Acceptance`. Per ADR-058 D2, this ADR is
authoritative once it is tracked on the default branch with `Status: Accepted`
and landed under the repository's applicable write/merge controls — carried by
the commit that lands this acceptance (recorded in the Status Log).
**Acceptance authorizes the B2 architecture, not an implementation** — the B2
implementation is a separate subsequent batch bound by §13, §18, §19 and every
B2 Invariant, and authorizes nothing outside this ADR's defined scope.
**Date Proposed:** 2026-09-09
**Date Accepted:** 2026-09-09
**Decision Type:** Architecture / Governance — narrow authorization of the
first Sentinel-authored investment recommendation (deterministic concur/abstain
on the existing entry path), one additive `Decision` provenance field, one
**fixed three-model unanimity predicate** over already-existing evidence (not a
general aggregation framework — §5.4), and one function-scoped ADR-002
exception. No execution, approval, sizing, calibration, or `bot/` gate change.
**Related ADRs:** ADR-001, ADR-002, ADR-011, ADR-020, ADR-044, ADR-045,
ADR-047, ADR-048, ADR-049, ADR-050, ADR-058, ADR-065, ADR-066, ADR-067,
ADR-068.

---

## 1. Context

### 1.1 Where B1 left the production `Decision`

ADR-067 (Accepted, landed `d7e64a4`) established the causal `Decision`
lifecycle: `bot/_main_trust_decisions.py::EntryDecisionRecorder.__init__()`
generates one `decision_id` before any entry gate and constructs one
`sentinel_engine.domain.decision.Decision` with the **literal** `action="BUY"`
(ADR-067 §3.A / §6), `confidence = final_confidence` (the existing
`ensemble_confidence(...)` weighted average), and the six optional `Decision`
fields left at their `None` defaults. That `Decision` is persisted via
`get_decision_service().create_decision(...)` on the single shared composition
pair (`sentinel_engine/composition/decision_lifecycle.py`), seeding one
`DecisionProjection`.

ADR-068 (Accepted, landed `a06a95e`; implementation landed `ccfbbb0`, current
HEAD) added **B1 deterministic evidence polarity**: for each of the three
`MODEL_OUTPUT` `Evidence` records (`xgboost`, `lstm`, `finbert`) built by
`sentinel_engine/adapters/evidence_adapter.py::to_evidence_records()`,
`polarity` is set by a pure, signal-only function of that record's own
`Evidence.data["signal"]`:

```
signal == "BUY"   ->  EvidencePolarity.SUPPORTING
signal == "SELL"  ->  EvidencePolarity.CONTRADICTING
signal == "HOLD"  ->  None   (and any other value -> None)
```

ADR-068 §3.1 **mandates** that, during B1, the production `Decision` be
described everywhere — code, docs, logs, UI, product copy — as an
**"interpreted strategy decision"**, never as a **"Sentinel recommendation."**
The upstream strategy / ensemble is the sole author of the action.

### 1.2 The B1 → B2 boundary ADR-068 drew

ADR-068 §5 states: *"B2 begins at the first act of Sentinel judgment"* and
lists, among others, **selecting an action**, **withholding an action because
Sentinel disagrees**, **emitting `WAIT`**, and **weighting or aggregating
evidence; counting / netting / scoring evidence; corroboration logic** as B2 —
each of which *"requires its own separate governance."* ADR-068 §6 restates
these as non-goals of ADR-068. ADR-066 §10 independently defers *"Operative
`EvidencePolarity` use — weighting, scoring, corroboration rules"* to separate
governance. **This ADR is that separate governance, for the minimum viable
slice and nothing more.**

### 1.3 Phase 2D read-only audit findings this ADR relies on

A read-only audit against HEAD `ccfbbb0` established:

- The **only** production caller of `DecisionService.create_decision()` is
  `EntryDecisionRecorder.__init__()`. The exit path
  (`record_exit_decision_safe` / `ExitDecisionRecorder`) never creates a
  Sentinel `Decision`.
- `RiskManager.approve_buy()` (`bot/_main_cycle.py:321`) is the sole
  execution-blocking gate and consumes zero Sentinel input.
  `GovernanceService.record_approval()` / `register_policy()` have zero
  production callers; `evaluate_policy()`'s `bool` result is discarded at the
  call site (`bot/_main_trust_decisions.py:100`).
- Nothing downstream of `create_decision()` branches on `Decision.action` to
  gate, size, or execute a trade. `Decision.action` currently flows only into
  the `DECISION_CREATED` event payload and `DecisionProjection.action`, whose
  one real consumer,
  `applications/trading_intelligence/.../sentinel_projection_decision_source.py`,
  maps it into a UI `DecisionContract` (display only).
- `model_outputs` — the exact dict B1's `to_evidence_records()` consumes — is
  already computed in `EntryDecisionRecorder.__init__()` (line 131), **before**
  the `Decision` is constructed (line 163). The `Evidence` objects themselves
  are built later, in `record_decision_safe()`.
- `DecisionAction` (`{BUY, BUY_MORE, HOLD, SELL, WAIT}`) is ratified (ADR-066)
  but inert. `WAIT` has **no** production semantics anywhere — no scheduling,
  no consumer branch. `HOLD` **is** overloaded: `ExitDecisionRecorder.hold()`
  writes `"HOLD"` to the legacy `decision_events` table on the exit path, and
  `applications/trading_intelligence/.../candidate_decision_query_service.py`
  branches `rec.action == "HOLD"` to emit exit-message UI copy.
- `Decision` has **no** provenance / authorship field. A `Decision(action=X)`
  is indistinguishable between "upstream chose X" and "Sentinel chose X."

### 1.4 Problem

For Sentinel to legitimately state *"Based on the available evidence, Sentinel
recommends BUY"* (or *"…does not concur at this time"*), it must (a) form that
position itself from the evidence rather than copy the upstream action, and
(b) record that it — not the strategy — authored the position. No Accepted ADR
authorizes either. ADR-068 §3.2 currently forbids (a); no field exists for
(b). This ADR grants exactly the minimum needed for both, bounded to the
existing entry path and to a single deterministic rule, with **no** execution,
approval, sizing, or calibration consequence.

---

## 2. Decision (summary)

Authorize **B2 — Sentinel Recommendation Intelligence**, exactly as specified
in §3–§13 and the **B2 Invariants**, and nothing else:

**Hard precondition (§4.1).** B2 recommendation formation is invoked **only**
after the existing upstream strategy has already produced a BUY candidate for
this symbol/cycle (`bot/strategy/ensemble.py::ensemble_signal()` →
`action_to_int(...) == 1`) and the pipeline has already reached
`_handle_entry()` → `EntryDecisionRecorder.__init__()`, and **before** the
causal `Decision` is persisted. B2 is **not** a general-purpose action
generator: it does not originate entry candidates and does not replace
`ensemble_signal()` / `action_to_int()` as the upstream entry trigger.

1. On that existing entry path only, Sentinel forms its own recommendation by
   applying the single fixed rule (§5) to the three already-computed
   `MODEL_OUTPUT` signals, and **selects** `Decision.action` as either `BUY`
   (concur) or `WAIT` (abstain).
2. Add one additive, backward-compatible `Decision` provenance field,
   `action_source` (§8), vocabulary `{STRATEGY, SENTINEL}`, default `None`.
3. When B2 runs, the entry-path `Decision` carries `action_source = "SENTINEL"`
   and `action ∈ {BUY, WAIT}` per the rule. When B2 is disabled or its rule
   falls back on the entry path, the `Decision` carries `action = "BUY"`
   literal and `action_source = "STRATEGY"` (explicit — the upstream strategy
   authored the action), and trade / gate / lifecycle behavior is byte-for-byte
   pre-B2. `action_source` is left `None` only for genuinely legacy / unknown /
   unspecified provenance — pre-B2 `Decision`s, the exit path, and any
   `Decision` built by code not updated for B2.
4. The recommendation is the **same** ADR-067 `Decision` / `decision_id` /
   `DecisionProjection`. No `Recommendation` class, no second `Decision`, no
   second lifecycle, no second persistence model.
5. The recommendation has **zero** execution authority (§12).

This ADR narrowly supersedes only the specific clauses of ADR-066, ADR-067 and
ADR-068 enumerated in §15, and only to the extent B2 requires.

---

## 3. Scope

**In scope — authorized by this ADR (architecture only; implementation is a
later batch):**

- §4 authority grant.
- §5's single fixed recommendation rule — **Candidate A, unanimity, the sole
  authorized B2 rule** — including the one fixed three-model agreement
  predicate it entails (§5.4: not a general aggregation framework).
- §7 abstain representation (`DecisionAction.WAIT`, as an inert label).
- §8 `Decision.action_source` additive field + a new `ActionSource` inert
  vocabulary enum.
- §11 lifecycle placement (recommendation derived from `model_outputs` in
  `EntryDecisionRecorder.__init__()`, authoritative at `DECISION_CREATED`).
- §13's function-scoped ADR-002 exception for
  `EntryDecisionRecorder.__init__()` only.
- The architectural test contract in §18 (written and run at implementation
  time, not now).

**Out of scope — not authorized, not touched (see §14 for the full list):**
every non-goal in §14; the exit path; any `bot/` file other than the one
function in §13; `RiskManager`, `PaperExecutor`, `AlpacaClient`,
`bot/execution/factory.py`, `bot/main.py`, `EntryContext`, `_handle_entry()`'s
gate sequence; the legacy `decision_events` action string; any `Policy` /
`Approval` wiring; any confidence, uncertainty, thesis, horizon, or allocation
methodology; any ADR-004 persistence selection; and
`sentinel_engine/tests/test_recommendation_governance_lifecycle.py` (remains
deferred and untouched — §14, §22).

---

## 4. Authority granted to Sentinel

B2 grants Sentinel exactly this new authority, and no more:

**G-1 — Entry-path recommendation formation.** On a cycle/symbol that has
already produced an upstream BUY candidate and reached `_handle_entry()` →
`EntryDecisionRecorder.__init__()`, Sentinel may apply the §5 rule and thereby
**author** the value of `Decision.action` for that one `Decision`.

**G-2 — Concur or abstain, from a two-value subset.** The authored value is
restricted to:
- `DecisionAction.BUY` — "Sentinel concurs: the evidence supports the BUY."
- `DecisionAction.WAIT` — "Sentinel does not concur at this time" (abstain).
No other `DecisionAction` value may be authored by B2.

**G-3 — Provenance assertion.** When B2 authors the action, it sets
`Decision.action_source = ActionSource.SENTINEL`, making the recommendation
distinguishable from an upstream strategy decision (§8).

**G-4 — Read-only consumption of existing evidence signals.** B2 may read the
three `MODEL_OUTPUT` `signal` values already present in `model_outputs` (the
same values B1 classifies). Nothing else (§6).

That is the complete grant. G-1..G-4 produce an audit/intelligence artifact on
the `Decision`; they change nothing about what executes.

### 4.1 Hard upstream-BUY precondition (architectural invariant)

B2 recommendation formation is **not a general-purpose action generator.** It
is invoked **only** after the existing upstream strategy has produced a BUY
candidate and **before** the causal `Decision` is persisted. Concretely and
non-negotiably:

- An upstream **non-BUY** outcome (`action_to_int(...) != 1` — i.e. SELL, HOLD,
  or no candidate) must **never** be converted into a Sentinel BUY.
- B2 must **not** manufacture a BUY from a SELL, a HOLD, or the absence of a
  candidate.
- B2 is **not** authorized to originate a new entry candidate.
- B2 does **not** replace `ensemble_signal()` / `action_to_int()` as the
  upstream entry trigger, and does not alter the existing entry-path condition.
- B2 remains strictly **downstream of the existing strategy candidate** and
  **upstream of `create_decision()`** — it changes only which `action` /
  `action_source` values the already-triggered `Decision` is born with, never
  whether a `Decision` is created at all.

Authorized architectural flow:

```
upstream strategy produces BUY candidate
      (ensemble_signal -> action_to_int == 1 ; _handle_entry reached)
                    |
                    v
        B2 recommendation formation   (this ADR: concur BUY / abstain WAIT)
                    |
                    v
        Decision creation   (create_decision -> DECISION_CREATED)
                    |
                    v
        existing gates / risk.approve_buy() / execution   (unchanged)
```

Explicitly **not** authorized:

```
model evidence
      |
      v
arbitrary Sentinel action generation
      |
      v
new trade candidate
```

This precondition is enforced structurally — B2 code runs only inside
`EntryDecisionRecorder.__init__()`, which is only ever constructed on the
existing upstream-BUY entry path — and is covered by §18 items 21, 30 and 31
and by B2 Invariant 21.

---

## 5. The recommendation rule (analyzed; Candidate A locked as the sole rule)

This ADR does **not** treat rule selection as a detail. Four candidate rules
were analyzed against ADR-066/068 and the repository.

### 5.1 Candidate analysis

For each: **J** = constitutes real Sentinel judgment? · **AGG** = aggregates /
counts evidence? · **CONF** = conflicts with ADR-066/068 absent explicit
authorization? · **DET** = deterministic? · **EXPL** = explainable? · **FC** =
false-confidence risk · **NEWSEM** = requires new evidence semantics?

| Rule | Definition | J | AGG | CONF | DET | EXPL | FC | NEWSEM |
|---|---|---|---|---|---|---|---|---|
| **A — Unanimity** | Concur `BUY` iff all three `MODEL_OUTPUT` signals are `"BUY"`; else `WAIT`. | Yes (independent action selection) | Yes — a bounded 3-way `AND` / "all supporting" quantifier | Yes — needs explicit narrow authorization of the bounded agreement check (ADR-068 §3.9 "count supporting sources"; ADR-066 §10 "corroboration rules") | Yes | Yes — "all three model outputs pointed to BUY" / "model *X* did not" | **Low–moderate**: "all agree" can overstate independent corroboration (xgb/lstm are correlated; the ensemble already blends them). Mitigated by §9 confidence invariants + §3.1 terminology | No — uses existing `signal` |
| **B — Majority (≥2 of 3)** | Concur `BUY` iff ≥2 signals are `"BUY"`; else `WAIT`. | Yes | Yes — an explicit **vote count with a threshold**; the canonical "model voting / majority vote" ADR-068 §3.9 names | Yes — and it is the *least* conservative; it is exactly the "2 of 3 support" scope-creep ADR-068 §11 warns against | Yes | Yes | **High**: recommends BUY while a model actively contradicts; presents a vote as a recommendation | No |
| **C — No-contradiction (≥1 SUPPORTING, 0 CONTRADICTING)** | Concur `BUY` iff at least one `polarity == SUPPORTING` and no `polarity == CONTRADICTING`; else `WAIT`. | Yes (independent dissent veto) | Yes — quantifies over records ("no CONTRADICTING", "≥1 SUPPORTING") | Yes — same category as A (a corroboration / independence rule) | Yes | Yes — "Sentinel abstains: model *X* contradicts the BUY" | **Moderate**: more permissive than A — concurs on `BUY / HOLD / HOLD`, i.e. thin support; produces more Sentinel BUYs with weaker backing | No |
| **D — Concur only (no independent selection)** | Keep `action = "BUY"` from upstream; attach evidence; do not select. | **No** — this is still B1; Sentinel forms no recommendation | No | No | Yes | n/a | n/a | No |

### 5.2 Conclusion

- **Candidate D is not B2.** It forms no recommendation and grants no new
  authority. Ratifying it would leave the B1→B2 gap exactly where Phase 2D
  found it.
- **Candidates A, B and C are all genuine B2** and all require counting /
  quantification over evidence records — the thing ADR-066 §10 and ADR-068
  §3.9 / §5 defer. None can be ratified as "mere inspection." Any B2 rule that
  actually selects an action **must** be an explicit, narrowly-scoped
  authorization of one fixed predicate. This ADR makes that authorization
  explicit (§5.4) rather than disguising it.
- **Candidate B is rejected** (§16): it is the least conservative, is the exact
  majority / model-voting pattern ADR-068 §3.9 names, and carries the highest
  false-confidence risk.
- **Candidate C is rejected** (§16): it permits a Sentinel `BUY` on
  **non-unanimous** support (e.g. `BUY / HOLD / HOLD` → `BUY`), producing more
  Sentinel-authored BUYs with weaker backing — the opposite of "minimum
  defensible." It is **not** an acceptance-time alternative.
- **Candidate A is locked as the sole B2 recommendation rule this ADR
  authorizes** (§5.3, §5.4, §5.5). Acceptance of ADR-069 does **not** leave an
  algorithmic choice open. Any future change from unanimity to a different
  evidence rule requires its own subsequent explicit architectural decision /
  ADR.

### 5.3 Ratified rule: Candidate A — Unanimity (the sole authorized B2 rule)

> **Sentinel concurs (`Decision.action = "BUY"`, `Decision.action_source =
> "SENTINEL"`) if and only if all three existing `MODEL_OUTPUT` signals are
> `"BUY"`:**
>
> ```
> IF   model_outputs["xgboost"]["signal"] == "BUY"
>  AND model_outputs["lstm"]["signal"]    == "BUY"
>  AND model_outputs["finbert"]["signal"] == "BUY"
> THEN Decision.action        = "BUY"
>      Decision.action_source = "SENTINEL"
> ELSE Decision.action        = "WAIT"     # inert abstention (§7)
>      Decision.action_source = "SENTINEL"
> ```
>
> **"Every other case" is exhaustive:** any `"SELL"`, any `"HOLD"`, any
> missing, empty, or unrecognised signal on any of the three models yields
> `WAIT`. There is no fourth branch and no configuration point.

This is the **sole** recommendation rule ADR-069 authorizes; it is fixed at
acceptance (§5.5). Rationale it is the safest *minimum*:

- **Most conservative action selection.** Sentinel puts its name on a BUY only
  when there is zero dissent *and* zero neutrality among the model outputs.
- **Abstention is costless.** B2 is non-gating (§12): whether Sentinel concurs
  or abstains, the trade still runs the normal `bot/` gates and
  `risk.approve_buy()` unchanged. A `WAIT` recommendation stops nothing; it is
  purely an honest audit signal. So "abstains more often" has no execution
  downside — only more transparency.
- **Trivially explainable**, from data already on the `Decision`'s evidence:
  the three B1 polarities already say which model, if any, was not
  `SUPPORTING`.
- **Deterministic and signal-only** — it consumes the same `signal` strings
  B1 consumes, applies no new threshold, no band, no `is_degraded`, no numeric
  weighting.

### 5.4 The evidence-aggregation boundary (one fixed predicate, not a framework)

Candidate A **technically quantifies** over the three `MODEL_OUTPUT` /
`Evidence` records — `all(signal == "BUY")` is a three-input reduction. This
ADR states that plainly rather than disguising it as "inspection."

The architectural distinction ADR-069 draws: **B2 does not establish a general
evidence-aggregation framework.** It authorizes **exactly one** fixed,
deterministic, three-model unanimity predicate, for the existing entry
recommendation path, and nothing else:

- compute the single boolean
  `model_outputs["xgboost"]["signal"] == "BUY"` **and**
  `model_outputs["lstm"]["signal"] == "BUY"` **and**
  `model_outputs["finbert"]["signal"] == "BUY"`;
- select `Decision.action` from `{"BUY", "WAIT"}` on the strength of that one
  boolean.

**ADR-069 must not be read as authorization for any of the following** — each
requires its own separate, explicit architectural decision / ADR:

- arbitrary evidence counting; a count exposed as a value anywhere;
- majority voting or any non-unanimous / "k of n" variant;
- weighted evidence; per-model weights;
- evidence scoring; evidence quality ranking;
- confidence aggregation or averaging;
- generalized corroboration or independence logic;
- dynamic, configurable, or tunable thresholds;
- adding further evidence types or sources to the predicate;
- generalized polarity netting / a net or aggregate polarity value;
- applying the predicate to any other decision, action, or path;
- feeding outcomes back into the predicate (calibration / learning).

Any future evidence-aggregation mechanism beyond this one fixed predicate is
out of scope and requires a subsequent explicit architectural decision.

### 5.5 The rule is locked — acceptance leaves no algorithmic choice open

Rule selection is the single most consequential choice in this ADR, and this
draft **resolves it** rather than deferring it:

- **Candidate A (unanimity, §5.3) is the sole B2 recommendation rule ADR-069
  authorizes.** Accepting ADR-069 means accepting exactly this predicate.
- **Candidate B is rejected** as majority / model voting (§5.2, §16).
- **Candidate C is rejected** because it permits a Sentinel `BUY` on
  non-unanimous support (§5.2, §16). It is **not** an acceptance-time
  alternative.
- Acceptance of ADR-069 must **not** leave an algorithmic choice open, a
  configuration flag, or an "A or C" decision for the implementer or the
  Architecture Owner. The implemented rule is Candidate A, verbatim.
- **Any future change** from unanimity to a different evidence rule — a
  different predicate, a threshold, a weighting, an added model — requires its
  own subsequent explicit architectural decision / ADR in this lineage. It is
  not a configuration change and is not within this ADR's authority.

---

## 6. B1 evidence boundary — exact inputs B2 may read

B2 may consume **only** the three existing `MODEL_OUTPUT` records
(`xgboost`, `lstm`, `finbert`) and, of each, **only** the fields marked
*read* below:

| Field | B2 may read? | Notes |
|---|---|---|
| `Evidence.data["signal"]` (`"BUY"` / `"SELL"` / `"HOLD"`) | **Yes — read** | The sole input to the §5 rule. Equivalently, B2 may read the B1 `polarity` derived from it — the two are interchangeable for this rule. |
| `Evidence.polarity` (B1) | **Yes — read** | Derived from `signal`; see above. |
| `Evidence.data["confidence"]` (raw model score) | **No** | Reading it would reintroduce numeric model scoring. |
| `Evidence.data["metadata"]` (SHAP drivers, `val_loss`, headlines, …) | **No** | Not a directional input. |
| `Evidence.data["metadata"]["is_degraded"]` (lstm) | **No — explicitly prohibited** | B1 deliberately ignored it (ADR-068 §3.4, §10 alt 3). B2 must not reintroduce it. Degraded-model / reliability intelligence remains deferred. |
| LSTM ensemble `[0.45, 0.55]` indeterminate band | **No — explicitly prohibited** | Ensemble-score-internal; not part of the `MODEL_OUTPUT` evidence path (ADR-068 §3.4, §10 alt 2). B2 must not reintroduce it. |

B2 must **not** read or classify `market_context`, `portfolio_snapshot`,
`risk_checks`, regime, macro, technical gates, relative strength, or any
non-model data, and must **not** create any additional `Evidence` record.

**Explicitly prohibited operations** (unless a *future* ADR narrowly
authorizes each): numeric evidence weighting; confidence averaging;
probability calibration; per-model weighting; evidence scoring; evidence
quality ranking; causal inference; net/aggregate polarity; any count exposed
as a value; corroboration or independence logic beyond the single fixed §5.3
unanimity boolean; macro / technical / portfolio / risk evidence of any kind.

B2 introduces **no** new evidence semantics: `to_evidence_records()`'s
signature, its three-record output, every `Evidence` field including
`evidence_id` / `evidence_type` / `source` / `data` / `collected_at` /
`polarity`, and the `EVIDENCE_ATTACHED` payload are **byte-for-byte
unchanged**. B2 does not mutate `Evidence.data`.

---

## 7. Abstain representation

**Decision: abstention is represented as `Decision.action = DecisionAction.WAIT`
(the string `"WAIT"`), with `Decision.action_source = ActionSource.SENTINEL`.**

Options evaluated:

| Option | Verdict | Reason |
|---|---|---|
| **A. `HOLD`** | Rejected | `HOLD` has **existing production semantics**: `ExitDecisionRecorder.hold()` writes `"HOLD"` to the legacy `decision_events` table on the exit path, and `applications/trading_intelligence/.../candidate_decision_query_service.py` branches `rec.action == "HOLD"` to emit exit-message UI copy. An entry-path abstention labelled `HOLD` would collide with position-exit semantics in at least one live consumer. ADR-067 §15 also defers "HOLD … causal Decisions." |
| **B. `WAIT`** | **Chosen** | `WAIT` is in the ratified `DecisionAction` vocabulary (ADR-066 §3.1) and has **zero** production semantics anywhere — no scheduler, no consumer branch, no legacy-ledger meaning. ADR-066 §3.1 already frames it as *"a first-class recommendation outcome, never an execution order"* — precisely an "abstain / not now" meaning. `decision_adapter.to_decision()` already accepts it. Lifecycle-compatible: `DecisionProjection.action` just carries the string. |
| **C. null `action` + `SENTINEL` source** | Rejected | `Decision.action: str` is a required, non-`Optional` field on a `frozen` dataclass, and `decision_adapter` requires it non-empty and in-vocabulary; `DecisionProjection.action` is likewise required. Making it nullable is a materially larger contract change than reusing a ratified enum value, and touches every projection consumer. |
| **D. keep `action="BUY"` + a separate `concurs: bool` field** | Rejected | Adds a second new field beyond `action_source`; larger surface; leaves `action` misleading (`"BUY"` on a Decision Sentinel did not endorse). |

**Explicit constraint carried by this ADR:** an entry-path `Decision` with
`action = "WAIT"` is an **inert recommendation label only**. It triggers **no**
scheduling, **no** re-evaluation, **no** retry, **no** position lifecycle, and
**no** execution behavior of any kind — re-affirming ADR-066 §6. It is an
audit/intelligence value that flows through `DECISION_CREATED` →
`DecisionProjection.action` and into read-side/UI consumers as display data.

**Follow-on (not a B2 blocker, flagged in §17):** once B2 lands,
`sentinel_projection_decision_source.py` will begin surfacing `action = "WAIT"`
and `action_source`; downstream UI copy for a `WAIT` recommendation is a
separate `applications/trading_intelligence` concern, not authorized or
required here.

---

## 8. Decision provenance — `action_source`

### 8.1 New field

Add one additive field to `sentinel_engine/domain/decision.py::Decision`:

```
action_source: Optional[str] = None
```

No domain-object validation (matching the module's trusting-domain-object
convention); enforced-when-present at the adapter boundary
(`decision_adapter.to_decision()`), exactly as ADR-066 §3.8 did for `action`.

### 8.2 New inert vocabulary enum

Add `sentinel_engine/domain/action_source.py`:

```
class ActionSource(str, Enum):
    STRATEGY = "STRATEGY"   # the action was authored by the upstream strategy / ensemble
    SENTINEL = "SENTINEL"   # the action was authored by Sentinel's B2 recommendation rule
```

Exactly two members. Inert: it carries a value and nothing else — no
evaluation, no enforcement beyond the adapter boundary check, no lifecycle, no
side effect, no authority. This mirrors the ADR-066 treatment of
`DecisionAction` / `Horizon` / `EvidencePolarity`.

### 8.3 Smallest safe vocabulary?

Yes. Two explicit values are the minimum that distinguishes "upstream
authored" (`STRATEGY`) from "Sentinel authored" (`SENTINEL`). **No other
provenance value is introduced.** A third value (e.g. `SENTINEL_CONCUR` vs
`SENTINEL_OVERRIDE`) is unnecessary because B2 cannot override — it only
concurs (`BUY`) or abstains (`WAIT`), both of which are `SENTINEL`. `None`
(field absent) remains valid as a third *state* — **legacy / unknown /
unspecified** provenance — but is never the deliberate value for an
entry-path `Decision` once B2 is implemented (§8.4): those always set either
`SENTINEL` or `STRATEGY`.

### 8.4 Provenance semantics (resolved) and backward compatibility

**Final provenance semantics — exactly three states, no others:**

| `action_source` | Meaning |
|---|---|
| `"STRATEGY"` | The action was authored by the upstream strategy / ensemble. |
| `"SENTINEL"` | The action was authored by Sentinel's B2 recommendation rule (§5.3) — concur (`BUY`) or abstain (`WAIT`). |
| `None` (absent) | Legacy / unknown / unspecified provenance. |

On the entry path, once B2 is implemented, `action_source` is **always set
explicitly** — the recorder never deliberately leaves it `None` there:

- B2 runs, rule concurs → `action_source = "SENTINEL"`, `action = "BUY"`.
- B2 runs, rule abstains → `action_source = "SENTINEL"`, `action = "WAIT"`.
- **B2 disabled, or its rule falls back** (the rule raises and is caught, or
  the feature is turned off) → `action_source = "STRATEGY"`, `action = "BUY"`
  literal. The upstream strategy authored the entry candidate/action, so
  `"STRATEGY"` is the accurate, explicit provenance. Trade / gate / lifecycle
  behavior is byte-for-byte pre-B2; the only difference from pre-B2 is that
  the additive field now carries `"STRATEGY"` instead of not existing.
- The **only** entry-path case that leaves `action_source` `None` is a failure
  of `Decision` construction / `create_decision()` *itself* — already isolated
  by ADR-067 §9, and one where no `Decision` (hence no provenance) is recorded
  at all.

**`None` — legal, never rewritten.** `None` remains a valid value for every
pre-B2 `Decision`, every `Decision` on a path B2 does not cover (the exit
path), and any `Decision` built by code not updated for B2. **Historical
records are never rewritten** — no migration, no backfill. A `Decision` (or
`decision_events` row, or `DecisionProjection`) created before B2 keeps
`action_source` absent forever. `"STRATEGY"` is never written to a `Decision`
B2 did not process (e.g. an exit-path `Decision`).

### 8.5 No new object / identity / lifecycle

`action_source` is one optional field on the **existing** `Decision`. This ADR
introduces **no** `Recommendation` class, **no** second `Decision` identity,
**no** second lifecycle, **no** duplicate persistence model, and **no** new
correlation identifier — the single ADR-067 `decision_id` remains the only
lifecycle identity.

---

## 9. Confidence semantics (unchanged)

Ratified explicitly, restating ADR-068 §3.3:

- `Decision.confidence` **remains** the existing `final_confidence` —
  `ensemble_confidence(xgb_prob, lstm_prob, sentiment, macro_score)` — passed
  through **byte-for-byte unchanged**. B2 does not recompute, rescale,
  calibrate, reinterpret, or adjust it.
- It is an **uncalibrated ensemble model score**. It is **not** a probability
  of correctness, **not** a calibrated confidence, and **not** a "Sentinel
  recommendation confidence."
- B2 creates **no** new numeric confidence value anywhere.
- Any surface displaying `Decision.confidence` — including surfaces that now
  also show `action_source = "SENTINEL"` — must continue to describe it as an
  uncalibrated ensemble score, not as Sentinel's confidence in its
  recommendation.

---

## 10. Other `Decision` fields (unchanged — remain `None`)

On every B2-produced `Decision`, all six optional fields remain at their `None`
default:

- `thesis` — remains `None`. Populating it would require a thesis methodology
  (deferred — ADR-011, ADR-066 §5, ADR-068 §3.8). The recommendation's
  explanation is the deterministic §5 rule plus the already-attached B1
  polarities, not a generated string.
- `counterfactual` — remains `None`.
- `uncertainty` — remains `None`. No uncertainty methodology is defined or
  authorized (ADR-068 §3.3, §6).
- `horizon` — remains `None` (ADR-020, ADR-066 §5).
- `desired_allocation` — remains `None`. No sizing (§14).
- `minimum_viable_allocation` — remains `None`.

B2 populates none of them and reads none of them to derive anything.

---

## 11. Causal lifecycle & the ordering resolution

### 11.1 One identity, one lifecycle

B2 uses the ADR-067 lifecycle unchanged:

```
DECISION_CREATED  ->  EVIDENCE_ATTACHED  ->  GOVERNANCE_EVALUATED  ->  DECISION_EXECUTED
```

with exactly **one** `decision_id`, **one** `Decision`, **one**
`DecisionProjection`, **one** lifecycle. The recommendation *is* the Decision
that ADR-067 already creates pre-gate; B2 changes only which `action` /
`action_source` values that Decision is born with.

### 11.2 The recommendation must be authoritative at `DECISION_CREATED`

The rule result must be known **before** `create_decision()` is called, so the
`action` recorded in the `DECISION_CREATED` event and the seeded
`DecisionProjection` is the final, authoritative recommendation — never a
placeholder later corrected. (`Decision` is `frozen`; the projection walks
once; a post-creation action change is prohibited — see §14, B2 Invariant 15.)

### 11.3 Ordering resolution (Phase 2D open item)

`model_outputs` is available in `EntryDecisionRecorder.__init__()` (line 131);
the `Evidence` objects are constructed later in `record_decision_safe()`.

**Resolution: B2 derives its recommendation directly from the same
`model_outputs` dict B1 converts into `Evidence`, inside
`EntryDecisionRecorder.__init__()`, before `create_decision()` is called.**
The ordering of `record_decision_safe()` and `to_evidence_records()` is **not**
changed. Rationale:

- It is the smallest change that preserves causal integrity — no reordering,
  no new call, no duplicated evidence construction.
- The §5 rule needs only the three `signal` strings, which are already in
  `model_outputs["xgboost"|"lstm"|"finbert"]["signal"]` — the identical values
  B1 reads. B2 does not need constructed `Evidence` objects.
- It mirrors B1's own pattern (`evidence_adapter._polarity_for_signal(signal)`
  works off the signal string).

### 11.4 Preferred implementation seam (bounds, not a mandate)

A new `sentinel_engine`-internal function — e.g.
`sentinel_engine/adapters/recommendation_adapter.py::recommend_entry_action(model_outputs: dict) -> tuple[str, str]`
returning `(action, action_source)` — pure, deterministic, zero `bot` import,
signal-only, applying §5.3. `EntryDecisionRecorder.__init__()` calls it with
`self.model_outputs` and passes the result into the existing `Decision(...)`
construction. An equivalent `sentinel_engine`-internal seam is permissible
provided it introduces no second signal representation and no `bot/strategy/`
import into `sentinel_engine/` (mirrors ADR-068 §4).

### 11.5 Rejection / failure / absence behavior

- **Early gate rejection / `RiskManager` rejection / fill failure** — unchanged
  from ADR-067 §5 / ADR-065. The projection terminates at the stage it
  reached; the legacy `QUALIFIED_REJECTION` row is the authoritative negative
  record. A B2 `action` of `WAIT` on such a Decision is just the recorded
  recommendation; it does not add or change any rejection semantics, and
  `"WAIT"` is never written as a `DecisionAction` cause of rejection.
- **B2 rule failure / unavailability** — the recorder still constructs the
  `Decision` with `action = "BUY"` literal and `action_source = "STRATEGY"`
  (explicit strategy provenance, §8.4); the `decision_id` is retained and the
  trade proceeds unaffected. Only a failure of `Decision` construction /
  `create_decision()` itself is caught by the ADR-067 §9 failure-isolation
  `try/except`, in which case no `Decision` (and no `action_source`) is
  recorded — byte-for-byte pre-B2. In neither case does B2 block, delay,
  retry, or alter the gate sequence, `risk.approve_buy()`, `client.buy()`, or
  the Trust Ledger write.
- **Non-entry paths** — the exit path never calls `create_decision()`; B2 does
  not touch it.

---

## 12. Execution / approval invariants

Ratified explicitly. A B2 recommendation — whether `BUY` or `WAIT`:

1. **cannot execute a trade** — no code path from `Decision` / `DecisionService`
   / `action_source` to any executor exists or is created; the four lifecycle
   services import no `bot` / `alpaca` module (guard-tested).
2. **cannot approve a trade** — `GovernanceService.record_approval()` and
   `register_policy()` remain uncalled in production; `evaluate_policy()`'s
   result remains discarded at the call site.
3. **cannot veto `RiskManager`** — `risk.approve_buy()` consumes zero Sentinel
   input; B2 adds none.
4. **cannot bypass `RiskManager`** — no path around Gate 8f is created.
5. **cannot alter `PaperExecutor`** — untouched.
6. **cannot alter `AlpacaClient`** — untouched.
7. **cannot alter `bot/` gate ordering** — `_handle_entry()`'s Gates 0–8f are
   unmodified, unreordered, unreduced in strictness.
8. **cannot consume or enable Robinhood / live execution** — none introduced or
   implied.
9. **cannot create autonomous execution authority** — none introduced.

`RiskManager.approve_buy()` remains the sole execution-blocking gate.
`PaperExecutor` remains the sole execution authority. A `WAIT` recommendation
does not stop the trade; a `BUY` recommendation does not authorize it. The
Constitution rules (ADR-047/048/049/050/051) remain advisory and non-blocking;
B2 adds no new authority and makes no governance verdict consequential.

---

## 13. Module boundaries & ADR-002 exception

### 13.1 `sentinel_engine/` side — no ADR-002 exception

New `sentinel_engine/domain/action_source.py`, the additive
`Decision.action_source` field, the adapter-boundary validation, and the new
recommendation function/seam (§11.4) are all inside `sentinel_engine/`, which
governs itself under ADR-001. `sentinel_engine`'s zero-import-of-`bot`
guarantee is preserved: the new modules import only the standard library and
`sentinel_engine` internals; no `bot/strategy/` helper (`_prob_signal`,
`_sentiment_signal`, `build_model_outputs`, `_LSTM_INDETERMINATE_*`) is
imported. No ADR-002 exception is created or needed for the
`sentinel_engine/` work.

### 13.2 `bot/` side — one narrow, function-scoped ADR-002 exception

**Protected file:** `bot/_main_trust_decisions.py`
**Symbol:** `EntryDecisionRecorder.__init__()` — this only.

**Permitted, and only this:**
- add the necessary `import` of the new `sentinel_engine` recommendation
  function/seam and `ActionSource` (both outside `bot/`, `bot → sentinel_engine`
  direction, consistent with ADR-001 and the existing
  evidence/governance/decision imports already in this file);
- call that function with the already-computed `self.model_outputs`;
- pass the returned `action` value (in place of the current literal `"BUY"`)
  and the returned `action_source` value into the existing `Decision(...)`
  construction at `create_decision()`;
- wrap only as needed within the **existing** ADR-067 §3.A failure-isolation
  `try/except` (no new control flow beyond obtaining the two values and
  passing them in).

**Prohibited:** any change to `reject()`, `record_executed()`,
`record_order_not_filled()`, `record_decision_safe()`,
`record_exit_decision_safe()`, `ExitDecisionRecorder`,
`record_risk_evaluation_safe()`, `record_data_quality_safe()`, the ADR-009
evidence block, the ADR-045 governance block, or the ADR-067 `decision_id`
threading; any change to the legacy `decision_events` action string passed to
`write_decision_event()` (it stays `"BUY"` / `"REJECT"` exactly as today — B2
touches only the *Sentinel* `Decision.action`); any change to gate logic, risk
logic, execution, order-fill behavior, or control flow beyond obtaining and
passing the two values; any second `bot/` file; any `bot/main.py` /
`EntryContext` / `_handle_entry()` gate-sequence change; any
`bot/trust_ledger/decisions.py` change; any `sentinel_engine → bot` import.

**No `.github/workflows/*` change is authorized or required.** Both ADR-002
entry points (CLI `trade.yml → bot/main.py`; scheduler/HTTP
`watchdog.yml → dashboard/http_endpoints.py GET /run/cron →
scheduler/trading_job.py → bot.main.run()`) must be exercised in
implementation testing. Implementation occurs on an isolated branch/worktree,
not directly on `main`; the full `sentinel_engine/tests` and `tests/` suites
and `scripts/verify_single_write_path.py` must pass before and after.

This is the eighth application of the ADR-006/009/012/013/014/045/065/067
narrow-exception template.

---

## 14. Non-goals

This ADR does **not** authorize, imply, prepare for, or partially enable any of
the following; each remains governed elsewhere or explicitly deferred:

- Originating a `BUY` recommendation for any symbol/cycle that did not already
  reach the entry decision path (`action_to_int(...) == 1`). B2 never
  manufactures a decision.
- Any `SELL`, `BUY_MORE`, or real `HOLD` exit/position-lifecycle behavior;
  averaging-down; blank-slate reassessment.
- `WAIT` scheduling, timers, deferred re-evaluation, or any behavior beyond
  `WAIT` as an inert label.
- Overriding the upstream action into a contrary actionable order; turning
  `BUY` into `SELL`.
- Any execution, execution veto, gate bypass, or change to
  `RiskManager` / `PaperExecutor` / `AlpacaClient` / `bot/execution/factory.py`.
- `GovernanceService.register_policy()`; `record_approval()` production wiring;
  operative `GovernanceService` approval; acting on the `evaluate_policy()`
  result.
- Any Sentinel approval authority; any Sentinel authority over
  `RiskManager.approve_buy()`.
- Autonomous execution; automatic authority expansion; live / Robinhood
  execution.
- Portfolio sizing; position sizing; Kelly logic; allocation policy;
  capital-pool interaction; risk optimization.
- Numeric evidence weighting; confidence averaging; probability calibration;
  per-model weighting; evidence scoring; evidence quality ranking; causal
  inference; a net/aggregate polarity; any count exposed as a value; any
  corroboration rule other than the single fixed §5.3 unanimity boolean.
- Consuming `is_degraded`, the LSTM `[0.45, 0.55]` band, model `confidence`,
  `metadata`, or any non-`MODEL_OUTPUT` evidence.
- A calibration / learning / feedback loop; Investment Memory.
- A distinct "Sentinel recommendation confidence"; any `uncertainty` value or
  methodology; any `thesis` / `counterfactual` / `horizon` population.
- A `Recommendation` class / object / service; a "Risk Governor"; a second
  `Decision`; a second lifecycle; a second identity; a duplicate persistence
  model.
- Any new `EventType`, `DecisionState`, or `ApprovalStatus` member. (`WAIT`
  and `ActionSource` values are inert vocabulary, not lifecycle states.)
- Any change to `to_evidence_records()`, the `EVIDENCE_ATTACHED` payload, or
  any `Evidence` field; any `Evidence.data` mutation.
- Any change to the legacy `decision_events` action string, schema, or write
  path.
- Any ADR-004 persistence / ledger-backend selection.
- Any modification to
  `sentinel_engine/tests/test_recommendation_governance_lifecycle.py` — it
  remains deferred (it exercises `Policy(enabled=True)` / `record_approval()`,
  which B2 does not authorize) and untouched.
- Any `bot/` change beyond the one function in §13.

---

## 15. Relationship to existing ADRs (supersession accounting)

### 15.1 Not reopened, not modified

- **ADR-044** — the architecture authority hierarchy and its
  conflict-resolution rule are **not reopened or reinterpreted**. This ADR
  slots in as a Tier-2 Accepted ADR in the ADR-066/067/068 lineage.
- **ADR-047 (Risk Governor Authority)** — **not modified.** Constitution Rule 1
  stays advisory-only; `risk.approve_buy()` stays the independent
  execution-blocking BUY gate. B2 adds no authority here.
- **ADR-048 (Drawdown Circuit Breaker)** — **not modified.** Rule 4 stays
  advisory-only.
- **ADR-049 (Trade Structure)** — **not modified.** B2 introduces no trade
  structure, stop, target, or R:R logic.
- **ADR-050 (Approval Escalation)** — **not modified.** The approval ladder
  stays advisory, logged, non-blocking; B2 makes no governance verdict
  consequential and wires no approval.
- **ADR-045** — its §3 prohibition on operative `Policy` registration and
  `record_approval()` wiring is **unchanged and re-affirmed**.
- **ADR-065** — its execution-outcome-reporting path and SQL-recency
  correlation are **not rewritten**. `record_execution()` now runs against a
  `Decision` whose `action` may be `WAIT`; that is display/audit data and does
  not change the FILLED/REJECTED/FAILED outcome logic.
- **ADR-001 / ADR-002** — preserved; §13 is the requested narrow, function-
  scoped exception, following the established template.
- **ADR-011 / ADR-020** — adjacency only. B2 implements no Thesis/Conviction
  (`thesis` stays `None`) and no exit/sell/`holding_horizon` intelligence
  (`horizon` stays `None`; no `SELL`/`HOLD`/`BUY_MORE`). Neither is superseded
  or amended.

### 15.2 Narrowly superseded — exactly these clauses, only for the entry path

| ADR / clause | What it says today | Narrow supersession | Why B2 requires it |
|---|---|---|---|
| **ADR-068 §3.2** ("Action preservation": `Decision.action` is *"copied, unchanged, from the upstream strategy decision"*; *"B1 has no authority to change, suppress, replace, veto, or withhold the action"*) | Entry-path `action` is always the upstream `"BUY"` literal | Superseded **only** so that, on the entry path, Sentinel's §5.3 rule may set `action` to `BUY` (concur) or `WAIT` (abstain). No suppression of the *trade*; no `SELL`; no origination. | This is the definitional core of B2 — "the first act of Sentinel judgment" ADR-068 §5 itself names and defers to "its own separate governance." |
| **ADR-068 §3.9 / §5 / §6** (classification-only; "count supporting sources" and "corroboration logic" are B2 / non-goals) | B1 may not count, aggregate, or select an action | Not a supersession of ADR-068's *ratifications* — it is the exercise of the deferral ADR-068 §5 explicitly points here. This ADR authorizes **exactly one** bounded corroboration boolean (§5.4) and nothing else. | B2's rule inherently quantifies over the three records; ADR-068 required that a separate ADR authorize it explicitly and narrowly — §5.4 does. |
| **ADR-066 §10** ("Operative `EvidencePolarity` use — weighting, scoring, corroboration rules" deferred to separate governance) | Polarity is inert | Exercised, not superseded: this ADR is that separate governance, for the single §5.3 rule. No weighting, no scoring, no score value. | Same as above. |
| **ADR-066 §6 / ADR-067 §6** ("the entry path is BUY-only"; "no code path creates a `Decision` with `BUY_MORE`, `HOLD`, `SELL`, `WAIT`"; "special execution logic for `BUY_MORE` or `WAIT`" is a non-goal — "they are action labels only") | Entry-path `Decision.action` is only ever `"BUY"` | Superseded **only** so the entry-path `Decision` may carry `action = "WAIT"` as an **inert label** representing Sentinel abstention. Re-affirms: no scheduling, re-evaluation, or execution behavior attaches to it. | Abstention needs a representation; `WAIT` is the ratified label with no competing production semantics (§7). |
| **ADR-067 §14** ("Sentinel action selection; action override" listed as a non-goal) | ADR-067 authorizes no action selection | Superseded **only** for selection between `{BUY, WAIT}` on the entry path. **Not** override (no `BUY→SELL`, no origination). | Definitional core of B2. |

No ADR beyond ADR-066, ADR-067 and ADR-068 is superseded or amended. If
implementation review finds a further ADR must be touched, implementation
**stops** and a scope amendment is required (§21).

---

## 16. Alternatives considered

1. **Candidate D — concur only, no independent selection.** Rejected: it is
   still B1. It forms no recommendation, grants no new authority, and leaves
   the B1→B2 gap exactly where Phase 2D found it.
2. **Candidate B — majority (≥2 of 3).** Rejected: least conservative; it is
   the canonical "model voting / majority vote" ADR-068 §3.9 names by way of
   prohibition, and the "2 of 3 support" scope-creep ADR-068 §11 explicitly
   warns against; highest false-confidence risk (recommends `BUY` while a
   model actively contradicts).
3. **Candidate C — no-contradiction (≥1 SUPPORTING, 0 CONTRADICTING).**
   Rejected outright: it permits a Sentinel `BUY` on **non-unanimous** support
   — e.g. `BUY / HOLD / HOLD` → `BUY` — producing more Sentinel-authored BUYs
   with weaker backing, the opposite of "minimum defensible." Its
   dissent-detector framing is noted but does not outweigh that. Candidate C
   is **not** an acceptance-time substitution for Candidate A (§5.5); adopting
   it later would require its own ADR.
4. **Introduce a `Recommendation` class to hold the interpreted decision.**
   Rejected: `Decision` already carries every needed field; a second type forks
   identity and lifecycle (ADR-068 §10 alt 5; ADR-067 §14 non-goal).
5. **A second `Decision` referencing the first.** Rejected: "a second decision
   identity space" is an ADR-067 §14 non-goal; breaks the one-projection walk.
6. **Mutating the existing `Decision.action` after `create_decision()`.**
   Rejected: `Decision` is `frozen`; the lifecycle is event-sourced and walks
   once; the `DECISION_CREATED` event and seeded projection would disagree with
   the "real" recommendation. §11.2 requires the recommendation to be
   authoritative at creation.
7. **Abstain as `HOLD`.** Rejected: `HOLD` has live exit-path and UI-consumer
   semantics (§7).
8. **Abstain as a nullable `action`.** Rejected: larger contract change than
   reusing a ratified enum value; touches every projection consumer (§7).
9. **Implement the rule in `bot/`** (e.g. in `build_model_outputs` or
   `record_decision_safe`). Rejected: `record_decision_safe` runs *after*
   `create_decision()`, so the recommendation could not be authoritative at
   `DECISION_CREATED`; and a `sentinel_engine`-internal seam off `model_outputs`
   needs a strictly smaller ADR-002 exception (§11.3, §13).
10. **Populate `thesis` with a generated explanation string.** Rejected:
    requires a thesis methodology (deferred). The rule + B1 polarities are
    self-explaining without a stored string.

---

## 17. Risks

- **Rule mis-selection.** The §5.3 rule is a genuine judgment call. Mitigation:
  §5.1 candidate analysis is on the record; §5.5 **locks** Candidate A as the
  sole authorized rule (no acceptance-time A/C choice, no configuration flag),
  and requires any future rule change to go through its own subsequent ADR.
- **Scope creep from a boolean to a count/score.** Once a three-way agreement
  check exists, a configurable threshold or an exposed count is a small code
  step away. Mitigation: §5.4 authorizes *only* the fixed unanimity boolean;
  §18 requires a guard test that no count/threshold/weight/score is computed or
  exposed (mirrors ADR-068 invariant 8).
- **False confidence from "all models agree."** The three models are not
  independent (xgb/lstm both price-trained; the ensemble already blends them).
  A `SENTINEL / BUY` decision may read as strong corroboration. Mitigation:
  §3.1 / §9 terminology and confidence invariants; the recommendation is
  non-gating; unanimity is the most conservative available bar.
- **Terminology flip.** ADR-068 §3.1 bans "Sentinel recommendation" for the
  production `Decision`. B2 flips this **only** for
  `action_source == "SENTINEL"` decisions; every `action_source != "SENTINEL"`
  decision (i.e. `"STRATEGY"` or `None` — fallback, exit-path, legacy) keeps
  the "interpreted strategy decision" label. Mitigation: §8.4 provenance
  semantics; §18 item 1 requires consumers to key the label on
  `action_source == "SENTINEL"`, not on the mere existence of a `Decision`.
  Enumerating every affected UI/log surface is a non-blocking implementation
  follow-on, not part of this ADR.
- **Downstream `WAIT` handling.** After B2 lands,
  `sentinel_projection_decision_source.py` surfaces `action = "WAIT"` and
  `action_source` into `applications/trading_intelligence` UI; copy/rendering
  for a `WAIT` recommendation is unspecified there. Flagged as a follow-on;
  **not** authorized or required by this ADR, and **not** a B2 blocker (the
  value is inert).
- **`confidence` mislabelling** carries over from ADR-068 §11 and is
  re-fenced by §9.
- **Existing guard test churn.**
  `tests/phase1a/test_causal_decision_lifecycle.py::test_construction_seeds_one_sentinel_decision_with_action_buy`
  asserts the current `"BUY"` literal and will need an additive update under
  B2 (concur → `BUY`, abstain → `WAIT`, fallback → `BUY`). Called out in §18;
  no test is written by this ADR.
- **`ActionSource` / `action_source` are new vocabulary** and, like ADR-066's
  additions, rest on this ADR for their authorization — acceptance is a
  prerequisite to landing them (§21).

### 17.1 Resolved at acceptance (Phase 2F)

The fallback / B2-disabled entry-path `Decision` **sets `action_source =
"STRATEGY"` explicitly** (§8.4) — the upstream strategy authored the entry
candidate/action, so `"STRATEGY"` is the accurate, explicit provenance. `None`
is reserved for genuinely legacy / unknown / unspecified provenance (pre-B2
`Decision`s, the exit path, code not updated for B2) and remains legal; it is
never the deliberate value for an entry-path `Decision` once B2 is
implemented. No other provenance value exists.

---

## 18. Test contract (architectural — written and run at implementation, not now)

A B2 implementation authorized by this ADR must prove, each with a direct
test:

**Recommendation identity & provenance**
1. A `SENTINEL`-sourced `Decision` is distinguishable from a `STRATEGY` /
   unset one via `action_source` alone.
2. `action_source` vocabulary is exactly `{STRATEGY, SENTINEL}`; `None`
   remains valid; the adapter boundary rejects any other value when present.
3. No historical `Decision` / `decision_events` row / `DecisionProjection` is
   rewritten or backfilled.

**The rule (§5.3)**
4. **The complete 27-row (`3^3`) truth table** over
   `signal ∈ {"BUY", "SELL", "HOLD"}` for `xgboost` × `lstm` × `finbert`,
   plus a defensive missing / empty / unrecognised value on each model:
   `Decision.action == "BUY"` **iff** all three signals are exactly `"BUY"`
   (the single row `BUY/BUY/BUY`); **every one of the other 26 rows** — and
   every defensive case — yields the inert `Decision.action == "WAIT"`; the
   rule never raises into the trade path.
5. Guard: no count, threshold, weight, score, or net/aggregate polarity is
   computed, stored, or exposed anywhere; the rule reads only the three
   `MODEL_OUTPUT` signals and performs exactly one three-input `AND`.
6. Guard: `is_degraded`, the LSTM `[0.45, 0.55]` band, model `confidence`, and
   `metadata` are not read by the rule.
7. Guard: no non-`MODEL_OUTPUT` data (`market_context`, `portfolio_snapshot`,
   `risk_checks`, regime, macro) is read by the rule.

**Abstain representation**
8. Abstention is `Decision.action == "WAIT"` with `action_source == "SENTINEL"`.
9. Guard: a `WAIT` `Decision` triggers no scheduling, re-evaluation, retry,
   position-lifecycle, or execution behavior; `"WAIT"` is never written as a
   `DecisionAction` cause of a rejection row.

**One identity / lifecycle**
10. Exactly one `Decision`, one `decision_id`, one `DecisionProjection` per
    entry cycle; no `Recommendation` type exists; no second `Decision` is
    created.
11. The recommendation is authoritative at `DECISION_CREATED`: the
    `DECISION_CREATED` payload `action` and the seeded `DecisionProjection.action`
    equal the final rule result (no placeholder-then-correction).
12. The `Decision` remains `frozen`; `action` is never mutated after creation.

**Evidence untouched**
13. `to_evidence_records()` output — `evidence_id`, `evidence_type`, `source`,
    `data` (all contents), `collected_at`, `polarity` — and the
    `EVIDENCE_ATTACHED` payload are byte-for-byte identical to pre-B2 for the
    same inputs.
14. `Evidence.data` is not mutated by B2.

**Confidence & other fields**
15. `Decision.confidence` on a B2 `Decision` equals `ensemble_confidence(...)`
    byte-for-byte; B2 writes no separate confidence value.
16. `uncertainty`, `thesis`, `counterfactual`, `horizon`,
    `desired_allocation`, `minimum_viable_allocation` are `None` on every
    B2-produced `Decision`.

**Execution / approval invariants (§12)**
17. `RiskManager.approve_buy()` receives byte-for-byte identical arguments;
    its call site in `bot/_main_cycle.py` is unchanged; blocking behavior
    unchanged.
18. `GovernanceService.register_policy()` and `record_approval()` are never
    invoked across a full `_handle_entry()`; `evaluate_policy()`'s result is
    still discarded.
19. Structural: the recommendation seam and the four lifecycle services import
    no `bot` / `alpaca` module (extends the existing AST-scan guard).
20. `bot/` gate ordering (Gates 0–8f) is unchanged; `client.buy()` still
    routes through `PaperExecutor` via `bot/execution/factory.py`.
21. **Negative:** an upstream cycle that did **not** produce a BUY candidate
    (`action_to_int(...) != 1`, `_handle_entry()` not reached) produces **no**
    `SENTINEL` `Decision` and no B2 `BUY` — B2 never manufactures a decision.
22. **Negative:** B2 never authors `SELL`, `BUY_MORE`, or `HOLD`; the
    authored value is always in `{BUY, WAIT}`.

**Failure / absence safety**
23. With B2 disabled or its rule raising, the entry-path `Decision` carries
    `action = "BUY"` literal and `action_source == "STRATEGY"` (§8.4);
    `_handle_entry()` trade / gate / lifecycle behavior is byte-for-byte
    pre-B2; `decision_id` retained; trade unaffected. Only a failure of
    `Decision` construction / `create_decision()` itself leaves no `Decision`
    (and no `action_source`) recorded, per ADR-067 §9.

**Regression / boundary**
24. `sentinel_engine/tests/test_package_imports.py` and the
    `applications/trading_intelligence` equivalent pass unchanged (extended to
    the new module).
25. `scripts/verify_single_write_path.py` passes unchanged.
26. Existing ADR-009 / ADR-012 / ADR-036 / ADR-068 evidence tests and ADR-065
    reporting tests pass unchanged.
27. `tests/phase1a/test_causal_decision_lifecycle.py` guard tests
    (`approve_buy` call site unchanged; no `record_approval` / `register_policy`
    in the live path; `EntryContext` has no Sentinel `decision_id`; exactly
    one `create_decision` call site) pass, with
    `test_construction_seeds_one_sentinel_decision_with_action_buy` updated
    additively for the concur / abstain / fallback cases.
28. `sentinel_engine/tests/test_recommendation_governance_lifecycle.py` is
    untouched.
29. Both ADR-002 entry points (CLI and scheduler/HTTP) exercise the B2 path.

**Upstream-BUY precondition & rule-lock**
30. **B2 invocation is restricted to the existing upstream-BUY entry path.**
    B2's recommendation code path is reachable **only** from
    `EntryDecisionRecorder.__init__()`, which is constructed only when
    `action_to_int(...) == 1` and `_handle_entry()` has been reached. No other
    call site invokes it.
31. **No general-purpose action-generation path exists.** There is no function,
    entry point, or code path by which B2 (or any `sentinel_engine`
    recommendation code) produces a `Decision`, a `BUY`, or an entry candidate
    from evidence alone, independent of an already-triggered upstream BUY
    candidate. Negative: an upstream `SELL`, an upstream `HOLD`, and an absent
    candidate each produce **no** `SENTINEL` `Decision` and **no** B2 `BUY`.
32. **The implemented rule is Candidate A verbatim — no A/C choice, no flag.**
    The recommendation function computes exactly the three-model unanimity
    predicate (§5.3); it exposes no configuration parameter, no threshold
    argument, and contains no `≥1 SUPPORTING / 0 CONTRADICTING` (Candidate C)
    branch or any other alternate rule path. Candidate C cannot be enabled by
    an acceptance-time or runtime choice.
33. **Evidence aggregation is limited to the single fixed unanimity predicate.**
    The rule performs exactly one three-input `AND` over the three
    `MODEL_OUTPUT` signals and nothing else — no count value, no weight, no
    score, no ranking, no net polarity, no k-of-n, no additional evidence
    type — matching §5.4.
34. **Rule-change governance is recorded.** The recommendation module and this
    ADR state that changing the predicate (a different rule, a threshold, a
    weighting, an added model) requires a subsequent explicit architectural
    decision / ADR; the module carries no mechanism to change it at runtime or
    by configuration.

Negative tests are required for every prohibited behavior in §5.4, §6, §12 and
§14 — including §4.1 (an upstream non-BUY, and an absent candidate, must each
produce no `SENTINEL` `Decision` and no B2 `BUY`).

---

## 19. Verification requirements

Before a B2 *implementation* may be proposed for acceptance of the
implementation:

1. Every §18 test passes; every **B2 Invariant** below has a direct test.
2. Full `sentinel_engine/tests` and `tests/` suites pass before and after,
   0 regressions; `scripts/verify_single_write_path.py` passes.
3. Both ADR-002 entry points are exercised.
4. Implementation stayed within §13's exception scope; any need to touch a
   second `bot/` file, `RiskManager`, an executor, `bot/main.py`,
   `EntryContext`, or the gate sequence **stopped** implementation and
   triggered a scope amendment.
5. A rollback plan (§22) is recorded before code changes start; implementation
   occurred on an isolated branch/worktree.

---

## 20. B2 Invariants

A B2 implementation authorized by this ADR must prove all of the following:

1. **Bounded authority** — B2 authors `Decision.action` **only** on the
   existing entry path (`action_to_int(...) == 1`, `_handle_entry()` reached),
   and **only** as a value in `{BUY, WAIT}`.
2. **No manufactured decisions** — no `Decision`, and no `SENTINEL` provenance,
   for any symbol/cycle that did not already reach the entry decision path.
3. **Deterministic unanimity rule — the sole authorized rule.** `action =
   "BUY"` iff all three `MODEL_OUTPUT` signals equal `"BUY"`; otherwise
   `action = "WAIT"`. The rule consults nothing else, exposes no threshold or
   configuration, and contains no Candidate-B / Candidate-C branch or any
   other alternate rule path (§5.3–§5.5).
4. **No aggregation exposure** — no count, threshold, weight, score, net
   polarity, or vote tally is computed as a value, stored, or surfaced; the
   rule is a single fixed boolean.
5. **Signal-only** — the rule reads only `Evidence.data["signal"]` /
   equivalently the B1 `polarity`; never `is_degraded`, the LSTM band, model
   `confidence`, `metadata`, or any non-`MODEL_OUTPUT` data.
6. **Provenance** — `action_source == "SENTINEL"` on every B2-authored
   `Decision` (concur or abstain); `action_source == "STRATEGY"` on the
   fallback / B2-disabled entry path (§8.4); `None` only for legacy / unknown /
   unspecified provenance (pre-B2, exit path); no other value; historical
   records never rewritten.
7. **Abstain = inert `WAIT`** — abstention is `action == "WAIT"`,
   `action_source == "SENTINEL"`, with zero scheduling / re-evaluation /
   execution behavior attached.
8. **One identity / lifecycle** — one `Decision`, one `decision_id`, one
   `DecisionProjection`; no `Recommendation` type; no second `Decision`; no
   second lifecycle; no new correlation identifier.
9. **Authoritative at creation** — the rule result is set before
   `create_decision()`; `DECISION_CREATED` and the seeded projection carry the
   final value; `Decision` stays `frozen`; `action` never mutated post-creation.
10. **Confidence identity** — `Decision.confidence` equals
    `ensemble_confidence(...)` byte-for-byte; no separate/new confidence value;
    not relabelled as Sentinel confidence.
11. `Decision.uncertainty` / `thesis` / `counterfactual` / `horizon` /
    `desired_allocation` / `minimum_viable_allocation` remain `None`.
12. **Evidence provenance intact** — every `Evidence` field and the
    `EVIDENCE_ATTACHED` payload are byte-for-byte unchanged from B1; no
    `Evidence.data` mutation.
13. **No new lifecycle vocabulary** — no new `EventType`, `DecisionState`, or
    `ApprovalStatus` member. `ActionSource` and `WAIT` are inert value
    vocabulary only.
14. **RiskManager unchanged** — `approve_buy()` receives byte-for-byte
    identical arguments and remains the sole execution-blocking gate,
    consuming zero Sentinel input.
15. **No approval/execution change** — `register_policy()` and
    `record_approval()` never invoked in the production path; `evaluate_policy()`
    result still discarded; `PaperExecutor` / `AlpacaClient` /
    `bot/execution/factory.py` / `bot/main.py` / `EntryContext` /
    `_handle_entry()` gate sequence untouched; no live/Robinhood/autonomous
    execution.
16. **No sizing** — no allocation, position-sizing, Kelly, or risk-optimization
    logic anywhere in B2.
17. **Module boundary** — all rule/vocabulary code is inside `sentinel_engine/`
    with zero `bot` import; the only `bot/` change is `EntryDecisionRecorder.__init__()`
    per §13.
18. **Failure safety** — if the B2 rule is unavailable or raises, the
    entry-path `Decision` carries `action = "BUY"` literal and
    `action_source == "STRATEGY"` (§8.4); trade / gate / lifecycle behavior is
    byte-for-byte pre-B2; the failure never blocks, delays, retries, or alters
    the gate sequence, `risk.approve_buy()`, `client.buy()`, or the Trust
    Ledger write. A failure of `Decision` construction / `create_decision()`
    itself records no `Decision` at all (ADR-067 §9).
19. **No terminology regression** — surfaces call a `Decision` a "Sentinel
    recommendation" only when `action_source == "SENTINEL"`; all others keep
    the "interpreted strategy decision" label.
20. **`test_recommendation_governance_lifecycle.py` untouched.**
21. **Upstream-BUY precondition (§4.1).** B2 runs only after the upstream
    strategy produced a BUY candidate (`action_to_int(...) == 1`,
    `_handle_entry()` reached) and only upstream of `create_decision()`. B2
    originates no entry candidate; an upstream `SELL` / `HOLD` / absent
    candidate can never become a Sentinel `BUY`; B2 does not replace
    `ensemble_signal()` / `action_to_int()`. B2 changes only the `action` /
    `action_source` values an already-triggered `Decision` is born with —
    never whether a `Decision` exists.

---

## 21. Acceptance criteria

This ADR may be considered **Accepted** only when the Architecture Owner
confirms, in writing, through the ADR-058 D2/D4 mechanism (tracked on the
default branch, `Status: Accepted`, landed under applicable write/merge
controls — an in-file "Accepted By" string alone is insufficient), that:

- The recommendation rule is **Candidate A (unanimity, §5.3) and only
  Candidate A** — no acceptance-time substitution, no configuration flag, no
  alternate rule path. Candidates B and C are rejected (§5.2, §16). Any future
  rule change requires its own subsequent ADR (§5.5).
- The §4.1 hard upstream-BUY precondition holds: B2 runs only after
  `action_to_int(...) == 1` and `_handle_entry()` is reached, and only
  upstream of `create_decision()`; an upstream non-BUY can never become a
  Sentinel BUY; B2 originates no entry candidate and does not replace
  `ensemble_signal()` / `action_to_int()`.
- Abstention is `DecisionAction.WAIT` as an inert label (§7).
- Provenance is the additive `Decision.action_source` field + `ActionSource
  {STRATEGY, SENTINEL}` inert enum (§8). Final semantics: `"STRATEGY"` =
  strategy-authored action, `"SENTINEL"` = Sentinel-authored B2 recommendation,
  `None` = legacy / unknown / unspecified. The fallback / B2-disabled
  entry-path `Decision` sets `action_source = "STRATEGY"` explicitly (§8.4);
  `None` remains valid for legacy records and is never deliberately written on
  the entry path; no other provenance value; no historical rewrite.
- The authority granted is exactly G-1..G-4 (§4); every §14 non-goal remains
  non-authorized; the §12 execution/approval invariants hold.
- The lifecycle is the single ADR-067 `Decision` / `decision_id` /
  `DecisionProjection`; the recommendation is derived from `model_outputs` in
  `EntryDecisionRecorder.__init__()` and is authoritative at `DECISION_CREATED`
  (§11).
- The only `bot/` change authorized is `EntryDecisionRecorder.__init__()` per
  §13; no ADR beyond ADR-066/067/068 is superseded, and only the §15.2 clauses
  of those three.
- The ADR-068 header staleness (§23) is acknowledged as harmless and handled
  separately, not by editing ADR-068 here.
- `sentinel_engine/tests/test_recommendation_governance_lifecycle.py` and the
  unrelated working-tree items in §24 remain untouched.

Acceptance authorizes the **B2 architecture only**. The B2 implementation is a
further separate batch bound by §13, §18, §19 and the B2 Invariants, and must
prove every one of the 21 invariants.

---

## 22. Rollback

If the §4–§13 implementation is landed under this ADR and later reverted:

1. In `bot/_main_trust_decisions.py::EntryDecisionRecorder.__init__()`, restore
   the literal `action="BUY"` and drop the `action_source` argument and the
   recommendation-function import — restoring the ADR-067 form exactly.
2. Remove the `Decision.action_source` field and its adapter-boundary
   validation.
3. Delete `sentinel_engine/domain/action_source.py` and the recommendation
   function/module (`recommendation_adapter.py` or equivalent) and their tests.
4. Remove the B2 tests; revert the additive update to
   `test_causal_decision_lifecycle.py::test_construction_seeds_one_sentinel_decision_with_action_buy`.
5. No schema, migration, persistence, `EventType`, `DecisionState`,
   `ApprovalStatus`, `RiskManager`, `PaperExecutor`, `AlpacaClient`,
   `bot/main.py`, or `decision_events` rollback — none is touched. Any
   `action_source` values already written to the in-memory/temporary
   composition ledger are inert and need no cleanup.

Single-commit revert, no secondary cleanup — identical in character to
ADR-009 / ADR-045 / ADR-065 / ADR-067 rollback sections.

---

## 23. Note on ADR-068 header staleness (reported, not fixed here)

ADR-068's status header still reads *"ADR-058 D2 is not yet satisfied — this
file is not yet tracked on the default branch"*. That statement is **factually
stale**: ADR-068 is tracked, `Status: Accepted`, landed at `a06a95e`, its B1
implementation landed at `ccfbbb0` (current HEAD), and both are on
`origin/main`. ADR-068's own `## Acceptance` and `## Status Log` sections
record the explicit acceptance and landing.

**This does not create an authority problem for B2.** ADR-058 D2 status is
determined by repository facts (tracked + `Status: Accepted` + landed under
write/merge controls), all of which now hold for ADR-068. This ADR treats
ADR-068 as Accepted and authoritative. Per the Phase 2E task constraint,
**ADR-068 is not modified here.** Correcting the stale header line is a
separate documentation-consistency change for a future batch.

---

## 24. Working-tree safety

The following unrelated working-tree items are **not** touched, staged, or
modified by this ADR-drafting task:

- `docs/REQUIREMENTS.md`
- `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`
- `tests/req_snapshots/req_state.json`
- `sentinel_engine/tests/test_recommendation_governance_lifecycle.py`

Only this file (`docs/decisions/ADR-069-sentinel-b2-recommendation-authority.md`)
is created.

---

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-09-09
**Accepted By:** Architecture Owner (explicit act — Phase 2F, Finalize and
Accept ADR-069 — not inferred from the Phase 2E draft, from any
implementation, or from any other source).

The Architecture Owner explicitly accepts ADR-069. This acceptance ratifies the
ADR-069 text as finalized in Phase 2F; only the header status/date lines, §8.3,
§8.4, §17.1, the provenance wording in §2 / §11.5 / §18 / §20 / §21, this
`## Acceptance` section, and the Status Log entry below were altered to perform
the finalization and acceptance. No substantive Context, Decision (§2–§4.1),
rule (§5.1–§5.5), evidence-boundary (§6), abstain-representation (§7),
lifecycle (§11), execution/approval-invariant (§12), module-boundary (§13),
non-goal (§14), supersession-accounting (§15), test-contract (§18),
verification (§19) or B2-Invariant (§20) content was weakened or expanded.

### Accepted scope — exactly, and only

- **G-1..G-4 (§4).** On the existing upstream-BUY entry path only, and only
  before `create_decision()`, Sentinel authors `Decision.action` as `BUY`
  (concur) or `WAIT` (abstain) per the single fixed rule, and sets
  `Decision.action_source = "SENTINEL"`.
- **The §4.1 hard upstream-BUY precondition.** B2 is not a general-purpose
  action generator: it runs only after `ensemble_signal()` / `action_to_int()`
  produced a BUY candidate and `_handle_entry()` was reached; it originates no
  entry candidate; it does not replace the upstream entry trigger; an upstream
  `SELL` / `HOLD` / absent candidate can never become a Sentinel `BUY`.
- **The §5.3 rule — Candidate A (three-model unanimity) — as the sole
  authorized B2 rule.** `action = "BUY"` iff the `xgboost`, `lstm` and
  `finbert` signals are all `"BUY"`; every other case → `action = "WAIT"`.
  Both branches set `action_source = "SENTINEL"`. Candidates B and C are
  rejected. Acceptance leaves **no** algorithmic choice, configuration flag,
  or A/C decision open. Any future rule change requires its own subsequent ADR
  in this lineage.
- **The §5.4 evidence-aggregation boundary.** Exactly one fixed three-input
  `AND` over the three `MODEL_OUTPUT` signals; no counting exposed as a value,
  no majority / k-of-n, no weighting, no scoring, no ranking, no confidence
  aggregation, no generalized corroboration, no dynamic threshold, no added
  evidence type, no polarity netting, no calibration / learning.
- **Abstention = `DecisionAction.WAIT` as an inert label (§7)** — no
  scheduling, re-evaluation, retry, position lifecycle, or execution behavior.
- **Provenance (§8).** The additive optional `Decision.action_source` field and
  the two-member inert `ActionSource {STRATEGY, SENTINEL}` enum. Final
  semantics — exactly three states: `STRATEGY` = strategy-authored action,
  `SENTINEL` = Sentinel-authored B2 recommendation, `None` = legacy / unknown /
  unspecified. The fallback / B2-disabled entry-path `Decision` sets
  `action_source = "STRATEGY"` explicitly; `None` stays legal for legacy
  records and is never deliberately written on the entry path. No other
  provenance value.
- **One causal identity (§11).** The same ADR-067 `Decision` / `decision_id` /
  `DecisionProjection`; recommendation derived from `model_outputs` in
  `EntryDecisionRecorder.__init__()` and authoritative at `DECISION_CREATED`.
- **One function-scoped ADR-002 exception (§13.2)** —
  `bot/_main_trust_decisions.py::EntryDecisionRecorder.__init__()` only.
- **The narrow supersessions in §15.2** — only the named clauses of ADR-066,
  ADR-067 and ADR-068, only for the entry path.
- **The §18 test contract and the 21 B2 Invariants (§20)** — binding on the
  implementation batch.

### Not authorized by this acceptance

Every §14 non-goal remains non-authorized, restated because acceptance does not
expand it: no `Recommendation` class; no second `Decision`, identity, or
lifecycle; no origination of `BUY` where upstream did not; no `SELL` /
`BUY_MORE` / real `HOLD` / exit / position-lifecycle action; no `WAIT`
scheduling; no execution, execution veto, gate bypass, or change to
`RiskManager` / `PaperExecutor` / `AlpacaClient` / `bot/execution/factory.py` /
`bot/main.py` / `EntryContext` / the gate sequence; no `Policy` registration,
`record_approval()` wiring, operative `GovernanceService` approval, or acting
on the `evaluate_policy()` result; no Sentinel approval or execution authority;
no live / Robinhood / autonomous execution; no portfolio or position sizing;
no evidence weighting / scoring / voting / calibration beyond the §5.3 rule;
no distinct Sentinel confidence; no `uncertainty` / `thesis` / `counterfactual`
/ `horizon` / allocation population; no new `EventType` / `DecisionState` /
`ApprovalStatus` member; no `Evidence` change or `Evidence.data` mutation; no
change to the legacy `decision_events` action string or write path; no ADR-004
persistence selection; no modification to
`sentinel_engine/tests/test_recommendation_governance_lifecycle.py`; no
reopening of ADR-044 / ADR-047 / ADR-048 / ADR-049 / ADR-050; no modification
of ADR-068 (its stale header line, §23, is a separate documentation-
consistency issue).

### Authoritative status and next step

ADR-069 is now **authoritative** (ADR-058 D2: tracked on `main`,
`Status: Accepted`, landed under the repository's direct-to-`main` flow by the
commit recorded in the Status Log). **B2 implementation may proceed — as a
separate subsequent batch — only within the scope defined above**, on an
isolated branch/worktree, bound by §13, §18, §19 and every one of the 21 B2
Invariants. This acceptance authorizes nothing outside ADR-069 and adds no
authority beyond G-1..G-4.

---

## 25. Status Log

**Proposed — DRAFT / NOT ACCEPTED — 2026-09-09 (Phase 2E).** Drafted as an
ADR-authoring-only task following the Phase 2 Recommendation Intelligence
audit, the Phase 2A Recommendation Authority audit, ADR-068 (B1) landing, and
the Phase 2D read-only B2 boundary audit. Defines the minimum defensible B2
capability: entry-path-only, deterministic concur (`BUY`) / abstain (`WAIT`)
via a single explicitly-authorized unanimity rule over the three existing
`MODEL_OUTPUT` signals; one additive inert `Decision.action_source` field;
zero execution / approval / sizing / calibration effect; one function-scoped
ADR-002 exception at `EntryDecisionRecorder.__init__()`. **Candidate A
(unanimity) is locked as the sole authorized B2 rule** (§5.3–§5.5): acceptance
leaves no algorithmic choice open, Candidates B and C are rejected, and any
future rule change requires its own subsequent ADR. A **hard upstream-BUY
precondition** (§4.1) makes explicit that B2 is not a general-purpose action
generator — it runs only after the upstream strategy has produced a BUY
candidate and only upstream of `create_decision()`, and can never convert an
upstream non-BUY into a Sentinel BUY. No production code, test, or other ADR
was modified;
ADR-068 was not modified despite its stale header line (§23); no `docs/platform/`
governance file, `docs/REQUIREMENTS.md`, or `tests/req_snapshots/req_state.json`
was touched; `sentinel_engine/tests/test_recommendation_governance_lifecycle.py`
was not touched; nothing was staged, committed, or pushed. This ADR is not
accepted and authorizes no implementation.

**Accepted + Landed — 2026-09-09 (Phase 2F).** The Architecture Owner
explicitly accepted ADR-069 in the form finalized in this phase, and it was
landed on the default branch `main` in the same commit ("docs: accept and land
ADR-069 B2 recommendation authority"). The one remaining open question (§17.1)
was resolved: the fallback / B2-disabled entry-path `Decision` sets
`action_source = "STRATEGY"` explicitly (§8.4); `None` is reserved for legacy /
unknown / unspecified provenance; provenance has exactly three states —
`STRATEGY`, `SENTINEL`, `None` — and no others. `Status` now reads `Accepted`,
scoped exactly to §3–§13 and the 21 B2 Invariants (§20), excluding every §14
non-goal. With this commit ADR-058 D2's three conditions are met — tracked on
`main`, `Status: Accepted`, landed under applicable write/merge controls — and
ADR-069 is authoritative. Candidate A (three-model unanimity) remains the sole
authorized B2 rule; no acceptance-time algorithmic choice, no configuration
flag. No production code, test, or other ADR was modified; ADR-068 was not
modified (its stale header line, §23, remains a separate documentation-
consistency issue); `docs/REQUIREMENTS.md`,
`docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`,
`tests/req_snapshots/req_state.json`, and
`sentinel_engine/tests/test_recommendation_governance_lifecycle.py` were not
touched or staged. B2 implementation is a separate subsequent batch bound by
§13, §18, §19 and every B2 Invariant, authorized to proceed only within
ADR-069's defined scope.
