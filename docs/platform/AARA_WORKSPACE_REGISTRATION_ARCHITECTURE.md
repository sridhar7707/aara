# AARA Workspace Registration Architecture

**Status:** Registration architecture — Phase 4F. Documentation only. No code
was changed. `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`,
`database/`, `ledger/`, `sentinel_engine/` untouched, confirmed via `git
status` before and after.

**Authority:** `AARA_PLATFORM_SHELL_ARCHITECTURE.md`,
`AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md`,
`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`,
`AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`.

---

## 1. Purpose

`Product` (built in Phase 4D — `product_id`, `name`, `entitlement_required`,
`description`, `status`) is coarse-grained: one entry per product. But
`AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md`'s nested nav tree needs finer
granularity — which *screens* exist within a product (Decision Center,
Portfolio, Risk...) — without the shell importing that product's UI code, per
`AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 4's rule that the shell "must
not know trading logic." `Workspace` is the missing middle layer: coarser
than a screen's actual implementation, finer than a product's single registry
entry. It is why `Product` deliberately excludes `workspace_routes`
(Phase 4D) — that responsibility belongs here, one level down, not folded
into the product descriptor itself.

## 2. Ownership Boundaries

**Platform owns:**
- Workspace discovery — a future `WorkspaceRegistry`, analogous to
  `ProductRegistry` (Phase 4D) but at workspace granularity. Not built.
- Navigation metadata — display name, description, ordering; enough to
  render a nav tree, not enough to render a screen.
- Entitlement filtering — same `EntitlementChecker` pattern already built
  (Phase 4C/4E), applied per-workspace (see Section 3's open question on
  whether workspace visibility inherits from the product or is independent).

**Products own:**
- Screens — e.g. `applications/trading_intelligence/ui/decision_center/`
  (real, built).
- Business logic — `services/`, `adapters/` (product-internal).
- Data — each product's own contracts/projections.
- UI implementation — the actual rendering, wherever a frontend framework
  eventually attaches (still undecided, Section 7).

Unchanged from `AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md` Section 3, applied
one layer down.

## 3. Workspace Descriptor Model

Future metadata — **not implemented**:

| Field | Purpose |
|---|---|
| `workspace_id` | Unique identifier, e.g. `trading_intelligence.decision_center` |
| `product_id` | References the owning product's `product_id` — a plain string link, not an import, matching how `EntitlementChecker` already references products by id rather than by type |
| `display_name` | e.g. "Decision Center" — for the shell's nav rendering |
| `description` | Short text, not a full screen spec |
| `route`/`key` | A symbolic identifier only — **not a real, implemented route**. `Product` excluded UI routing entirely (Phase 4D), and this document's own Section 7 leaves frontend routing and React architecture unresolved. This field is a placeholder a real router would eventually consume, not a working route today. |
| `visibility` | Entitlement-driven, same shape as `EntitlementChecker.has_access()`. **Open question, not resolved here:** does a workspace's visibility always inherit from its parent product's entitlement, or can a workspace have its own, finer-grained entitlement independent of the product's? Both are plausible; neither is decided. |
| `ordering` | A sort key for consistent nav rendering — no vocabulary or numbering scheme decided. |

## 4. Registration Flow

```
Product Descriptor
   (e.g. TRADING_INTELLIGENCE_PRODUCT -- real, applications/trading_intelligence/product.py)
        |
        v
Workspace Descriptors
   (Section 3's model -- not implemented anywhere)
        |
        v
Platform Shell
   (ShellModel/ShellBuilder -- real, built in Phase 4E, but only discovers
    Products today; would need extending to also discover Workspaces --
    not done, documentation only)
        |
        v
Future UI Navigation
   (does not exist -- no frontend framework chosen)
```

## 5. Trading Intelligence Example

All six screens from `AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`
Section 5 — no screen invented beyond that list:

| Workspace (illustrative, not implemented) | Real UI status |
|---|---|
| `trading_intelligence.decision_center` — "Decision Center" | **Only one with real code:** `applications/trading_intelligence/ui/decision_center/` (`screen.py`, `mock_data.py`, `controller.py`) |
| `trading_intelligence.morning_brief` — "Morning Brief" | No `applications/trading_intelligence/ui/` implementation; `dashboard/components/brief.py` is the current, separate `dashboard/` implementation |
| `trading_intelligence.portfolio` — "Portfolio" | No `applications/trading_intelligence/ui/` implementation; `dashboard/components/portfolio.py` is current |
| `trading_intelligence.risk` — "Risk" | No `applications/trading_intelligence/ui/` implementation; `dashboard/components/risk.py` is current |
| `trading_intelligence.performance` — "Performance" | No `applications/trading_intelligence/ui/` implementation; `dashboard/components/attribution.py` etc. are current |
| `trading_intelligence.settings` — "Settings" | No `applications/trading_intelligence/ui/` implementation; `dashboard/components/settings.py` is current |

No descriptor object was created for any of these — this table illustrates
the shape Section 3 describes against real, already-documented screens; it
does not implement it.

## 6. Wealth Intelligence Example

Referencing `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` Section 10's
existing six screens only — no new feature created:

- Wealth Home
- Wealth X-Ray
- Wealth Map
- Insight Detail
- Wealth Chronicle
- Monthly Wealth Review

**None of these has any implementation anywhere** — unlike Trading
Intelligence (one of six screens has real code), `applications/wealth_intelligence/`
is an empty directory with zero files. All six would be equally
descriptor-only if this model were implemented.

## 7. Open Decisions

Not resolved by this document:

- **Frontend routing** — restates, does not resolve,
  `AARA_PLATFORM_SHELL_ARCHITECTURE.md`'s open "frontend framework" item.
- **React architecture** — a narrower, more specific question than "frontend
  framework": *if* React is chosen, component/routing architecture is a
  separate decision not addressed by anything in this migration.
- **Authentication provider** — restates
  `AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md` Section 4's open item.
- **Deployment model** — restates `AARA_PLATFORM_SHELL_ARCHITECTURE.md`/
  `AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md`'s open item.
- **Plugin system** — restates `AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md`'s
  open "plugin architecture" item, now at workspace granularity too.

---

## Constraints Confirmed

No code was changed. No protected path was touched.
