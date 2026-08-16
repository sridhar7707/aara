# ADR-031: In-Memory Principal Allocator (PrincipalRegistry, Process-Local Only)

**Status:** Accepted
**Date:** 2026-08-15
**Decision Type:** Implementation Authorization — In-Memory Placeholder Only (follows ADR-004's
"backend-neutral, in-memory placeholder" precedent)
**Related ADRs:** ADR-030 (named `Principal(principal_id: str)`, shape only, no implementation —
this ADR builds exactly that shape plus an in-memory allocator, nothing more), ADR-027 (§4:
`principal_id` must never derive from a Supabase identifier, directly or indirectly — preserved by
construction, see §1/§2), ADR-004 (precedent: `LedgerStore`/`ProjectionRepository` kept
backend-neutral via in-memory placeholders, "not a production persistence choice," until Phase 1A
closes and a real backend decision is made — this ADR follows the identical pattern for
`Principal`), ADR-029 (built and wired `SupabaseAuthenticationProvider` into Trading Intelligence's
`bootstrap.py` only — this ADR does not touch that wiring or extend it), ADR-002 (`database/`,
`bot/`, `ledger/`, `dashboard/`, `scheduler/`, `.github/workflows/*.yml` remain frozen; untouched
by this ADR)

---

## 1. Context

ADR-030 named `Principal(principal_id: str)` as a shape only — no file, no implementation, no
allocation mechanism. A read-only audit (this session) confirmed:

- `str(uuid.uuid4())` is the repository's own established idiom for generating AARA-owned,
  externally-independent identifiers — used for `event_id` in
  `sentinel_engine/services/decision_service.py:30` and four other `sentinel_engine`
  adapters/services. The same mechanism is directly reusable for `principal_id`, satisfying ADR-027
  §4's requirement that durable identifiers never derive from a Supabase identifier, directly or
  indirectly: a `uuid4()` value has no mathematical or structural relationship to any input at all.
- `applications/platform/identity/` holds `user.py`, `authentication_provider.py`,
  `supabase_authentication_provider.py` — no `principal.py` yet. This ADR's target module does not
  exist.
- ADR-004 keeps `LedgerStore`/`ProjectionRepository` backend-neutral via documented in-memory
  placeholders ("minimal in-memory placeholders, not a production persistence choice"), deferring
  any real backend decision until Phase 1A's 30-day validation window closes (**2026-08-27**; today
  is 2026-08-15, 12 days out) and until a second product's consumption pattern is clearer. This ADR
  follows that exact precedent for `Principal`: build the shape and an in-memory allocator now,
  defer any durable-store decision to its own future ADR, informed by — though not bound by, since
  ADR-004's text scopes only to `sentinel_engine/ledger/` — the same precedent.
- `applications/platform/tests/test_platform_structure.py`'s forbidden-import scan (`bot`,
  `dashboard`, `scheduler`, `database`, `ledger`, and every product package) already passes for any
  module under `applications/platform/identity/` that imports none of those — a `principal.py`
  importing only `dataclasses`/`uuid` satisfies this without any test change.
- `applications/platform/tests/` follows a flat, one-file-per-module convention
  (`test_user.py`, `test_authentication_provider.py`, `test_supabase_authentication_provider.py`) —
  `test_principal.py` follows the same pattern.

## 2. Decision

### 2.1 New module: `applications/platform/identity/principal.py`

```python
@dataclass(frozen=True)
class Principal:
    principal_id: str


class PrincipalRegistry:
    def __init__(self) -> None: ...
    def get_or_create(self, key: str) -> Principal: ...
```

- `Principal` is exactly the one field ADR-030 §2 named. No other field is added.
- `PrincipalRegistry.get_or_create(key)` allocates `principal_id` via `str(uuid.uuid4())` — the
  repository's own established idiom (§1) — the first time a given `key` is seen by a given
  registry instance, and returns the identical `Principal` (same object, not merely an equal one)
  for that same `key` on every subsequent call to the same instance.
- **`key` is completely opaque to this module.** `PrincipalRegistry` must not inspect, parse,
  derive from, transform, log, or persist `key` in any way beyond using it as a lookup key in its
  own in-memory mapping. This module must not import `User` (`applications/platform/identity/user.py`)
  or `AuthenticationProvider` — deciding what `key` is, and whether it is ever derived from a
  `User`, is a caller's decision this ADR does not make, matching ADR-030 §3's own deferral of
  "any mapping, association, or allocation logic between `User` and `Principal`." This module
  contains no logic connecting `User` and `Principal` in any form — `User` is never imported,
  referenced, or reachable from it. ADR-030 §3's prohibition on "mapping, association, or
  allocation logic between `User` and `Principal`" therefore does not describe anything this module
  does: `get_or_create(key)` allocates a `Principal` for an opaque key with no established,
  assumed, or implied relationship to `User`. ADR-030 remains fully intact and unmodified by this
  ADR; this ADR simply does not touch the ground ADR-030 §3 covers.

### 2.2 Process-local only, no durability claim

`PrincipalRegistry`'s internal state exists only for the lifetime of one Python instance. A newly
constructed `PrincipalRegistry` holds no state from any prior instance, this process's prior runs,
or any other process. This ADR makes no idempotency claim across process restarts, deployments, or
separate registry instances — mirroring ADR-004's own framing of `_InMemoryLedgerStore` as "not a
production persistence choice."

