# AARA Workspace Activation Architecture

**Status:** Design analysis. Documentation only. No code was created or
modified. No resolver, router, or factory was created. No existing
architecture was changed. `applications/trading_intelligence/`,
`applications/platform/`, `sentinel_engine/`, `ledger/`, `bot/`,
`dashboard/`, `scheduler/`, `.github/workflows/`, `database/` untouched,
confirmed via `git status` before and after. This document does not choose
among the options it evaluates — that choice, if and when needed, belongs
to a future ADR, per the same deferral discipline `ADR-003` and `ADR-004`
already use.

**Authority:** `AARA_WORKSPACE_ENTRY_ARCHITECTURE.md`,
`AARA_PLATFORM_SHELL_ARCHITECTURE.md`, `ADR-005-platform-shell-model.md`,
`AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md`.

---

## 1. Current Validated Flow

```
NavigationItem
        |
        v
DecisionCenterController   (test-only construction)
```

Real, tested, verified directly against
`applications/platform/tests/test_trading_intelligence_product_integration.py`'s
`test_navigation_item_can_be_used_to_construct_decision_center_experience`:
a `NavigationModel` is built by `NavigationBuilder` for an entitled demo
user; the test locates the `NavigationItem` whose `workspace_id` equals
`"trading_intelligence.decision_center"` via a plain equality check written
directly in the test; the same test then constructs
`SentinelProjectionDecisionSource` → `DecisionQueryService` →
`DecisionCenterController` inline and calls `.load_screen()`, producing a
correct `DecisionCenterScreen`. A companion test in the same file
(`test_navigation_driven_construction_performs_no_writes`) proves this stays
read-only.

**This is the entire validated flow.** No object anywhere resolves this
generically; the identity check and the construction are both hand-written,
once, inside one test file, for one workspace.

## 2. Why Current Test Composition Cannot Become Production Code Directly

Three distinct reasons, not one:

1. **It would violate the platform/product boundary that is already an
   enforced rule, not just a preference.** The test imports
   `DecisionCenterController` (and its full supporting chain) directly
   alongside `NavigationBuilder`/`NavigationItem`, in one file. Integration
   tests are explicitly permitted to do this — established precedent
   throughout this codebase's `tests/` directories (`ADR-005`;
   `test_trading_intelligence_registration.py`; this file itself). Real,
   non-test code is not covered by that exemption. If the same import
   pattern existed in a module under `applications/platform/` outside
   `tests/`, it would directly violate `AARA_PLATFORM_SHELL_ARCHITECTURE.md`
   Section 4's rule that the shell "must not know trading logic... anything
   in `bot/`, or Trading Intelligence's own `services/`/`adapters/`" and
   "does not call into that product's services directly." This is the
   primary reason, not a secondary concern — the other two below are
   consequences of trying to work around it, not separate defects.
2. **The identity check does not generalize.** `workspace_id ==
   "trading_intelligence.decision_center"` is a single hardcoded string
   comparison, correct for exactly one workspace. As production code, it
   would need to grow into a lookup covering every workspace of every
   product — either an ever-growing conditional chain (which is, in effect,
   Option A below, written informally) or some other real lookup mechanism
   (Options B/C). The test doesn't need to solve this generally because it
   only proves one path once; production code inherently would.
3. **The test's data sources are fakes by design, and that's independent of
   the composition question.** `InMemoryProjectionRepository` and the fake
   `AuthenticationProvider`/`EntitlementChecker` implementations exist
   because no real backend exists yet (`ADR-004`) and no real identity
   provider exists yet (`ADR-003`) — not because of anything about workspace
   activation specifically. Even a perfect activation mechanism would still
   have nothing real to activate against today. This document does not
   address that gap; it is listed here only so it isn't mistaken for a
   defect of the three options in Section 3.

## 3. Options

### Option A: Platform Directly Creates Product Experiences

The platform imports and constructs each product's controller directly —
literally the current test pattern (Section 1), promoted to production
code.

- **Ownership:** blurred. Platform would need to know *how* to build a
  `DecisionCenterController`, a future `RiskController`, a future Wealth
  Intelligence controller, etc. — construction knowledge that
  `AARA_WORKSPACE_ENTRY_ARCHITECTURE.md` Section 3 already assigns to
  products, not the platform.
