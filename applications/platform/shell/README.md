# Platform Shell Model

**Status:** Abstract shell state and builder only. No login, no OAuth, no
frontend, no routes, no database.

## What this is

- **`ShellModel`** (`shell_model.py`) — built shell state: `current_user`,
  `visible_products`, `available_workspaces`. `available_workspaces` is the
  visible products' `product_id` list only, not real routes — `Product` has
  no `workspace_routes` field (deliberately excluded from the descriptor
  model, per `docs/platform/AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md`), and
  building real routes is out of scope for this step.
- **`ShellBuilder`** (`shell_builder.py`) — constructor-injects
  `AuthenticationProvider`, `EntitlementChecker`, and `ProductRegistry`
  (all interfaces, no concrete implementation of any of them exists anywhere
  in this codebase). `build()` gets the current user, lists all registered
  products, filters to only the ones the user is entitled to, and returns a
  `ShellModel`. If no user is authenticated, the result has no visible
  products — there's nothing to entitlement-check against. **Still separate
  from `NavigationBuilder`** (`navigation/navigation_builder.py`, Phase 4H) —
  `ShellBuilder` does not know about `WorkspaceRegistry` and produces a
  coarser model than `NavigationModel`. Not unified; see below.
- **`PlatformShellView`** (`platform_shell_view.py`) — presentation model:
  `current_user`, `navigation: List[NavigationItem]`. `navigation` holds a
  `NavigationModel`'s items directly, not the whole `NavigationModel` — kept
  as a separate field from `current_user` rather than nested, to avoid
  duplicating `current_user` inside two places.
- **`ShellPresenter`** (`shell_presenter.py`) — `present(NavigationModel) ->
  PlatformShellView`. A direct field transformation today; kept as its own
  class so future view-specific shaping has a home without touching
  `NavigationBuilder`'s own responsibility.

**Two parallel, unmerged pairs now exist in this package:**
`ShellBuilder`/`ShellModel` (product-level, Phase 4E) and
`NavigationBuilder`/`NavigationModel`/`ShellPresenter`/`PlatformShellView`
(workspace-level, Phases 4H-4I). Nothing in this codebase currently decides
whether `ShellModel` is superseded by `PlatformShellView`, kept as a
lighter-weight alternative, or something else. Not resolved here.

## Dependency rules

Same as the rest of `applications/platform/`: may know users/roles/
entitlements/products; must not know Trading Intelligence services, Wealth
Intelligence services, Sentinel Engine, `bot`, or `dashboard`. Checked in
`../tests/test_platform_structure.py`.
