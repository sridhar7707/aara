# ADR-015: Sentinel Engine Core Boundary and Wealth Intelligence Module Classification

---

## 1. Status

Accepted

---

## 2. Date

2026-08-12

---

## 3. Decision Summary

`sentinel_engine/` is the architectural boundary of the reusable Decision
Intelligence Core of AARA.

This ADR establishes an explicit classification rule for what belongs
inside that core, and applies that rule to four existing modules that
currently reside under `sentinel_engine/` but are consumed exclusively by
Wealth Intelligence today.

This ADR is a governance/classification decision only. It is **not** an
implementation or refactoring authorization. It moves no file, changes no
import, and alters no behavior.

---

## 4. Context

A read-only audit of `sentinel_engine/`, `applications/trading_intelligence/`,
and `applications/wealth_intelligence/` traced every production and test
importer of four modules living under `sentinel_engine/`:

- `sentinel_engine/presentation/investor_presenter.py`
- `sentinel_engine/application/investor_workspace.py`
- `sentinel_engine/queries/morning_brief_query.py`
- `sentinel_engine/queries/decision_center_query.py`

That audit established, by direct import-graph evidence (not inference):

- All four modules are consumed exclusively by `applications/wealth_intelligence/`
  in production today. Exhaustive search found zero production or test
  imports of any of the four, or their public types, anywhere under
  `applications/trading_intelligence/`.
- `applications/trading_intelligence/` independently implements its own,
  separately-built "Decision Center" read path
  (`applications/trading_intelligence/adapters/{sentinel_evidence_source,sentinel_governance_source,sentinel_projection_decision_source}.py`
  feeding its own query-service layer), rather than consuming
  `sentinel_engine/queries/decision_center_query.py`.
- By contrast, `sentinel_engine/queries/decision_query.py` — not audited by
  this ADR — is confirmed imported by **both** product bootstraps
  (`applications/trading_intelligence/bootstrap.py` and
  `applications/wealth_intelligence/bootstrap.py`), demonstrating that
  genuinely shared modules already exist side by side with the four
  single-consumer modules this ADR addresses.

No ADR has previously ruled on per-module product-affinity within
`sentinel_engine/`. `docs/decisions/ADR-001-sentinel-engine-structure.md`
settled package *structure* (a separate `sentinel_engine/` package,
independent of `bot/`, `dashboard/`, `database/`) but did not adjudicate
which individual files inside that package are genuinely core versus
product-specific. This ADR fills that gap for the four modules named
above only.

---

## 5. Governing Authority

Per `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`, Architecture Decision
Records (`docs/decisions/ADR-*.md`) are **Tier-2 architectural authority**:
explicit, dated resolutions that supersede any conflicting document below
them in the hierarchy (committed architecture/migration docs under
`docs/platform/`, `docs/implementation/`; gitignored local drafts under
`docs/architecture/`). Only committed code (Tier 1) outranks an accepted
ADR.

`AARA_ARCHITECTURE_AUTHORITY.md` also states the platform's conflict-resolution
rule directly: *"A new document that conflicts with an existing authoritative
doc does not silently coexist with it. Write a new ADR under `docs/decisions/`
that references both and states which wins and why."* This ADR is written
under that rule: it references `ADR-001` and
`docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md`, states that it does not
conflict with either, and states precisely what new ground it covers that
neither of them already decided.

---

## 6. Sentinel Engine Core Boundary Rule

The following is established as governance for this repository:

1. `sentinel_engine/` is the reusable Decision Intelligence Core of AARA.
2. The existence of only one current production consumer does **not**, by
   itself, make a module product-specific.
3. Core membership is determined by architectural responsibility, product
   neutrality, reusable contracts/logic, and the absence of
   product-specific presentation/workflow coupling — not by consumer
   count alone.
4. Product-specific UI, presentation view models, product-branded
   facades, and product-specific workflows belong outside
   `sentinel_engine/`.
5. The core remains dependency-directionally isolated:
   `sentinel_engine` depends on no product/application/integration
   package; products and integrations are permitted to depend on
   `sentinel_engine`.
6. A module may legitimately remain in `sentinel_engine/` while currently
   having exactly one consumer, if its responsibility is genuinely
   engine-level and product-neutral in behavior and contract shape.
7. Classification must not be based solely on current consumer count. It
   must weigh vocabulary, behavior, and reusability of the underlying
   capability, not just today's import graph.

This rule states "`sentinel_engine/` is the architectural boundary of the
reusable Decision Intelligence Core." It makes no claim of any kind about
legal ownership, licensing, copyright, or sale rights over that boundary
or its contents.

---

## 7. Classification Test

For each module, this ADR asks:

1. **Consumers:** which product(s), if any, currently import it in
   production?
2. **Vocabulary:** do its public types/contracts use product-branded
   terminology (e.g. "Investor"), or generic decision-lifecycle
   terminology?
3. **Behavior:** is its responsibility genuine engine/domain capability
   (reading or writing decision-lifecycle state through the engine's own
   repositories/services), or product presentation/workflow (formatting,
   view-model mapping, UI-shaped delegation)?
