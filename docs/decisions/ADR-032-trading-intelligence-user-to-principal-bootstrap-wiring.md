# ADR-032: Trading Intelligence User-to-Principal Bootstrap Wiring (Process-Local)

**Status:** Accepted
**Date:** 2026-08-15
**Decision Type:** Implementation Authorization — Narrow Lift of Three Named Prior Deferrals
**Related ADRs:** ADR-029 (wired `SupabaseAuthenticationProvider` into Trading Intelligence's
`bootstrap.py`, §2.4 confined `current_user` to local scope only — this ADR narrowly lifts that
one confinement, nothing else), ADR-030 (named `Principal(principal_id: str)`, §3 deferred any
`User`↔`Principal` mapping/allocation logic — this ADR is that named future authorization, scoped
to one call site), ADR-031 (built the unwired `PrincipalRegistry` allocator, §2.3/§3 explicitly
withheld bootstrap wiring — this ADR is that named future follow-on), ADR-027 (§4: durable
identifiers must be AARA-owned, never a Supabase identifier, directly or indirectly — preserved;
see §3), ADR-002 (`bootstrap.py` remains outside its protected paths; unaffected either way)

---

## 1. Context

A read-only audit (this session) traced the smallest legal path for `User → Principal` mapping
using the already-built, already-unwired `PrincipalRegistry` (ADR-031). It found the mapping is
entirely buildable at the code level — `PrincipalRegistry.get_or_create(key)` takes any opaque
string — but is blocked by three separate, explicit non-authorizations already on record:

- **ADR-029 §2.4** confines `current_user` to `build_application()`'s own local scope, "never
  passed to any collaborator constructed below."
- **ADR-030 §3** defers "any mapping, association, or allocation logic between `User` and
  `Principal` — including how or when a `Principal` would be created for a given `User`."
- **ADR-031 §2.3** states "nothing in this ADR constructs or calls `PrincipalRegistry` from any
  `bootstrap.py`," and **§3** explicitly non-authorizes "any wiring of `PrincipalRegistry` into
  `applications/trading_intelligence/bootstrap.py`... or any other production call site."

This ADR is the single, narrow authorization each of those three clauses named as a future,
separately-scoped step. It authorizes exactly one call site — Trading Intelligence's
`bootstrap.py` — and nothing broader.

The audit also confirmed: `SupabaseAuthenticationProvider`'s placeholder client
(`_NoOpSupabaseClient`, ADR-029 §2.1) still deterministically returns `None`, so
`current_user` remains `None` in this build today — the wiring this ADR authorizes has zero
observable effect until a future ADR authorizes a real client, exactly as ADR-029 §5 already
stated for its own wiring. `Wealth Intelligence` has zero identity references and is unaffected.
`DecisionCenterController`/`DecisionCenterUI` accept no identity parameter today and are not
changed by this ADR.

## 2. Decision

In `applications/trading_intelligence/bootstrap.py`'s `build_application()`, immediately after the
existing line `current_user: Optional[User] = auth_provider.get_current_user()`:

1. Construct exactly one fresh `PrincipalRegistry()`.
2. If `current_user is not None`: use `current_user.user_id` as the lookup key and call
   `principal_registry.get_or_create(current_user.user_id)` exactly once. If `current_user is
   None`, no call is made — no `Principal` is allocated, and this is not an error, matching the
   `None`-handling convention ADR-029 §2.3 already established.
3. Retain the resulting `Principal` (or the absence of one) as a local value inside
   `build_application()` only.
4. **`current_user.user_id` is used here strictly as today's opaque lookup key, nothing more.**
   Using it as `PrincipalRegistry`'s key does not establish `user_id` as AARA's permanent
   principal identity, does not authorize any durable identity mapping, and does not change what
   `principal_id` means anywhere else in the codebase. `principal_id` itself remains, as ADR-031
   established, always independently generated via `uuid4()` — never derived from `user_id` — so
   this wiring introduces no new dependency of `principal_id` on any Supabase-sourced value.
