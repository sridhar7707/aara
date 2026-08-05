# Confidence Integrity Redesign — Implementation Plan (Synchronized)

**Status:** Planning only. No code was written or modified, confirmed via
`git status` before and after. This plan does not authorize implementation
— `bot/` and `ledger/` remain protected paths (`ADR-002`); each phase below
still requires its own go-ahead when actually executed.

**This is a synchronization pass, not a new design.** The original version
of this document was written before six subsequent decisions were made. Every
section below is updated to match those decisions; nothing architectural is
re-argued here. Superseded statements from the original version are marked
explicitly, not silently dropped, so the evolution is traceable.

**Synthesizes, in order of authority:** `RISK_GOVERNOR_SAFETY_AUDIT.md` →
`DECISION_CONFIDENCE_INTEGRITY_DESIGN.md` → `CONFIDENCE_EDGE_CASE_ANALYSIS.md`
→ `DECISION_EVENT_SCHEMA_CHANGE_REVIEW.md` → `CONFIDENCE_EXPLANATION_UX.md` →
`CONFIDENCE_POLICY_DECISIONS.md` → the Decision Lifecycle Trace →
`CONFIDENCE_DECISION_POLICY_DESIGN.md` → the module-ownership design (this
session, unversioned) → the Shadow Mode read-only-pattern design (this
session, unversioned).

---

## Files to Create

| File | Purpose | Status |
|---|---|---|
| `bot/strategy/confidence_engine.py` | **The one calculation module** (module-ownership design). Covers Directional + Context Evidence only (`xgb_prob`, `lstm_prob`, `sentiment_score`, `macro_score`) — zero dependency on `RiskManager`, Trust Ledger, UI, Database, or `bot/main.py`. Public API: `calculate_confidence(...) -> ConfidenceResult`, where `ConfidenceResult` carries `displayed_confidence`, `evidence_completeness`, `disagreement_spread`, `confidence_state` (the six-state machine from `CONFIDENCE_POLICY_DECISIONS.md`), and `evidence_basis`. | **Supersedes** the original plan's `bot/trust_ledger/confidence.py`-as-calculation-site proposal — that file is now writer-only (below); placing the calculation itself inside `bot/trust_ledger/` would have violated the module-ownership design's zero-Trust-Ledger-dependency requirement. |
| `bot/trust_ledger/confidence.py` | Writer only — records `ConfidenceResult` (plus, in Shadow Mode, the separately-read Risk Evidence state) to `decision_confidence_events`. Computes nothing. | Unchanged in purpose from the original plan; scope narrowed to writer-only now that calculation has its own module. |
| `bot/tests/test_confidence_engine.py` | Unit tests for `calculate_confidence()`. | **Must be computed fresh against the final three-factor formula** (`raw_score × evidence_completeness × agreement_score`, `CONFIDENCE_POLICY_DECISIONS.md`) — **not copy-pasted from `CONFIDENCE_EDGE_CASE_ANALYSIS.md`**. That document's seven worked numbers were computed under an earlier two-factor formula with a threshold-gated (not continuous) disagreement discount; only Scenario 4 (spread `0.50`, both formulas floor at the same value there) survives unchanged by coincidence. Every other scenario's expected value needs recomputing before it becomes a test assertion. |
| `bot/tests/test_evidence_categories.py` | New — Directional/Context/Risk categorization logic (`CONFIDENCE_DECISION_POLICY_DESIGN.md` Section 3), including the Fallback Mode conditions. Not present in the original plan; this category structure didn't exist when it was written. |
| `tests/test_shadow_mode_zero_side_effects.py` | New, and the single most important addition to the testing surface — captures `RiskManager`'s full mutable state (`halted`, `daily_start_value`, `portfolio_high`, etc.) before and after a Shadow Mode cycle runs, and asserts byte-for-byte equality. Directly proves the Shadow Mode read-only-pattern design's central claim. |
| `tests/test_decision_confidence_events_schema.py` | New-table tests — unchanged in purpose from the original plan. |
| `tests/test_verify_all_chains_regression.py` | Unchanged from the original plan — proves `verify_all_chains()` reports zero breaks after the new table is added. |

