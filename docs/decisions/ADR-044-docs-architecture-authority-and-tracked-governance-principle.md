# ADR-044: `docs/architecture/*` Authority and the Tracked-Governance Principle

**Status:** Accepted
**Date Proposed:** 2026-08-24
**Date Accepted:** 2026-08-24
**Decision Type:** Architecture / Governance — Document Authority Resolution
**Related ADRs:** ADR-011 (narrow precedent this ADR generalizes), ADR-001/ADR-008 (already-Accepted
decisions that structurally diverged from `docs/architecture/*` content without ever being asked to
reconcile against it)

---

## 1. Context

Two tracked, committed governance documents state directly conflicting authority hierarchies for
`docs/architecture/*`:

- `docs/DOCUMENT_INDEX.md` §1 places "Frozen Architecture Documents — anything in
  `docs/architecture/ARCHITECTURE_FREEZE_STATUS.md`'s registry" at Tier 3: binding, "changeable only
  via a dated addendum or a narrowly-scoped ADR exception." §2 names `architecture/ARCHITECTURE_FREEZE_STATUS.md`
  itself as the canonical "Doc governance / freeze registry" document, and separately names other
  `docs/architecture/*` files (e.g. `DECISION_INTELLIGENCE_ARCHITECTURE.md`, `SYSTEM_EVENT_MODEL_v1.2.md`,
  `SENTINEL_DESIGN_SYSTEM_FINAL.md`, `QA_ACCEPTANCE_SPECIFICATION_v1.1.md`) as canonical/authoritative
  for their areas. §3 ("Key Folders") describes `docs/architecture/` as "Frozen platform architecture,
  requirements, design system, confidence-integrity design chain."
- `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md` §Hierarchy places `docs/architecture/*` at Tier 4:
  "gitignored (`.gitignore:44`). Local working drafts, not the project's controlled source of truth.
  Useful for ideas; not binding." Its Directory Structure section states a document only belongs in
  `docs/architecture/` "if it is a local, exploratory draft not yet promoted to a decision; once a
  document starts being used to make real calls... it moves to `docs/platform/`" — citing
  `TRADING_INTELLIGENCE_BOUNDARY.md` and `DASHBOARD_DEPENDENCY_REDUCTION_PLAN.md` as prior examples of
  that promotion actually happening. Its Current Document Roles table names `docs/architecture/*`
  (remaining files) explicitly "Not binding on `sentinel_engine/` or product-identity decisions."

Verified directly: `.gitignore:49` contains `docs/architecture/`; `git ls-files docs/architecture/`
returns zero tracked files; `git status --short --ignored docs/architecture/` reports `!!` (actively
ignored), confirming the entire directory has zero commit history and is not silently tracked through
any other mechanism.

**ADR-011** (Accepted, 2026-08-11) already encountered this exact conflict and adopted
`AARA_ARCHITECTURE_AUTHORITY.md`'s Tier-4/non-binding reading — but scoped that adoption narrowly to
one question (Phase 1 applicability of the Decision Intelligence Architecture). ADR-011 §"Relationship
to AARA_ARCHITECTURE_AUTHORITY.md" explicitly states it "does not modify `AARA_ARCHITECTURE_AUTHORITY.md`
and does not itself update its document-roles registry; any such registration is a separate, future
action outside this ADR's scope." ADR-011 also declined to correct `DOCUMENT_INDEX.md`'s conflicting
Tier-3 language. The general conflict between the two documents has therefore remained open, on the
record, by ADR-011's own explicit disclaimer — not merely by omission.

ADR-011's own reasoning is direct precedent for how this conflict should be resolved: it held that a
local, gitignored addendum (`DECISION_INTELLIGENCE_ARCHITECTURE_PHASE1_ADDENDUM.md`) "cannot itself
resolve the applicability ambiguity it identifies, regardless of its own internal 'Status' field" —
i.e., a document's own self-declared approval status cannot substitute for being tracked, when tracked
status is what the governing hierarchy actually keys authority to.

