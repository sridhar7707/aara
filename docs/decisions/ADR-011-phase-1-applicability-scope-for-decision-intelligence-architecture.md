# ADR-011: Phase 1 Applicability Scope for the Decision Intelligence Architecture

**Status:** Proposed
**Date:** 2026-08-11

## Context

`docs/architecture/DECISION_INTELLIGENCE_ARCHITECTURE.md` defines a 12-stage
lifecycle as the long-term vision for Sentinel, self-declared "FROZEN" and
listed as such in `docs/architecture/ARCHITECTURE_FREEZE_STATUS.md` and
`ARCHITECTURE_INDEX.md`. All three files live under `docs/architecture/`,
which is entirely gitignored (`.gitignore:48`) and has zero commits in this
repository's history.

`docs/platform/AARA_ARCHITECTURE_AUTHORITY.md` — tracked in git — states an
explicit authority hierarchy for this repository:

1. Committed code (highest authority).
2. `docs/decisions/ADR-*.md` — **Tier 2**.
3. `docs/platform/`, `docs/implementation/`, and related tracked
   migration/governance documents — Tier 3, authoritative in the absence of
   a conflicting ADR.
4. `docs/architecture/*` — gitignored. Described there as "Local working
   drafts, not the project's controlled source of truth... Not binding on
   `sentinel_engine/` or product-identity decisions."

That same document prescribes its own conflict-resolution mechanism: "A new
document that conflicts with an existing authoritative doc does not silently
coexist with it. Write a new ADR... that references both and states which
wins and why."

A read-only governance review (2026-08-11) examined a local, gitignored
addendum — `docs/architecture/DECISION_INTELLIGENCE_ARCHITECTURE_PHASE1_ADDENDUM.md`
— which reached a substantively sound conclusion (that Stage 3
Thesis/Conviction and Stage 11-12 Investment Memory are not a Phase 1
implementation dependency), supported by direct inspection of the codebase
(e.g. `trades.db.decision_log.thesis`: 0/18 rows populated) and cross-checked
for consistency against `docs/platform/SENTINEL_ENGINE_PHASE1_DECISION_LIFECYCLE.md`.
That review also found three pre-existing, unresolved documentation defects
recorded by the addendum but not caused by it or by this ADR:

- **G7** — a dangling reference to `SOFTWARE_ARCHITECTURE_DOCUMENT.md` in
  `DECISION_INTELLIGENCE_ARCHITECTURE.md`'s own References section; the file
  does not exist anywhere in the repository.
- **G8** — `DECISION_INTELLIGENCE_ARCHITECTURE.md` self-declares "Version:
  1.0" while `ARCHITECTURE_FREEZE_STATUS.md` and `ARCHITECTURE_INDEX.md`
  both register it as "1.2, FROZEN."
- **G9** — the frozen domain-model artifact registered in
  `ARCHITECTURE_FREEZE_STATUS.md` is a backup-suffixed file
  (`SYSTEM_DOMAIN_MODEL.md.v1.1_backup`), not a canonically-named document.

Because `docs/architecture/*` is Tier 4 (non-binding) under
`AARA_ARCHITECTURE_AUTHORITY.md`'s own tracked hierarchy, the addendum
cannot itself resolve the applicability ambiguity it identifies, regardless
of its own internal "Status" field. The addendum was useful supporting
architectural analysis for reaching this decision, but it is not, and
cannot be, the source of authority for it. This ADR formally establishes
the Phase 1 applicability decision at Tier 2, the level at which it can
actually bind.

Separately, `docs/platform/SENTINEL_ENGINE_PHASE1_DECISION_LIFECYCLE.md`
(tracked, Tier 3, dated 2026-08-06) already defines the narrower lifecycle
`sentinel_engine/` Phase 1 work is actually being built against:
`Decision → Evidence → Governance Evaluation → Approval → Ledger Event →
Projection → Query`. Its own header already disclaims authorizing any code
change by itself — it is "an implementation contract, not an
implementation."

This ambiguity was also identified as an open objection during review of
[ADR-009](ADR-009-sentinel-evidence-integration.md), which remains
Proposed and unaccepted.

## Decision

For current Phase 1 `sentinel_engine/` implementation:

- This ADR authorizes no code, schema, test, runtime, execution, or product
  behavior change of any kind.
- `docs/platform/SENTINEL_ENGINE_PHASE1_DECISION_LIFECYCLE.md` is the
  authoritative current-build lifecycle.
