# ADR-033: Wealth Intelligence Bootstrap Identity + Principal Wiring (Mirrors ADR-032)

**Status:** Accepted
**Date:** 2026-08-15
**Decision Type:** Implementation Authorization — Narrow Lift of Wealth-Intelligence-Specific
Deferrals Only (mirrors ADR-032's pattern exactly, for the second product)
**Related ADRs:** ADR-029 (built the `SupabaseAuthenticationProvider` + `_NoOpSupabaseClient`
placeholder pattern and wired it into Trading Intelligence only, §3 explicitly withholding Wealth
Intelligence — this ADR is that named future extension), ADR-030 (named `Principal(principal_id:
str)`, §3 deferred `User`↔`Principal` mapping generally), ADR-031 (built the unwired
`PrincipalRegistry` allocator, §3 explicitly non-authorized Wealth Intelligence wiring), ADR-032
(authorized the identical pattern for Trading Intelligence only, §5 explicitly non-authorized "any
other Wealth Intelligence changes" — this ADR is the Wealth Intelligence counterpart, mirroring
ADR-032 mechanically, not extending its authorization), ADR-027 (§4: durable identifiers must be
AARA-owned, never a Supabase identifier, directly or indirectly — preserved identically to
ADR-032 §3), ADR-002 (`bootstrap.py` remains outside its protected paths; unaffected either way)

---

## 1. Context

A read-only audit (this session) confirmed Trading Intelligence's identity+`Principal` wiring
(ADR-029, ADR-032) is complete, tested, and functionally inert (placeholder client always returns
`None`), and identified Wealth Intelligence wiring as the smallest legal next architectural slice —
smaller than real credentials, downstream `Principal` usage, or durable persistence, because it
requires no new abstraction or design decision, only mechanically replicating an already-proven
pattern onto a second, structurally symmetric file.

- `applications/wealth_intelligence/bootstrap.py` ([current text](applications/wealth_intelligence/bootstrap.py))
  has zero identity references today — confirmed by grep across the entire
  `applications/wealth_intelligence/` tree. Its `build_application()` constructs
  `_InMemoryLedgerStore`, `_InMemoryProjectionRepository`, the `sentinel_engine` write-side facade,
  the three read queries, `InvestorWorkspaceFacade`, `InvestorPresenter`, and returns
  `InvestorWorkspaceUI(presenter)` — no step accepts or could accept a `User`/`Principal`
  parameter today.
- Every prior ADR in this chain that touched identity or `Principal` explicitly withheld Wealth
  Intelligence: ADR-029 §3 ("Any Wealth Intelligence bootstrap wiring"), ADR-030 §3 ("Any Wealth
  Intelligence bootstrap wiring, product registration, or workspace registration"), ADR-031 §3
  ("Any wiring of `PrincipalRegistry` into... Wealth Intelligence's `bootstrap.py`"), ADR-032 §5
  ("Any Wealth Intelligence change of any kind."). None of these clauses forbid Wealth Intelligence
  wiring forever — each names it as a future, separately-scoped step, exactly matching this
  repository's established convention (ADR-028 → ADR-029 did the identical thing for Trading
  Intelligence's own bootstrap wiring one product at a time).
- ADR-029's own Context already established, and this audit re-confirms, that Trading Intelligence
  was chosen first by scope choice, not because its `bootstrap.py` is architecturally different
  from Wealth Intelligence's — both products' `bootstrap.py` files are structurally symmetric
  composition roots. This ADR is that deferred second product.
- `applications/wealth_intelligence`'s existing structural test convention has no forbidden-import
  scan equivalent to Trading Intelligence's `test_package_imports.py` restricting
  `applications.platform` — importing `applications.platform.identity.*` into
  `wealth_intelligence/bootstrap.py` is legal by the same reasoning ADR-029/032 already
  established for Trading Intelligence: `applications.platform` is not among any protected or
  forbidden path.
- `applications/wealth_intelligence/tests/` currently has `test_bootstrap.py`,
  `test_investor_presenter.py`, `test_investor_workspace_facade.py`, `test_main.py` — no
  identity-related test file exists yet.

## 2. Decision

Mirror ADR-032's Trading Intelligence pattern, applied to
`applications/wealth_intelligence/bootstrap.py`'s `build_application()`, exactly:

1. Construct `SupabaseAuthenticationProvider` using the identical placeholder pattern ADR-029 §2.1
   established for Trading Intelligence: a locally-defined `_NoOpSupabaseClient` (or equivalently
   named class, same shape) whose `get_user()` unconditionally returns `None`, makes no network
   call, and holds no credential. This is a new, Wealth-Intelligence-local class — it does not
   reuse or import Trading Intelligence's `_NoOpSupabaseClient`, mirroring how
   `_InMemoryLedgerStore`/`_InMemoryProjectionRepository` are already independently defined in
   each product's own `bootstrap.py` rather than shared.
2. Capture `current_user: Optional[User] = auth_provider.get_current_user()` with the identical
   None-safe handling ADR-029 §2.3 established: a `None` result is not an error, no exception is
   raised, no placeholder `User` is fabricated.
3. Construct exactly one fresh `PrincipalRegistry()` inside `build_application()` — local to that
   single invocation, matching ADR-032 §2 item 1 and ADR-031 §2.2's non-durability framing exactly.
4. When `current_user is not None`, call `principal_registry.get_or_create(current_user.user_id)`
   exactly once, using `current_user.user_id` strictly as today's opaque lookup key — identical to
   ADR-032 §2 items 2/4, including the same disclaimer: this does not establish `user_id` as AARA's
   permanent principal identity, and `principal_id` remains always independently `uuid4()`-generated,
   never derived from `user_id`.
5. The resulting `current_user`/`current_principal` values stay local to `build_application()` —
   never passed to `InvestorWorkspaceFacade`, `InvestorPresenter`, `InvestorWorkspaceUI`, any
   `sentinel_engine` object, or any other collaborator constructed in that function. Identical
   confinement discipline to ADR-029 §2.4 and ADR-032 §2 item 6, applied to Wealth Intelligence's
   own collaborators.
6. **Registry lifetime is fresh-per-call, with no cross-call guarantee** — identical to ADR-032 §2
   item 5: this ADR makes no guarantee that the same `current_user.user_id` maps to the same
   `Principal` across separate `build_application()` calls, process runs, or restarts. Because
   nothing is persisted, this does not constitute a "durable record" under ADR-027 §4, for the same
   reason ADR-032 §2 item 5 already established for Trading Intelligence.
7. **This wiring is functionally inert today.** Because the placeholder client named in item 1
   unconditionally returns `None`, `current_user` is always `None` and `get_or_create()` is never
   called in the current build — identical honesty disclosure to ADR-029 §5 and ADR-032 §6, stated
   here for Wealth Intelligence's own instance of the same mechanism.

## 3. Explicit Authorization / ADR Reconciliation

This ADR is the Wealth Intelligence counterpart to ADR-032, authorizing an identical pattern at a
second, previously-deferred call site — it does not alter, reopen, or reinterpret any other clause
of ADR-029, ADR-030, ADR-031, or ADR-032:

- **ADR-029 §3**'s "Any Wealth Intelligence bootstrap wiring" is lifted to the extent, and only to
  the extent, of the identity capture pattern named in §2 items 1-2 above, applied to
  `applications/wealth_intelligence/bootstrap.py` alone.
- **ADR-030 §3**'s deferral of `User`↔`Principal` mapping logic is fulfilled for this one call
  site, exactly as ADR-032 §3 already fulfilled it for Trading Intelligence — not generalized
  beyond the two named files across both ADRs.
- **ADR-031 §3**'s "Any wiring of `PrincipalRegistry` into... Wealth Intelligence's `bootstrap.py`"
  is lifted to the extent, and only to the extent, of §2 items 3-4 above.
- **ADR-032 §5**'s "Any Wealth Intelligence change of any kind" is lifted to the extent, and only
  to the extent, of this ADR's own §2 — ADR-032 itself remains otherwise unaltered and continues to
  govern Trading Intelligence's wiring exactly as before.
- No clause of any of these four ADRs is edited, superseded in general, or reopened beyond the
  narrow scope named above.

## 4. Test Scope

`applications/wealth_intelligence/tests/test_bootstrap_principal_mapping.py` (new, mirrors
`applications/trading_intelligence/tests/test_bootstrap_principal_mapping.py`'s structure exactly):

- `build_application()` constructs exactly one `PrincipalRegistry`.
- With the real (placeholder) `get_current_user()` returning `None`, `get_or_create()` is never
  called — no `Principal` allocated, no exception raised.
- With `SupabaseAuthenticationProvider.get_current_user` monkeypatched to return a `User`,
  `get_or_create()` is called exactly once with `current_user.user_id`.
- The resulting `Principal`/`None` is never passed to `InvestorWorkspaceFacade`,
  `InvestorPresenter`, or `InvestorWorkspaceUI` — verified via constructor-call tracking, mirroring
  the controller-args assertion pattern already established in Trading Intelligence's equivalent
  test.
- Two separate `build_application()` calls with the same underlying `user_id` do **not** produce
  the same `Principal` — explicit proof of §2 item 6's no-cross-call-guarantee.

## 5. Explicit Non-Authorization

This ADR authorizes exactly §2's seven points and §4's test file, applied only to
`applications/wealth_intelligence/bootstrap.py` and its one new test file. It does not authorize:

- Any real Supabase credentials, live client, or network call — the placeholder client named in
  §2 item 1 must never be upgraded to a real one under this authorization.
- Any persistence or database mechanism for `Principal`, `User`, or the mapping between them.
- Any `sentinel_engine/` change of any kind.
- Any `ledger/` change, or the `principal_id` ledger field named in ADR-027 §3/§4.
- Any `Role` or SUPER_USER abstraction, implementation, or field.
- Any `EntitlementChecker` implementation, or any entitlement/authorization enforcement.
- Any Capital Pool or `bot/` change.
- Any downstream use of `current_user` or `current_principal` beyond §2 item 5's local capture —
  no passing to `InvestorWorkspaceFacade`, `InvestorPresenter`, `InvestorWorkspaceUI`, or any other
  collaborator.
- Any login flow, session-acquisition mechanism, token issuance/refresh, or MFA implementation.
- Any FastAPI, HTTP, or API/session-layer infrastructure.
- Any shared or module-level `PrincipalRegistry` — the registry constructed in §2 item 3 is
  strictly local to one `build_application()` invocation, identical to ADR-032's constraint.
- Any change to Trading Intelligence's `bootstrap.py`, `AuthenticationProvider`, `User`,
  `SupabaseAuthenticationProvider`, or `PrincipalRegistry`/`Principal` themselves — all remain
  exactly as ADR-027 through ADR-032 left them.
- Any other Wealth Intelligence change beyond the two files named in this ADR's scope.
- Any new dependency.

## 6. Consequences

**Positive:**

- Closes the last of the four Wealth-Intelligence-specific deferrals named across ADR-029/030/031/032,
  using the narrowest possible mechanism: a mechanical mirror of an already-built, already-tested
  pattern, introducing zero new design decisions.
- Both products now have symmetric, equally inert identity+`Principal` wiring — removing the
  asymmetry ADR-029 introduced deliberately as a scope choice, not an architectural one.
- Keeps `sentinel_engine`, `database`, `bot/`, `Role`, and entitlement enforcement completely
  untouched, continuing the one-slice-per-ADR pattern (ADR-027 → ... → ADR-032 → this ADR).

**Negative / Open Risk:**

- Identical open risks to ADR-032, duplicated for Wealth Intelligence: no cross-call identity
  continuity, zero observable effect until a future ADR authorizes a real client, no progress on
  `Role`, entitlement enforcement, durable persistence, or the `sentinel_engine` `principal_id`
  ledger field.
- Two independent `_NoOpSupabaseClient`-equivalent classes and two independent
  `PrincipalRegistry`-construction sites now exist (one per product) rather than a shared
  mechanism — an intentional consequence of this repository's existing per-product,
  no-shared-composition-code convention (`_InMemoryLedgerStore`/`_InMemoryProjectionRepository`
  are already duplicated the same way), not an oversight of this ADR.

## 7. Status

**Accepted.** This ADR authorizes only what is stated in §2 — acceptance does not retroactively
authorize anything listed in §5, and does not reopen any clause of ADR-029, ADR-030, ADR-031, or
ADR-032 beyond the four narrow lifts named in §3.
