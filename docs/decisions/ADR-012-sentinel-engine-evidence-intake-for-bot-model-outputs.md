# ADR-012: Sentinel Engine Evidence Intake for Bot Model Outputs

**Status:** Accepted
**Date:** 2026-08-11

## Context

ADR-009 authorizes exactly one bot → sentinel_engine call — forwarding
decision_row["decision_id"] and decision_row["model_outputs"] to "a
plain-data intake boundary on the sentinel_engine side" — but explicitly
declines to authorize creation of that boundary itself. ADR-009 states
that any new file(s) outside bot/ needed to implement the plain-data
intake boundary and Evidence translation are outside its jurisdiction.

A read-only repository review confirmed no such Evidence translation
boundary currently exists.

sentinel_engine/adapters/decision_adapter.py establishes the precedent:
plain data enters the Sentinel Engine boundary, no bot type is imported,
and required fields are validated at the boundary.

No equivalent Evidence translator currently exists.

The producer
bot/strategy/model_output_adapter.py::build_model_outputs()
currently returns exactly three required top-level keys:

- xgboost
- lstm
- finbert

Each model entry contains exactly:

- signal: str
- confidence: numeric
- metadata: dict

The current Evidence dataclass requires exactly:

- evidence_id: str
- evidence_type: str
- source: str
- data: Dict[str, Any]
- collected_at: datetime

Evidence has no decision_id field. Decision linkage is handled separately
by EvidenceService.associate_evidence(decision_id, evidence).

The MODEL_OUTPUT vocabulary and shape were previously described in
docs/architecture/EVIDENCE_POLICY_DECISIONS.md, but that document is
non-binding architecture material and is not itself the governing
Tier-2 decision.

sentinel_engine is outside ADR-002's protected bot boundary. Therefore
this ADR is not an ADR-002 exception. It records a narrow architectural
and implementation decision for a new receiving-side translation
boundary.

This ADR is independent of ADR-009. It does not accept, reject, amend,
or supersede ADR-009.

## Decision

Authorize creation of exactly one new production file:

sentinel_engine/adapters/evidence_adapter.py

That file shall expose exactly this public translation function:

def to_evidence_records(model_outputs: dict) -> list[Evidence]:

The function shall:

1. Accept exactly one input argument: model_outputs.
2. Require model_outputs to contain all three required keys:
   xgboost, lstm, and finbert. model_outputs MAY contain additional
   top-level keys beyond these three; any such additional keys are
   ignored and are not treated as an error.
3. For each of the three required models, validate the corresponding
   model entry as follows:
   - signal must be present and must be a non-empty str.
   - confidence must be present and must be numeric.
   - metadata must be present and must be a dict.
   - Missing or invalid required fields must raise ValueError.
   - The error must identify the missing or invalid model/field
     sufficiently for diagnosis.
   - Validation must occur at the adapter boundary before any Evidence
     records are returned.
   - No additional normalization rules are introduced beyond these
     requirements.
4. Return exactly three Evidence instances after successful validation:
   one for xgboost, one for lstm, and one for finbert, regardless of
   any additional top-level keys present in model_outputs.
5. Set evidence_type to exactly "MODEL_OUTPUT" for every returned
   Evidence.
6. Set source to the model name:
   "xgboost", "lstm", or "finbert".
