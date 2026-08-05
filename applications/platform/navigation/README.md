# Platform Navigation Contracts

**Status:** Abstract contracts only. No builder, no router, no UI, no URL
paths.

## What this is

- **`NavigationItem`** (`navigation_item.py`) — a single composed navigation
  entry: `product_id`, `workspace_id`, `label`, `order`, `visibility`. Per
  `docs/platform/AARA_NAVIGATION_MODEL_ARCHITECTURE.md` Section 4 — the
  shell's intended output, built from `Product` + `Workspace` data.
- **`NavigationModel`** (`navigation_model.py`) — `current_user` +
  `items: List[NavigationItem]`.

- **`NavigationBuilder`** (`navigation_builder.py`) — constructor-injects
  `ProductRegistry`, `WorkspaceRegistry`, `EntitlementChecker`,
  `AuthenticationProvider` (all interfaces, no concrete implementation of any
  of them exists anywhere). `build()` gets the current user, filters
  registered products by entitlement, and composes a `NavigationItem` per
  workspace of each entitled product.

**Resolves a previously-open question, not just documents it:**
`EntitlementChecker.has_access()` only takes a `product_id`, not a
`workspace_id` — so a product's workspaces are all-or-nothing visible
together. Whether workspace visibility inherits from the product or can be
independent (`AARA_WORKSPACE_REGISTRATION_ARCHITECTURE.md` Section 3,
`AARA_NAVIGATION_MODEL_ARCHITECTURE.md` Section 3) is now answered by this
implementation: it inherits, because no other interface exists to check
otherwise.

**Still separate from `ShellBuilder`** (Phase 4E) — the two builders are not
unified. `ShellBuilder` still only produces a `ShellModel` with a plain
product-id list; `NavigationBuilder` is the newer, finer-grained path. Whether
they should be merged is not addressed here.

## Dependency rules

Same as the rest of `applications/platform/`: may know users/roles/
entitlements/products/workspaces; must not know Trading Intelligence
services, Wealth Intelligence services, Sentinel Engine, `bot`, or
`dashboard`. Checked in `../tests/test_platform_structure.py`.
