# Platform Workspace Registration

**Status:** Abstract contracts only. No frontend routes, no React components,
no UI import, no database. No Trading Intelligence or Wealth Intelligence
workspace instance exists anywhere in this codebase yet.

## What this is

- **`Workspace`** (`workspace.py`) — `workspace_id`, `product_id`,
  `display_name`, `visibility` (required); `description`, `order` (default).
  Six fields, deliberately fewer than the seven-field model in
  `docs/platform/AARA_WORKSPACE_REGISTRATION_ARCHITECTURE.md` Section 3 —
  `route`/`key` is omitted, since frontend routing remains an open decision
  and adding it now would mean inventing routing ahead of that choice.
- **`WorkspaceRegistry`** (`workspace_registry.py`) — `register_workspace()`
  / `list_workspaces(product_id)`, analogous to `ProductRegistry` (Phase 4D)
  but scoped per product. No concrete implementation exists.

## Dependency rules

Same as the rest of `applications/platform/`: may know users/roles/
entitlements/products/workspaces; must not know Trading Intelligence
services, Wealth Intelligence services, Sentinel Engine, `bot`, or
`dashboard`. Checked in `../tests/test_platform_structure.py`.
