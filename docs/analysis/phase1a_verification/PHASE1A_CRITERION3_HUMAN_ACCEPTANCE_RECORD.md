# ADR-004 Criterion 3 — Human Review / Acceptance

**Status:** Accepted

**Recorded by:** sridhar7707 (git identity landing this record on the default
branch `main`). Per [ADR-058](../../decisions/ADR-058-architecture-authority-and-adr-ratification-rule.md)
D1/D2, this record's authority derives from the same mechanism every other
Accepted ADR/acceptance record in this repository relies on, not from an
invented title or an asserted role.

**Date:** 2026-09-11

**Authority for this review:**
[ADR-004](../../decisions/ADR-004-sentinel-ledger-ownership-strategy.md)
Criterion 3 — "A tested dry run exists against real `trust_ledger` data ...
nothing about `sentinel_engine`'s adapters has ever been exercised against
the shapes real `decision_events`/`risk_evaluation_events`/etc. rows
actually take in production." This record is that review, for Criterion 3
only.

**Reviewed evidence:**
[PHASE1A_CRITERION3_HUMAN_REVIEW_PACKET.md](PHASE1A_CRITERION3_HUMAN_REVIEW_PACKET.md)
and the underlying run of `scripts/verify_adapters_against_real_ledger.py`
(uncommitted at the time of this decision).

---

## Overall Decision

**ACCEPTED WITH FOLLOW-UP**

"Accepted With Follow-Up" means: the demonstrated real-data adapter dry run
is accepted as satisfying Criterion 3, while `decision_adapter` and
`execution_adapter` real-data coverage remain explicitly open and recorded
as follow-up, not resolved and not treated as closed.

---

## Evidence Basis

- Real production `trust_ledger`/`decision_events` data was used (HF
  repo_id `ksri77/ai-trading-bot-db`, revision
  `fc04da62abf003fc9799b3dd88051e420df753f8`).
- Real `decision_events` row shapes were used — `model_outputs`/`action`
  taken directly from real rows, unmodified.
- `evidence_adapter.to_evidence_records`: 10/10
- `recommendation_adapter.recommend_entry_action`: 10/10
- `governance_adapter.to_policy_id`: 10/10
- Failures: 0
- The verification used a disposable SQLite copy opened read-only
  (`mode=ro`); no production database, code, or data was modified.

---

## Explicit Remaining Follow-Up

- **`decision_adapter` real-data coverage** — `decision_adapter.to_decision()`
  was not exercised against real rows. The prior feasibility review
  established it requires a translation/reconstruction layer rather than a
  direct real-row match (field names differ from `decision_events`'
  actual columns). This remains open.
- **`execution_adapter` real-data coverage** — `execution_adapter
  .to_execution_outcome()` was not exercised against real rows for the same
  reason (its inputs are synthesized at execution-report time, not
  persisted verbatim on any ledger row). This remains open.

---

## Explicit Scope Limits

- This record does not select ADR-004 Option A/B/C.
- This record does not constitute overall ADR-004 readiness.
- This record does not constitute selection of a ledger ownership option.
- This record does not close or dismiss the `decision_adapter`/
  `execution_adapter` follow-up items — both remain open.
- This record does not alter or reinterpret the Criterion 1 acceptance
  record (`PHASE1A_HUMAN_ACCEPTANCE_RECORD.md`) or its INCONCLUSIVE
  findings (PER_DAY_ENUMERATION, FAILED_WRITES, PROVENANCE_CHAIN).
- This record authorizes no implementation work of any kind.

---

## Recording Requirement

Per [ADR-058](../../decisions/ADR-058-architecture-authority-and-adr-ratification-rule.md)
D2, this decision becomes repository-authoritative only once this file is
tracked on the default branch under applicable write/merge controls — the
act of committing this file to `main` is what satisfies D2 for this record.
