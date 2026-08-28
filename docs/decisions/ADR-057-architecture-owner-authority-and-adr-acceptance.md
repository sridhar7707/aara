# ADR-057 — Architecture Owner Authority and a Verifiable ADR Acceptance Mechanism

**Status:** Proposed
**Date Proposed:** 2026-08-27
**Decision Type:** Architecture / Governance — Governance Role Definition
**Related ADRs:** ADR-044 (affirms `AARA_ARCHITECTURE_AUTHORITY.md` as the controlling
authority hierarchy, and establishes the tracked-governance principle — that a document's
self-declared status cannot substitute for the hierarchy's actual authority key), ADR-011
(precedent: a document's internal "Status" field cannot by itself confer authority the
governing hierarchy keys elsewhere), ADR-045 (the most elaborate prior acceptance-process
text; still relies on an undefined "architecture owner"), ADR-043 / ADR-046 / ADR-047 /
ADR-048 / ADR-049 / ADR-050 / ADR-051 / ADR-052 (Accepted under the prior self-attested
convention — preserved by §7 here), ADR-053 (Proposed — simply follows this ADR once both
are Accepted), ADR-054 / ADR-055 / ADR-056 (marked Accepted before any verifiable mechanism
existed — §8 requires their re-attestation)

---

## 1. Problem

Established facts about this repository's governance:

1. The authority hierarchy is defined and affirmed: `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`
   is the controlling document (ADR-044 §2.2), with tiers **(1) committed code → (2) committed
   Accepted ADRs → (3) tracked `docs/platform/` + `docs/implementation/` documents → (4) untracked
   `docs/architecture/*` (non-binding)**.
2. **Accepted ADRs are authoritative** and supersede any lower-tier document
   (`AARA_ARCHITECTURE_AUTHORITY.md` §Hierarchy; `docs/DOCUMENT_INDEX.md` §1 — "binding once
   status is Accepted; a Proposed ADR is not yet authoritative"; `docs/AI_AGENT_GUIDELINES.md`
   §6). A Proposed ADR is not.
3. **Many ADRs make "Architecture Owner" confirmation the trigger for acceptance.** The phrase
   *"this ADR may be considered Accepted only when the architecture owner has explicitly
   confirmed …"* (or equivalent) appears in ADR-013, ADR-014, ADR-043, ADR-044, ADR-045,
   ADR-046, ADR-047, ADR-048, ADR-049, ADR-050, ADR-051, ADR-052, ADR-053, and ADR-054–056.
4. **No authoritative repository document defines or assigns the "Architecture Owner" role.**
   There is no `GOVERNANCE.md`, no `CODEOWNERS`, no `OWNERS`/`MAINTAINERS` file, and no role
   definition in `AARA_ARCHITECTURE_AUTHORITY.md`, `DOCUMENT_INDEX.md`, `AI_AGENT_GUIDELINES.md`,
   or either `CLAUDE.md`. `docs/DOCUMENT_GOVERNANCE_MATRIX.md` has an "Owner" column, but it is
   a self-labelled DRAFT inventory artifact and its values are functional-area labels
   (`Platform`, `Sentinel Engine`, `Trading Intelligence`) denoting document stewardship, not
   ratifying authority.
5. The "Architecture Owner" confirmation, where it is recorded, is recorded only as in-ADR prose
   or an `## Acceptance` block whose `**Accepted By:**` line reads the **literal string
   "Architecture Owner"** — never a name, GitHub handle, commit SHA, PR number, or signature.
6. **Therefore ADR acceptance authority is not objectively verifiable.** A reader cannot, from
   the repository alone, confirm that any given "Accepted" status was set by a party with the
   authority to set it. This is the exact class of defect ADR-044 §1 and ADR-011 already
   identified for self-declared document status — applied here to ADR acceptance itself.

This ADR does **not** claim that any existing Accepted ADR is invalid, and does **not** reopen
any historical ADR (see §7). It closes the definitional gap prospectively.

## 2. Decision

**`docs/platform/AARA_ARCHITECTURE_AUTHORITY.md` shall be the authoritative location for the
Architecture Owner definition and the ADR acceptance mechanism.** ADR-057 states the rule; the
corresponding text (§9) is added to that document as a separate, tracked edit after ADR-057 is
Accepted (§9, §10).

**This ADR proposes the following governance designation** (a designation being *made here*,
not an existing fact recorded elsewhere):

> The **Architecture Owner** of this repository is the **GitHub account that owns the `origin`
> repository**:
> - GitHub account: **`sridhar7707`**
> - Repository: **`github.com/sridhar7707/aara`**

Rationale for this choice: it is the single identity that is (a) already the sole authority over
the repository's contents, (b) externally verifiable through GitHub's own authentication, and
(c) the author of the repository's entire commit history. It introduces no new person and
creates no new governance body. Acceptance of ADR-057 is what makes this designation
authoritative; until then it is a proposal only.

## 3. Authority Boundary

Architecture Owner authority **covers exactly**:

- **Accepting** an ADR (moving it Proposed → Accepted);
- **Rejecting** an ADR;
- **Superseding** an ADR (via a later ADR that names it);
- **Approving amendments** to `AARA_ARCHITECTURE_AUTHORITY.md`.

The role **does NOT automatically confer**, and must not be read as conferring:

- **document stewardship** — the per-area "Owner" concept in `DOCUMENT_GOVERNANCE_MATRIX.md`
  is a separate axis and is unchanged by this ADR;
- **implementation authority** — the right to write code, edit workflows, or change
  configuration flows **only** from an individual Accepted ADR's own terms, never from this
  role;
- **code-review authority** — no reviewer role is defined by this repository and none is
  created here;
- **deployment authority** — the right to deploy, push to a Hugging Face Space, or run a
  release;
- **production operational authority** — running the bot, managing live credentials, operating
  the trading runtime;
- **authority to bypass an Accepted ADR** — the Architecture Owner is bound by Accepted ADRs
  exactly as everyone else is; changing a binding decision requires a superseding ADR, not an
  exercise of role authority.

These roles remain conceptually distinct. One natural person may hold several of them; that
does not merge them.

## 4. Acceptance Mechanism

An ADR may be treated as **Accepted** only when **all** of the following hold:

- **A. Status.** The ADR's header `**Status:**` line reads `Accepted`.
- **B. Date.** A `**Date Accepted:**` line is present in the header (and, where the ADR uses an
  `## Acceptance` section, repeated there).
- **C. Attribution.** The ADR's `## Acceptance` section identifies the Architecture Owner **by
  GitHub handle** (`sridhar7707`), not by the bare role name alone.
- **D. Verifiable GitHub-authenticated action.** The acceptance is tied to an action GitHub
  itself authenticated as performed by the Architecture Owner's account. **Primary evidence,
  preferred wherever the repository uses pull requests:** a GitHub **PR review approval** by
  `sridhar7707` on the pull request that sets the ADR to `Accepted`.
- **E. Reference recorded.** The `## Acceptance` section records the **PR number** and/or the
  **commit SHA** that carried the status change, so the acceptance can be located in GitHub's
  history.

**Direct commits to `main` (currently this repository's normal flow).** Where no pull request
is used, raw git author/committer metadata is **not** sufficient identity proof on its own — it
is trivially settable via `git config`. The minimum additional evidence required for a
direct-commit acceptance is **both** of:

1. The acceptance commit is a **verified commit on GitHub** — i.e. GitHub displays the
   "Verified" badge for a signature (GPG or SSH) whose key is registered to the `sridhar7707`
   account; **and**
2. The `## Acceptance` section cites that commit's **full SHA**, and the commit message
   references the ADR number (e.g. `govern(ADR-0NN): accept`).

If signed commits are not in use at the time, acceptance must go through a pull request (the
primary path) so that GitHub PR-approval authentication supplies the identity proof instead.

An ADR whose `**Status:**` says `Accepted` but which does not satisfy A–E is **not validly
Accepted** for any governance purpose; its status text is provisional pending correction.

## 5. Delegation

The Architecture Owner may delegate, but **only through a tracked, Accepted governance
decision** — a dedicated ADR, or an amendment to `AARA_ARCHITECTURE_AUTHORITY.md` that is
itself accepted under §4. An informal or untracked delegation has no effect.

A delegation record must state:

- the **delegate's GitHub handle**;
- the **authority scope** — which of the §3 powers are delegated (it may be a strict subset,
  e.g. "accept ADRs in `docs/decisions/` numbered ≥ N" or "approve `AARA_ARCHITECTURE_AUTHORITY.md`
  amendments only");
- the **start date**;
- an **expiration date**, or an explicit statement that the delegation is **indefinite** until
  revoked;
- **whether the delegate may accept ADRs**, or may only perform another named governance
  function.

The Architecture Owner **remains accountable** for any action taken under a delegation.
Revocation is itself a tracked, Accepted governance decision.

## 6. Conflict / Recusal

Minimal rule, no framework:

- Authoring or drafting an ADR's text does **not** constitute a conflict — that is the normal
  path, and the Architecture Owner routinely both drives and accepts ADRs in this repository.
- A **substantive conflict of interest** exists only where the Architecture Owner has a
  material personal stake in the *outcome the ADR implements* that is separate from the
  repository's interest (for example, an ADR whose effect is primarily to benefit an external
  entity the Owner is party to).
- Where a substantive conflict exists, the `## Acceptance` section must **disclose it in one
  sentence**. In a future multi-party configuration a §5 delegate accepts in the Owner's place;
  in the current single-owner repository, disclosure is the requirement.

## 7. Historical ADRs (Transitional Clause)

- Every ADR whose status was `Accepted` **before ADR-057 becomes effective** remains Accepted
  and **is not reopened** solely because the Architecture Owner role was previously undefined.
- Their historical acceptance convention (in-ADR prose or an `## Acceptance` block attributing
  acceptance to "Architecture Owner") is **preserved as-is** and is deemed sufficient for those
  ADRs.
- **No retroactive re-attestation is required** of any pre-existing Accepted ADR solely on
  account of this governance gap. (A specific historical ADR may still be revisited later on
  its own merits — but never merely because §1's definitional gap existed when it was
  accepted.)
- This clause covers, without limiting: ADR-001 through ADR-053, and any other ADR marked
  Accepted before ADR-057's effective date. ADR-053, which is currently Proposed, simply
  follows §4 when it is accepted.

## 8. ADR-054, ADR-055, ADR-056 (Not Covered by §7)

These three are treated differently from the historical set, and explicitly:

- They were **marked Accepted after the Architecture Owner authority gap had been identified in
  this conversation, and before any verifiable mechanism existed** — the status flip was
  performed on the strength of an operator instruction treated as owner approval, a basis a
  subsequent authority audit found **NOT ESTABLISHED**.
- Their acceptance was therefore **not supported by an objectively verifiable Architecture
  Owner authority** at the time it was recorded.
- They **require re-attestation under §4** — a fresh Accepted-status action satisfying criteria
  A–E, performed by the Architecture Owner as defined in §2 — **before they may be treated as
  validly Accepted for the purpose of gating downstream work**.
- **Until that re-attestation is recorded, no implementation, workflow modification, secret
  provisioning, or deployment associated with ADR-054, ADR-055, or ADR-056 may occur.** For
  downstream-gating purposes they are to be treated as though Proposed, regardless of the
  `Accepted` string currently in their headers.
- **ADR-057 does not change the status of ADR-054, ADR-055, or ADR-056**, and does not itself
  re-attest them. It only states that re-attestation is the required next step for those three.
- ADR-054/055/056 should **not be committed** to the repository in their current
  (un-re-attested) state; committing would place an unverifiable acceptance into permanent
  history.

## 9. `AARA_ARCHITECTURE_AUTHORITY.md` Amendment (Specified Here, Performed Separately)

After ADR-057 is Accepted, and as a separate tracked edit (not performed by this ADR), a new
section is added to `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`, immediately after its
`## Hierarchy` section, reading substantially:

> ## Decision Authority
>
> **Architecture Owner.** The Architecture Owner is the GitHub account that owns the `origin`
> repository — **`sridhar7707`** (`github.com/sridhar7707/aara`). The Architecture Owner has
> authority to accept, reject, and supersede ADRs, and to approve amendments to this document.
> This role does not by itself confer document stewardship, implementation authority,
> code-review authority, deployment authority, production operational authority, or any right
> to act contrary to an Accepted ADR. See ADR-057.
>
> **ADR acceptance.** An ADR is Accepted only when its `Status:` is `Accepted`, a
> `Date Accepted:` is present, its Acceptance section names the Architecture Owner by GitHub
> handle and records the accepting PR number and/or commit SHA, and the acceptance is tied to a
> GitHub-authenticated action by the Architecture Owner (a PR approval by `sridhar7707`, or a
> GitHub-"Verified" signed direct commit by `sridhar7707` citing the ADR). Raw git author
> metadata alone is not sufficient. See ADR-057 §4.
>
> **Delegation.** Only via a tracked, Accepted governance decision naming the delegate's GitHub
> handle, scope, start date, and expiry (or explicit indefinite duration). The Architecture
> Owner remains accountable. See ADR-057 §5.
>
> **Transitional.** ADRs Accepted before ADR-057's effective date remain Accepted under their
> historical convention and are not reopened. ADR-054, ADR-055, and ADR-056 require
> re-attestation under this mechanism before they gate any downstream work. See ADR-057 §7–§8.

The exact heading level, wording, and placement are finalised when the edit is made; ADR-057
does not make the edit.

## 10. Implementation / Operational Boundary

ADR-057, in itself:

- changes **no application behaviour**;
- changes **no workflow** (`.github/workflows/*` untouched);
- provisions **no secret** (GitHub or Hugging Face);
- **deploys nothing**;
- changes **no database** and **no Trust Ledger**;
- changes **no requirements file, UI specification, or configuration**;
- does **not** perform the `AARA_ARCHITECTURE_AUTHORITY.md` edit described in §9;
- does **not** authorize implementation of ADR-054, ADR-055, or ADR-056, and does not change
  their status;
- does **not** resolve ADR-004 or the "Q1" hash-chained-event-table question, and does not
  touch `docs/architecture/*`.

It is a governance decision record only.

## 11. Acceptance Criteria

ADR-057 may be treated as Accepted only when the Architecture Owner (as defined in §2), acting
through the mechanism in §4, confirms all of the following:

- The **Architecture Owner identity is explicitly defined** — a named GitHub handle
  (`sridhar7707`), not the bare role string.
- The **acceptance mechanism is objectively verifiable** — criteria §4 A–E, with GitHub-
  authenticated PR approval preferred and raw commit-author metadata explicitly insufficient
  on its own.
- The **four roles remain separated** — Architecture Owner authority does not confer document
  stewardship, implementation, code review, deployment, or production operational authority
  (§3).
- **Historical Accepted ADRs are preserved** — §7's transitional clause stands; no retroactive
  re-attestation is forced by this gap.
- **ADR-054 / ADR-055 / ADR-056 are explicitly recorded as requiring re-attestation** under §4
  before they gate any downstream implementation, workflow change, secret provisioning, or
  deployment (§8).
- The **`AARA_ARCHITECTURE_AUTHORITY.md` amendment is specified** (§9) **but not performed** by
  ADR-057 itself.
- **No implementation authorization** is granted by acceptance of ADR-057 (§10).

## 12. Rollback

The governance amendment can be reverted without disturbing any historical ADR decision or any
application behaviour:

1. A later superseding ADR removes or replaces the `## Decision Authority` section added to
   `AARA_ARCHITECTURE_AUTHORITY.md` under §9, and marks ADR-057 `Superseded by ADR-0NN`.
2. **Historical ADR decisions are unaffected** by such a rollback: §7 already severs every
   pre-ADR-057 Accepted ADR from this mechanism, so removing the mechanism cannot retroactively
   unsettle them.
3. **No application behaviour, workflow, secret, database, or deployment state is involved** in
   ADR-057 or in reverting it — there is nothing operational to roll back.
4. Any re-attestation of ADR-054/055/056 already performed under §4 before the rollback would
   itself need explicit revisiting by the superseding ADR; absent that, those three revert to
   "require re-attestation" status.

Rollback is thus a pure documentation operation.

## 13. Status

**Proposed.** Awaiting Architecture-Owner review and disposition under the mechanism this ADR
itself defines (§4). No party has accepted ADR-057.

## Acceptance

*(To be completed only upon acceptance — left blank while Proposed.)*

**Status:** Proposed
**Date Accepted:** —
**Accepted By:** — (must be `sridhar7707`, per §2/§4)
**Accepting PR / commit:** —
