# AARA Navigation Model Architecture

**Status:** Navigation architecture — Phase 4G. Documentation only. No code
was changed. `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`,
`database/`, `ledger/`, `sentinel_engine/` untouched, confirmed via `git
status` before and after.

**Authority:** `AARA_PLATFORM_SHELL_ARCHITECTURE.md`,
`AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md`,
`AARA_WORKSPACE_REGISTRATION_ARCHITECTURE.md`.

---

## 1. Purpose

Navigation — what's visible, in what order, gated by what entitlement — is a
platform concern, separate from how any product renders its own screens. The
platform composes a nav structure from `Product` and `Workspace` data; it
never touches a product's screen implementation to do it (`ui/decision_center/`
remains entirely product-owned, per `AARA_PLATFORM_SHELL_ARCHITECTURE.md`
Section 4's rule that the shell "must not know trading logic"). This document
defines the data shape navigation composition would produce — not the UI that
would eventually render it.

## 2. Navigation Hierarchy

```
Platform
 |
 Product
 |
 Workspace
```

Matches what's already built: `ProductRegistry` (Product level, Phase 4D) and
`WorkspaceRegistry` (Workspace level, scoped by `product_id`, Phase 4F), with
the platform (`ShellBuilder`/`ShellModel`, Phase 4E) composing across both.

## 3. Ownership Boundaries

**Platform owns:**
- Navigation composition — combining `Product` and `Workspace` data into one
  coherent structure.
- Ordering — `Workspace.order`, already a real field (Phase 4F).
- Visibility filtering — `EntitlementChecker`, already built (Phase 4C),
  already used by `ShellBuilder` at the product level (Phase 4E). Whether it
  also applies independently at the workspace level, or whether workspace
  visibility always inherits from the parent product, is **still an open
  question** — `AARA_WORKSPACE_REGISTRATION_ARCHITECTURE.md` Section 3 raised
  it and this document does not resolve it either.

**Products own:**
- Workspace content — e.g. `applications/trading_intelligence/ui/decision_center/`.
- Screen behavior — `DecisionCenterController`'s logic.
- Business logic — `services/`, `adapters/`.

## 4. Navigation Model

Future metadata — **not implemented**. A composed navigation entry, distinct
from both `Product` and `Workspace` (which are registry-level descriptors) —
this is the shell's *output*, built from them:

| Field | Source |
|---|---|
| `product_id` | Pass-through from `Workspace.product_id` |
| `workspace_id` | Pass-through from `Workspace.workspace_id` |
| `label` | Would come from `Workspace.display_name` |
| `order` | Pass-through from `Workspace.order` |
| `visibility` | The resolved visibility decision — not yet defined whether this is the workspace's own `visibility` field, an entitlement-check result, or both (Section 3's open question) |

No dataclass or class was created for this — the table describes an intended
future shape.

## 5. Build Flow

```
Identity
   (AuthenticationProvider.get_current_user() -- real, Phase 4C)
 |
Entitlements
   (EntitlementChecker.has_access() -- real, Phase 4C)
 |
Product Registry
   (ProductRegistry.list_products() -- real, Phase 4D)
 |
Workspace Registry
   (WorkspaceRegistry.list_workspaces(product_id) -- real, Phase 4F)
 |
Navigation Model
   (Section 4 -- not implemented)
```

**Important, not glossed over:** `ShellBuilder` (Phase 4E) implements only
the first three steps — it predates `WorkspaceRegistry`'s existence (built
one phase later, Phase 4F) and has not been extended to consume it. Today,
`ShellBuilder.build()` produces a `ShellModel` with `visible_products` and a
plain `available_workspaces` list of product ids (Phase 4E's own deliberately
minimal design, before workspace-level granularity existed). It does **not**
call `WorkspaceRegistry` and does **not** produce anything resembling
Section 4's Navigation Model. Steps 4-5 above are a target this document
describes; they are not current `ShellBuilder` behavior.

## 6. Trading Intelligence Example

Using the same three-item curated subset as
`AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 2's original nav tree — not the
fuller six-screen list used in `AARA_WORKSPACE_REGISTRATION_ARCHITECTURE.md`
Section 5, stated explicitly rather than silently switching lists:

| Workspace | Implementation status |
|---|---|
| Decision Center | **Real:** `applications/trading_intelligence/ui/decision_center/` (`screen.py`, `mock_data.py`, `controller.py`) |
| Portfolio | Not implemented under `applications/trading_intelligence/ui/`. `dashboard/components/portfolio.py` is the current, separate `dashboard/` implementation. |
| Risk | Not implemented under `applications/trading_intelligence/ui/`. `dashboard/components/risk.py` is current. |

No navigation entries were created for any of these — this table is
illustrative only.

## 7. Open Decisions

Not resolved by this document:

- **Frontend router** — restates `AARA_PLATFORM_SHELL_ARCHITECTURE.md`'s open
  "frontend framework" item.
- **React implementation** — restates
  `AARA_WORKSPACE_REGISTRATION_ARCHITECTURE.md`'s open "React architecture"
  item.
- **URL strategy** — a more specific question than either of the above: even
  once a router is chosen, how `workspace_id` maps to an actual URL path is
  undecided.
- **Mobile navigation** — genuinely new; not raised in any prior document in
  this migration.
- **Permissions hierarchy** — restates Section 3's still-open question:
  whether workspace visibility inherits from product entitlement or can be
  independent.

---

## Constraints Confirmed

No code was changed. No protected path was touched.