## Files to Modify

| File | Change | Status |
|---|---|---|
| `ledger/schema.sql` | Add `decision_confidence_events` (new table + standard triggers). No existing DDL touched. | **Unchanged** from the original plan — `DECISION_EVENT_SCHEMA_CHANGE_REVIEW.md` already validated this and nothing since has revised it. |
| `ledger/ledger.py` | Register `decision_confidence_events` in `_LEDGER_TABLES`. | **Unchanged.** |
| `bot/trust_ledger/ids.py` | Add `new_confidence_event_id()`. | **Unchanged.** |
| `bot/strategy/model_output_adapter.py` | Extend `build_model_outputs()` with `status`/`weight_applied` per model. | **Narrowed in scope** — applies only to Directional/Context evidence (XGB, LSTM, FinBERT, Macro); Risk Evidence has no representation here, by design (Section 3 of the Decision Policy design). |
| `bot/strategy/ensemble.py` | Remove the calculation logic entirely; **consume** `confidence_engine.calculate_confidence()`'s result; retain only action-threshold comparison (`STRONG_BUY_THRESHOLD`/`BUY_THRESHOLD`/etc.) against the received `ConfidenceResult`. | **Superseded, risk downgraded.** The original plan called this "the highest-risk file" because it held the calculation. It no longer does — the calculation moved to `confidence_engine.py`. Remaining risk here is narrower: re-pointing five of the seven `ensemble_confidence()`-adjacent call sites at the new module without changing their observed values. |
| **`bot/main.py`** | Orchestrate: call `confidence_engine.calculate_confidence()`; call `bot.trust_ledger.risk.read_only_governor_state()` once per cycle for Shadow Mode's Risk Evidence read; pass results to `ensemble.py` (action) and `bot/trust_ledger/confidence.py` (recording). | **New to the files-to-modify list.** The original plan omitted this file entirely; the Decision Lifecycle Trace identified `bot/main.py:324` as the correct insertion point, and the module-ownership design confirmed orchestration belongs here, not in `ensemble.py`. |
| `bot/_main_cycle.py` | Add the Directional-coverage gate: minimum 2-of-2 Directional signals (`XGB`, `LSTM`) `USED`, or exactly 1 under explicitly-enabled Fallback Mode with its stricter confidence floor and capped sizing (`CONFIDENCE_DECISION_POLICY_DESIGN.md` Section 3). | **Reframed.** The original plan described this as a generic "evidence-completeness floor." It is now a specific, per-category rule, not a single percentage threshold. |
| **`bot/trust_ledger/risk.py`** | Add `read_only_governor_state()`, promoted verbatim (zero logic change) from `constitution.py`. | **New to the files-to-modify list** — the Shadow Mode read-only-pattern design's deliverable. |
| **`bot/trust_ledger/constitution.py`** | Remove the now-private-and-duplicate `_read_only_governor_state()`; import and call the promoted version from `risk.py` instead. Behavior at this call site is unchanged. | **New to the files-to-modify list**, and independently shippable — see Implementation Sequence, Phase 1.5. |
| **`config.py`** | Add `CONFLICT_THRESHOLD` (recommended starting value `0.40`, `CONFIDENCE_POLICY_DECISIONS.md`), the Fallback Mode enable flag, Fallback Mode's stricter confidence floor, and Fallback Mode's position-size cap fraction. | **New to the files-to-modify list** — none of these constants had a designated home in the original plan. |

**Confirmed not modified, explicitly out of scope — reaffirmed, not newly decided:**
- `bot/risk/risk_manager.py` — the module-ownership design confirmed this stays untouched; `RiskManager` consumes results, never computes or gates on evidence quality itself.
- Any `dashboard/` file or `applications/trading_intelligence/` UI file — unchanged reasoning from the original plan; no rendering layer exists yet.

**Still an open, unresolved item — carried forward, not newly discovered:**
- `bot/db/trade_log.py`'s two independent `ensemble_confidence()` call sites (Decision Lifecycle Trace finding). Whether they should consume the new `confidence_engine.py` result or remain intentionally separate is not decided by any document in this series yet. Must be resolved before Phase 4.

## Database Migration Strategy

