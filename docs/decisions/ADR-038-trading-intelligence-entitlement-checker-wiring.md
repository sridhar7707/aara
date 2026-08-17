# ADR-038: Trading Intelligence EntitlementChecker Implementation and Composition Wiring

**Status:** Accepted
**Date:** 2026-08-17
**Decision Type:** Implementation Authorization — Narrow Lift of Three Named Prior Deferrals
**Related ADRs:** ADR-003 (recorded the role/entitlement requirement this ADR implements the
Trading-Intelligence-only slice of, without changing the requirement itself), ADR-029 (wired
`SupabaseAuthenticationProvider` into Trading Intelligence's `bootstrap.py`, §3 explicitly withheld
"`EntitlementChecker`, `NavigationBuilder`, and any gating of UI/data access by identity" — this ADR
is that named future authorization, scoped to one product), ADR-032 (wired `PrincipalRegistry` into
the same call site, §5 separately withheld "Any `EntitlementChecker` implementation, or any
entitlement/authorization enforcement" — same lift, narrower still), ADR-033 (mirrored ADR-032 for
Wealth Intelligence, §5 withheld the identical clause for that product — **not** lifted by this ADR;
Wealth Intelligence remains untouched), ADR-030/ADR-031 (`Principal`/`PrincipalRegistry` — unaffected,
not read by anything this ADR authorizes), ADR-002 (`bootstrap.py` remains outside its protected
paths; unaffected either way)

---

## 1. Context

A read-only audit (this session) traced the current, real state of every abstraction this ADR
touches, to establish the smallest legal next slice.

**No concrete `EntitlementChecker` exists anywhere in the codebase.** `applications/platform/
entitlements/entitlement_checker.py:14-17` defines only the abstract contract
(`has_access(user: User, product_id: str) -> bool`); `entitlements/README.md:3` states "Abstract
contract only. No permissions engine, no database." The only implementations anywhere are
test-local fakes (`applications/platform/tests/test_entitlement_checker.py:8-16`,
`test_navigation_builder.py`, `test_shell_builder.py`,
`test_trading_intelligence_product_integration.py:102-107`) — all structurally identical: an
injected `set` of `(user_id, product_id)` grants, checked by membership.

**`NavigationBuilder` and `ShellBuilder` are both fully built, fully tested, and completely unwired
in production.** `navigation/README.md:15-18` and `shell/README.md:14-17` each state their builder
"constructor-injects... `EntitlementChecker`... (all interfaces, no concrete implementation of any
of them exists anywhere in this codebase)." A repository-wide search confirms neither
`NavigationBuilder(` nor `ShellBuilder(` is called from any file under `applications/*/bootstrap.py`
or any other production composition path — only from `applications/platform/tests/`.