- `docs/architecture/DECISION_INTELLIGENCE_ARCHITECTURE.md` remains the
  long-term target/reference architecture.
- Phase 1 does not require Stage 3's structured Thesis or structured
  Conviction.
- Phase 1 does not require Stage 11's Investment Memory.
- Phase 1 does not require Stage 12's feedback/learning loop.
- Phase 1 does not adopt a `sentinel_engine`-native Capital Pool merely
  because the long-term architecture contains one.
- Existing `bot/` `CapitalPool` behavior (`bot/_main_cycle.py`) remains
  governed independently, under its existing authority (ADR-002), and is
  unaffected by this ADR.
- [ADR-004](ADR-004-sentinel-ledger-ownership-strategy.md)'s ledger-ownership
  choice remains deferred, unchanged.

## Non-Goals

This ADR does not authorize, and explicitly excludes:

1. Any decision on ADR-004's ledger-ownership options (A/B/C) — remains
   deferred exactly as ADR-004 states.
2. Acceptance, rejection, or modification of ADR-009 — ADR-009 is reviewed
   and decided independently, on its own merits.
3. Any modification of ADR-010 or its Amendment 1.
4. Implementation of a `sentinel_engine`-native Capital Pool.
5. Any scheduling commitment for Thesis, structured Conviction, or
   Investment Memory — this ADR states current inapplicability, not that
   these are never built.
6. Any edit to `DECISION_INTELLIGENCE_ARCHITECTURE.md` — it remains FROZEN,
   unedited, exactly as authored.
7. Any `bot/` or `sentinel_engine/` implementation change.
8. Resolution of G7, G8, or G9 (see Context) — all three remain explicitly
   unresolved and out of scope for this ADR.

## Consequences

- Phase 1 reviews now have a Tier-2 applicability decision to cite, instead
  of relying on a non-binding local document.
- The long-term architecture remains the target/reference architecture,
  unedited and unaffected.
- ADR-009 can proceed independently, without the Phase 1 Thesis/Memory
  applicability ambiguity as an open objection.
- No runtime behavior changes.
- Future expansion of Phase 1 scope (e.g. introducing Thesis, Conviction
  structure, or Investment Memory) requires its own separate, governed
  decision — it is not authorized, foreclosed, or scheduled by this ADR.

## Relationship to ADR-009

ADR-009 remains Proposed and unaccepted. This ADR resolves only the Phase 1
applicability ambiguity relevant to ADR-009's review — whether Phase 1 must
also implement Thesis/Memory to be architecturally complete (it does not).
This ADR does not accept, reject, or otherwise decide ADR-009; that remains
its own independent review.

## Relationship to ADR-010

ADR-010 and its Amendment 1 remain the sole governing decision for
FRED/macro failure handling. This ADR does not reinterpret, amend,
duplicate, or supersede ADR-010 in any respect. The Phase 1 scope
established here is compatible with ADR-010's existing implementation and
invariants. SELL/exit-path independence from FRED availability remains
governed by ADR-010, not by this ADR.

## Relationship to ADR-004

Unaffected and unchanged. ADR-004's Option A/B/C ledger-ownership choice
remains deferred until Phase 1A validation completes, exactly as ADR-004
already states.

## Relationship to ADR-002

ADR-011 is not an ADR-002 exception and authorizes no change to any
ADR-002-protected file. ADR-002 remains fully in force and continues to
govern the protected bot runtime boundary independently of this ADR.

## Relationship to AARA_ARCHITECTURE_AUTHORITY.md

This ADR follows the Tier-2 authority level and the conflict-resolution
mechanism described in `AARA_ARCHITECTURE_AUTHORITY.md`. This ADR does not
modify `AARA_ARCHITECTURE_AUTHORITY.md` and does not itself update its
document-roles registry; any such registration is a separate, future action
outside this ADR's scope.

## Supporting Architectural Analysis

`docs/architecture/DECISION_INTELLIGENCE_ARCHITECTURE_PHASE1_ADDENDUM.md`
was reviewed as supporting architectural analysis for this decision — its
factual findings (stage-by-stage applicability, the recorded exit-path
independence invariant) informed the Decision above. However, because
`docs/architecture/` is non-binding, local working material under this
repository's tracked authority hierarchy (see Context), the addendum itself
does not establish, and was not treated as, the governing decision. This
ADR is that governing decision.
