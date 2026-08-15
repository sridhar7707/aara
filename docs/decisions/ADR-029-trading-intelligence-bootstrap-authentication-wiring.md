# ADR-029: Trading Intelligence Bootstrap Authentication Wiring

**Status:** Accepted
**Date:** 2026-08-15
**Decision Type:** Implementation Authorization (fulfills ADR-028 §3's named deferred
bootstrap-wiring authorization)
**Related ADRs:** ADR-027 (selected Supabase Auth, established the ownership boundary this ADR
respects), ADR-028 (built the concrete adapter and staged it for deployment, but explicitly
withheld bootstrap-wiring authorization — this ADR is that named future follow-on), ADR-003
(identity/role/entitlement model remains an accepted requirement only — not advanced by this
ADR), ADR-002 (`bootstrap.py` is not an ADR-002-protected path; unaffected either way), ADR-004
(ledger backend strategy — unaffected, no ledger change made here), ADR-016 (names
`applications/*/bootstrap.py` as out of its own scope; **Proposed** status, not binding — see §1)

---

## 1. Context

ADR-028 §2.1 authorized and commit `fefb355` implemented a concrete `SupabaseAuthenticationProvider`
in `applications/platform/identity/`, translating a Supabase session into AARA's own
`User(user_id, display_name)`. ADR-028 §3 explicitly withheld one thing: *"Wiring the adapter into
`bootstrap.py`... requires its own future authorization."* This ADR is that authorization.

A read-only audit (this session) established the exact current state this ADR is written against:

- `applications/trading_intelligence/bootstrap.py` and `applications/wealth_intelligence/bootstrap.py`
  each remain each product's sole composition root (per their own docstrings), and neither imports
  any part of `applications.platform.identity` today.
- **Trading Intelligence is chosen as this ADR's target by scope choice, not because its
  `bootstrap.py` is architecturally different from Wealth Intelligence's.** Both files are
  structurally symmetric today — identical `_InMemoryLedgerStore`/`_InMemoryProjectionRepository`
  scaffolding, identical zero identity references, identical composition-root role per their own
  docstrings. Nothing in the code forces Trading Intelligence over Wealth Intelligence; this ADR
  narrows scope to one product deliberately, the same way ADR-028 narrowed to two named files
  rather than authorizing both products' full identity wiring at once. Wealth Intelligence's
  `bootstrap.py` remains untouched and available for its own, identical future ADR.
- `applications.trading_intelligence`'s own structural test
  (`tests/test_package_imports.py::test_no_module_imports_forbidden_runtimes`) forbids imports of
  `bot`, `dashboard`, `scheduler`, `database`, `ledger` only. `applications.platform` is not
  forbidden — a Trading Intelligence import of `applications.platform.identity` is already
  structurally legal under existing, passing tests, without any test change.
- `applications/platform/navigation/navigation_builder.py` is the only place in the repository that
  currently consumes `AuthenticationProvider` in production code (not test-only). Its `build()`
  method establishes the repository's only existing convention for a `None` result:
  `user = self._auth_provider.get_current_user(); if user is None: return NavigationModel(current_user=None, items=[])`
  — propagate `Optional[User]`, do not raise, do not fabricate a placeholder user. `NavigationBuilder`
  itself is not wired into either `bootstrap.py` and is not touched by this ADR.
- Neither `DecisionCenterController` nor `DecisionCenterUI` — the two objects
  `trading_intelligence/bootstrap.py` constructs downstream of its `sentinel_engine` wiring — accept
  a `User`/identity parameter today. There is currently no consumer for a resolved `User` beyond the
  composition root itself.
- No real Supabase credentials, project, or client-construction mechanism exist anywhere in the
  repository. `SupabaseAuthenticationProvider` is constructor-injected with a client it never builds
  itself (ADR-028 §2.1) — this ADR does not change that, and does not introduce credential
  provisioning of any kind.
- `ADR-016` (`Status: Proposed — Implementation Deferred`) separately lists "any change to
  `applications/*/bootstrap.py`" as outside its own scope. Because ADR-016 is not Accepted, it is
  not authoritative per `docs/DOCUMENT_INDEX.md` §1, and in any case that clause withholds only
  *ADR-016's own* authorization to touch `bootstrap.py` for its unrelated ConstitutionRuleCheck
  contract-naming work — it does not purport to bind this or any other separately-scoped future
  ADR. No conflict exists between ADR-016 and this ADR.

## 2. Decision

This ADR authorizes exactly four things, and no more, scoped to **Trading Intelligence only**:

### 2.1 Construction

`applications/trading_intelligence/bootstrap.py` may import and construct the existing, unmodified
`SupabaseAuthenticationProvider` from `applications.platform.identity`. The client object passed to
its constructor must be a locally-defined placeholder that makes no network call and holds no real
credential — consistent with ADR-028 §3's continuing prohibition on real Supabase connectivity.
Real client/credential provisioning is explicitly not authorized here (see §3) and remains its own
future work.

### 2.2 Invocation

`build_application()` may call `.get_current_user()` on the constructed provider exactly once,
during composition, alongside its existing `sentinel_engine` object-graph construction.

### 2.3 None behavior

