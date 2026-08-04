# AARA Platform User Experience

**Status:** Design concept — Phase 3 (Product Development Planning), first
objective. Documentation only. No UI was built, no `dashboard/` file was touched,
no authentication/authorization code exists for anything described here.

**Constraints honored:** ADR-002 (`dashboard/` untouched — confirmed via `git
status` before and after), ADR-003 (roles described here are UX/product concepts,
not an authentication implementation — no schema, no middleware, no user
database), ADR-004 (no ledger backend or storage-adapter implications).

**Grounds itself in:** `AARA_ARCHITECTURE_AUTHORITY.md`'s Product Model and
Terminology, `ADR-003`'s three roles, `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`'s
existing screen list, `TRADING_INTELLIGENCE_BOUNDARY.md`'s responsibilities, and
`CODEBASE_MIGRATION_MATRIX.md`'s `dashboard/` split (Trading UI →
`applications/trading_intelligence/ui/`; Sentinel/governance UI →
`sentinel_engine/admin_ui/`) — the model ADR-001 established as authoritative.
Does not invent new product scope beyond what those documents already define.

---

## 1. AARA Platform Shell

A single outer navigation frame that every authenticated user lands in, regardless
of which products they can access. Its job is orientation and switching, not
product-specific functionality — it doesn't know about trading logic or wealth
analysis, only about which workspaces exist and which ones the current user's
entitlements (per ADR-003) permit.

```
AARA Platform Shell
 |
 +-- Product Switcher
 +-- Active Workspace (Trading Intelligence | Wealth Intelligence | Platform Admin)
 +-- Account/Identity menu (concept only — no implementation, per ADR-003)
```

Today, no such shell exists. The current `dashboard/` (protected, unchanged) is a
single Gradio application that implements something close to a Trading
Intelligence workspace directly, with no product-switching concept at all — this
section describes a future frame, not a redesign of what exists.

## 2. Product Switcher

A UI element (concept, not a component spec) that lists only the workspaces a
user's role entitles them to, per ADR-003's role table:

| Role | Sees in switcher |
|---|---|
| Trading Intelligence User | Trading Intelligence workspace only |
| Wealth Intelligence User | Wealth Intelligence workspace only |
| AARA Super User / Platform Administrator | Trading Intelligence, Wealth Intelligence, Platform Admin |

A single-product user never sees a switcher with only one option rendered as a
dead end — for them the shell can route directly into their one workspace. The
switcher only becomes visually meaningful once a user has 2+ entitlements, which
today applies to nobody, since no identity/entitlement system exists yet.

## 3. Trading Intelligence Workspace

Represents Product #1, per `TRADING_INTELLIGENCE_BOUNDARY.md`'s Responsibilities:
signal generation, strategy evaluation, portfolio decisions, capital management,
risk management, execution orchestration.

**Today:** the existing `dashboard/` (protected under ADR-002, unchanged by this
document) is the de facto implementation — its ~30 components (overview,
portfolio, positions, signals, risk, capital, decision, history, trade journal,
attribution, symbol detail, simulator, rebalance, settings, and more) already
cover most of this workspace's likely surface, just without the platform
shell/product-switcher frame around them, and tightly coupled to `bot/`
internals (see `DASHBOARD_DEPENDENCY_REDUCTION_PLAN.md`).

**Target (not committed, not scheduled):** the same functional surface,
eventually reachable through the platform shell as one workspace among several,
sourced through `sentinel_engine`-mediated data (per
`TRADING_INTELLIGENCE_EVENT_MODEL.md`'s target interface) once ledger ownership
is decided (ADR-004) — not before.

## 4. Wealth Intelligence Workspace

Represents Product #2, per `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`'s
already-defined screens — this document does not redefine them, only places them
inside the platform shell concept:

- Wealth Home
- Wealth X-Ray
- Wealth Map
- Insight Detail
- Wealth Chronicle
- Monthly Wealth Review

**Today:** none of this exists in code. `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`
is a product definition with no engine wiring and no UI implementation.

## 5. Admin / Super Role Experience

Represents the AARA Super User / Platform Administrator role from ADR-003:
access to both product workspaces, plus platform administration capabilities.
Conceptually distinct from either product workspace — closer to
`CODEBASE_MIGRATION_MATRIX.md`'s `sentinel_engine/admin_ui/` destination for
"governance views, audit history, decision chains, evidence views" than to either
product's own UI.

Concept surface (not designed in detail here, not implemented):
- Cross-product oversight (both workspaces, unfiltered)
- Governance/audit views — decision chains, evidence, policy state (drawing on
  `sentinel_engine.governance`/`evidence`/`ledger` contracts once a backend
  exists, per ADR-004)
- Platform administration — product entitlement visibility (not management;
  ADR-003 has no authorization middleware yet to manage anything through)

## 6. Navigation Hierarchy

```
AARA Platform Shell
 |
 +-- Product Switcher
 |
 +-- Trading Intelligence Workspace   (Trading Intelligence User, Super User)
 |     +-- [today: existing dashboard/ component surface]
 |
 +-- Wealth Intelligence Workspace    (Wealth Intelligence User, Super User)
 |     +-- Wealth Home
 |     +-- Wealth X-Ray
 |     +-- Wealth Map
 |     +-- Insight Detail
 |     +-- Wealth Chronicle
 |     +-- Monthly Wealth Review
 |
 +-- Platform Admin                   (Super User only)
       +-- Governance / audit views
       +-- Cross-product oversight
```

## 7. Future Multi-Product Expansion

Per `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`'s Long-Term Expansion
section (Aara CFO, Aara Tax, Aara Estate, Aara Retirement Intelligence), the
shell/switcher/workspace pattern is designed to add products, not just host two:

```
AARA Platform Shell
 |
 +-- Product Switcher
       +-- Trading Intelligence
       +-- Wealth Intelligence
       +-- (future) CFO Intelligence
       +-- (future) Tax Intelligence
       +-- (future) Estate Intelligence
       +-- (future) Retirement Intelligence
```

Each future product is expected to follow the same shape established here: its
own workspace, its own entitlement role (per ADR-003's pattern), consuming the
shared Sentinel Intelligence Engine rather than each other.

---

## Explicitly Out of Scope for This Document

- No component-level UI spec (colors, layout, framework choice).
- No authentication/authorization implementation (ADR-003 remains deferred).
- No `dashboard/` code changes or migration timeline (ADR-002 remains enforced).
- No ledger/backend wiring implications (ADR-004 remains deferred).
- Not a commitment to build any of this on any timeline — a target shape only.