**Unchanged from the original plan — still verified correct.** `ledger/db.py`'s `init_schema()` runs `executescript()` against the whole `schema.sql` file idempotently; the new table requires no separate migration runner, no `ALTER TABLE`, no downtime.

## Shadow Mode

**Fully specified now — this section did not exist in this form in the
original plan, which described Shadow Mode's *intent* without resolving
*how* it reads Risk Evidence safely.** Per the read-only-pattern design
(this session):

- Risk Evidence is read via `bot.trust_ledger.risk.read_only_governor_state()` — verified, by direct inspection, to call no state-mutating `RiskManager` method.
- Read once per cycle, not once per decision — matching `classify()`'s own established discipline, avoiding the same per-decision-frequency problem `constitution.py`'s docstring already documents as the reason a naive reuse would be unsafe.
- Result is written only to `decision_confidence_events`; nothing reads it back into `action`, `notional`, or `approve_buy()` during Shadow Mode.
- Proven, not just argued: `test_shadow_mode_zero_side_effects.py` (above) asserts `RiskManager`'s full state is identical before and after a Shadow Mode cycle.

## Rollback Strategy

**Refined to separate two independently-revertable changes, per
`CONFIDENCE_DECISION_POLICY_DESIGN.md`'s recommendation that they get
separate sign-off** — the original plan treated the eventual cutover as one
revertable unit; it is now explicitly two:

