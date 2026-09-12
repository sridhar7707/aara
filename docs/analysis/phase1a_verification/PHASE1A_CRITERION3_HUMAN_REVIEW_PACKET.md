# ADR-004 Criterion 3 — Human Review Packet

## 1. Purpose

This packet assembles existing technical evidence relevant to a human review
of [ADR-004](../../decisions/ADR-004-sentinel-ledger-ownership-strategy.md)
Criterion 3. **This packet does not ratify, accept, reject, or select an
ADR-004 option.** It is an evidence-organizing document only; the acceptance
decision, if any, is a separate act a named human reviewer would need to
make and record per ADR-058 D2, exactly as was done for Criterion 1 in
`PHASE1A_HUMAN_ACCEPTANCE_RECORD.md`.

## 2. Literal Criterion 3

Verbatim, from ADR-004's "Future Decision Criteria":

> "3. **A tested dry run exists against real `trust_ledger` data**, not just
> the current 82 tests (which all run against in-memory fakes). Whichever
> option is chosen, nothing about `sentinel_engine`'s adapters has ever been
> exercised against the shapes real `decision_events`/`risk_evaluation_events`/
> etc. rows actually take in production."

## 3. Existing Phase 1A Real-Data Evidence

The Phase 1A verification tooling (`scripts/phase1a_verification.py`,
`scripts/phase1a_daily_acceptance_check.py`, `ledger/reproducibility.py`) has
already been run, repeatedly, against real production `trust_ledger.db`/
`trades.db` snapshots — see
`20260910T182601.816493Z-phase1a-verification-day-01.md` and the
`PHASE1A_HUMAN_ACCEPTANCE_RECORD.md` it informed. This tooling validates
real-data linkage completeness, hash-chain integrity, and model-artifact
checksum reproducibility.

**This is raw-SQL/data-integrity verification, not adapter-level
verification.** Confirmed directly from source: none of
`scripts/phase1a_verification.py`, `scripts/phase1a_daily_acceptance_check.py`,
or `ledger/reproducibility.py` imports `sentinel_engine` at all — they
validate the ledger's own data via independent SQL queries and checksum
comparisons, never by invoking `sentinel_engine`'s adapter code. These two
categories of evidence are not the same thing and this packet does not
conflate them.

## 4. New Adapter-Level Evidence

From the read-only run of `scripts/verify_adapters_against_real_ledger.py`
(uncommitted, present in the working tree at the time of this packet):

- **repo_id:** `ksri77/ai-trading-bot-db`
- **revision:** `fc04da62abf003fc9799b3dd88051e420df753f8`
- **rows sampled:** 10
- **evidence_adapter.to_evidence_records:** 10/10 PASS
- **recommendation_adapter.recommend_entry_action:** 10/10 PASS
- **governance_adapter.to_policy_id:** 10/10 PASS
- **failures:** none
- **overall:** PASS

These three adapters were each fed a real, unmodified value taken directly
from a real `decision_events` row (`model_outputs`, parsed with
`json.loads()` and passed through without transformation; the raw `action`
string) — not a synthetic fixture. This is genuine adapter-level exercise
against real production row shapes, independently audited (implementation
audit: PASS; result-consistency audit: PASS; side-effect-safety audit: PASS)
in this review process.

## 5. Adapter Coverage Boundary

| Adapter | Status |
|---|---|
| `evidence_adapter` | **COVERED** — 10/10 |
| `recommendation_adapter` | **COVERED** — 10/10 |
| `governance_adapter` (`to_policy_id`) | **COVERED** — 10/10 |
| `decision_adapter` | **NOT COVERED** |
| `execution_adapter` | **NOT COVERED** |

`decision_adapter.to_decision()` and `execution_adapter.to_execution_outcome()`
were deliberately not exercised. A prior read-only feasibility review
established that neither has a direct real-row match: `to_decision()`
expects field names (`symbol`, `confidence`, `evidence_reference`,
`risk_reference`, a `datetime` object) that differ from `decision_events`'
actual columns (`asset`, `final_confidence`, no `evidence_reference`/
`risk_reference` column, a string timestamp); `to_execution_outcome()`
expects values (`outcome`, `side`, `is_paper`) that are synthesized at
execution-report time by `bot/_main_cycle.py`, not persisted verbatim on any
ledger row. Exercising either would require a translation/reconstruction
layer standing between the real row and the adapter call. **This is not a
failure of the verification script** — the script correctly scopes itself to
the three adapters it can exercise without inventing or reshaping real data,
exactly as instructed.