5. **Registry lifetime is fresh-per-call, with no cross-call guarantee.** The `PrincipalRegistry`
   constructed in step 1 is local to that single invocation of `build_application()`. This ADR
   makes no guarantee that the same `current_user.user_id` maps to the same `Principal` across
   separate `build_application()` calls, process runs, or restarts — mirroring
   `_InMemoryLedgerStore`/`_InMemoryProjectionRepository`'s existing per-call construction pattern
   in the same function, and ADR-031 §2.2's own non-durability statement. Because this mapping is
   never persisted anywhere, it does not constitute a "durable record" in ADR-027 §4's sense — that
   clause targets records that outlive a single call, most importantly the immutable ledger; a
   process-scoped dict entry, discarded with the object and unrecoverable across a second call
   (§4's own test proves this explicitly), does not meet that bar.
6. The resulting `Principal` (or `None`) is never passed to `DecisionCenterController`,
   `DecisionCenterUI`, any `sentinel_engine` object, or any other collaborator constructed in
   `build_application()` — identical confinement discipline to ADR-029 §2.4, applied one layer
   deeper for `Principal`.

## 3. Explicit Authorization / ADR Reconciliation

This ADR is the single, narrow authorization for this one Trading Intelligence bootstrap mapping
point only. It reconciles, and narrowly lifts, exactly the following three clauses — no other
clause of ADR-029, ADR-030, or ADR-031 is altered, reopened, or reinterpreted:

- **ADR-029 §2.4** is lifted to the extent, and only to the extent, that `current_user.user_id`
  (not `current_user` itself, not any other field) may be passed to exactly one collaborator:
  `PrincipalRegistry.get_or_create()`. `current_user` as a whole remains confined to local scope;
  it is still never passed to `DecisionCenterController`, `DecisionCenterUI`, or any
  `sentinel_engine` object, per §2 item 6 above.
- **ADR-030 §3** is fulfilled, not overridden: this is the "real design decision" ADR-030 §3 named
  as deferred, made here narrowly for this one call site. It does not authorize any other
  `User`↔`Principal` mapping/allocation logic anywhere else in the codebase.
- **ADR-031 §2.3 and §3** are lifted to the extent, and only to the extent, that
  `applications/trading_intelligence/bootstrap.py` — named specifically — may construct a
  `PrincipalRegistry` and call `get_or_create()` once. No other production call site is authorized
  to construct or call `PrincipalRegistry` by this ADR.

## 4. Test Scope

`applications/trading_intelligence/tests/test_bootstrap_principal_mapping.py` (new, focused,
mirrors `test_bootstrap_authentication.py`'s structure):

- `build_application()` constructs exactly one `PrincipalRegistry`.
- When `get_current_user()` returns `None` (today's actual behavior via the ADR-029 placeholder),
  `get_or_create()` is never called — no `Principal` allocated, no exception raised.
- With `get_current_user()` monkeypatched to return a `User`, `get_or_create()` is called exactly
  once, with `current_user.user_id` as its argument.
- The resulting `Principal`/`None` is never passed to `DecisionCenterController` — reuses the
  existing 4-positional-args/0-kwargs assertion pattern already established in
  `test_bootstrap_authentication.py`.
- Two separate `build_application()` calls with the same underlying `user_id` do **not** produce
  the same `Principal` — an explicit test proving the stated no-cross-call-guarantee (§2 item 5),
  not an implicit gap.

## 5. Explicit Non-Authorization

This ADR authorizes exactly §2's six points and §4's test file. It does not authorize:

- Any Wealth Intelligence change of any kind.
- Any `Role` or SUPER_USER abstraction, implementation, or field.
- Any `EntitlementChecker` implementation, or any entitlement/authorization enforcement.
- Any persistence or database mechanism for `Principal`, `User`, or the `current_user.user_id` →
  `Principal` association — the mapping remains exactly as non-durable as `PrincipalRegistry`
  itself (ADR-031 §2.2), unchanged by this ADR.
- Any `sentinel_engine/` change of any kind.
- Any `ledger/` change, or the `principal_id` ledger field named in ADR-027 §3/§4 — still its own,
  separately-scoped future ADR.
- Any Capital Pool or `bot/` change.
- Any change to `User`, `AuthenticationProvider`, or `SupabaseAuthenticationProvider` — all remain
  exactly as ADR-027/028/029 left them.
- Any login flow, session-acquisition mechanism, token issuance/refresh, or MFA implementation.
- Any FastAPI, HTTP, or API/session-layer infrastructure.
- Any shared or module-level `PrincipalRegistry` — the registry constructed in §2 item 1 is
  strictly local to one `build_application()` invocation; no singleton, cache, or shared instance
  of any kind is authorized.
- Any cross-process or cross-restart idempotency guarantee — explicitly disclaimed in §2 item 5
  and tested in §4.
- Any wiring of `PrincipalRegistry` into Wealth Intelligence's `bootstrap.py`, or into any call
  site other than the one named in §2.

## 6. Consequences

**Positive:**

- Closes the specific gap ADR-029 §2.4, ADR-030 §3, and ADR-031 §2.3/§3 each separately named as
  deferred, using the narrowest possible authorization: one call site, one collaborator, one field.
- Keeps `sentinel_engine`, `database`, `bot/`, Wealth Intelligence, `Role`, and entitlement
  enforcement completely untouched, continuing this repository's one-slice-per-ADR pattern
  (ADR-027 → 028 → 029 → 030 → 031 → this ADR).
- `principal_id` remains structurally independent of any Supabase-sourced value even after this
  wiring — only the internal, non-durable lookup `key` is `user_id`-derived; the allocated
  `Principal.principal_id` is still always a fresh `uuid4()` value, preserving ADR-027 §4 by
  construction, not by convention alone.

**Negative / Open Risk:**

- Because the registry is fresh-per-call, this wiring provides no real identity continuity even
  within one process if `build_application()` is ever invoked more than once — an explicitly
  accepted limitation (§2 item 5), not an oversight, and one a future ADR would need to resolve
  before this mechanism could support anything beyond a first illustrative slice.
- Because `_NoOpSupabaseClient` still returns `None` deterministically, this wiring has zero
  observable effect in the current build — same honesty disclosure ADR-029 §5 already required for
  its own wiring, restated here for this one layer deeper.
- Still does not complete the identity story: durable `Principal` persistence, the `sentinel_engine`
  `principal_id` ledger field, `Role`/entitlement enforcement, and Wealth Intelligence wiring all
  remain open, each its own future work, unchanged by this ADR.

## 7. Status

**Accepted.** This ADR authorizes only what is stated in §2 — acceptance does not retroactively
authorize anything listed in §5, and does not reopen any clause of ADR-029, ADR-030, or ADR-031
beyond the three narrow lifts named in §3.
