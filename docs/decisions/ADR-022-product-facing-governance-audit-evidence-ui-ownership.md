# ADR-022 — Product-Facing Governance/Audit/Evidence UI Ownership

**Status:** Accepted
**Date:** 2026-08-14
**Decision Type:** Architecture — UI Ownership Classification Only
**Related ADRs:** ADR-005 (Accepted, cited as supporting precedent), ADR-007 (Proposed, not accepted or modified by this ADR — its boundary principle is cited only)

---

## 1. Context

A prior audit verified a standing, unrecorded conflict between two documents on where product-facing governance/audit/evidence/decision-chain UI belongs:

- `docs/implementation/CODEBASE_MIGRATION_MATRIX.md` §3 ("Dashboard Migration") routes "Sentinel UI" — governance views, audit history, decision chains, evidence views — to a destination of `sentinel_engine/admin_ui/`. That path does not exist anywhere in the repository (confirmed: no `admin_ui` directory or file under `sentinel_engine/`).
- `docs/decisions/ADR-007-aara-platform-hierarchy.md` (**Status: Proposed**, not yet binding per `docs/DOCUMENT_INDEX.md`'s rule that a Proposed ADR "is not yet authoritative") states, at §Boundaries: *"Sentinel Intelligence Engine... has no product-specific UI or customer-facing identity of its own."*
- The real, committed, tested implementation already places this exact category of UI — Evidence, Governance & Policy, Approval, and Audit Trail panels — inside `applications/trading_intelligence/ui/decision_center/` (`applications/trading_intelligence` test suite, 280 tests passing), never inside `sentinel_engine/`.

Per `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`'s own hierarchy ("Committed code — highest authority. What's actually built and tested wins over any document"), the implementation already resolves this operationally. No document had ever recorded that resolution, leaving `CODEBASE_MIGRATION_MATRIX.md`'s stated destination and the real implementation in unreconciled disagreement — exactly the situation `AARA_ARCHITECTURE_AUTHORITY.md` §"Resolving future conflicts" requires an ADR for: *"A new document that conflicts with an existing authoritative doc does not silently coexist with it."*

---

## 2. Decision

Product-facing governance, audit, evidence, and decision-chain UI belongs inside the owning AARA product's own application package. It must **not** live inside `sentinel_engine/`.

- Trading Intelligence → `applications/trading_intelligence/ui/`
- Wealth Intelligence → `applications/wealth_intelligence/ui/`, when implemented

This ADR resolves UI ownership only.

---

## 3. Explicit Non-Authorization

This ADR authorizes no code change of any kind. It does not:

- Create, move, or modify anything under `sentinel_engine/`, including `sentinel_engine/admin_ui/` — that path remains unauthorized and continues not to exist.
- Modify any file under `applications/trading_intelligence/` or `applications/wealth_intelligence/`.
- Modify `dashboard/`, any `.github/workflows/*.yml`, or any deployment configuration.
- Accept ADR-007 in full — ADR-007's own **Status remains Proposed**, unchanged by this ADR. Only ADR-007's already-stated boundary principle (the engine has no product-specific UI) is cited here as supporting rationale for this narrower, already-verified conflict.

---

## 4. Scope of Supersession

This ADR supersedes exactly one destination in `CODEBASE_MIGRATION_MATRIX.md` §3 ("Dashboard Migration" → "Sentinel UI" → destination `sentinel_engine/admin_ui/`), and only as that destination applies to product-facing governance/audit/evidence/decision-chain UI.

It does **not** supersede any other part of that document: §1 (Sentinel Intelligence Engine candidates), §2 (Trading Intelligence module destinations), §3's own "Trading UI" destination (`applications/trading_intelligence/ui/`, unaffected and consistent with this decision), §4 (Analytics Migration), or §5 (Tools and Scripts) all remain as written.

Whether `sentinel_engine/` should ever have its own internal engine-maintenance UI, unrelated to any single product's governance/audit surface, is a separate and different question this ADR does not address.

---

## 5. Relationship to ADR-007

This ADR does not accept ADR-007. ADR-007's Status remains **Proposed**, and its broader `AARA Systems → Sentinel Intelligence Engine → Products` naming hierarchy is untouched by this decision. This ADR borrows only ADR-007 §Boundaries' already-stated principle as rationale for a narrower, already-verified conflict; it does not depend on ADR-007 being accepted and remains valid independent of ADR-007's own future disposition.

---

## 6. Relationship to ADR-005

ADR-005 (Accepted — Platform Shell Model) already established "Workspace Isolation": products own their own screens; the platform shell does not render product content. This ADR extends the same "products own their own UI" principle to the `sentinel_engine/`-vs-product boundary specifically, for governance/audit/evidence UI. It is consistent with, and does not supersede, ADR-005.

---

## 7. Explicit Non-Decisions

This ADR does not decide:

1. Whether ADR-007 itself should be Accepted.
2. Any other `CODEBASE_MIGRATION_MATRIX.md` destination or migration phase not named in §4.
3. Whether `sentinel_engine/` should ever have its own internal admin/maintenance UI.
4. Any deployment, packaging, or Hugging Face Space topology question.
5. Any Wealth Intelligence implementation detail beyond where its future UI belongs, if and when built.

---

## 8. Consequences

**Positive:**
- Removes the standing, previously unrecorded conflict between `CODEBASE_MIGRATION_MATRIX.md` and the real implementation.
- Gives Decision Center's already-built Evidence/Governance/Approval/Audit Trail panels an explicit, citable authorization for their current location, satisfying `AARA_ARCHITECTURE_AUTHORITY.md`'s own conflict-resolution rule.
- Zero implementation risk: no code is authorized, moved, or changed by this ADR.

**Negative:**
- None identified. This ADR formalizes a state that already exists and is already tested; it does not introduce new behavior.

---

## 9. Acceptance Criteria

This ADR is accepted on the basis that it:

- Decides UI ownership only; authorizes no code, no file move, and no `sentinel_engine/` change.
- Does not accept ADR-007; ADR-007's own Status is unchanged by this document.
- Supersedes exactly the one conflicting `CODEBASE_MIGRATION_MATRIX.md` destination named in §4 — no other ADR or document section.
- Does not modify `dashboard/` or any deployment configuration.

---

## 10. Decision Statement

> Product-facing governance, audit, evidence, and decision-chain UI belongs inside the owning AARA product's own application package — Trading Intelligence's inside `applications/trading_intelligence/ui/`, Wealth Intelligence's inside `applications/wealth_intelligence/ui/` when implemented — never inside `sentinel_engine/`.
>
> This ADR supersedes only `CODEBASE_MIGRATION_MATRIX.md` §3's "Sentinel UI → `sentinel_engine/admin_ui/`" destination, as it applies to this category of UI. It does not accept ADR-007 in full, does not modify `sentinel_engine/`, `dashboard/`, or any code, and does not resolve any other open architectural question.

---

## 11. Status

**Accepted.**