## 6. Safety / Scope

- The verification operates on a disposable copy of the production ledger,
  never the original.
- SQLite is opened strictly read-only (`mode=ro`).
- No production database write, migration, `INSERT`/`UPDATE`/`DELETE`, or
  `PRAGMA` write operation occurs.
- No execution, retraining, or service (`DecisionService`/`EvidenceService`/
  `GovernanceService`) path is invoked.
- No production code was changed to build or run this verification.
- The verification script itself emits no Phase 1A evidence file — it is a
  console-only diagnostic.
- The disposable working directory is removed on every exit path.
- `scripts/verify_adapters_against_real_ledger.py` is currently **uncommitted**
  (untracked) in the working tree.

## 7. Remaining Limitations

- The sample is bounded to 10 rows — not exhaustive historical adapter
  coverage.
- `decision_adapter` remains unexercised against real data.
- `execution_adapter` remains unexercised against real data.
- No persistent record of the actual verification run exists beyond the
  reported result and this review packet — the script does not write a
  dated evidence artifact the way `phase1a_verification.py` does.
- Criterion 3 acceptance remains a human decision; nothing in this packet
  or the verification run itself constitutes that decision.

## 8. Relationship to ADR-004 Readiness

This evidence **materially strengthens the literal adapter-level portion of
Criterion 3** — real `sentinel_engine` adapter code has now been demonstrably
exercised against real production row shapes for three of five adapters,
closing exactly the gap Criterion 3's own text names for those three. It
does **not** mean ADR-004 is now satisfied, that Criterion 3 is accepted,
that ADR-004 is ready for an Option A/B/C selection, or that all adapters
are verified. The human acceptance question for Criterion 3 remains open.

The existing, separately-recorded Phase 1A follow-up findings are preserved
here unchanged, not reopened or reinterpreted:

- **PER_DAY_ENUMERATION** remains a documented follow-up/inconclusive area
  (per `PHASE1A_HUMAN_ACCEPTANCE_RECORD.md`).
- **FAILED_WRITES** remains a documented structural limitation/follow-up
  (per the same record).
- **FinBERT provenance** (`PROVENANCE_CHAIN`) remains an open follow-up gap
  (per the same record).
- Criterion 3 itself requires human review, not automated closure — this
  packet is preparation for that review, not a substitute for it.

## 9. Human Review Questions

1. Does the evidence satisfy the intent of ADR-004 Criterion 3 despite
   `decision_adapter` and `execution_adapter` not being directly exercised?
2. Are the documented adapter boundaries acceptable, or is additional
   real-data adapter testing required?
3. Is Criterion 3 **ACCEPTED**, **ACCEPTED WITH FOLLOW-UP**, or still **OPEN**?

*(Not answered here.)*

## 10. Evidence References

- ADR-004: `docs/decisions/ADR-004-sentinel-ledger-ownership-strategy.md`
- ADR-058: `docs/decisions/ADR-058-architecture-authority-and-adr-ratification-rule.md`
- Existing Phase 1A verification evidence:
  `docs/analysis/phase1a_verification/20260910T182601.816493Z-phase1a-verification-day-01.md`,
  `docs/analysis/phase1a_verification/20260910T181339.863763Z-phase1a-verification-pre-window-baseline.md`
- Phase 1A Criterion 1 human acceptance record:
  `docs/analysis/phase1a_verification/PHASE1A_HUMAN_ACCEPTANCE_RECORD.md`
- New adapter-level verification script:
  `scripts/verify_adapters_against_real_ledger.py` (uncommitted)
- Adapter feasibility review: conducted as a read-only review in this
  process; **no separate tracked file records it** — its conclusions (the
  §5 coverage boundary) are reflected in this packet and in the verification
  script's own docstring, which documents the identical boundary and
  rationale.

## 11. Review Status

```
Technical evidence assembled: YES
Automated acceptance: NOT CLAIMED
Human review required: YES
ADR-004 Option selected: NO
```