### 2.3 Unwired

Nothing in this ADR constructs or calls `PrincipalRegistry` from any `bootstrap.py`, any product
code, or any other production call site. It is buildable and testable in isolation, exactly as
`AuthenticationProvider`/`SupabaseAuthenticationProvider` were before ADR-029 wired the latter.

## 3. Explicit Non-Authorization

This ADR authorizes exactly `principal.py`'s two classes above, and `test_principal.py`. It does
not authorize:

- Any persistence, database, or durable-storage mechanism of any kind for `Principal` — the
  in-memory mapping inside `PrincipalRegistry` is the only storage this ADR authorizes, and it is
  explicitly non-durable (§2.2).
- Any wiring of `PrincipalRegistry` into `applications/trading_intelligence/bootstrap.py`,
  `applications/wealth_intelligence/bootstrap.py`, or any other production call site.
- Any `Role` or SUPER_USER abstraction, implementation, or field.
- Any `EntitlementChecker` implementation, or any entitlement/authorization enforcement.
- Any Wealth Intelligence change of any kind — untouched.
- Any `sentinel_engine/` change of any kind, including the `principal_id` ledger field named in
  ADR-027 §3/§4, which remains its own, separately-scoped future ADR.
- Any `ledger/`, `bot/`, `database/`, or Capital Pool change — all remain exactly as ADR-002
  protects them.
- Any login flow, session-acquisition mechanism, token issuance/refresh, or MFA implementation.
- Any FastAPI, HTTP, or API/session-layer infrastructure.
- Any change to `User`, `AuthenticationProvider`, `SupabaseAuthenticationProvider`, or either
  product's `bootstrap.py` — all remain exactly as ADR-027/028/029 left them.
- Any real/durable persistence decision for `Principal` — remains separately deferred; ADR-004's
  Phase 1A closure and consumption-clarity criteria are relevant precedent for that future decision
  but are not binding requirements of ADR-004 outside `sentinel_engine/ledger/`. ADR-002's lifting
  checklist remains binding if `database/` is ever selected as the target.
- Any new dependency — `uuid` is Python standard library, already used elsewhere in the repo.

## 4. Test Scope

`applications/platform/tests/test_principal.py`, mirroring the existing one-file-per-module
convention:

- `Principal` is a frozen dataclass with exactly one field, `principal_id`.
- `get_or_create(key)` returns a `Principal` with a non-empty `principal_id`.
- The same `key`, called twice on the same `PrincipalRegistry` instance, returns the identical
  `Principal` object (`is`, not just `==`).
- Two different `key`s, on the same instance, return two different `principal_id`s.
- A newly constructed `PrincipalRegistry` holds no state from a prior instance — constructing a
  second registry and calling `get_or_create` with a `key` already used on a first registry
  produces a *different* `principal_id`, proving non-durability explicitly rather than by absence
  of a store.
- No test constructs or calls `principal.py` from any `bootstrap.py` or product code.

## 5. Relationship to ADR-004 and ADR-030

This ADR does not resolve ADR-004 (still deferred) or ADR-027 §7 item 2 (`Principal`
persistence/schema, still deferred). It implements exactly the shape ADR-030 named, using the
in-memory-placeholder pattern ADR-004 already established as this repository's standard way to
keep architecture options open at zero sunk cost. A future ADR choosing a durable backend for
`Principal` — informed by ADR-004's closure criteria as precedent (ADR-004 itself binds only
`sentinel_engine/ledger/`), and bound by ADR-002's lifting checklist if `database/` is ever the
target — replaces `PrincipalRegistry`'s internals without requiring any change to `Principal`'s
shape or to any caller, exactly as ADR-004 §Consequences describes for `LedgerStore`. This ADR's
test scope (§4) supersedes ADR-030 §3's note limiting any future minimal step to "confirm[ing] the
dataclass itself is well-formed" — that note bounded ADR-030's own authorization, not any later
ADR's; this ADR is the separately-scoped future authorization ADR-030 anticipated, and it
authorizes `PrincipalRegistry`'s full behavioral test coverage as stated in §4, not field-
well-formedness checks alone.

## 6. Consequences

**Positive:**

- Gives `Principal` its first working (if deliberately inert) implementation, directly reusable by
  a future wiring ADR without inventing an allocation mechanism at that time.
- Reuses this repository's own established `uuid4()` idiom rather than introducing a new one,
  keeping `principal_id` structurally independent of any external identifier by construction, not
  by convention alone (no `User` import is even possible to violate).
- Keeps `sentinel_engine`, `database`, `bot/`, Wealth Intelligence, `Role`, and enforcement fully
  untouched, matching every prior ADR in this chain (ADR-027 → 028 → 029 → 030 → this ADR).

**Negative / Open Risk:**

- Provides no durability and no cross-process idempotency — a `Principal` allocated in one process
  run is unrecoverable once that `PrincipalRegistry` instance is gone. This is a known, explicitly
  stated limitation (§2.2), not an oversight.
- Does not advance SUPER_USER, entitlement enforcement, Wealth Intelligence, or Capital Pool
  authorization — each remains blocked behind its own future ADR, unchanged by this one.

## 7. Status

**Accepted.** This ADR authorizes only what is stated in §2 — acceptance does not retroactively
authorize anything listed in §3.