Separately, `docs/decisions/ADR-001-sentinel-engine-structure.md` and `ADR-008-sentinel-scaffold-disposition.md`
(both Accepted) already established and formally archived a structurally different implementation
(`sentinel_engine/`) than the one `docs/architecture/ARCHITECTURE_FREEZE_STATUS.md` describes (e.g. its
"19 immutable event types" and "hash-chained ledger integrity" claims, `ARCHITECTURE_FREEZE_STATUS.md:50-53`,
match the archived `sentinel/` scaffold's design, not `sentinel_engine/`'s actual 8-member `EventType`
enum). This is offered as evidence that treating `docs/architecture/*`'s specific technical claims as
binding today would retroactively manufacture obligations that already-Accepted ADRs never built toward
and, in ADR-008's case, formally superseded — not as a finding this ADR re-adjudicates.

## 2. Decision

**Principle:** Being tracked in this repository's version-controlled history is a **necessary** condition
for a document to be authoritative; it is **not sufficient** on its own. A document must also occupy an
authoritative role under the existing hierarchy (an Accepted ADR, or a Tier-3 `docs/platform/`/
`docs/implementation/`-equivalent tracked migration-governance document) to be binding. An untracked
document cannot be authoritative regardless of its internal "Status" field, its filename, or a claim
made about it inside another document — but a tracked document is not automatically authoritative
merely by virtue of being tracked.

Specifically:

1. `docs/architecture/*`, in its entirety, is **non-binding** — local, exploratory working material —
   for as long as it remains gitignored and untracked. This applies generally, to every document in the
   directory, not only to the Decision Intelligence Architecture question ADR-011 settled.
2. `AARA_ARCHITECTURE_AUTHORITY.md`'s Hierarchy (Tier 1 Code, Tier 2 Accepted ADRs, Tier 3 tracked
   `docs/platform/`/`docs/implementation/`/equivalent tracked migration-governance documents, Tier 4
   untracked `docs/architecture/*`) is affirmed as the controlling authority hierarchy for this
   repository generally.
3. `docs/DOCUMENT_INDEX.md`'s conflicting description of `docs/architecture/*`/`ARCHITECTURE_FREEZE_STATUS.md`'s
   registry as Tier-3 "Frozen Architecture Documents" is superseded by this ADR to the extent of the
   conflict. `DOCUMENT_INDEX.md` should be corrected in a follow-up documentation change to remove that
   characterization and to point instead to `AARA_ARCHITECTURE_AUTHORITY.md`'s hierarchy; that correction
   is not itself performed by this ADR (see §4).
4. **Promotion is the only path to bindingness**, and promotion requires the document to become tracked:
   moved into `docs/platform/`, `docs/products/`, or written as its own ADR under `docs/decisions/`.
   Being "approved," "frozen" in its own text, or cited as authoritative by another document does not
   promote a `docs/architecture/*` document on its own — the citing document would itself need to either
   incorporate the content directly or be the instrument that commits the promoted file, consistent with
   the precedent already set by `TRADING_INTELLIGENCE_BOUNDARY.md` and `DASHBOARD_DEPENDENCY_REDUCTION_PLAN.md`.
5. No content currently in `docs/architecture/*` is promoted by this ADR. Every claim originating there
   (including but not limited to the Five-Metric Framework wording, the "Derived Views Only"/"never raw
   ledger" rule, the Phase 2A "Mock Decision Data" scope item, and the "19 event types"/hash-chained-ledger
   claims) remains non-binding unless and until a future, separate action promotes the specific document
   or provision in question.

## 3. Explicit Non-Authorization

This ADR does not:

- Delete, move, or edit any file under `docs/architecture/*`. All content there is preserved as
  non-binding reference/exploratory material, exactly as `AARA_ARCHITECTURE_AUTHORITY.md` already
  describes its role.
- Retroactively invalidate any decision already made by citing `docs/architecture/*` content as
  supporting rationale (as opposed to as binding authority) — the distinction this ADR draws is about
  what can be *cited as the source of a binding requirement*, not about whether `docs/architecture/*`
  may inform reasoning.
- Amend or reopen ADR-011's own narrow decision; ADR-011 remains valid and is generalized, not revised.
- Promote any specific `docs/architecture/*` document to a tracked location. Any future promotion
  requires its own action (a documentation change, a product-doc addition, or an ADR), on a
  document-by-document basis.
- Resolve any of the other three architecture questions (Q1: Bot→Sentinel decision lineage; Q2: Audit
  Trail "never raw ledger" semantics; Q3: Constitution/Risk Governor contract) analyzed alongside this
  one. Q2 in particular depends on this ADR's outcome (the "never raw ledger" rule lives in
  `ARCHITECTURE_FREEZE_STATUS.md`, whose bindingness this ADR resolves as non-binding) but is not itself
  decided here.

