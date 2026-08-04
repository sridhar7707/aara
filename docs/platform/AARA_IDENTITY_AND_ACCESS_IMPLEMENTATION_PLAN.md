# AARA Identity and Access Implementation Plan

**Status:** Implementation plan — Phase 4A. Documentation only. No
authentication code, no database change, no UI implementation. `bot/`,
`dashboard/`, `scheduler/`, `.github/workflows/`, `database/`, `ledger/`,
`sentinel_engine/` untouched, confirmed via `git status` before and after.

**Authority:** ADR-003, `AARA_PLATFORM_USER_EXPERIENCE.md`,
`AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md`,
`AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`,
`AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` — this document plans
ADR-003's implementation; it does not change the requirement ADR-003 already
recorded.

---

## 1. User Identity Model

- **User** — the fundamental identity: a person with credentials and a
  profile. Knows nothing about products or roles itself.
- **Organization/tenant (future)** — not needed today. Both existing product
  definitions target individual, self-directed users (`AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`'s
  "Self-directed investors" target segment; Trading Intelligence's paper
  validation is inherently single-operator today). Multi-tenant/organization
  support is a real future extension, explicitly not designed further here —
  premature to specify before a single-user model exists at all.
- **Product entitlement** — the link between a `User` and a specific product
  (Trading Intelligence, Wealth Intelligence, future products), per ADR-003's
  "Product Entitlements" layer.
- **Role** — determines which capabilities a user has *within* their entitled
  products. Per ADR-003: Trading Intelligence User, Wealth Intelligence User,
  AARA Super User / Platform Administrator.

## 2. Roles

Unchanged from ADR-003:

| Role | Access |
|---|---|
| Trading Intelligence User | Trading Intelligence workspace only |
| Wealth Intelligence User | Wealth Intelligence workspace only |
| AARA Super User / Platform Administrator | All product workspaces, plus governance/admin capabilities |

## 3. Product Access Model

```
User
 |
 v
Role
 |
 v
Entitlement
 |
 v
Workspace
```

**Refinement, stated explicitly:** this is not identical to ADR-003's original
concept diagram (`User -> Identity -> Product Entitlements -> Workspaces ->
Capabilities`). Two changes: `Role` is now explicit between `User` and
`Entitlement` — making clear that entitlements are *derived from* role
assignment, not independently granted — and `Capabilities` is folded into
`Workspace` (workspace access implies its capabilities, rather than being a
separately-modeled final step). Both chains describe the same underlying
requirement; this is a refinement for implementation planning, not a
contradiction of ADR-003, and not a change to the requirement itself.

## 4. Authentication Boundary

Three future options, **none selected**:

- **Google OAuth** — lowest build cost; fits the self-directed-investor target
  profile directly (most individual users already have a Google account); ties
  identity to a third-party account the user doesn't control from AARA's side.
- **Auth provider** (e.g. a managed identity platform) — more flexible
  (multiple login methods, less custom code to maintain) at the cost of a new
  vendor dependency and recurring cost.
- **Internal identity service** — full control, tightest fit with the
  data-privacy principle already established for `sentinel_engine`
  (`SENTINEL_ENGINE_BOUNDARY_AND_API_CONTRACTS.md`'s "Sentinel does not own
  consumer financial data" — an internal service keeps identity data from
  flowing through any third party at all) — at the highest build and
  maintenance cost.

**No implementation is selected by this document.**

## 5. Authorization Rules

**What users can see** (visibility only — not defined here: how this gets
enforced at the backend):

| Role | Sees |
|---|---|
| Trading Intelligence User | Trading Intelligence workspace |
| Wealth Intelligence User | Wealth Intelligence workspace |
| AARA Super User / Platform Administrator | Both product workspaces + Platform Admin/Governance workspace |

This table is unchanged from `AARA_PLATFORM_USER_EXPERIENCE.md`/`AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md`.
**Backend permission enforcement — API-level checks, data-level access
control, session/token validation — is explicitly not defined here.** That is
Phase 3 (Section 6) and requires its own design work this document doesn't do.

## 6. Implementation Phases

**Phase 1: Identity abstraction.** Define `User`/`Role`/`Entitlement`/`Workspace`
as code-level interfaces (framework-independent, no real backend) — the same
pattern already used for `DecisionSource`/`DecisionContract` in
`applications/trading_intelligence/`: an abstraction that can be built and
tested against fakes before any real system exists behind it. Likely lives
outside any single product package (per `CLAUDE_AARA_MIGRATION.md`'s
`shared/authentication`, `shared/users` concept) since identity spans both
Trading Intelligence and Wealth Intelligence — not created by this document,
only noted as a probable future location.

**Phase 2: Authentication integration.** Select and wire one option from
Section 4. Blocked on that selection (Section 7).

**Phase 3: Product entitlement enforcement.** Real backend permission checks
gating workspace access, per Section 5's explicit deferral. Blocked on Phase 2.

**Phase 4: Admin capabilities.** Build out the Super User/Platform
Administrator-specific governance and cross-product features described in
`AARA_PLATFORM_USER_EXPERIENCE.md` Section 5. Blocked on Phases 1-3.

## 7. Explicit Classification

**Can start immediately:**
- Documentation (this document, and Phase 1's interface design).
- Interfaces — `User`/`Role`/`Entitlement`/`Workspace` as abstract, unwired
  code, matching the `DecisionSource`-style pattern already proven in
  `applications/trading_intelligence/`.
- UI routing concepts — which routes/workspaces map to which roles (a design
  question, not an enforcement mechanism); the product-switcher concept in
  `applications/trading_intelligence/ui/` already anticipates this without
  implementing it.

**Requires ADR approval:**
- Authentication provider selection (Section 4).
- User database (a real schema/data-store decision — note `database/` is a
  protected path under ADR-002; any real schema work here would also need to
  satisfy that ADR's lifting checklist, not just an identity-specific ADR).
- Production security model (Phase 3's enforcement design).

**Blocked:**
- Production beta user onboarding — downstream of everything above; cannot
  happen before authentication, entitlement enforcement, and a security model
  all exist.

---

## Constraints Confirmed

No authentication code, database schema, or UI was implemented. No protected
path was touched.
