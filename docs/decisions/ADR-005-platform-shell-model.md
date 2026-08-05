# ADR-005: Platform Shell Model

**Status:** Accepted — Analysis and Recommendation, No Refactoring Performed
**Date:** 2026-08-05

**Scope note:** Documentation only. No code was renamed, merged, or
refactored to produce this ADR. `applications/platform/`, `bot/`,
`dashboard/`, `scheduler/`, `.github/workflows/`, `database/`, `ledger/`,
`sentinel_engine/` all untouched, confirmed via `git status` before and
after.

**Authority:** `AARA_PLATFORM_SHELL_ARCHITECTURE.md`,
`AARA_NAVIGATION_MODEL_ARCHITECTURE.md`,
`AARA_WORKSPACE_REGISTRATION_ARCHITECTURE.md`,
`AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md`.

---

## 1. Problem Statement

Three pairs of objects now exist in `applications/platform/`, built across
three separate, independently-authorized implementation phases:

- `ShellBuilder` / `ShellModel` (Phase 4E)
- `NavigationBuilder` / `NavigationModel` (Phase 4H)
- `ShellPresenter` / `PlatformShellView` (Phase 4I)

`ShellBuilder` and `NavigationBuilder` independently duplicate the same core
logic — get the current user, then filter all registered products by
entitlement — before diverging: `ShellBuilder` stops at the product level;
`NavigationBuilder` goes one level further, also pulling each entitled
product's workspaces. Verified directly (not assumed): nothing in this
codebase wires `ShellBuilder`'s output into `NavigationBuilder`, or vice
versa — they are two independent, parallel pipelines built from overlapping
inputs.

**Why this ambiguity exists:** the platform layer was built incrementally, one
authorized phase at a time (Phase 4E, then 4H, then 4I), each adding the
smallest testable next piece without a unifying pass across all of them. That
is the same incremental discipline used throughout this entire migration —
this is an expected byproduct of it, not a mistake, and it is exactly what
this ADR now resolves with a dedicated architectural pass.

## 2. Current Architecture

Described exactly as verified in code today — no future behavior assumed:

- **`ShellBuilder(auth_provider, entitlement_checker, product_registry).build()`**
  → `ShellModel(current_user, visible_products: List[Product],
  available_workspaces: List[str])`. `available_workspaces` is a plain list
  of visible products' `product_id` values — not workspace-level data.
- **`NavigationBuilder(product_registry, workspace_registry,
  entitlement_checker, auth_provider).build()`** → `NavigationModel(current_user,
  items: List[NavigationItem])`. For each product the user is entitled to,
  fetches that product's workspaces from `WorkspaceRegistry` and emits one
  `NavigationItem` per workspace.
- **`ShellPresenter().present(navigation_model)`** → `PlatformShellView(current_user,
  navigation: List[NavigationItem])`. A direct field transform of
  `NavigationModel`.

**Verified via direct code search, not inferred:**
- `ShellModel` is referenced only by `shell_builder.py` (which produces it)
  and its own module. **Nothing consumes it further.** Despite being the
  first of the three pairs built, it is currently a dead end.
- `NavigationModel` is referenced by `navigation_builder.py` (produces it)
  and by `shell_presenter.py`/`platform_shell_view.py` (consumes it). It is
  the only one of the two builders' outputs that currently reaches a
  presentation layer.
- No code path connects `ShellBuilder` and `NavigationBuilder` to each other.

## 3. Responsibilities

| Component | Responsibility | Category |
|---|---|---|
| `ShellBuilder` | Determine who the user is and which products they can access at all — coarse, product-level authorization | Platform context |
| `ShellModel` | The platform context data: current user + visible products | Platform context |
| `NavigationBuilder` | Compose platform context into a concrete, orderable, workspace-level navigation structure | Navigation composition |
| `NavigationModel` | The navigation composition data: current user + ordered `NavigationItem`s | Navigation composition |
| `ShellPresenter` | Transform navigation composition into a shape ready for actual UI consumption | Presentation model |
| `PlatformShellView` | The presentation data: current user + navigation items, UI-facing | Presentation model |

## 4. Recommended Architecture

- **`ShellModel` remains a platform context model** — "what can this user
  touch," not "how to navigate it."
- **`NavigationModel` remains the navigation domain model** — the
  workspace-level composed structure, a refinement of platform context.
- **`PlatformShellView` remains the presentation model** — the final,
  UI-facing shape.

