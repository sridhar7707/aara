# ADR-058 — Architecture Owner Authority Source and ADR Ratification Rule

**Status:** Accepted
**Date Proposed:** 2026-08-28
**Date Accepted:** 2026-08-28
**Decision Type:** Architecture / Governance — Ratification Record of a Constitutive Governance Decision
**Related ADRs:** ADR-044 (tracked-governance principle this record builds on and completes), ADR-011 (precedent: a document's internal "Status" field cannot by itself confer authority the governing hierarchy keys elsewhere), ADR-057 (Proposed, untracked — a separate, more elaborate proposal on the same subject; neither accepted, rejected, superseded, nor amended by this ADR)

---

## Context

A read-only governance audit (the "Q4" review series in this repository's working history) established:

- **ADR-044** (Accepted, tracked) affirms `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`'s hierarchy — committed code › committed Accepted ADRs › tracked `docs/platform/` / `docs/implementation/` governance documents › untracked `docs/architecture/*` (non-binding) — and holds that being tracked in version control is a **necessary but not sufficient** condition for a document to be authoritative.
- No tracked, authoritative repository document states the **source** of the "Architecture Owner" authority that many ADRs name as their acceptance trigger, and the repository has **no objective test** distinguishing an ADR that was genuinely ratified from one whose header merely reads `Accepted`. Where recorded at all, acceptance appears only as the literal role string `**Accepted By:** Architecture Owner`, never tied to a verifiable identity or repository event.
- **ADR-057** proposes one resolution to that gap but is `Status: Proposed` and untracked, and by its own text "cannot bootstrap its own authority."

On **2026-08-28** the party holding control of this repository's authoritative default branch made a constitutive governance decision resolving that gap. That decision — recorded verbatim in §Decision below as D1, D2, D3, and D4 — **was made before this document existed**. This ADR is the tracked recording instrument for it.

This ADR does **not** create the authority it records, and does **not** derive that authority from itself. The constitutive act preceded this file; this file is the record of it.

---

## Decision

The following, already ratified by the constitutive act described in §Context, is recorded:

### D1 — Source of Architecture Owner authority

Architecture Owner authority derives from control of the authoritative repository / default branch.

### D2 — When an ADR is authoritative

An ADR is authoritative when **all** of the following hold:

1. it is tracked on the authoritative default branch,
2. its `Status:` is `Accepted`, and
3. it was landed under the repository's applicable write / merge controls.

In-file `Accepted By` attribution is metadata; it is **not** sufficient proof of ratification.

### D3 — Continuity, and non-authoritative ADRs

- Tracked **and** `Accepted` ADRs that exist as of the constitutive act recorded in §Context remain authoritative under continuity.
- They are **not** invalidated solely because a historical `Accepted By: Architecture Owner` attribution cannot now be independently resolved.
- Untracked ADRs are non-authoritative regardless of their `Status:` header.
- ADR-054, ADR-055, and ADR-056 therefore remain non-authoritative unless and until they are properly tracked and landed under D2.
- ADR-057 cannot bootstrap or establish its own authority.

### D4 — Proposing an ADR is separate from ratifying an ADR

Authoring a file — or committing one whose header reads `Status: Proposed` — records a **proposal** only. An ADR becomes **authoritative** only when D2 is satisfied. This ADR is itself an instance: it is `Proposed` until it is landed under D2.

---

## Scope of This Record

- This ADR records D1–D4 **exactly as ratified**. It does not add to, narrow, reinterpret, or infer beyond them.
- "Applicable write / merge controls" in D2.3 means whatever controls in fact govern writes to the authoritative default branch at the time a given ADR is landed. This ADR does not specify, mandate, or standardize any particular control.
- D3's continuity rule does **not** require reconstructing historical git-host permission settings for any prior ADR. A prior ADR that is tracked and `Accepted` continues to be authoritative without further evidence.

---

## Explicit Non-Goals / Non-Claims

This ADR does **not**:

1. Name a specific person, GitHub account, or handle as the Architecture Owner. D1 states the *source* of the authority, not an identification.
2. Introduce any pull-request requirement, `CODEOWNERS` requirement, signed-commit requirement, branch-protection requirement, or any other specific write / merge mechanism.
3. Establish a governance committee, quorum, voting rule, delegation framework, or recusal framework.
4. Accept, reject, supersede, amend, or re-attest ADR-057. ADR-057 remains `Proposed`; its disposition is out of scope here.
5. Change the `Status`, `Accepted By` line, dates, or any other content of ADR-054, ADR-055, ADR-056, or any other existing ADR. D3's effect on ADR-054/055/056 follows from their being untracked, not from any edit made here.
6. Perform a retrospective substantive review of ADR-001 through ADR-053, or reopen any of them.
7. Resolve or address Q1, Q2, or Q3, or any question other than the Q4 authority question.
8. State, reopen, or conclude anything about Phase 1A validation, ADR-004's decision criteria, or the ledger-ownership options.
9. Authorize or require any code, schema, test, workflow, configuration, deployment, or documentation change. It does not itself edit `AARA_ARCHITECTURE_AUTHORITY.md`, and it does not address whether `AARA_ARCHITECTURE_AUTHORITY.md` should be amended; that question is out of scope for this ADR.
10. Claim that this document created its own initial authority. The authority was constituted by the act described in §Context; this document only records it.
11. Make any additional governance decision beyond recording D1–D4.

---

## Relationship to ADR-044

ADR-044 (Accepted, tracked) established that tracked status is **necessary but not sufficient** and affirmed `AARA_ARCHITECTURE_AUTHORITY.md`'s hierarchy as controlling. This ADR is consistent with ADR-044 and completes the part ADR-044 left open: what *additionally* makes a tracked ADR authoritative (D2), and where the authority to ratify it comes from (D1). It does not conflict with ADR-044 and does not modify it, so no supersession is stated.

## Relationship to ADR-057

ADR-057 (Proposed, untracked) proposes a more elaborate Architecture-Owner definition and acceptance mechanism — a named GitHub handle, PR-approval / signed-commit verification, and a §7/§8 split on historical ADRs. This ADR records a **narrower** decision that was actually ratified, using only the terms in D1–D4. It neither adopts ADR-057's additional mechanisms nor forecloses a future, separately-ratified ADR that does. ADR-057's own `Status` is unchanged by this ADR.

---

## Evidence

- `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md` — §"Hierarchy" (tiers; "Committed … ADRs"); §"Resolving future conflicts" ("Write a new ADR under `docs/decisions/` that references both and states which wins and why"). Not modified by this ADR.
- `docs/decisions/ADR-044-docs-architecture-authority-and-tracked-governance-principle.md` — §2 and §"Decision Statement": tracked = necessary, not sufficient; hierarchy affirmed as controlling.
- `docs/decisions/ADR-011-phase-1-applicability-scope-for-decision-intelligence-architecture.md` — §Context: a document's internal "Status" field cannot by itself confer authority the governing hierarchy keys elsewhere.
- `docs/decisions/ADR-057-architecture-owner-authority-and-adr-acceptance.md` — §1 (the undefined-Architecture-Owner / not-objectively-verifiable-acceptance gap), §2 ("a proposal only"; the mapping is "a designation being made here, not an existing fact"), §13 ("No party has accepted ADR-057"). Cited as the record of the gap; its disposition is not decided here.
- `git status` at repository HEAD `d441836` — ADR-054, ADR-055, ADR-056, and ADR-057 are untracked (`??`); this establishes the application of D3 to those four.
- The Q4 review series in this conversation — records the constitutive ratification of D1–D4 on 2026-08-28, prior to the creation of this file.

---

## Decision Character

This is a **ratification record** of a constitutive governance decision that was already made. It authorizes no implementation of any kind. It becomes the authoritative record of D1–D4 when it is itself landed in accordance with D2; until then, per D4, it is a proposal.

---

## Consequences

**Positive:**

- Gives the repository, for the first time, a tracked instrument that states the source of Architecture Owner authority (D1) and an objective test for whether an ADR is authoritative (D2).
- Records the resolution of the Q4 authority question that the ADR-044 and ADR-057 records left open, on the narrowest terms that do so.
- Preserves every existing tracked + `Accepted` ADR without any retrospective review (D3).
- Makes the proposing-vs-ratifying distinction (D4) explicit and citable, including for this ADR itself.

**Negative / Limitation:**

- Does not identify the Architecture Owner by name or handle; identification, if wanted, is a separate future decision.
- Does not standardize the "applicable write / merge controls" referenced in D2.3; their sufficiency is judged case by case.
- Leaves ADR-057's disposition (accept / supersede / withdraw) unresolved.
- ADR-054, ADR-055, and ADR-056 remain non-authoritative until they are separately tracked and landed under D2; this ADR neither performs nor schedules that.
- Does not address whether `AARA_ARCHITECTURE_AUTHORITY.md` should be amended; that question is out of scope for this ADR.

---

## Acceptance

*(Completed only when this ADR is landed under D2. Left as a stub while `Proposed`. Per D2, authority follows from this document being tracked on the authoritative default branch with `Status: Accepted`, landed under the applicable write / merge controls; the lines below are a locator and the conventional metadata, not the source of authority — and per D2 the `Accepted By` string is metadata only. Per §Context, completing this section does not create the D1–D4 authority, which was constituted before this file; it records that this instrument has been landed.)*

**Status:** Accepted
**Date Accepted:** 2026-08-28
**Accepted By:** Architecture Owner
