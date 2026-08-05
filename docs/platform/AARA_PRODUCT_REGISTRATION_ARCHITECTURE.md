# AARA Product Registration Architecture

**Status:** Registration architecture — Phase 4D. Documentation only. No code
was implemented. `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`,
`database/`, `ledger/`, `sentinel_engine/` untouched, confirmed via `git
status` before and after.

**Authority:** `AARA_PLATFORM_SHELL_ARCHITECTURE.md`,
`AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md`, ADR-003,
`AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md`.

---

## 1. Product Registration Purpose

`AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 4 requires the shell to know
"which products exist, their names... a registry-level knowledge" while
explicitly forbidding it from knowing "trading logic... wealth calculations...
Sentinel internals." Registration is the mechanism that makes both halves of
that rule simultaneously true: a product declares itself through a data-only
descriptor rather than the shell importing the product's code to find out
what it is. Discovery (the shell asking "what products exist") stays entirely
decoupled from coupling (the shell depending on any product's implementation).

## 2. Product Descriptor Model

Future metadata — **not implemented**. Broader than the `Product` dataclass
already built in `applications/platform/registry/product_registry.py`
(`product_id`, `name` only) — stated explicitly, not glossed over as the same
thing:

| Field | Purpose |
|---|---|
| `product_id` | Stable identifier (e.g. `trading_intelligence`), matching the already-established package/directory naming convention |
| `display_name` | Human-readable name for the shell's product switcher |
| `description` | Short text for the switcher/onboarding, not a full product spec |
| `entitlement_required` | The entitlement code gating access — distinct from `product_id` (see Section 5's naming note) |
| `workspace_routes` | The top-level entry points the shell routes to — the curated subset from `AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 2, not a product's full internal screen list |
| `status` | Platform-facing lifecycle state (e.g. active / in development / coming soon) — exact vocabulary not decided, see Section 7 |

## 3. Ownership Boundaries

**Platform owns:**
- Registry — `ProductRegistry` (already built as an interface,
  `applications/platform/registry/`).
- Discovery — the shell querying the registry to render the switcher.
- Access checks — `EntitlementChecker` (already built as an interface,
  `applications/platform/entitlements/`).

**Products own:**
- Features, screens (`applications/trading_intelligence/ui/`, and any future
  product's own `ui/`).
- Business logic (`services/`, `adapters/` — product-internal).
- Data (each product's own contracts/projections).

This is unchanged from `AARA_TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md`'s
ownership split and `AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 3 — this
document applies it specifically to registration, not a new boundary.

## 4. Registration Flow

```
Product
   (e.g. applications/trading_intelligence/ -- not yet emitting a descriptor)
        |
        v
Product Descriptor
   (Section 2's model -- not implemented anywhere yet)
        |
        v
Product Registry
   (ProductRegistry.register() -- interface exists, no concrete
    implementation, no product has ever called it)
        |
        v
Platform Shell
   (ProductRegistry.list_products() -- would drive the switcher; the shell
    itself is still interfaces-only, per AARA_PLATFORM_SHELL_ARCHITECTURE.md
    Phase 1)
```

Every stage above is either not yet built or, where an interface exists
(`ProductRegistry`), not yet exercised by any real product.

## 5. Trading Intelligence Example (Registration Only — Not Implemented)

```
product_id: trading_intelligence
entitlement_required: TRADING_INTELLIGENCE
```

**Naming note, stated rather than left ambiguous:** `entitlement_required`
uses upper-snake-case (`TRADING_INTELLIGENCE`) — a distinct entitlement *code*
— while `product_id` uses lower-snake-case (`trading_intelligence`), matching
the string already used in `applications/platform/tests/test_entitlement_checker.py`'s
examples and the actual package directory name. These are deliberately two
different identifiers for two different concerns (which package this is, vs.
which entitlement code gates it), not a typo or inconsistency.

No `descriptor.py`, no registration call, no code of any kind was added to
`applications/trading_intelligence/` to produce this example. It illustrates
the shape Section 2 describes; it does not create it.

## 6. Future Products

Per `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`'s Long-Term Expansion
section — each would eventually submit its own descriptor the same way:

- Wealth Intelligence (Product #2 — already has a product architecture
  document; no descriptor, no code)
- CFO Intelligence
- Tax Intelligence
- Estate Intelligence
- Retirement Intelligence

None of these has a registry entry, a descriptor, or any implementation
anywhere in this codebase.

## 7. Open Decisions

Not resolved by this document:

- **Plugin architecture** — is registration static (a hardcoded list the
  platform ships with) or dynamic (products self-register at startup,
  plugin-style)? Not decided.
- **Deployment model** — restates, does not resolve,
  `AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 6's already-open "deployment
  architecture" item.
- **Microservices vs. monolith** — new question, not raised in any prior
  document: does each product run as a separately deployable service, or do
  all products run in one process? Not decided.
- **Frontend routing** — restates, does not resolve, that same document's
  "frontend framework" open item — routing mechanics depend on a framework
  choice that hasn't been made.

---

## Constraints Confirmed

No code was implemented. No protected path was touched.