4. **Portability:** would relocating it outside `sentinel_engine/` change
   any import direction rule, or does it depend only on already-legitimate
   engine-core types?
5. **Coupling if retained:** does keeping it inside `sentinel_engine/`
   bind the shared package's public surface to one product's screens or
   naming?

A module scoring "generic/engine-level" on tests 2–3, independent of test
1, is a candidate for Core even with a single current consumer. A module
scoring "product-branded/presentation-only" on tests 2–3 is
Product-specific regardless of its physical location today.

---

## 8. Classification of Existing Modules

| Module | Current consumer(s) | Vocabulary | Behavior | Classification |
|---|---|---|---|---|
| `sentinel_engine/presentation/investor_presenter.py` | Wealth Intelligence only | Explicit "Investor" branding; display-ready view models (`MorningBriefView`, `DecisionCenterViewModel`, etc.) | Presentation-only: formatting/mapping, no domain logic; zero internal `sentinel_engine` consumers — a leaf | **B — Product-specific** |
| `sentinel_engine/application/investor_workspace.py` | Wealth Intelligence only | Explicit `InvestorWorkspaceFacade` naming | Product read-facade: pure delegation to three query objects, shaped around one product's screens | **C — Transitional** |
| `sentinel_engine/queries/morning_brief_query.py` | Wealth Intelligence only | "Morning Brief" is product-flavored naming | Genuine engine-level read aggregation directly over `LedgerRepository`/`ProjectionRepository` (decision-status grouping, pending-governance/approval counts) | **C — Transitional, leaning toward future Core** |
| `sentinel_engine/queries/decision_center_query.py` | Wealth Intelligence only | "Decision Center" is not inherently Wealth-specific — Trading Intelligence has its own, separately-implemented Decision Center concept | Genuine engine-level read logic, built on the shared `decision_query.py`; duplicated in spirit by Trading Intelligence's independent implementation | **C — Transitional, leaning toward future Core** |

None of the four is classified as "not part of Sentinel Engine" in a
blanket sense. Three of the four (B, C, D below) remain physically inside
`sentinel_engine/` today, and this ADR does not change that.

---

## 9. Decision for Each Module

### A. `sentinel_engine/presentation/investor_presenter.py` — Product-specific

Classified as Wealth Intelligence product code. Future relocation to
`applications/wealth_intelligence/` may be proposed separately. **This ADR
does not authorize relocation.**

### B. `sentinel_engine/application/investor_workspace.py` — Transitional

Its current product-specific naming and single-product ownership prevent
treating it as unquestionably core today, even though its delegation
behavior could potentially represent a reusable facade pattern. This ADR
assigns it a transitional classification and takes no further action. A
future decision must either genericize it into a genuinely reusable
engine abstraction or relocate it to Wealth Intelligence. **This ADR does
not relocate or refactor it.**

### C. `sentinel_engine/queries/morning_brief_query.py` — Transitional, leaning toward future Core

Its implementation performs genuine engine-level read aggregation over
decision state, ledger, and projection data, and its underlying
capability may be reusable across products even though its current name
and sole consumer are Wealth-Intelligence-specific. This ADR preserves
its transitional classification and does not relocate it. Future
governance should determine whether to genericize/rename it as a
reusable engine query, or relocate it if the capability turns out to
remain Wealth-specific in practice.

### D. `sentinel_engine/queries/decision_center_query.py` — Transitional, leaning toward future Core

It contains genuine engine-level read logic and is built on the shared
`decision_query.py`, but Trading Intelligence currently has an
independently implemented Decision Center read path that does not consume
it. This duplication must be resolved before this module can be declared
definitively core. This ADR does not relocate it and does not consolidate
the two Decision Center implementations. Future governance must determine
whether this query becomes the shared engine-level Decision Center query,
or whether the two product implementations remain intentionally separate.

---

## 10. Relationship to ADR-001

`docs/decisions/ADR-001-sentinel-engine-structure.md` establishes
`sentinel_engine/` as a separate package extracted from `sentinel/`,
independent of `bot/`, `dashboard/`, and `database/`, explicitly to give
"cleaner isolation for multiple future products... consuming one shared
engine." That product-isolation rationale motivates the boundary
classification this ADR performs.

**ADR-015 does not supersede or amend ADR-001.** ADR-001 decided package
*structure*; it did not decide per-module product-affinity within that
structure. ADR-015 provides the per-module classification that ADR-001
did not explicitly define, for exactly the four modules named in Section
8, and no others.

---

## 11. Relationship to ADR-013

`docs/decisions/ADR-013 — Minimal Temporary EvidenceService Wiring for
Trust Decisions.md` is referenced only as precedent for a governance
pattern: that narrowly-scoped exceptions or temporary mechanisms living
inside `sentinel_engine/` (in ADR-013's case, a temporary
`EvidenceService` composition boundary) should be explicitly governed and
labeled by name, rather than silently treated as general core
architecture. ADR-013 itself states its composition module "shall not
become a general-purpose Sentinel composition root."