**`ShellBuilder` is a dead-end branch today, independent of scope choice.**
`shell_presenter.py:14`'s `ShellPresenter.present()` — the only code in this repository that turns a
builder's output into an actual presentation model (`PlatformShellView`) — takes a `NavigationModel`
(`NavigationBuilder`'s output) as its sole argument; it never takes a `ShellModel`
(`ShellBuilder`'s output). A repository-wide search for `ShellModel`/`ShellBuilder` confirms both
names appear only inside `applications/platform/shell/`'s own files and their own tests — zero
consumers anywhere else, production or test. `ShellBuilder`'s exclusion from this ADR (§2.2 item 5)
is therefore not merely a narrower scope choice; `ShellBuilder`/`ShellModel` have no path to any
consumer that exists in this codebase today, wired or unwired.

**No platform-wide composition root exists.** There is no `applications/platform/bootstrap.py` or
equivalent; `applications/trading_intelligence/bootstrap.py` and `applications/wealth_intelligence/
bootstrap.py` are each, per their own docstrings, the *sole* composition root for their own product
only. Neither constructs a `ProductRegistry` or `WorkspaceRegistry` today. This ADR does not assume
such a root exists or will exist; it authorizes wiring that works without one.

**Trading Intelligence's own product data already exists, unregistered.**
`applications/trading_intelligence/product.py:26-42` already defines `TRADING_INTELLIGENCE_PRODUCT`
(`entitlement_required="TRADING_INTELLIGENCE"`) and `DECISION_CENTER_WORKSPACE` — proven correct
against the real `ProductRegistry`/`WorkspaceRegistry`/`NavigationBuilder` interfaces by
`test_trading_intelligence_product_integration.py`, but "not registered with any registry
implementation anywhere in this codebase" per the module's own docstring (`product.py:6-8,20-21`).

**`Product.entitlement_required: str` (`product_registry.py:23`) is the only concrete trace of
ADR-003's role concept in code.** No `Role`, `SUPER_USER`, or entitlement-enum type exists anywhere
— confirmed by repository-wide search. `User` (`identity/user.py:10-13`) is exactly
`{user_id: str, display_name: str}`; it carries no role, entitlement, or product-access field.
`docs/platform/AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md` §2/§5 (non-binding, Tier 5 per
`docs/DOCUMENT_INDEX.md`) restates ADR-003's three roles unchanged, and its §7 classifies "Production
security model (Phase 3's enforcement design)" as **requiring its own ADR** — this document is that
ADR, deliberately scoped to far less than a full "production security model."

**`Product.entitlement_required` is not what `has_access()` is ever actually called with.**
`navigation_builder.py:45` and `shell_builder.py:31` both call
`entitlement_checker.has_access(user, product.product_id)` — the lowercase, hyphen-free registry key
(`"trading_intelligence"`), never `product.entitlement_required` (the separate, uppercase
`"TRADING_INTELLIGENCE"` descriptive string). §2.1 below authorizes a checker keyed on `product_id`
for exactly this reason: it is the only field either builder ever passes to `has_access()`.
`entitlement_required` remains present on `Product` but is not read by any code this ADR authorizes
— it is pre-existing, unconsumed descriptive metadata, not an input this checker or either builder
acts on.

**The boundary that governs where a Trading-Intelligence-specific class may live is already
enforced by a passing test.** `applications/platform/tests/test_platform_structure.py:57-67`
asserts every production file under `applications/platform/` forbids importing
`applications.trading_intelligence` or `applications.wealth_intelligence` — the platform layer must
never know a product's internals. `applications/trading_intelligence/tests/
test_package_imports.py:43-44` forbids only `bot`, `dashboard`, `scheduler`, `database`, `ledger` —
`applications.platform` is not forbidden, and ADR-029/032 already established, in real (not
test-only) code, that Trading Intelligence importing `applications.platform.*` is legal. The
dependency direction is therefore one-way: products may depend on platform; platform, and sibling
products, must never be depended on in the other direction. A concrete `EntitlementChecker` scoped
to one product's own entitlement rule cannot legally live under `applications/platform/entitlements/`
without violating that boundary the moment it needs to know Trading-Intelligence-specific facts (its
`product_id` string) as anything more than an opaque parameter — it belongs in
`applications/trading_intelligence/`, constructed by that product's own composition root.

**Current authentication is a deterministic no-op.** ADR-029 §5 and ADR-032 §1 both already state
`SupabaseAuthenticationProvider.get_current_user()` always returns `None` in this build
(`_NoOpSupabaseClient.get_user()`, `bootstrap.py:96-97`, unconditionally). `NavigationBuilder.
build()` (`navigation_builder.py:39-41`) and `ShellBuilder.build()` (`shell_builder.py:24-26`) both
check `if user is None` and return an empty model **before** either ever calls
`entitlement_checker.has_access(...)`. Any `EntitlementChecker` wired through this path today is
therefore provably unreachable code in production, not merely untested — the same honesty
disclosure ADR-029 §5/ADR-032 §1 already made for their own layers, one layer deeper.

**`NavigationBuilder.build()` resolves its own user internally — it does not accept an
already-resolved one.** `navigation_builder.py:38-39` shows `build()` takes no arguments and its
first line is `user = self._auth_provider.get_current_user()`; the constructor
(`navigation_builder.py:26-32`) accepts an `auth_provider: AuthenticationProvider`, not an
`Optional[User]`. There is no parameter on either the constructor or `build()` through which
`bootstrap.py`'s own already-captured `current_user` (`bootstrap.py:226`) could be handed in
directly — the existing contract offers exactly one way to get a user into a `NavigationModel`:
give `NavigationBuilder` an `AuthenticationProvider` and let it call `.get_current_user()` itself.
Passing it the same `SupabaseAuthenticationProvider` instance ADR-029 §2.1 constructs would make
`build_application()` responsible for two calls to `.get_current_user()` on that one instance in a
single invocation — the existing direct call at `bootstrap.py:226`, plus the one `build()` makes
internally — which would violate ADR-029 §2.2's "exactly once" constraint on that provider instance.
§2.2 below resolves this within `NavigationBuilder`'s existing, unmodified contract: `bootstrap.py`
constructs a second, local `AuthenticationProvider` implementation whose `get_current_user()`
returns the already-captured `current_user` value directly, with no lookup of its own, and passes
*that* object to `NavigationBuilder` instead of the real provider. `NavigationBuilder` still calls
`.get_current_user()` exactly once, on the object it was given — satisfying its contract exactly as
written — but zero additional calls reach the `SupabaseAuthenticationProvider` instance ADR-029 §2.2
governs, so that clause's "exactly once" count is preserved, not merely disclosed as violated.

**Three explicit non-authorizations currently block this work**, each naming it as deferred, future,
separately-scoped work:

- **ADR-029 §3**: "Any entitlement or authorization enforcement — `EntitlementChecker`,
  `NavigationBuilder`, and any gating of UI/data access by identity remain unauthorized; ADR-003
  remains a recorded requirement only."
- **ADR-032 §5**: "Any `EntitlementChecker` implementation, or any entitlement/authorization
  enforcement."
- **ADR-033 §5**: the identical clause, for Wealth Intelligence — **this ADR does not touch it.**

## 2. Decision

This ADR authorizes exactly three things, scoped to **Trading Intelligence only**:

### 2.1 A concrete `EntitlementChecker` for Trading Intelligence

A new class, `applications/trading_intelligence/entitlements.py`
(`TradingIntelligenceEntitlementChecker(EntitlementChecker)`), implementing exactly ADR-003's
Trading-Intelligence-User rule and no other:

- `has_access(user: User, product_id: str) -> bool` returns `True` **only** if
  `product_id == "trading_intelligence"` **and** `user.user_id` is present in an explicit grant
  collection supplied at construction time (constructor-injected `Set[str]` of entitled
  `user_id`s, defaulting to an empty set). Every other input — any other `product_id`, including
  `"wealth_intelligence"`; any user not in the grant set — returns `False`. Fail-closed by
  construction, not by convention.
- The `product_id` parameter this method compares against is `Product.product_id` (the registry
  key both builders already pass — `navigation_builder.py:45`, `shell_builder.py:31`), **not**
  `Product.entitlement_required`. This class must not read, compare against, or otherwise consume
  `entitlement_required` — see §1's finding that no authorized code path ever passes it to
  `has_access()`.
- This is the identical shape already proven, repeatedly, by every existing test fake for this
  interface (`test_entitlement_checker.py:8-16`, and the fakes in `test_navigation_builder.py`/
  `test_shell_builder.py`/`test_trading_intelligence_product_integration.py:102-107`) — promoted
  from test-only to a real, importable production class. No new rule shape is invented.
- Implements no `Role`, `Entitlement`, or enum type. Does not read, infer, or derive anything from
  `user.display_name`. Does not implement Wealth Intelligence or AARA Super User semantics — those
  are simply never reachable through this class, because it only ever evaluates one hardcoded
  `product_id`.
- Lives in `applications/trading_intelligence/`, not `applications/platform/entitlements/`, per §1's
  boundary finding: it is a Trading-Intelligence-owned policy, not a platform-generic one.

### 2.2 Product-local registries and `NavigationBuilder` construction in `bootstrap.py`

In `applications/trading_intelligence/bootstrap.py`'s `build_application()`:

1. Construct one fresh, process-local, in-memory `ProductRegistry` implementation and one fresh,
   process-local, in-memory `WorkspaceRegistry` implementation — new private classes local to this
   file, mirroring the existing `_InMemoryLedgerStore`/`_InMemoryProjectionRepository` per-call,
   non-durable pattern already established in the same file (`bootstrap.py:70-89`). Not shared, not
   a singleton, not module-level.
2. Register **only** the already-existing `TRADING_INTELLIGENCE_PRODUCT` and
   `DECISION_CENTER_WORKSPACE` descriptors from `applications/trading_intelligence/product.py`. No
   new `Product` or `Workspace` value is created. No import of `applications.wealth_intelligence`,
   directly or indirectly, is introduced anywhere.
3. Construct one `TradingIntelligenceEntitlementChecker` (§2.1).
4. Construct one new, local `AuthenticationProvider` implementation — a small private class local
   to `bootstrap.py` (e.g. `_ResolvedUserAuthenticationProvider`), constructor-injected with the
   already-captured `current_user` value (`bootstrap.py:226`), whose `get_current_user()` returns
   that value directly and performs no lookup, network call, or re-invocation of the real
   `SupabaseAuthenticationProvider` of any kind. This is the existing `AuthenticationProvider`
   interface (`identity/authentication_provider.py`, unmodified — see §5), given a second
   *conforming implementation*, not a new API. Construct exactly one `NavigationBuilder`, using the
   registries and checker above plus **this** wrapper — never the real `SupabaseAuthenticationProvider`
   instance itself. See §1's finding: this is required, not stylistic, to keep ADR-029 §2.2's
   "exactly once" call count on the real provider intact.
5. `ShellBuilder` construction is **not** authorized by this ADR. `NavigationBuilder` is the
   workspace-granular successor (`navigation/README.md:31-34`), already proven against Trading
   Intelligence's real descriptors by `test_trading_intelligence_product_integration.py`, and is the
   only builder in this codebase on any path to a real presentation model (§1's `ShellPresenter`
   finding); wiring the older, coarser, unconsumed `ShellBuilder` as well would duplicate this same
   authorization for no additional capability and is left to its own future ADR if ever needed.

### 2.3 Confinement of the result

The resulting `NavigationModel` is retained only as a local value inside `build_application()`. It
is never passed to `DecisionCenterController`, `DecisionCenterUI`, any `sentinel_engine` object, or
returned from `build_application()` — identical confinement discipline to ADR-029 §2.4 and ADR-032
§2 item 6, applied one layer further. `build_application()`'s return type
(`DecisionCenterUI`) and observable behavior are unchanged by this ADR. This is the smallest
possible legal behavior: construct and call, do not propagate or render.

The `_ResolvedUserAuthenticationProvider` wrapper (§2.2 item 4) is equally confined: constructed
and passed only to the one `NavigationBuilder` built in this function, never returned, never passed
to any other collaborator, and never constructed anywhere outside `build_application()`.

## 3. Explicit Acknowledgment: Enforcement Is Currently Inert

Per §1's trace: because `SupabaseAuthenticationProvider.get_current_user()` deterministically
returns `None` today (ADR-029 §5, ADR-032 §1, unchanged by this ADR), `NavigationBuilder.build()`
always takes its `if user is None` branch and returns before ever calling
`TradingIntelligenceEntitlementChecker.has_access(...)`. **This ADR's entire authorization —
including the new concrete `EntitlementChecker` — has zero observable effect in the current build
and cannot be exercised by any real request until a future, separately-scoped ADR authorizes real
Supabase credentials** (still withheld by ADR-028 §3, ADR-029 §3, ADR-032/033's own placeholder
clauses, all unchanged here). This is stated explicitly, not left implicit, matching this
repository's established practice (ADR-029 §5, ADR-032 §1/§6) of disclosing a wiring's inertness
rather than letting acceptance be read as a claim of working enforcement.

## 4. Explicit Authorization / ADR Reconciliation

This ADR narrowly lifts exactly the following clauses — no other clause of ADR-003, ADR-029,
ADR-032, or ADR-033 is altered, reopened, or reinterpreted:

- **ADR-029 §3**'s "Any entitlement or authorization enforcement — `EntitlementChecker`,
  `NavigationBuilder`, and any gating of UI/data access by identity remain unauthorized" is lifted
  to the extent, and only to the extent, of §2 above: one concrete `EntitlementChecker` class, one
  `NavigationBuilder` construction, both confined per §2.3, both scoped to Trading Intelligence only.
  "Any gating of UI/data access by identity" remains unauthorized — this ADR gates nothing; §2.3
  guarantees the result is never consumed.
- **ADR-032 §5**'s "Any `EntitlementChecker` implementation, or any entitlement/authorization
  enforcement" is lifted identically, for Trading Intelligence only.
- **ADR-029 §2.2 is preserved exactly and is not lifted, touched, or reinterpreted.**
  `build_application()` still calls `.get_current_user()` on the `SupabaseAuthenticationProvider`
  instance exactly once, at `bootstrap.py:226`, unchanged by this ADR. §2.2 item 4's
  `_ResolvedUserAuthenticationProvider` wrapper is a second, distinct `AuthenticationProvider`
  *implementation*, not a second call on the provider ADR-029 §2.2 governs — `NavigationBuilder`
  calling `.get_current_user()` on the wrapper does not count against, and is not the same event as,
  a call on the real provider. This ADR would be malformed without this clause: absent it, §2.2 item
  4 as literally written would require a second real call and directly conflict with an Accepted
  ADR clause this ADR does not otherwise touch.
- **ADR-003** remains a recorded requirement, not advanced beyond the one-role slice §2.1
  implements. Its "Explicitly Not Done By This ADR" clause ("No authentication implementation... No
  authorization middleware") is unaffected — §2.1's class is not authorization middleware; nothing
  in this codebase calls it from a request path, because no request path exists.
- **ADR-033 §5** is **not** lifted. Wealth Intelligence's identical non-authorization clause remains
  fully in force (see §5 below).

## 5. Explicit Non-Authorization

This ADR authorizes exactly §2's three points. It does not authorize:

- **Any Wealth Intelligence change of any kind.** `applications/wealth_intelligence/bootstrap.py`
  is untouched. ADR-033 §5's `EntitlementChecker` non-authorization remains in force, unlifted.
- **Any real permissions engine, database, or persistence mechanism.** The grant set in §2.1 is a
  constructor-injected, in-memory value, defaulting to empty — matching `entitlements/
  README.md:15-17`'s "does not implement *how* access is decided... that is a real permissions
  engine, explicitly not built here."
- **Any `Role`, `Entitlement`, `SUPER_USER`, or new identity/access type of any kind.** `User`
  (`identity/user.py`) is not modified and is not read for any field beyond `user_id`.
- **Any change to `NavigationBuilder`, `ShellBuilder`, `User`, `Principal`, `PrincipalRegistry`,
  `AuthenticationProvider`, `SupabaseAuthenticationProvider`, `ProductRegistry`, or
  `WorkspaceRegistry` themselves** — all five interfaces and both concrete identity classes are
  used exactly as they exist today; none is edited. §2.2 item 4's
  `_ResolvedUserAuthenticationProvider` is a new, additional conforming implementation of the
  unmodified `AuthenticationProvider` interface, the same relationship
  `TradingIntelligenceEntitlementChecker` (§2.1) has to `EntitlementChecker` — not an edit to
  `AuthenticationProvider` or to `SupabaseAuthenticationProvider`.
- **Any second call to `.get_current_user()` on the real `SupabaseAuthenticationProvider`
  instance.** ADR-029 §2.2's "exactly once" count on that specific instance is preserved without
  exception — see §4. `NavigationBuilder` is never given that instance; it is given only the local
  wrapper described in §2.2 item 4.
- **`ShellBuilder` construction or wiring** — see §2.2 item 5.
- **Any change to `applications/platform/entitlements/entitlement_checker.py`,
  `applications/platform/registry/product_registry.py`, or `applications/platform/workspaces/
  workspace_registry.py`** — the abstract contracts are unchanged; only a new conforming
  implementation is added, in `applications/trading_intelligence/`.
- **Any UI, rendering, or `gradio_view.py` change.** §2.3 guarantees the `NavigationModel` never
  reaches any UI-layer object.
- **Any real Supabase credential, session, or login flow.** Still governed entirely by ADR-028 §3/
  ADR-029 §3's continuing prohibition, unchanged.
- **Any `principal_id`, `Principal`, or `PrincipalRegistry` involvement.** This ADR's wiring is
  independent of ADR-032's; neither reads the other's local value.
- **Any change to `sentinel_engine/`, `database/`, `ledger/`, `bot/`, `dashboard/`, or `scheduler/`.**
- **Any new dependency.**
- **Any `applications/platform/bootstrap.py` or platform-wide composition root.** None is created;
  none is assumed to exist. If a true multi-product `NavigationModel` (showing both products
  together) is ever wanted, that is its own, separately-scoped future ADR — this ADR's
  `ProductRegistry`/`WorkspaceRegistry` instances are Trading-Intelligence-local and see only
  Trading Intelligence's own two descriptors.

## 6. Test Scope

`applications/trading_intelligence/tests/test_entitlements.py` (new):

- `TradingIntelligenceEntitlementChecker` cannot be instantiated missing `has_access` (inherited
  ABC guarantee — mirrors `test_entitlement_checker.py:23-25`).
- `has_access(user, "trading_intelligence")` is `False` for a `user_id` not in the grant set
  (default-deny).
- `has_access(user, "trading_intelligence")` is `True` for a `user_id` explicitly passed in the
  grant set at construction.
- `has_access(user, "wealth_intelligence")` is `False` regardless of grants — proves the hardcoded
  product scope, not an accidental pass-through.
- `has_access(user, "trading_intelligence")` is `False` when the checker is constructed with no
  grant set argument (empty-default fail-closed).

`applications/trading_intelligence/tests/test_bootstrap_navigation_wiring.py` (new, mirrors
`test_bootstrap_authentication.py`/`test_bootstrap_principal_mapping.py`'s structure):

- `build_application()` constructs exactly one `ProductRegistry`, one `WorkspaceRegistry`, one
  `TradingIntelligenceEntitlementChecker`, and one `NavigationBuilder`.
- The constructed `ProductRegistry.list_products()` contains exactly `TRADING_INTELLIGENCE_PRODUCT`
  — nothing else, no Wealth Intelligence descriptor.
- With `get_current_user()` at its real, current behavior (`None`), the resulting `NavigationModel`
  is never passed to `DecisionCenterController` or `DecisionCenterUI` — reuses the existing
  4-positional-args/0-kwargs assertion pattern from `test_bootstrap_authentication.py`.
- `build_application()`'s return value is unchanged in shape and behavior from before this ADR
  (same assertion style as ADR-029 §4/ADR-032 §4's own regression checks).
- **`.get_current_user()` is called exactly once on the real `SupabaseAuthenticationProvider`
  instance per `build_application()` invocation** — reuses
  `test_bootstrap_authentication.py`'s existing call-counting pattern
  (`test_build_application_calls_get_current_user_exactly_once`), asserted again after this ADR's
  change to prove ADR-029 §2.2 still holds with `NavigationBuilder` wired in, not merely assumed
  from §4's reasoning.
- `_ResolvedUserAuthenticationProvider.get_current_user()` returns the same `current_user` value
  `build_application()` already captured at `bootstrap.py:226`, without querying
  `SupabaseAuthenticationProvider` or its client again — proves the wrapper is a pure pass-through,
  not a second resolution path.

`applications/trading_intelligence/tests/test_package_imports.py`'s existing `_SUBPACKAGES` list
(currently ending at `"applications.trading_intelligence.services.decision_governance_query_service"`,
`test_package_imports.py:15-35`) gains one entry: `"applications.trading_intelligence.entitlements"`
— the same clean-import coverage every other production submodule in this list already has. No
change to the list's existing entries or to `test_no_module_imports_forbidden_runtimes`'s
forbidden-prefix scan, which already covers this new file automatically (it scans every `.py` file
under the package root, not a maintained list).

Full existing suite re-run: `applications/platform/tests/`, `applications/trading_intelligence/
tests/` — zero regressions required. `applications/wealth_intelligence/tests/` re-run as a sanity
check confirming zero change, even though not touched.

## 7. Verification

- Confirm `applications/platform/tests/test_platform_structure.py`'s forbidden-import scan and
  `applications/trading_intelligence/tests/test_package_imports.py`'s
  `test_no_module_imports_forbidden_runtimes` scan both pass with **zero change to their
  assertion logic** — this ADR relies on the existing import boundary (`applications.platform`
  legal for Trading Intelligence; `applications.trading_intelligence`/`applications.wealth_intelligence`
  forbidden for the platform layer) already being correct, not on relaxing either scan.
  `test_package_imports.py`'s separate `_SUBPACKAGES` list gains one additive entry per §6 — a
  coverage extension, not a loosening of either forbidden-import rule.
- Confirm, via a dedicated assertion (§6), that `entitlement_checker.has_access(...)` is never
  actually invoked when `get_current_user()` returns `None` in the real composition path — proving
  §3's inertness claim rather than assuming it.
- Confirm, via the dedicated assertion in §6, that `.get_current_user()` is still called exactly
  once on the real `SupabaseAuthenticationProvider` instance — proving ADR-029 §2.2 holds with
  `NavigationBuilder` wired in, per §4's reconciliation.
- `scripts/arch_review.py --diff` clean on the new file and the `bootstrap.py` diff.
- Rollback: revert the `entitlements.py` addition and the `bootstrap.py` diff. No data, schema, or
  deployment rollback required — nothing durable is written by this ADR's authorization.

## 8. Consequences

**Positive:**

- Closes the specific gap ADR-029 §3 and ADR-032 §5 each separately named as deferred, using the
  narrowest possible authorization: one class, one product, one composition point, zero shared
  platform state.
- Gives `NavigationBuilder` — fully built and tested since Phase 4H/4I but never constructed in
  production — its first real, non-test caller, without requiring a platform composition root that
  does not exist and that this ADR does not invent.
- Keeps `sentinel_engine`, `database`, `bot/`, Wealth Intelligence, `Role`/`Entitlement`, `ShellBuilder`,
  and any real permissions engine completely untouched, continuing this repository's
  one-slice-per-ADR pattern (ADR-027 → 028 → 029 → 030 → 031 → 032 → 033 → this ADR).
- Preserves ADR-029 §2.2's "exactly once" call count on the real `SupabaseAuthenticationProvider`
  instance by construction (§2.2 item 4's wrapper), not by convention or disclosure alone — closing
  a conflict identified during this ADR's own acceptance audit before acceptance, rather than
  leaving a latent double-call defect to surface only once a future ADR wires real credentials.

**Negative / Open Risk — stated explicitly to avoid overclaiming:**

- **This authorization has zero observable effect today** (§3) — it proves the class/construction/
  invocation edge is legal and non-crashing, not that entitlement enforcement works.
- Trading Intelligence's `ProductRegistry`/`WorkspaceRegistry` instances see only their own
  product — this is not a platform-wide navigation view, and this ADR does not claim to be one.
- The grant set backing `TradingIntelligenceEntitlementChecker` has no real data source; until a
  future ADR authorizes one, it is either empty or manually seeded, matching every other
  process-local placeholder already accepted at this composition root (`_InMemoryLedgerStore`,
  `_InMemoryProjectionRepository`, `PrincipalRegistry`).
- Still does not complete the identity/access story: real credential provisioning, a real
  permissions engine, `Role`/`Entitlement` types, `ShellBuilder` wiring, a platform-wide composition
  root, and Wealth Intelligence's equivalent wiring all remain open, each its own future work.

## 9. Status

**Accepted.** This ADR authorizes only what is stated in §2 — acceptance does not retroactively
authorize anything listed in §5, and does not reopen any clause of ADR-003, ADR-029, ADR-032, or
ADR-033 beyond the two narrow lifts named in §4.