## 4. Follow-On Action (Not Authorized by This ADR)

`docs/DOCUMENT_INDEX.md` §1 and §2 should be corrected in a separate documentation change to remove
`docs/architecture/ARCHITECTURE_FREEZE_STATUS.md` and its registry from the Tier-3 "Frozen Architecture
Documents" description, and to cite `AARA_ARCHITECTURE_AUTHORITY.md`'s hierarchy as controlling instead.
This ADR states that the correction is required and why; it does not perform the edit.

## 5. Relationship to ADR-011

This ADR generalizes ADR-011's Tier-4/non-binding reading of `docs/architecture/*` from a single named
question to a repository-wide principle. ADR-011's own decision, reasoning, and Consequences are
unchanged and remain valid — this ADR adopts the same conclusion ADR-011 already reached and removes the
scope limitation ADR-011 deliberately imposed on itself.

## 6. Consequences

**Positive:**
- Removes the standing, previously-unresolved conflict between `DOCUMENT_INDEX.md` and
  `AARA_ARCHITECTURE_AUTHORITY.md` as a general matter, not just for one prior dispute.
- Establishes an objective, low-ambiguity test for bindingness (tracked vs. untracked) rather than a
  subjective one (a document's own claimed status, or another document's characterization of it).
- Aligns with this project's stated governance principle of auditability: a tracked document's history
  is itself an audit trail of who changed what and when; an untracked document can be edited with no
  record, which is inconsistent with treating it as binding.
- Gives every future citation of `docs/architecture/*` content an unambiguous answer: informative, not
  binding, until promoted.

**Negative:**
- Any prior work (inside or outside this repository's ADRs) that treated a `docs/architecture/*`
  provision as binding must be re-examined; where such a provision is still wanted as governing, it now
  requires an explicit promotion action it did not previously need.
- `docs/DOCUMENT_INDEX.md` remains, until corrected, in a state this ADR has already ruled it conflicts
  with — some risk of a reader consulting `DOCUMENT_INDEX.md` alone and reaching the superseded
  conclusion until the follow-on correction (§4) is made.

**Primary Risk:** Same in kind as ADR-011 already named for its narrower version of this decision — a
reader who consults only one of the two conflicting documents, and not this ADR, may still reach the
wrong conclusion about `docs/architecture/*`'s bindingness until `DOCUMENT_INDEX.md` is corrected.

## 7. Acceptance Criteria

This ADR may be considered accepted only when the architecture owner has explicitly confirmed the
tracked-governance principle stated in §2. Acceptance does not itself perform the `DOCUMENT_INDEX.md`
correction named in §4, and does not promote any `docs/architecture/*` content.

**Satisfied at acceptance (2026-08-24):** the architecture owner explicitly confirmed the
tracked-governance principle in §2. Acceptance authorizes only the exact scope defined in §2 — it does
not itself perform the `DOCUMENT_INDEX.md` correction in §4, does not promote any `docs/architecture/*`
content, and does not modify `.gitignore`, `docs/architecture/`, or `docs/DOCUMENT_INDEX.md`.

## 8. Decision Statement

> Being tracked is necessary but not sufficient for a document to be authoritative in this repository —
> a document must be both tracked and occupy an authoritative role under the existing hierarchy (an
> Accepted ADR, or a Tier-3 tracked platform/implementation document). `docs/architecture/*`, in its
> entirety, is non-binding local working material for as long as it remains gitignored and untracked —
> this generalizes ADR-011's narrow ruling to a repository-wide principle.
> `AARA_ARCHITECTURE_AUTHORITY.md`'s authority hierarchy controls; `docs/DOCUMENT_INDEX.md`'s conflicting
> Tier-3 treatment of `docs/architecture/ARCHITECTURE_FREEZE_STATUS.md` is superseded to the extent of
> the conflict and should be corrected in a separate, future documentation change. Promotion to binding
> status requires a document to become tracked — moved into `docs/platform/`, `docs/products/`, or
> written as its own ADR — not merely cited or self-declared. No content in `docs/architecture/*` is
> promoted by this ADR.

## 9. Status

**Accepted (2026-08-24).**
