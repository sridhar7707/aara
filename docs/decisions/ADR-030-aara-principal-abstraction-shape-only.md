# ADR-030: AARA Principal Abstraction (Shape Only, Implementation Deferred)

**Status:** Accepted
**Date:** 2026-08-15
**Decision Type:** Architecture / Governance — Contract Classification Only (follows ADR-016's
precedent for naming a shape without authorizing its implementation)
**Related ADRs:** ADR-027 (established that durable identifiers must be AARA's own `principal_id`,
never a Supabase identifier, directly or indirectly — this ADR names the shape that rule requires,
nothing more), ADR-028 (built the concrete Supabase adapter, explicitly deferred `Principal`),
ADR-029 (wired the adapter into Trading Intelligence's bootstrap only, explicitly deferred
`Principal`/`Role`/enforcement), ADR-003 (Role/SUPER_USER remain an accepted requirement only —
not advanced by this ADR), ADR-016 (precedent this ADR follows: name a dataclass shape, authorize
nothing else), ADR-002 (`bot/`, `database/`, `ledger/`, `dashboard/`, `scheduler/`,
`.github/workflows/*.yml` remain frozen; untouched by this ADR)

---

## 1. Context

A read-only audit (this session) traced the smallest architecturally legal path from a Supabase
`User` to an eventual SUPER_USER authorization model. It found:

- `Principal`/`principal_id` do not exist anywhere in the codebase. ADR-027 §3 named the
  `sentinel_engine` ledger's `principal_id` field as "a future, separately-scoped need, not
  authorized here." ADR-027 §7 item 2 separately named "where and how AARA-side `Principal`...
  records persist" as its own deferred, future schema/database decision. ADR-027 §8 anticipated at
  least one further ADR for this specifically.
- `User(user_id, display_name)` ([applications/platform/identity/user.py](applications/platform/identity/user.py))
  is unchanged since ADR-027/028/029 and remains the only identity shape in the codebase.
