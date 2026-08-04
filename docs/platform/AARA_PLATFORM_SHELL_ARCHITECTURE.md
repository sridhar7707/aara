# AARA Platform Shell Architecture

**Status:** Shell architecture — Phase 4B. Documentation only. No UI, routing,
or authentication code was implemented. `bot/`, `dashboard/`, `scheduler/`,
`.github/workflows/`, `database/`, `ledger/`, `sentinel_engine/` untouched,
confirmed via `git status` before and after.

**Authority:** ADR-003, `AARA_PLATFORM_USER_EXPERIENCE.md`,
`AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md`,
`AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md`.

---

## 1. Shell Responsibilities

- **Global navigation** — persistent chrome across all workspaces, unchanged
  from `AARA_PLATFORM_USER_EXPERIENCE.md` Section 1.
- **Product switching** — the entitlement-filtered switcher, unchanged from
  that document's Section 2.
- **User menu** — corresponds to `AARA_PLATFORM_USER_EXPERIENCE.md`'s
  "Account/Identity menu (concept only)."
- **Workspace selection** — routing into whichever product workspace the user
  chooses.
- **Notifications** — **new in this document.** No prior document
  (`AARA_PLATFORM_USER_EXPERIENCE.md`, `AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md`)
  scoped a notification system. Named here as a shell responsibility per this
  task's request; no design exists for it — flagged as needing its own future
  design, not detailed further.
- **Settings — a naming collision worth resolving now, not later:** Trading
  Intelligence's own workspace already has a "Settings" screen
  (`AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` Section 5,
  `dashboard/components/settings.py`) — product-specific configuration
  (trading parameters, thresholds). Shell-level "Settings" here means
  something different: account/platform-wide preferences (notification
  preferences, profile). Both can coexist, but they are not the same thing,
  and neither should be assumed to satisfy the other.

## 2. Navigation Model

```
AARA Shell

    Trading Intelligence
        Decision Center
        Portfolio
        Risk

    Wealth Intelligence
        Overview
        Allocation
        Insights

    Admin
        Governance
        Audit
        System
```

**This is a curated subset, not the full screen list for either product —
stated explicitly, not left implicit:**

- Trading Intelligence's full workspace (`AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`
  Section 5) has six screens: Morning Brief, Decision Center, Portfolio
  Intelligence, Risk Intelligence, Performance & Learning, Settings. Only
  three appear here (Decision Center, Portfolio, Risk — shortened names).
  Morning Brief, Performance & Learning, and Settings are omitted from this
  top-level tree, not eliminated from the product.
- Wealth Intelligence's full screen set (`AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`
  Section 10) has six screens: Wealth Home, Wealth X-Ray, Wealth Map, Insight
  Detail, Wealth Chronicle, Monthly Wealth Review. Only three appear here
  (Overview → Wealth Home, Allocation → Wealth Map, Insights → Insight Detail,
  per the mapping already established in `AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md`
  Section 4). Wealth X-Ray, Wealth Chronicle, and Monthly Wealth Review are
  omitted here, not eliminated.
- **Admin's "System" repeats a finding already on record, not a new one:**
  `AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md` Section 5 already found no
  existing workspace or component named "System Administration" anywhere in
  `sentinel/frontend/` or `dashboard/components/`, and that same document's
  "Feature Discovery vs. Feature Invention Principle" states missing
  capabilities "are recorded as product decisions, not created by assumption."
  Applying that principle here: "Governance" and "Audit" have real grounding
  (`sentinel/frontend/components/governance_badge.py`, `audit_fingerprint.py`,
  `chain_timeline.py`, and the `decision_history`/`decision_review`/
  `governance_review`/`governance_status` workspaces). **"System" still does
  not.** It appears in this tree because it was requested, not because a
  capability now backs it — the same open item, not a new resolution of it.

## 3. Workspace Isolation

- **Products own their screens** — Trading Intelligence and Wealth
  Intelligence each own their own screen implementations; the shell does not
  render product content itself.
- **Shell owns navigation** — the switcher, the menu, routing between
  workspaces; the shell does not own product logic.
- **Identity owns access decisions** — *which* workspaces a user may reach is
  decided by identity/entitlements (`AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md`),
  not by the shell itself. The shell consults identity; it does not make
  access policy.

Three distinct owners, no overlap: shell (navigation), products (screens),
identity (access policy).

## 4. Dependency Rules

**Shell may know:**
- Identity (the abstraction from `AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md`
  Phase 1 — not yet built)
- Entitlements (which products/workspaces a user's role grants — the "what
  users can see" table, not enforcement logic)
- Products (which products exist, their names, their workspace entry points —
  a registry-level knowledge, not their internals)

**Shell must not know:**
- Trading logic (anything in `bot/`, or Trading Intelligence's own
  `services/`/`adapters/`)
- Wealth calculations (any future Wealth Intelligence analysis logic)
- Sentinel internals (`sentinel_engine` contracts, `ProjectionRepository`, etc.)

**This is a stricter boundary than the UI layer already built.** Trading
Intelligence's own `ui/` is allowed to depend on
`applications.trading_intelligence.services` (per its README's dependency
rule, enforced by `test_screen_components_do_not_import_services_directly`
via the controller exception). The shell sits one level higher and should not
depend on any single product's service layer at all — only on the
identity/entitlement/registry knowledge above. It routes to a product's
workspace; it does not call into that product's services directly.

## 5. Implementation Phases

**Phase 1: Shell interfaces.** Abstract navigation/registry concepts (e.g. a
product registry listing available workspaces, an entitlement-check
interface) — same "interfaces first, no backend" pattern already used for
`DecisionSource` and planned for identity (`AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md`
Phase 1).

**Phase 2: Navigation prototype.** A mock navigation tree (Section 2, with
hardcoded/mock entitlements) — the shell-level equivalent of Decision
Center's own Phase 1 mock UI. No real identity wiring.

**Phase 3: Identity integration.** Wire the shell to a real identity/entitlement
implementation, once `AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md`'s own
Phase 1-2 exist. Blocked on that document's phases, not just this one's.

**Phase 4: Product onboarding.** Connect each product's real workspace entry
point into the shell — Trading Intelligence's `applications/trading_intelligence/ui/decision_center/`
first (already exists as a mock prototype), future Wealth Intelligence UI
after.

## 6. Open Decisions

Not resolved by this document:

- **Frontend framework** — no technology choice made anywhere in this
  migration for a real (non-mock) UI.
- **Authentication provider** — still open per
  `AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md` Section 4 (Google OAuth /
  auth provider / internal service).
- **Tenant model** — still open per that same document's Section 1
  (organization/tenant marked future, not designed).
- **Deployment architecture** — not discussed in any prior document in this
  migration; genuinely new open territory, not a restatement of an existing
  gap.

---

## Constraints Confirmed

No UI, routing, or authentication code was implemented. No protected path was
touched.