**Reasoning:** each already has a genuinely distinct *shape* (product list vs.
workspace-item list vs. presentation-ready list), even though their
*builders* currently duplicate logic. The redundancy lives in how the models
are built, not in the models themselves. Collapsing the models would remove a
real distinction; fixing how they're built would not. This also matches the
pattern used everywhere else in this migration — `sentinel_engine` keeps
`Decision`, `Event`, and `DecisionProjection` as separate, narrow types
connected by explicit transformations rather than one combined object, and
this platform layer should follow the same precedent.

## 5. Builder Relationships

**Intended long-term conceptual flow — not current implementation:**

```
Authentication
    ↓
ShellBuilder
    ↓
ShellModel
    ↓
NavigationBuilder
    ↓
NavigationModel
    ↓
ShellPresenter
    ↓
PlatformShellView
```

This means `NavigationBuilder` would eventually consume `ShellModel` (the
already-computed user + visible products) rather than independently
re-deriving them from `AuthenticationProvider`/`EntitlementChecker`/
`ProductRegistry`, as it does today. **This is not current behavior.** Today,
`NavigationBuilder`'s constructor takes all four raw abstractions directly and
has no dependency on `ShellBuilder` or `ShellModel` at all. Section 8 states
when changing this would become appropriate; this ADR does not make that
change.

## 6. Alternatives Considered

**Option A — Keep all three layers with distinct responsibilities,
sequence them per Section 5.**
- *Advantages:* matches the established pattern of narrow, single-purpose
  types connected by explicit transforms (`sentinel_engine`'s own layering);
  each layer already independently tested (93 tests today, one concern per
  layer); a second product (Wealth Intelligence) can reuse the platform
  context layer unchanged and run its own navigation composition on top.
- *Disadvantages:* three models to keep conceptually aligned; realizing the
  Section 5 flow requires a real, if modest, future change to
  `NavigationBuilder`'s constructor.

**Option B — Merge `ShellModel` into `NavigationModel`.**
- *Advantages:* eliminates the duplicated "who can see what products"
  computation; one model instead of two.
- *Disadvantages:* conflates a coarse, stable, product-level authorization
  concept with a finer, workspace-level structure more likely to change as UI
  needs evolve. A future consumer that only needs "is this user entitled to
  this product" (not full navigation) would be forced to depend on the
  heavier `NavigationModel`. Deletes the "platform context" concept entirely
  rather than clarifying it.

**Option C — Replace everything with one `PlatformContext` object.**
- *Advantages:* maximal simplicity; duplication becomes structurally
  impossible.
- *Disadvantages:* the most disruptive option. Collapses context, navigation
  composition, and presentation into one object, discarding the
  separation-of-concerns principle this migration has followed everywhere
  else — `sentinel_engine`'s own domain/events/evidence/governance/
  projections/repositories/services split, and the "products own
  presentation, platform owns composition" boundary already established in
  prior documents. Would also entangle authorization logic with
  presentation-shaping logic in one class. Highest testability cost — one
  object's tests would need to cover all three concerns together, losing the
  current ability (93 tests) to test each in isolation.

## 7. Decision

**Recommend Option A.**

- **Separation of concerns:** matches every other layered design already
  built in this migration; nothing elsewhere in this codebase collapses
  context/composition/presentation into one type.
- **Testability:** already proven — 93 tests exist today, each exercising one
  layer against fakes. Option A preserves this; B and C would require
  broader, more entangled test setups to cover merged concerns.
- **Future multi-product expansion:** `ShellBuilder`/`ShellModel`'s
  product-level context is exactly the layer a second product would reuse
  unchanged; `NavigationBuilder`'s workspace-level composition runs
  per-product on top of it. Option A's layering directly supports this; B and
  C blur the boundary a second product would need to plug into.
- **Maintainability:** sequencing the builders (Section 5) removes the
  duplication without destroying the layer boundaries — a smaller, more
  surgical fix than merging models.

**No code is modified by this ADR. No immediate refactoring is required.**

## 8. Future Refactoring Guidance

Refactoring toward the Section 5 flow becomes appropriate when:

- **A real UI actually consumes `PlatformShellView`.** At that point the
  actual data-flow requirements will be concretely known, and
  `NavigationBuilder` can be safely changed to accept `ShellModel` as input
  instead of re-deriving it.
- **`ShellBuilder` and `NavigationBuilder`'s duplicated logic causes a real
  bug** — e.g., the two independent implementations drift and disagree about
  which products a user can see. That divergence, if it happens, is the
  practical trigger — not a calendar date.
- **A second product (Wealth Intelligence) is implemented** and needs to
  reuse this platform layer. That is the real stress test of whether the
  current layering holds up; refactoring should follow evidence from that
  attempt, not precede it.

**No refactoring is performed by this ADR.** It records an analysis and a
recommendation for when the conditions above are met — not an action taken
now.