**ADR-013 does not govern the four modules classified in this ADR.**
ADR-013's subject matter (`sentinel_engine/composition/evidence.py`, its
temporary `LedgerStore`/`ProjectionRepository` pair, and `EvidenceService`
wiring) is unrelated to `investor_presenter.py`, `investor_workspace.py`,
`morning_brief_query.py`, or `decision_center_query.py`. This ADR draws
only the general governance principle from ADR-013 — explicit labeling
over silent inclusion — not any of its specific authorizations.

---

## 12. Wealth Intelligence Boundary Documentation Gap

`docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md` is Trading Intelligence's
(Product #1's) authoritative target-state ownership boundary against
`sentinel_engine/`. No equivalent document exists for Wealth Intelligence
(Product #2) today; a repository search for such a document found none,
and the only Product #2-specific authoritative document,
`docs/products/AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`, is
already flagged elsewhere as describing an aspirational product that does
not match the shipped `applications/wealth_intelligence/` application.

`TRADING_INTELLIGENCE_BOUNDARY.md` is cited here only as **structural
precedent** for how this repository records a product-versus-core
boundary. **This ADR does not create or replace a full Wealth Intelligence
boundary document.** It classifies four specific, already-existing
modules; it does not attempt the broader, document-length boundary
description `TRADING_INTELLIGENCE_BOUNDARY.md` provides for Product #1.
Producing a full Wealth Intelligence equivalent remains separate,
unauthorized future work.

---

## 13. Explicit Non-Authorization

**This ADR is classification-only. It authorizes no source-code movement,
import change, refactor, rename, deletion, test change, composition-root
change, or behavior change.**

Specifically, this ADR does not authorize:

- Moving `investor_presenter.py`, `investor_workspace.py`,
  `morning_brief_query.py`, or `decision_center_query.py` to any other
  location.
- Renaming any class, function, module, or file.
- Consolidating Trading Intelligence's independent Decision Center
  implementation with `decision_center_query.py`.
- Genericizing `InvestorWorkspaceFacade` or any other product-branded
  type.
- Any change to `sentinel_engine/composition/evidence.py` or creation of
  any new composition root.
- Any ADR-002 exception. This ADR touches none of `bot/`, `dashboard/`,
  `scheduler/`, `.github/workflows/`, `database/`, or top-level `ledger/`,
  and creates no exception to their protection.
- Any change to `sentinel_engine/tests/test_package_imports.py` or any
  other existing test.
- Any modification to `ADR-001`, `ADR-013`, or any other existing ADR.

**Any future relocation, genericization, consolidation, or refactoring
arising from this classification requires its own implementation or
governance decision.**

Three of the four modules classified above (`investor_workspace.py`,
`morning_brief_query.py`, `decision_center_query.py`) remain physically in
`sentinel_engine/` for now, precisely because this ADR is
classification-only and does not authorize movement.

---

## 14. Consequences

### Positive

- Makes Sentinel Engine's architectural role explicit.
- Prevents product-specific presentation code from silently expanding the
  core's public surface.
- Allows genuinely reusable engine capabilities to remain in the core
  even when currently single-consumer, rather than forcing premature
  relocation based on import count alone.
- Prevents premature movement or refactoring driven by this
  classification exercise.
- Gives future ADRs a stable, citable classification rule instead of
  requiring each to re-derive one.

### Negative

- Three of the four modules remain transitional; their long-term home is
  not settled by this ADR.
- The duplicate Decision Center implementations (Wealth Intelligence's
  `decision_center_query.py` path and Trading Intelligence's independent
  adapter chain) remain unresolved.
- `investor_presenter.py` remains physically inside `sentinel_engine/`
  until a separate decision moves it.
- A future governance decision is required before any of the three
  transitional classifications can change.

---

## 15. Future Change Requirements

Any of the following require a separate, future ADR or governance
decision — none are authorized here:

- Relocating `investor_presenter.py` to `applications/wealth_intelligence/`.
- Genericizing or relocating `investor_workspace.py`.
- Renaming, genericizing, or relocating `morning_brief_query.py`.
- Resolving the duplicate Decision Center implementations and deciding
  whether `decision_center_query.py` becomes the shared engine-level
  query both products use.
- Producing a full Wealth Intelligence boundary document equivalent to
  `TRADING_INTELLIGENCE_BOUNDARY.md`.
- Updating `docs/DOCUMENT_GOVERNANCE_MATRIX.md` to record this ADR.

---

## 16. Acceptance Criteria

This ADR may be considered accepted only when:

- It names `ADR-001`.
- It explicitly defines the Sentinel Engine Core boundary.
- It distinguishes product-specific code from reusable engine capability.
- It classifies all four named modules individually.
- It does not authorize code movement.
- It does not amend ADR-001.
- It does not create an ADR-002 exception.
- It does not make legal or intellectual-property ownership claims.
- It does not authorize a new composition root.
- It does not decide the future architecture of the duplicate
  Trading Intelligence / Wealth Intelligence Decision Center
  implementations.
- It leaves all implementation to future, separately governed work.