1. **Directional-coverage floor** (`bot/_main_cycle.py`'s new gate) — revertable independently via its own flag/commit.
2. **Risk Governor enforcement** (Risk Evidence `GREEN` requirement) — revertable independently. This is the larger change (it ends `bot/trust_ledger/risk.py`'s Observation Mode status for the first time) and should not be bundled into the same rollback unit as (1).

**Schema-level and shadow-data handling: unchanged from the original plan** — additive-only migration, no `DROP TABLE` as a routine rollback step, `git revert` sufficient at the code level.

## Testing Strategy

1. **Golden-output regression baseline** — unchanged in purpose from the original plan: capture current `ensemble_confidence()`/`ensemble_signal()` outputs before touching `ensemble.py`.
2. **Unit tests for `calculate_confidence()`** — **superseding the original plan's instruction to reuse Edge Case Analysis numbers directly.** Recompute all seven scenarios under the final three-factor formula (`CONFIDENCE_POLICY_DECISIONS.md`) before encoding them as assertions. Must include the Scenario 7 division-by-zero guard (never silently `0.0`).
3. **New: Evidence Category / Fallback Mode tests** — not present in the original plan; covers the 2-of-2 Directional rule, Fallback Mode's stricter floor and sizing cap, and Context/Risk category boundaries (`CONFIDENCE_DECISION_POLICY_DESIGN.md` Section 3).
4. **New: `test_shadow_mode_zero_side_effects.py`** — the load-bearing new test this synchronization adds. Directly resolves the previously-identified BLOCKER.
5. **Schema/ledger tests** — unchanged from the original plan.
6. **Integration test** — unchanged in shape (fake data source, real service chain), now targeting `confidence_engine.py` specifically rather than an undetermined location.
7. **Gate test** — unchanged in purpose (Directional-coverage gate, matching the existing `recorder.reject()` pattern); scope reframed per the category rules.

## Implementation Sequence

**Phase 1 — Schema only.** Unchanged from the original plan. Zero writers, provably safe.

**Phase 1.5 — Promote the read-only governor-state function (new phase, not in the original plan).** Move `_read_only_governor_state()` from `constitution.py` to `bot/trust_ledger/risk.py`, rename to public, update `constitution.py`'s call site. Pure relocation, zero logic change, independently shippable and testable before any confidence-engine work begins — `constitution.py`'s existing tests should pass unchanged, proving the relocation altered nothing.

**Phase 2 — Calculation module, Shadow Mode.** Build `bot/strategy/confidence_engine.py` (not `bot/trust_ledger/confidence.py`, correcting the original plan's proposed location) and extend `model_output_adapter.py`. Wire Shadow Mode into `bot/main.py`, using Phase 1.5's promoted function for the Risk Evidence read. `final_confidence`, the actual action, and all existing gates remain untouched.

**Phase 3 — Directional-coverage gate, logged-only.** Add to `bot/_main_cycle.py` in would-have-blocked logging mode, per the same caution `constitution.py` already applies to its own advisory checks.

**Phase 3.5 — Risk Governor enforcement gate, logged-only (new phase, split out per the rollback strategy above).** Kept separate from Phase 3 because `CONFIDENCE_DECISION_POLICY_DESIGN.md` identified this as the larger, separately-consequential change — ending `bot/trust_ledger/risk.py`'s Observation Mode status. Also logged-only initially.

**Phase 4 — Cutover.** Using Phases 2/3/3.5's shadow data, switch `ensemble.py`/`bot/main.py` to the real calculation and action driver, and flip both gates (3 and 3.5) from logged-only to enforced — **as two separate decisions, not one**, per the rollback strategy. `bot/db/trade_log.py`'s open question (Files to Modify, above) must be resolved before this phase.

**Phase 5 — UI.** Unchanged from the original plan — deferred, no rendering layer exists yet.

## Dependencies (New Section)

Not present in the original plan; added following the module-ownership
design's dependency diagram:

```
config.py (leaf)
    ↑
bot/strategy/confidence_engine.py  ← the one calculation module
    ↑
bot/strategy/ensemble.py  (consumes the result; unchanged edge to risk_manager.py for BUY_FRACTION)

bot/trust_ledger/risk.py  (owns both classify() and the new read_only_governor_state())
    ↑
bot/trust_ledger/constitution.py  (imports the promoted function; unchanged edge to risk_manager.py)

bot/main.py  (orchestrator — depends on all of the above; nothing depends on it)
```
No cycle exists. This directly resolves the previously-identified BLOCKER
(`ensemble.py → bot.trust_ledger.risk → bot.risk.risk_manager → ensemble.py`)
by construction: `confidence_engine.py` never imports `bot.trust_ledger` or
`bot.risk`, and the Risk Evidence read happens in `bot/main.py`, which
nothing imports back.

## Risks

1. **Superseded — disagreement-discount formula.** Original Risk #2 ("still illustrative, not decided") is resolved by `CONFIDENCE_POLICY_DECISIONS.md`'s Option D hybrid, `CONFLICT_THRESHOLD = 0.40` starting value. No longer a risk to track.
2. **Superseded — missing-vs-indeterminate equivalence.** Original Risk #3 is resolved by `CONFIDENCE_POLICY_DECISIONS.md`'s six-state machine (`MODEL_UNCERTAIN` vs. `DATA_INCOMPLETE`, distinct states, same numeric treatment — a deliberate, recorded choice, not an open gap).
3. **Superseded — calculation location / circular import.** Resolved by the module-ownership design (`bot/strategy/confidence_engine.py`, dependency diagram above).
4. **Superseded — Shadow Mode safety.** Resolved by the read-only-pattern design (Phase 1.5, `test_shadow_mode_zero_side_effects.py`).
5. **Still open — `ensemble.py`'s multiple call sites.** Narrower than originally stated (the calculation itself moves out, reducing exposure), but re-pointing every consumer at `confidence_engine.py`'s result without changing observed values still needs the golden-output baseline (Testing Strategy item 1) before Phase 4.
6. **Still open — `bot/db/trade_log.py`.** Unresolved whether its two independent call sites should consume the new calculation. Must be decided before Phase 4.
7. **Still open, now more precisely stated — Risk Governor enforcement authority.** Ending `bot/trust_ledger/risk.py`'s Observation Mode status is the largest single behavioral change in this whole plan. Phase 3.5 exists specifically to surface this in logged-only form before Phase 4 makes it real, and it has its own rollback unit, separate from the Directional-coverage change.
8. **`bot/` and `ledger/` remain protected paths** — unchanged from the original plan; every phase above still needs its own explicit go-ahead under `ADR-002`.

---

## Constraints Confirmed

No file was created or modified other than this document. No code was
written. This plan does not authorize implementation of any phase above.
No architecture was redesigned in producing this synchronization — every
decision reflected here was already made in one of the documents this plan
synthesizes.
