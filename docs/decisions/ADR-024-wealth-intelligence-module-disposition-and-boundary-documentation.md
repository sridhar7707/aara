# ADR-024: Wealth Intelligence Module Disposition and Boundary Documentation

**Status:** Accepted
**Date:** 2026-08-14
**Decision Type:** Architecture — Directional Disposition Only, No Implementation Authorized
**Related ADRs:** ADR-015 (classification unchanged, not amended), ADR-022 (cited as governing principle), ADR-004 (not resolved), ADR-013 (composition-root precedent, not extended)

---

## 1. Context

`ADR-015` (Accepted, 2026-08-12) classified four `sentinel_engine/`-resident modules consumed exclusively by `applications/wealth_intelligence/`:

- `sentinel_engine/presentation/investor_presenter.py` — **B, Product-specific**
- `sentinel_engine/application/investor_workspace.py` — **C, Transitional**
- `sentinel_engine/queries/morning_brief_query.py` — **C, Transitional, leaning toward future Core**
- `sentinel_engine/queries/decision_center_query.py` — **C/D, Transitional, leaning toward future Core**

`ADR-015` deliberately authorized no relocation, genericization, or consolidation, leaving each open question to "a separate, future ADR or governance decision" (`ADR-015` §13, §15). It also noted (§12) that no Wealth Intelligence equivalent of `docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md` exists.

Re-verified this session: the import graph is unchanged since `ADR-015`'s audit — `applications/wealth_intelligence/bootstrap.py` is still the sole production consumer of all four modules; `applications/trading_intelligence/` still imports none of them.

Two facts new since `ADR-015` bear directly on the open questions:

1. **`ADR-022`** (Accepted, this session) decided that product-facing governance/audit/evidence/decision-chain UI belongs inside the owning product's own application package, never inside `sentinel_engine/`. Trading Intelligence's own Decision Center (`applications/trading_intelligence/`) is now a mature, tested (280 tests), deployed implementation built entirely under that principle, independent of `sentinel_engine/queries/decision_center_query.py`.
2. **`docs/platform/AARA_PLATFORM_SHELL_ARCHITECTURE.md`'s navigation model** lists Trading Intelligence's own six screens as including **"Morning Brief"** — the same name currently borne by `sentinel_engine/queries/morning_brief_query.py`, a module today consumed only by Wealth Intelligence. "Morning Brief" is therefore not inherently a Wealth-only concept at the product-vocabulary level, even though only one product currently calls the module bearing that name.

---

## 2. Decision

Four directional dispositions, each a *direction*, not an implementation plan:

### 2.1 `investor_workspace.py` — **Wealth product**, not genericized

