# ADR-046 — Audit Trail "Derived Views Only" — Access-Path Interpretation

**Status:** Accepted
**Date Proposed:** 2026-08-24
**Decision Type:** Architecture / Governance — Interpretation / Clarification
**Related ADRs:** ADR-044, ADR-036, ADR-037

---

## Context

`docs/architecture/ARCHITECTURE_FREEZE_STATUS.md` §5 ("Derived Views Only") states: "Frontend displays projections, never raw ledger." ADR-044 (Accepted) established that `docs/architecture/*`, in its entirety, is Tier-4 and non-binding for as long as it remains gitignored and untracked. That wording therefore cannot itself be treated as the source of a binding requirement for any product surface, including the Audit Trail — regardless of how detailed, frozen-labeled, or long-standing it is.

ADR-044 §3 explicitly identified this exact question — named there as "Q2: Audit Trail 'never raw ledger' semantics" — as analyzed alongside that ADR but not decided by it, and named it as requiring its own separate governance action.

A read-only review of the repository's Accepted governance and real implementation found no Accepted ADR and no authoritative Tier-3 document that names the Audit Trail specifically and settles what "derived views only" means for it. Two materially different interpretations are both textually supportable from the non-binding source material and from adjacent, narrower Accepted decisions:

- **Payload-content opacity** — the Audit Trail must never expose raw event/ledger payload field content, only computed or summarized values.
- **Access-path abstraction** — the Audit Trail must never query the ledger or database directly; it must go through an approved query/repository/read-model abstraction, independent of what fields that abstraction happens to return.

This ADR selects the second interpretation, referred to below as **Q2-B**, as the governing meaning of "derived views only" for the Audit Trail specifically.

---

## Decision

For the Audit Trail:

**UI/application code must access ledger-derived information only through approved query/repository/read-model abstractions — never through direct access to raw ledger/database storage.**

Specifically:

- All Audit Trail data access must go through an approved abstraction layer (e.g. `DecisionQuery` and the repository interfaces it wraps), never through a direct database connection, direct SQL, or a direct read of a `LedgerStore`/persistence backend from the UI or application layer.
- This ADR resolves only *how* the Audit Trail reaches ledger-derived data (the access path), not *which* fields it may display once retrieved. It takes no position on field-level filtering, allowlisting, summarization, or transformation, and it does not require, forbid, weaken, or extend any such mechanism. The Audit Trail's presentation layer already applies its own field allowlist independently of this ADR — see Current Implementation below — and this ADR leaves it entirely unchanged.
- This is an interpretation of "derived views only" **specifically for the Audit Trail's access path**. It does not generalize this reasoning to any other component, panel, or contract not named in this ADR, and it does not generalize to the display-filtering question either.

---

## Current Implementation

`applications/trading_intelligence/adapters/sentinel_audit_source.py`'s `SentinelAuditSource` already accesses Audit Trail data exclusively through `sentinel_engine.queries.decision_query.DecisionQuery`, which itself reads only through `LedgerRepository`/`ProjectionRepository` — never through a direct database connection or raw SQL. This already satisfies the decision recorded above.

Separately, the Audit Trail's presentation layer (`applications/trading_intelligence/ui/decision_center/gradio_view.py`) already applies its own field-level allowlist, `_AUDIT_PAYLOAD_ALLOWED_KEYS`, to payload content before display. That allowlist was introduced in commit `167b89f` to fix a P0 accessibility/security finding — `_format_audit_detail_html()` had rendered every `Event.payload` key unfiltered, leaking the raw `decision_id` into the Audit Trail's expandable disclosure. This ADR does not evaluate, authorize, modify, extend, or depend on that filtering; it is noted here only so the access-path decision above is not mistaken for a claim about display-level filtering, which is a separate matter this ADR does not decide.

**No implementation change is authorized or required by this ADR.**

---

## Relationship to ADR-036 and ADR-037

ADR-036 (Evidence Data Event Payload Propagation) and ADR-037 (Decision Center Evidence Metadata Rendering) govern `EvidenceEntry`/Evidence-card behavior specifically — a different component from the Audit Trail. This ADR does not extend their authorization to the Audit Trail, and does not amend, reopen, or reinterpret either of them. Their existence, and their explicit authorization of specific Evidence-card payload fields, does not itself create — and is not relied upon here to create — any payload-scrubbing requirement for the Audit Trail. This ADR's Decision above is independent of both.

---

## Relationship to ADR-044

ADR-044 identified this exact question as unresolved and explicitly reserved it for a future, separate governance action. This ADR is that action. It does not amend, reopen, or reinterpret ADR-044, and it does not alter ADR-044's Tier-4/non-binding treatment of `docs/architecture/*` in general.

---

## Consequences

**Positive:**
- Establishes a precise, citable meaning of "derived views only" for the Audit Trail, closing the ambiguity ADR-044 left open.
- Aligns the governance language with the access-path architecture the implementation already follows.
- Resolves the access-path question without taking any position on field-level filtering, leaving the Audit Trail's existing `_AUDIT_PAYLOAD_ALLOWED_KEYS` allowlist — and the P0 security/accessibility finding that produced it — entirely undisturbed.

**Negative / Limitation:**
- This ADR itself does not guarantee, authorize, or extend payload minimization, field-level redaction, or filtering for the Audit Trail — the existing `_AUDIT_PAYLOAD_ALLOWED_KEYS` allowlist already governs that today, independently of this ADR. Any change to that allowlist is a separate architectural decision, not implied or authorized by this ADR.

---

## Implementation Impact

**Zero implementation risk.** No code, schema, repository, UI, or data migration is authorized or required by this ADR.

---

## Validation

Because no implementation change is authorized by this ADR, no validation gate, test suite run, or code change is required for its adoption. The current implementation (`SentinelAuditSource` → `DecisionQuery` → repository abstractions) was examined as evidence that the Decision above is already satisfied in practice — not as the source of this ADR's architectural authority, which rests on this ADR's own acceptance.

---

## Non-Goals

This ADR does not authorize, and explicitly excludes:

1. Payload scrubbing, allowlisting, summarization, or transformation of Audit Trail fields — the existing `_AUDIT_PAYLOAD_ALLOWED_KEYS` allowlist is unaffected by, and independent of, this ADR.
2. Any redesign of the Audit Trail.
3. Any modification to the Evidence card or `EvidenceEntry`.
4. Any amendment, reopening, or reinterpretation of ADR-036 or ADR-037.
5. Any amendment of ADR-044.
6. Resolution of Q3 (Constitution ↔ Risk Governor contract).
7. Resolution of Q1 (Bot → Sentinel decision lineage).

---

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-08-24
**Accepted By:** Architecture Owner
