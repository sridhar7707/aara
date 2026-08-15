# ADR-027: Selection of Supabase Auth as AARA's Initial Authentication Provider

**Status:** Accepted
**Date:** 2026-08-15
**Decision Type:** Provider Selection (fulfills ADR-003's deferred "Authentication provider selection" gate)
**Related ADRs:** ADR-003 (the broader identity/access requirement this ADR partially fulfills;
the specific "Requires ADR approval" gate for authentication-provider selection is from
`AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md` §7, not ADR-003 directly), ADR-001 (Sentinel
Engine Package Structure; the broader zero-touch governance convention `sentinel_engine/`
already operates under is established by consistent citation across other project documents,
not by ADR-001's own text — this ADR respects that convention regardless), ADR-002 (bot/dashboard/
scheduler protection — unaffected, not touched by this ADR)

---

## 1. Context

`ADR-003` established that AARA will support product-level access control, and named identity,
roles, entitlements, and workspace permissions as separate concerns, without selecting any
authentication mechanism. `docs/platform/AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md`
Section 4 named three provider categories (Google OAuth / a managed auth provider / an internal
identity service) and Section 7 explicitly classified provider selection as **"Requires ADR
approval"** — distinct from the identity *interfaces*, which that same document classifies as
buildable without an ADR.

A read-only repository audit (this session) confirmed the current state this ADR is written
against:

- `applications/platform/identity/authentication_provider.py` already defines
  `AuthenticationProvider(ABC)` with `get_current_user() -> Optional[User]` — its own docstring
  states "No concrete implementation exists here." This is the existing, canonical abstraction;
  no second identity abstraction exists anywhere in the repository.
- `shared/` exists at the repository root but is completely empty (no files, no `__init__.py`).
  It is *named* as a probable future location for identity in the implementation plan, but
  nothing has been placed there, and this ADR does not change that.
- **No FastAPI application boundary exists in the AARA platform today.** The only `FastAPI`
  reference anywhere under `applications/` or `sentinel_engine/` is `dashboard/http_endpoints.py`
  — Gradio's own underlying app object being wrapped for a couple of custom routes on the
  legacy, ADR-002-protected dashboard Space. Every current AARA product
  (`applications/trading_intelligence/`, `applications/wealth_intelligence/`) is a Gradio app
  with no HTTP/API/session layer of its own.
- `sentinel_engine/governance/approval.py`'s `Approval.approved_by: str` is the only
  actor-identifying field anywhere in `sentinel_engine`'s domain, event, or ledger models — a
  bare, untyped string. `sentinel_engine` has no concept of a structured principal today, and
  this ADR does not add one.

## 2. Decision

**Supabase Auth is selected as AARA's initial authentication provider.** Any future
implementation must be wired exclusively behind the existing `AuthenticationProvider`
abstraction in `applications/platform/identity/` — no second or alternative abstraction is
introduced anywhere by this decision.

**Ownership boundary, stated explicitly:**

- **Supabase owns:** credential authentication (login mechanics — password, OAuth, magic-link,
  etc.), MFA challenge execution, and token issuance/refresh/revocation.
- **AARA owns:** principals, tenants, roles, permissions, Capital Pools, and every authorization
  decision. A Supabase-issued session is translated into an AARA `Principal` at the
  `AuthenticationProvider` boundary and never propagated further into AARA's own domain logic —
  no Supabase-specific identifier, token, or session object crosses that boundary.
- **Sentinel (`sentinel_engine/`) remains completely authentication-provider agnostic** — it has
  no knowledge of Supabase, `AuthenticationProvider`, or any identity mechanism at all, today or
  after this ADR. This is already true of the current codebase (Section 1) and this ADR commits
  to preserving it, not changing it.

**No `shared/identity/` package, or any equivalent new shared package, is created or proposed
by this ADR.** The canonical location for `AuthenticationProvider` and any related identity code
remains `applications/platform/identity/`.

**FastAPI is named here only as a future application/API integration target** — the eventual
point where a real HTTP/session boundary would validate a Supabase token and resolve an AARA
`Principal` — not as something that exists or is deployed today. This ADR does not describe
FastAPI as a current part of AARA's architecture.

## 3. Explicit Non-Authorization

This ADR, if accepted, authorizes **only** the provider selection and ownership boundary stated
in Section 2. It does not authorize:

- **Any change to `sentinel_engine/`** — no new contract, no field addition to `Approval` or any
  other domain/event/ledger model, no new import, no dependency of any kind, direct or indirect.
  This includes the eventual need to record an AARA `principal_id` in the immutable ledger
  (Section 4) — that field-level change is named as a future, separately-scoped need, not
  authorized here.
- **Implementation of a concrete Supabase-backed `IdentityProvider`/`AuthenticationProvider`
  adapter.** This ADR authorizes the *selection*, not the *build*.
- **Creation of `shared/identity/`** or any equivalent shared package.
- **Any FastAPI or other API-layer code, scaffolding, or dependency addition.**
- **Any MFA implementation.** "Progressive MFA for higher-risk actions" is named as a future
  policy requirement (Section 7), not designed or built here.
- **Any database/schema work.** Where and how AARA-side principal/tenant/role/permission/Capital
  Pool records persist is explicitly deferred (Section 7); `database/` also remains
  ADR-002-protected regardless.
- **Any change to source code, tests, deployment files (including anything under
  `.github/workflows/`), or any existing ADR.** This document is a decision record only.

## 4. Security Boundaries

- Supabase-issued tokens are validated only at the (not-yet-built) `AuthenticationProvider`
  adapter boundary — never passed through to, stored by, or trusted directly by any AARA domain
  code, `sentinel_engine`, or the immutable ledger.
- Any durable record — most importantly the immutable ledger — must reference AARA's own
  `principal_id` (an AARA-issued identifier, stable regardless of provider), never a Supabase
  user ID, JWT, or session token, directly or indirectly. This is a normative requirement this
  ADR establishes even though its implementation (the ledger field-level change) is deferred to
  its own future ADR under Section 3's sentinel_engine constraint.
- Because no AARA-side identifier is ever provider-specific, a future provider change requires
  no reinterpretation of any historical record.

## 5. Migration Strategy

Because the AARA-side `principal_id` is provider-independent by design (Section 4), replacing
Supabase with a different provider later requires only a new `AuthenticationProvider`
implementation behind the existing abstraction — no ledger, authorization, or `sentinel_engine`
change. No data migration is authorized or anticipated by this ADR, since no implementation
exists yet to migrate from.

## 6. Alternatives Considered

- **Google OAuth directly** — not selected for now: a single login method with less flexibility
  than a managed provider, while still tying identity to a third party with none of a managed
  provider's additional session/MFA/token tooling.
- **Internal identity service** — not selected for now: highest build and maintenance cost of
  the three options named in the implementation plan; deferring this cost until real usage
  patterns justify it is the explicit intent behind choosing a managed provider *initially*.
- **Keycloak** (or any self-hosted identity platform) — not selected: unnecessary self-hosted
  operational burden at this stage; a premature microservice relative to AARA's current scale.
- **No authentication provider (defer indefinitely)** — not selected: ADR-003 already
  established product-level access control as a real requirement, and both Trading Intelligence
  and Wealth Intelligence need real entitlement enforcement before real user data flows through
  them.

## 7. Deferred Decisions

Not decided by this ADR, each requiring its own future, separately-scoped work:

1. The concrete `IdentityProvider`/`AuthenticationProvider` adapter implementation.
2. Where and how AARA-side `Principal`, tenant, role, permission, and Capital Pool records
   persist — a real schema/database decision, additionally gated by `database/`'s existing
   ADR-002 protection.
3. The exact `sentinel_engine` ledger field-level change needed to carry `principal_id` — its
   own future ADR, scoped separately, per Section 3's zero-`sentinel_engine`-change constraint.
4. FastAPI or any other concrete API/session-layer technology choice, and when it gets built.
5. Progressive MFA trigger conditions/policy — which specific actions count as "higher-risk."
6. Tenant model design — `AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md` already defers
   multi-tenant/organization support as "a real future extension, explicitly not designed
   further here"; this ADR does not revisit that deferral.

## 8. Consequences

**Positive:**

- Unblocks Phase 1 (identity abstraction) and clears the specific governance gate
  (`AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md` Section 7) blocking provider selection,
  without prematurely committing engineering effort to a concrete adapter.
- Preserves `sentinel_engine`'s existing zero-coupling-to-auth property, keeping it independently
  testable and portable regardless of any future identity-provider change.
- Avoids the operational cost and complexity of self-hosted identity infrastructure at a stage
  where real usage patterns don't yet justify it.

**Negative / Open Risk:**

- Real entitlement enforcement (ADR-003's Phase 3) remains blocked until a follow-on ADR
  authorizes the concrete adapter implementation and the ledger's `principal_id` field.
- At least two further ADRs are anticipated as near-term follow-ons (concrete adapter
  implementation; ledger `principal_id` field) — this ADR alone does not complete the identity
  story, only the provider-selection gate.

## 9. Status

**Accepted.** This ADR authorizes only the provider selection (Section 2) and is bound by every
constraint in Section 3 — acceptance does not retroactively authorize the adapter implementation,
the `sentinel_engine` ledger change, or any other deferred item in Section 7; each remains a
precondition for its own future, separately-governed ADR.