It is both product-named (`InvestorWorkspaceFacade`) and product-shaped (pure delegation to exactly three query objects selected for one product's screens), per `ADR-015`'s own finding. With a single consumer and no second product asking for this exact facade shape, genericizing now would invent a reusable abstraction with no second use case to justify it — the smaller, more defensible direction is that this module belongs to Wealth Intelligence as product code, not Sentinel Engine core.

### 2.2 `morning_brief_query.py` — **genericize as a reusable engine query**

Its aggregation behavior (decision-status grouping, pending-governance/approval counts over `LedgerRepository`/`ProjectionRepository`) is engine-level and product-neutral — this, per `ADR-015`'s own "leaning toward future Core" finding, is the primary basis for this direction. Trading Intelligence's own documented screen list separately names "Morning Brief" as one of its six screens; this is, at most, a tentative and unconfirmed secondary connection, not settled evidence — the screen's own documented required content ("portfolio snapshot, market mood/regime, today's candidate screening summary, overnight news relevant to holdings," per `AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`) is largely unrelated to this module's actual computed fields (`total_decisions`, `decisions_by_status`, `pending_governance_count`, `pending_approval_count`), and any overlap ("`DecisionProjection` summaries for recent decisions") is itself documented there as not yet wired. Direction: remains in `sentinel_engine/`, generalized (its current Wealth-flavored name and shape are not final), available to both products.

### 2.3 `decision_center_query.py` — duplication stands, not canonical/shared

`ADR-022` decided product-facing UI ownership only — it does not require product-local read logic, and does not by itself forbid a shared query layer (`decision_query.py` is already validly shared between both products' engine-facing code today, per `ADR-015` §4). Trading Intelligence's independent Decision Center implementation is already built, tested, and deployed with its own read path, not consuming this module. Direction: duplication stands unless a future ADR verifies the two read shapes can converge without violating `ADR-022`'s UI-ownership boundary — `decision_center_query.py` is not promoted to a shared canonical query by this ADR.

### 2.4 `investor_presenter.py` — **relocation authorized in direction**

The most clear-cut of the four: `ADR-015` classified it unambiguously Product-specific with no "leaning toward Core" hedge — pure presentation/view-model mapping, explicit "Investor" branding, zero internal `sentinel_engine` consumers. `ADR-022`'s principle already names its destination in kind (`applications/wealth_intelligence/`). No genuine open question remains about *whether* it belongs to Wealth Intelligence — only *when* it moves. This ADR authorizes relocation **in direction only**; the move itself, its exact target module path, and any import updates are a separate, future implementation change, not authorized here.

### 2.5 Wealth Intelligence boundary document — **required**

A Wealth Intelligence equivalent of `docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md`, recording the dispositions above in the same structured, durable format Trading Intelligence already has, is **required** — but not authored by this ADR. It must exist before or alongside the first implementation step that acts on any of §2.1–2.4 above (i.e., it is a prerequisite gate for implementation, not an immediate standalone task with its own deadline).

---

## 3. Explicit Non-Authorization

This ADR is directional only. It authorizes no code change of any kind. Specifically, it does not authorize:

- Any file move, rename, or refactor — `investor_presenter.py`, `investor_workspace.py`, `morning_brief_query.py`, `decision_center_query.py` all remain physically exactly where they are today.
- Any change to `sentinel_engine/composition/evidence.py` or creation of any new composition root (per `ADR-013`'s precedent, cited — not extended).
- Any resolution of `ADR-004`'s Option A/B/C ledger-ownership choice, or any ledger backend implementation.
- Any change to `applications/trading_intelligence/` — its existing, independent Decision Center implementation is affirmed as-is, not modified.
- Any deployment, workflow, or Hugging Face Space change (unrelated to `ADR-023`, not touched here).
- Writing the Wealth Intelligence boundary document's content — §2.5 decides only that one is required, not what it says.
- Any change to `sentinel_engine/tests/test_package_imports.py` or any other existing test.
- Any modification to `ADR-001`, `ADR-002`, `ADR-004`, `ADR-013`, or `ADR-015`. `ADR-015`'s own classification of all four modules (§8–§9) is unchanged and remains the governing classification; this ADR only resolves what `ADR-015` deliberately left open, it does not re-classify anything.

**Any future relocation, genericization, or the boundary document's authoring requires its own separate implementation or documentation change — not authorized by this ADR.**

---

## 4. Relationship to ADR-015

`ADR-015`'s classification (§8, §9) is unchanged and unamended. This ADR does not reclassify any module — it answers the disposition questions `ADR-015` itself posed and deliberately left to "a separate, future ADR or governance decision" (§13, §15). Where `ADR-015` said a module "may" be relocated or genericized, this ADR states a direction; it does not retroactively alter `ADR-015`'s own classification table or reasoning.

## 5. Relationship to ADR-022

`ADR-022` governs product-facing UI ownership only — it does not decide read-query ownership. It is the evidence cited for §2.4 above (`investor_presenter.py` is genuinely presentation/view-model code, the case `ADR-022` speaks to). It is **not** cited as justification for §2.3: `decision_center_query.py` is a `sentinel_engine/queries/` read module, not UI, and `ADR-022` does not decide whether such a module may be shared. This ADR does not modify `ADR-022`; it applies its already-accepted, correctly-scoped principle only where that principle actually applies.

## 6. Relationship to ADR-004 and ADR-013

Not resolved, not touched. No ledger backend, no `ProjectionRepository` implementation, and no composition-root change is authorized or implied by any decision in this ADR.

---

## 7. Explicit Non-Decisions

This ADR does not decide:

1. The exact destination module path for `investor_presenter.py` if/when relocated.
2. The new name or exact module location for the generalized `morning_brief_query.py`.
3. The Wealth Intelligence boundary document's content, structure beyond "mirrors `TRADING_INTELLIGENCE_BOUNDARY.md`'s intent," or exact filename.
4. A concrete deadline for the boundary document beyond "before or alongside first implementation acting on §2.1–2.4."
5. Whether `investor_workspace.py`, once confirmed as Wealth product code, should be merged with `investor_presenter.py` or kept as separate files — a file-organization detail, not a boundary question.
6. Any timeline for implementing §2.1, §2.2, or §2.4's relocations.

---

## 8. Consequences

**Positive:**
- Closes the four open disposition questions `ADR-015` explicitly deferred, using evidence (`ADR-022`'s principle, Trading Intelligence's own documented "Morning Brief" screen) that did not exist at `ADR-015`'s time.
- Gives future implementation work a citable, already-reasoned direction instead of re-deriving one.
- Keeps `sentinel_engine/`'s core surface honest going forward: two of four modules are now formally destined for product-side ownership, one is formally destined to stay and generalize, one's duplication formally stands rather than being centralized, unless a future ADR independently verifies convergence is possible.
- Zero implementation risk: no code moves, no behavior changes.

**Negative:**
- Three of four modules remain physically inside `sentinel_engine/` until a separate implementation change acts on this ADR's direction — the ambiguity of "wrong place, not yet moved" persists a while longer, now with a named target instead of an open question.
- The Wealth Intelligence boundary document remains unwritten until a future documentation change produces it.

---

## 9. Acceptance Criteria

This ADR is accepted on the basis that it:

- Decides a direction for all four `ADR-015`-classified modules, without moving, renaming, or refactoring any of them.
- Leaves `ADR-015`'s classification (§8–§9) unchanged.
- Authorizes no new composition root and does not touch `ADR-013`.
- Does not resolve `ADR-004`'s Option A/B/C.
- Makes no change to `applications/trading_intelligence/`.
- Makes no deployment, workflow, or Space change.
- Does not amend or supersede `ADR-001`, `ADR-002`, `ADR-004`, `ADR-013`, or `ADR-015`.
- States that a Wealth Intelligence boundary document is required, without authoring it.

---

## 10. Decision Statement

> `investor_workspace.py` is directionally Wealth product code (not genericized). `morning_brief_query.py` is directionally a reusable engine query (genericized, not relocated), primarily on `ADR-015`'s own engine-level/product-neutral finding. `decision_center_query.py`'s duplication alongside Trading Intelligence's own independent Decision Center implementation stands — not promoted to a shared canonical query — unless a future ADR verifies the two read shapes can converge without violating `ADR-022`'s UI-ownership boundary. `investor_presenter.py`'s relocation to `applications/wealth_intelligence/` is authorized in direction only. A Wealth Intelligence boundary document, mirroring `TRADING_INTELLIGENCE_BOUNDARY.md`, is required before or alongside implementation of any of the above.
>
> `ADR-015`'s classification is unchanged. No file is moved, renamed, or refactored by this ADR. No new composition root, no `ADR-004` resolution, no `applications/trading_intelligence/` change, and no deployment/workflow change is authorized.

---

## 11. Status

**Accepted.**
