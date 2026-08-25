# ADR-053 — Decision.evidence_reference Disposition: Retirement Review

**Status:** Proposed
**Date Proposed:** 2026-08-25
**Decision Type:** Architecture / Governance — Tier-4-to-Tier-2 Adjudication
**Related ADRs:** ADR-004, ADR-009, ADR-012, ADR-013, ADR-034, ADR-044

---

## 1. Context

`sentinel_engine.domain.decision.Decision` (and its read-side propagation,
`sentinel_engine.projections.decision_projection.DecisionProjection`) declares
`evidence_reference` as a required, non-empty `str` field.
`sentinel_engine.adapters.decision_adapter.to_decision()` validates only its
type and non-emptiness — no format, no lookup semantics, no construction
rule exists anywhere in the codebase.

A read-only architecture-governance investigation (this session) independently
traced every real reference to this field and confirmed:

- No consumer anywhere dereferences it. `DecisionView`
  (`applications/trading_intelligence/projections/decision_view.py`) carries
  no `evidence_reference` attribute at all —
  `test_decision_view.py` asserts this explicitly ("evidence_reference/
  risk_reference are internal pointers the UI doesn't need").
- The real, working decision-to-evidence relationship already exists and is
  used everywhere real evidence lookup happens:
  `EvidenceService.get_evidence_for_decision(decision_id)`,
  `SentinelEvidenceSource`, and `DecisionQuery.get_decision_timeline()` all
  key exclusively by `decision_id` — never by `evidence_reference`.
- Every real construction site populates the field with an arbitrary,
  non-deterministic placeholder, never a value with actual meaning:
  `applications/trading_intelligence/bootstrap.py` uses hardcoded
  illustrative literals (`"evidence-seed-001"`, etc.);
  `scripts/project_one_trust_ledger_decision.py` (ADR-043's authorized
  mechanism) uses `f"adr043-placeholder-{decision_id}"`.
- `candidate_event_id` — the one plausible existing bot-side identifier
  named as a candidate FK — is confirmed to be a source-event identifier
  for the candidate-screening pipeline stage
  (`candidate_evaluation_events`), not an evidence identity in the sense
  `sentinel_engine.evidence.Evidence` already represents
  (`docs/analysis/TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md` §1–§2).

Separately, `docs/architecture/EVIDENCE_POLICY_DECISIONS.md` ("V5-B", dated
2026-08-10) §7 already performed an end-to-end trace reaching the same
conclusion and recommended retiring the field. That document is Tier-4 —
gitignored, untracked, non-binding per ADR-044 — and explicitly
self-acknowledges its own non-binding status ("this document must be
reviewed and accepted by the architecture owner... it is a decision record,
not yet a ratified one merely by existing").

This is not a novel governance mechanism. `ADR-012` already established the
precedent for exactly this move, adjudicating the same source document's §6
(the `MODEL_OUTPUT` Evidence `data` shape) at Tier-2 without modifying the
Tier-4 source: *"That document is Tier-4, non-binding architecture
material — not the governing Tier-2 decision. This ADR is the authoritative
Tier-2 decision... This ADR does not modify
`docs/architecture/EVIDENCE_POLICY_DECISIONS.md` itself."* `ADR-009` §13
only cited §7 as background context ("stays deprecated-but-present per V5-B
§7; unrelated to this exception") without adjudicating it. This ADR is that
missing adjudication.

## 2. Decision

**`Decision.evidence_reference` / `DecisionProjection.evidence_reference` is
declared deprecated, non-authoritative, and slated for future removal.**

The real, sole, working mechanism for locating a decision's evidence is,
and remains, `decision_id` — via `EvidenceService.get_evidence_for_decision()`
and the read-side query paths that already use it
(`SentinelEvidenceSource`, `DecisionQuery`). `evidence_reference` is
recognized as carrying no operative meaning today and requiring no
construction rule, because no consumer needs it to have one.

This ADR does **not** itself remove the field. Physical removal
(`Decision`/`DecisionProjection` field deletion and updating the one
passthrough site) is explicitly deferred as a separate, future
`sentinel_engine`-internal implementation change, subject to appropriate
contract and test review. That implementation change is not authorized by
this ADR.

## 3. Alternatives Considered

1. **Retire (selected).** Matches the field's actual, verified behavior
   today; requires no new contract; consistent with the ADR-012 precedent
   for the sibling §6 question.
2. **FK-passthrough** (populate `evidence_reference` with an existing
   bot-side identifier, e.g. `candidate_event_id`, verbatim). Rejected as
   the *primary* path: `candidate_event_id` identifies a different pipeline
   stage (candidate screening), not evidence identity, and no consumer
   would ever read the resulting value — this would resolve the placeholder
   problem cosmetically without resolving the semantic-inertness problem.
3. **Synthesized `sentinel_engine.evidence.Evidence` reference** (make
   `evidence_reference` point at a real `Evidence` record). Rejected as the
   *primary* path: `Decision`'s real evidence is already a *plurality*
   (three records per decision — xgboost/lstm/finbert), while
   `evidence_reference` is a single string — a structural cardinality
   mismatch this ADR does not attempt to resolve, especially since the
   already-working `decision_id`-keyed lookup makes resolving it
   unnecessary.

Neither alternative 2 nor 3 is selected by this ADR. If a future,
separate governance decision determines the field should be retained after
all (contrary to this ADR's finding), that decision would need to
independently choose between them — this ADR does not pre-select either.

## 4. Consequences

**Positive:**
- Closes a real, previously-unadjudicated governance gap: §7 has sat
  unratified since 2026-08-10 while its sibling §6 was already adjudicated
  (ADR-012).
- Gives future code review a citable, binding basis to treat continued
  reliance on `evidence_reference` as a defect, not a design choice,
  consistent with V5-B §7's own stated intent.
- Removes ambiguity about whether a future adapter/reader implementation
  needs to solve `evidence_reference`'s construction — it does not.

**Negative / Limitation:**
- Does not itself remove the field — a reader encountering
  `evidence_reference` in code today will not see any visible change from
  this ADR alone.
- Does not resolve ADR-004, and does not accelerate any ledger-ownership
  work.

## 5. Non-Authorization / Scope Boundary

This ADR authorizes **only** the adjudication in the Decision section
above. It explicitly does **not**:

1. Select ADR-004 Option A, B, or C.
2. Establish Sentinel Engine as canonical ledger owner.
3. Establish Trading Intelligence as canonical ledger owner.
4. Establish dual-ledger synchronization of any kind.
5. Authorize any adapter implementation.
6. Authorize any reader implementation.
7. Authorize any query-service implementation.
8. Authorize any persistence implementation.
9. Authorize any production execution capability.
10. Modify `bot/`.
11. Modify `dashboard/`.
12. Modify `scheduler/`.
13. Modify `database/`.
14. Modify top-level `ledger/`.
15. Modify `.github/workflows/*.yml`.
16. Physically remove `evidence_reference` from `Decision` or
    `DecisionProjection` — that is separate, future, unauthorized-here
    implementation work.
17. Modify `docs/architecture/EVIDENCE_POLICY_DECISIONS.md` itself — it
    remains exactly as written, Tier-4, non-binding, unedited.
18. Amend, reopen, or reinterpret ADR-009, ADR-012, ADR-013, ADR-034, or
    ADR-044.
19. Select or pre-authorize either the FK-passthrough or
    synthesized-Evidence alternative for any future retain-path decision.

## 6. Relationship to Existing ADRs

**ADR-004:** Fully deferred and unaffected. This ADR makes no ledger-backend
or ownership decision of any kind; `evidence_reference`'s disposition is
independent of which of Option A/B/C is eventually chosen.

**ADR-009:** Unmodified. ADR-009 §13 stated the field "stays
deprecated-but-present" without adjudicating it; this ADR performs that
adjudication without amending ADR-009's own text or its narrow evidence-
integration authorization.

**ADR-012:** Unmodified. This ADR follows the identical adjudication pattern
ADR-012 already used for the same source document's §6, applied here to §7.

**ADR-013:** Unmodified. This ADR authorizes no `EvidenceService` wiring,
composition, or consumer change of any kind.

**ADR-034:** Unmodified. ADR-034's own "Relationship to
EVIDENCE_POLICY_DECISIONS.md" section already establishes the same
Tier-4-is-contextual-only principle this ADR relies on.

**ADR-044:** Not reopened. This ADR treats `docs/architecture/*` as
Tier-4/non-binding exactly as ADR-044 already established, and does not
revisit that ruling.

## 7. Evidence / Rationale

- `sentinel_engine/domain/decision.py` — `evidence_reference: str`, no
  further semantics.
- `sentinel_engine/adapters/decision_adapter.py` — validates only
  type/non-emptiness.
- `sentinel_engine/projections/decision_projection.py` — propagates the
  field unchanged.
- `applications/trading_intelligence/projections/decision_view.py` /
  `test_decision_view.py` — confirms `DecisionView` carries no
  `evidence_reference` attribute.
- `applications/trading_intelligence/bootstrap.py`,
  `scripts/project_one_trust_ledger_decision.py` — confirm every real
  construction site uses an arbitrary placeholder.
- `docs/analysis/TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md` §1–§2 —
  confirms `candidate_event_id`'s distinct role.
- `docs/architecture/EVIDENCE_POLICY_DECISIONS.md` §7 — the original
  end-to-end trace and retirement recommendation this ADR adjudicates.
- `docs/decisions/ADR-012-...md` §"Relationship to
  EVIDENCE_POLICY_DECISIONS.md" — the direct governance-pattern precedent.

## 8. ADR-004 Safety Statement

This ADR does not select ADR-004 Option A, B, or C; does not establish
Sentinel Engine as canonical ledger owner; does not establish Trading
Intelligence as canonical ledger owner; does not establish dual-ledger
synchronization of any kind; does not authorize any adapter, reader,
query-service, or persistence implementation; does not authorize any
production execution capability; and does not modify `bot/`, `dashboard/`,
`scheduler/`, `database/`, top-level `ledger/`, or any `.github/workflows/*.yml`
file. ADR-004 remains exactly as deferred as before this ADR.

## 9. Acceptance Criteria

This ADR may be considered Accepted only when the architecture owner has
explicitly confirmed, in writing:
- Ratification of the retirement finding (Decision section above), or an
  explicit rejection with reasoning, in which case this ADR's Alternatives
  Considered section becomes the starting point for a future, separate
  retain-path decision — not resolved by this ADR either way in advance.
- That no code, schema, test, or configuration change is authorized by
  acceptance itself.

## 10. Status

**Proposed.** Awaiting architecture-owner review and disposition.