`get_current_user()` returning `None` is not an error condition. Per the existing convention already
established by `NavigationBuilder.build()` (§1), a `None` result is simply the resolved value —
`build_application()` must not raise, must not construct a placeholder/anonymous `User`, and must not
alter, gate, or short-circuit any part of the existing object graph on account of it. Whether the
call returns a `User` or `None`, `build_application()`'s return value and behavior are unchanged from
today. This is the smallest possible legal behavior: capture the result, do not act on it.

### 2.4 Scope confinement

The resulting `Optional[User]` may exist only as a local value within
`applications/trading_intelligence/bootstrap.py`'s `build_application()` function. It must not be
passed as an argument to `DecisionCenterController`, `DecisionCenterUI`, any `sentinel_engine`
service, or any other object constructed in that function. No signature in this codebase changes as
a result of this ADR.

## 3. Explicit Non-Authorization

This ADR does not authorize:

- Any Wealth Intelligence bootstrap wiring — `applications/wealth_intelligence/bootstrap.py` is
  untouched by this decision and remains exactly as it is today.
- Any `Principal` abstraction, or any type beyond the existing, unmodified `User(user_id, display_name)`.
- Any `principal_id` field, anywhere, including `sentinel_engine`'s ledger — still deferred per
  ADR-027 §3/§7, unchanged by this ADR.
- Any change to `sentinel_engine/` of any kind — no import, no dependency, no field addition.
- Any change to `database/`, `ledger/`, or any persistence/backend decision (still governed by
  ADR-004's deferral).
- Any Capital Pool ownership change — `bot/capital/pool.py` remains untouched and remains
  ADR-002-protected.
- Any entitlement or authorization enforcement — `EntitlementChecker`, `NavigationBuilder`, and any
  gating of UI/data access by identity remain unauthorized; ADR-003 remains a recorded requirement
  only.
- Any login flow, session-acquisition mechanism, or credential provisioning of any kind — the
  placeholder client named in §2.1 must never be upgraded to a real one under this authorization.
- Any token refresh mechanism.
- Any MFA implementation.
- Any FastAPI, HTTP, or session-layer infrastructure — still deferred per ADR-027 §7 item 4.
- Any change to `AuthenticationProvider` (`authentication_provider.py`) or `User` (`user.py`) — both
  remain exactly as ADR-028 left them.
- Any change to `SupabaseAuthenticationProvider`'s own implementation.
- Any change to `bot/`, `dashboard/`, or `scheduler/`.
- Any change to any `.github/workflows/*.yml` file — the ADR-028 staging exception already covers
  what's needed for the adapter to exist in each Space; this ADR adds no new staging need, since
  `bootstrap.py` is already part of each product's staged package.
- Any new dependency — the pinned Supabase SDK line ADR-028 §2.3 already added is sufficient; this
  ADR adds no package of any kind.

## 4. Verification Requirements

Before this ADR's authorization is exercised in code:

1. **Named module only:** exactly `applications/trading_intelligence/bootstrap.py`. No other file
   changes, beyond an accompanying test exercising §2.1-§2.4 (both the `User`-returned and
   `None`-returned cases), which this ADR treats as implied and in-scope alongside the change itself.
2. Full regression pass of `applications/trading_intelligence` and `applications/platform` test
   suites, both before and after.
3. Confirm the structural boundary tests (`test_package_imports.py`,
   `test_platform_structure.py`) still pass unmodified — this ADR relies on the existing import
   direction already being legal, not on relaxing any boundary test.
4. Rollback: revert the `bootstrap.py` diff. No data, deployment, or workflow rollback is required —
   nothing outside `bootstrap.py` changes under this ADR.

## 5. Consequences

**Positive:**

- Closes the specific gap ADR-028 §3 named, using the smallest possible slice: one product, one
  call, no propagation, no new infrastructure.
- Keeps `sentinel_engine`, `database`, Wealth Intelligence, and every protected path completely
  untouched.
- Establishes, in real (not test-only) composition code, that the import/construction/invocation
  edge between `applications.trading_intelligence` and `applications.platform.identity` is legal
  and does not crash — a necessary precondition for any future, real-credential follow-on ADR.

**Negative / Open Risk — stated explicitly to avoid overclaiming:**

- **This wiring is a deterministic authentication no-op.** Because §2.1 mandates a placeholder
  client whose `get_user()` always returns `None`, `SupabaseAuthenticationProvider.get_current_user()`
  is guaranteed to always return `None` under this authorization — the `response.user` translation
  branch inside the adapter (mapping a Supabase user's `id`/`email` into `User`) can never execute
  via this composition path, no matter how many times `build_application()` runs.
- **This ADR proves only that the import, construction, and invocation edge is legal and
  non-crashing.** It does **not** exercise successful authentication, real Supabase connectivity,
  credential handling, or `User` translation anywhere in the composition path — those remain exactly
  as untested-in-production as before this ADR, and remain gated behind the future, separately-scoped
  authorization named in §2.1 and §3.
- Still does not complete the identity story: real credential provisioning, `Principal`/`principal_id`,
  entitlement enforcement, and Wealth Intelligence wiring all remain open, each its own future work.

## 6. Status

**Accepted.** This ADR authorizes only what is stated in §2 — acceptance does not retroactively
authorize anything listed in §3.