- **Dependency direction:** wrong. Platform → Product, a direct import of
  concrete product classes. This is the one property every other document
  in this series has already established as disqualifying —
  `AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 4's rule exists specifically
  to prevent this.
- **Impact on multiple products:** does not scale. Every new product or
  workspace requires a platform-code change (a new import, a new branch),
  coupling the platform's release cadence to every product team's feature
  work — the opposite of the isolation `ProductRegistry`/`WorkspaceRegistry`
  already achieve today.
- **Rollback difficulty:** low to revert technically (undo the platform
  change), but high in blast radius while live — a bug in one product's
  construction logic lives inside shared platform code, risking other
  products' workspace activation in the same deploy.

### Option B: Products Expose Workspace Entry Contracts

Each product defines its own entry-point implementation of a
platform-defined abstract contract (an interface, following the same shape
as `DecisionSource`/`AuthenticationProvider`/`ProjectionRepository`
elsewhere in this codebase) — the platform depends on the contract, never
on any product's concrete class.

- **Ownership:** clean split — platform owns the abstract contract shape;
  each product owns its own implementation entirely. Matches
  `AARA_WORKSPACE_ENTRY_ARCHITECTURE.md` Section 3's "product-owned" option
  exactly.
- **Dependency direction:** correct — platform depends on an interface;
  products implement it. No concrete product import from platform code, the
  same inversion this codebase already uses for every other cross-boundary
  interface.
- **Impact on multiple products:** scales well for the *shape* of what gets
  called — a new product implements the same interface independently, no
  platform code change needed for the interface itself. **Real, honest
  limitation:** Option B alone does not solve *discovery* — something still
  has to hand the platform a specific product's contract implementation
  without the platform importing it directly. Left unaddressed, Option B
  converges into needing Option C (or an equivalent) anyway.
- **Rollback difficulty:** moderate, and grows over time. Reverting or
  changing the contract's shape once multiple products implement it is a
  breaking change that ripples to every implementer — a cost the
  `DecisionSource`/`ProjectionRepository` interfaces in this codebase have
  so far avoided only because they've stayed frozen since first written.

### Option C: Workspace Activation Registry

A platform-owned registry, structurally parallel to `ProductRegistry`/
`WorkspaceRegistry`, mapping `workspace_id` → a registered constructor or
callable. Each product registers its own entry point (self-registration at
startup, or a static mapping — `AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md`
Section 7's already-open "static vs. dynamic" question applies identically
here, not resolved by this document either).

- **Ownership:** the cleanest three-way split of the three options — platform
  owns the registry mechanism itself (precedented: identical shape to
  `ProductRegistry`/`WorkspaceRegistry`, already built and tested twice in
  this codebase); each product owns exactly what it registers.
- **Dependency direction:** correct, and already a *proven* pattern in this
  exact codebase, not a new one — `ProductRegistry`/`WorkspaceRegistry`'s
  registry classes are already independently tested to never import product
  internals (`test_product_registry_module_does_not_import_product_internals`).
  Option C would extend that same, already-enforced pattern one level
  further (from registering descriptive data to registering an activation
  callable), rather than invent a new mechanism.
- **Impact on multiple products:** scales the same way `ProductRegistry`/
  `WorkspaceRegistry` already do — each product registers itself once;
  the registry's own code needs no change per new product. Directly solves
  the scaling weakness Option A has and the discovery gap Option B has on
  its own.
- **Rollback difficulty:** low. A registry is additive infrastructure —
  removing one product's registration doesn't affect another's (isolated
  blast radius), unlike Option A's shared-module coupling or Option B's
  cross-implementer contract-change risk.

## Observation, Not a Decision

Option C's shape already matches a pattern this codebase has independently
built and proven twice (`ProductRegistry`, `WorkspaceRegistry`) — that is a
structural observation about precedent, not a recommendation adopted by
this document. Option B is not a rejected alternative so much as a
necessary *part* of Option C (something must define what gets registered);
presenting them as three independent, mutually exclusive choices would
overstate how separable B and C actually are. **No option is chosen here.**
Consistent with `ADR-003`/`ADR-004`'s existing deferral pattern, an actual
choice — if and when a second workspace or product makes one necessary,
per `AARA_WORKSPACE_ENTRY_ARCHITECTURE.md` Section 4's stated revisit
trigger — belongs in a future, dedicated ADR, not this analysis document.

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `applications/platform/`,
`sentinel_engine/`, `ledger/`, `bot/`, `dashboard/`, or any other protected
path was created or modified. No resolver, router, or factory was created.
No existing architecture was changed. This document only reads and cites
existing code and prior documentation.