- **`User.user_id` is currently a direct copy of the Supabase user's own id.**
  `SupabaseAuthenticationProvider.get_current_user()` sets
  `User(user_id=supabase_user.id, display_name=supabase_user.email or supabase_user.id)`
  ([supabase_authentication_provider.py:52-55](applications/platform/identity/supabase_authentication_provider.py#L52-L55)).
  `User.user_id` is therefore a Supabase-sourced value carried under an AARA-named field, not an
  AARA-issued identifier.
- ADR-027 §4 states any durable record "must reference AARA's own `principal_id`... never a
  Supabase user ID, JWT, or session token, **directly or indirectly**." Given the finding above, a
  `Principal` shape that stores or references `User.user_id` would violate this rule by carrying a
  Supabase-sourced value into an AARA-owned record one layer removed. The narrowest compliant shape
  must not reference `User` at all.
- No `Role` type exists anywhere in the codebase; `Role`/SUPER_USER remain an ADR-003 requirement
  with zero implementation (confirmed by this session's audit and unchanged by ADR-027/028/029).
  Not advanced by this ADR.
- No concrete `EntitlementChecker` implementation exists anywhere in production code (interface
  only). Not advanced by this ADR.
- No `WEALTH_INTELLIGENCE_PRODUCT` descriptor or equivalent exists; Wealth Intelligence's
  `bootstrap.py` is unchanged since ADR-029 and imports no identity code. Not advanced by this ADR.
- `bot/capital/pool.py`'s `capital_pools` table has no user/owner/principal column and lives inside
  `bot/`, protected in full by ADR-002. Not advanced by this ADR.

## 2. Decision

Define, for future use, a new proposed dataclass shape:

```text
Principal
    principal_id: str
```

**This is a name and field list only.** This ADR does not create the file, does not write the
dataclass, and does not select its exact module path (a plausible future location would be
alongside `applications/platform/identity/user.py`, e.g.
`applications/platform/identity/principal.py` — noted here as a design consideration, not
authorized by this ADR).

**Deliberately one field, and deliberately no reference to `User`, `user_id`, or any other
Supabase-sourced value** — per §1's finding, `User.user_id` is itself a copy of the Supabase user's
id, so including it (or any derivative of it) on `Principal` would carry a Supabase identifier into
an AARA-owned record "indirectly," violating ADR-027 §4's rule this ADR exists to preserve. How a
`Principal` is allocated, generated, or associated with a `User` at authentication time is a real
design and persistence decision — deliberately not made here, matching ADR-027 §7 item 2's own
deferral of "where and how AARA-side `Principal`... records persist."

No `display_name`, `tenant_id`, `role`, or timestamp field is included — each would either
duplicate information already carried by `User` (not this abstraction's job) or anticipate a
concept (`Role`, tenancy) this ADR does not authorize.

## 3. Explicit Non-Authorization

This ADR authorizes naming a one-field shape only. It does not authorize, and implementation must
not include, any of the following:

- Any `Role` or SUPER_USER implementation, abstraction, or field — ADR-003 remains a recorded
  requirement only; unchanged by this ADR.
- Any `EntitlementChecker` concrete implementation, or any entitlement/authorization enforcement of
  any kind.
- Any Wealth Intelligence bootstrap wiring, product registration, or workspace registration.
- Any Capital Pool change, ownership field, or schema change — `bot/capital/pool.py` and all of
  `bot/` remain exactly as they are, protected by ADR-002.
- Any `sentinel_engine/` change of any kind — no import, no dependency, no field addition,
  including the `principal_id` ledger field named in ADR-027 §3/§4, which remains its own,
  separately-scoped future ADR.
- Any `database/` or `ledger/` change, including any persistence mechanism for `Principal`.
- Any login flow, credential handling, session-acquisition mechanism, token issuance/refresh, or
  MFA implementation.
- Any FastAPI, HTTP, or API/session-layer infrastructure.
- Any mapping, association, or allocation logic between `User` and `Principal` — including how or
  when a `Principal` would be created for a given `User`. This is a real design decision explicitly
  deferred, not implied by naming the shape.
- Any change to `AuthenticationProvider`, `User`, `SupabaseAuthenticationProvider`, or
  `applications/trading_intelligence/bootstrap.py` — all remain exactly as ADR-027/028/029 left
  them.
- Any new file, module, or test beyond what is strictly required to confirm the dataclass itself is
  well-formed (field names/types), if and when this ADR is accepted and that minimal step is
  separately taken — mirroring ADR-016 §3's identical constraint.
- Any new dependency.

## 4. Relationship to ADR-027

This ADR does not resolve ADR-027 §7 item 2 (where/how `Principal` records persist) or the
`sentinel_engine` `principal_id` ledger field named in ADR-027 §3/§4. Both remain their own,
separately-scoped future ADRs, exactly as ADR-027 anticipated in §8. This ADR only removes the
naming gap: once accepted, a future ADR authorizing persistence or ledger integration has a defined
shape to reference instead of inventing one at that time.

## 5. Consequences

**Positive:**

- Gives the ownership boundary ADR-027 §4 already established (Supabase owns credentials; AARA owns
  principals) a concrete name to reference in future, narrower ADRs — without prematurely deciding
  persistence, mapping, or enforcement.
- Keeps `sentinel_engine`, `database`, `bot/`, Wealth Intelligence, `Role`, and entitlement
  enforcement completely untouched, matching this repository's established one-slice-per-ADR
  pattern (ADR-027 → ADR-028 → ADR-029 → this ADR).

**Negative / Open Risk:**

- Does not advance SUPER_USER, cross-product access, or Capital Pool authorization in any way —
  each remains blocked behind its own, separately-scoped future ADR (`Role`, concrete
  `EntitlementChecker` + enforcement, Wealth Intelligence registration, Capital Pool linkage,
  `principal_id` ledger field), none of which this ADR advances or shortens.
- The `User` → `Principal` mapping question remains genuinely open and is not trivial: since
  `User.user_id` is Supabase-sourced, generating an AARA-issued `principal_id` requires either a
  lookup/allocation table (a persistence decision) or an equivalent mechanism — deliberately left
  to the ADR named in §4 above.

## 6. Status

**Accepted.** This ADR authorizes only what is stated in §2 — acceptance does not retroactively
authorize anything listed in §3.