7. Set data to a shallow copy of the corresponding model sub-dict,
   preserving signal, confidence, and metadata without normalization
   or invention of additional fields. The shallow-copy requirement is
   independence of the top-level model sub-dict only — nested values
   (e.g. metadata's contents) are not deep-copied or normalized.
8. Generate each evidence_id inside the adapter using:
   str(uuid.uuid4())
9. Generate collected_at inside the adapter using:
   datetime.now(timezone.utc).
10. Generate a distinct evidence_id for each of the three records.
11. Never accept or require decision_id. Decision linkage remains outside
    this adapter and belongs to the caller/EvidenceService boundary.
12. Perform pure in-memory translation only.
13. Not call EvidenceService, LedgerRepository, ProjectionRepository,
    any persistence mechanism, or any event-writing mechanism.
14. Import nothing from bot/.
15. Modify no existing sentinel_engine contract.

The adapter therefore has this exact conceptual boundary:

plain model_outputs dict
        ↓
to_evidence_records()
        ↓
three plain Evidence instances
        ↓
caller may separately associate each Evidence with decision_id

No persistence occurs inside the adapter.

## Authorized Files

Only this production file is authorized by this ADR:

- sentinel_engine/adapters/evidence_adapter.py

No existing file may be modified under this ADR.

The test file is NOT an authorized production change; it is specified
under Testing Requirements only.

## Non-Goals

This ADR does not authorize:

1. Any change to bot/_main_trust_decisions.py or any other bot file.
2. Acceptance, rejection, amendment, or modification of ADR-009.
3. Any schema, migration, or database change.
4. Any production LedgerStore or ProjectionRepository backend.
5. Any decision regarding ADR-004 Option A/B/C.
6. Any new EventType or DecisionState enum member.
7. Any modification to EvidenceService, LedgerRepository, ProjectionRepository,
   Evidence, or another existing Sentinel Engine contract.
8. Any persistence, event emission, projection update, or ledger write from
   the adapter.
9. Any Thesis, structured Conviction, Investment Memory, feedback loop,
   or sentinel_engine-native Capital Pool capability.
10. Any UI, scheduler, dashboard, workflow, or execution change.
11. Any additional model type beyond the current xgboost/lstm/finbert
    input contract.

## Testing Requirements

Create the accompanying test file:

sentinel_engine/tests/test_evidence_adapter.py

Required tests:

- valid input produces exactly three Evidence instances
- each record has the correct source
- every record has evidence_type == "MODEL_OUTPUT"
- every record preserves its model sub-dict in data
- missing xgboost raises ValueError
- missing lstm raises ValueError
- missing finbert raises ValueError
- malformed model entries raise ValueError identifying the invalid
  required field
- the adapter module imports nothing from bot/
- the three evidence_id values are unique
- collected_at values are timezone-aware UTC datetimes
- mutating the input model_outputs dict after the call does not alter
  the returned Evidence.data

The adapter boundary test should follow the existing
test_decision_adapter.py import-boundary testing pattern.

The existing
sentinel_engine/tests/test_package_imports.py
boundary test must remain unmodified and continue to pass.

Before implementation is considered complete:

- full sentinel_engine/tests must pass
- full tests/ suite must pass
- no existing Sentinel Engine contract may be modified
- no bot file may be modified by ADR-012

## Relationship to ADR-002

This ADR modifies no ADR-002-protected file.

sentinel_engine/adapters/ is outside ADR-002's protected scope.

This ADR is not an ADR-002 exception and does not expand or weaken
ADR-002.

## Relationship to ADR-004

This ADR does not choose, constrain, or imply any ADR-004 Option A/B/C
outcome.

The authorized function creates only in-memory Evidence objects. It
does not read from or write to any ledger backend.

ADR-004 remains fully deferred and unchanged.

## Relationship to ADR-009

This ADR fills exactly the receiving-side gap that ADR-009 explicitly
identifies as outside its jurisdiction.

It does not modify, accept, reject, or supersede ADR-009.

ADR-009 remains a separate governance decision.

If ADR-009 is never accepted, this adapter remains unused and inert.

If ADR-009 is later accepted and implemented, its authorized caller may
use this adapter as the translation boundary, while retaining
decision_id separately for EvidenceService association.

## Relationship to ADR-011

This ADR is fully within ADR-011's accepted Phase 1 applicability scope.

It introduces no Thesis, structured Conviction, Investment Memory,
feedback loop, or sentinel_engine-native Capital Pool capability.

ADR-011 remains unchanged.

## Relationship to EVIDENCE_POLICY_DECISIONS.md

docs/architecture/EVIDENCE_POLICY_DECISIONS.md §6 previously proposed a
data shape for MODEL_OUTPUT Evidence that included a model discriminator
key ("xgboost" | "lstm" | "finbert") inside data itself. That document is
Tier-4, non-binding architecture material — not the governing Tier-2
decision.

This ADR is the authoritative Tier-2 decision for the MODEL_OUTPUT
Evidence shape. It intentionally omits the model discriminator key that
docs/architecture/EVIDENCE_POLICY_DECISIONS.md §6 previously proposed
inside data, since Evidence.source already carries the model name; that
non-binding draft shape is superseded here.

This ADR does not modify docs/architecture/EVIDENCE_POLICY_DECISIONS.md
itself.

## Rollback

Rollback consists of deleting:

sentinel_engine/adapters/evidence_adapter.py

and its corresponding test file if created.

Because ADR-012 makes no bot change, no persistence change, and no caller
change, deleting the adapter has no runtime blast radius unless a
separate future ADR authorizes and implements a caller.

## Consequences

- The MODEL_OUTPUT Evidence vocabulary and translation contract become
  an explicit Tier-2 decision of record.
- ADR-009, if separately accepted, has a precise receiving-side
  translation boundary available to use.
- Evidence translation remains pure and persistence-free.
- No ADR-002 protected file is changed.
- No ADR-004 decision is made.
- No bot runtime, trading, risk, execution, scheduler, or UI behavior
  changes.
- The adapter remains inert until another independently authorized
  change invokes it.

## Governance Boundary

This ADR authorizes only the receiving-side translation boundary.

It does NOT authorize the caller.

It does NOT authorize the bot → sentinel_engine dependency.

It does NOT authorize Evidence association.

It does NOT authorize persistence.

It does NOT authorize implementation of ADR-009.

Those decisions remain governed independently by ADR-009 and the
applicable existing architecture.
