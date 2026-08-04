# Platform Entitlements

**Status:** Abstract contract only. No permissions engine, no database.

## What this is

`EntitlementChecker` (`entitlement_checker.py`) — the product access check
interface: `has_access(user: User, product_id: str) -> bool`. Products are
referenced by a plain string id, not by importing anything from `registry/`
or a product package — keeps this module decoupled from `registry/`'s
internal `Product` shape and from any product's code.

This defines *what* an access check looks like — "what users can see," per
`docs/platform/AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md` Section 5.
It does not implement *how* access is decided (no rules, no backend
permission logic) — that is a real permissions engine, explicitly not built
here.

## Dependency rules

May import `identity/` (needs `User` to check access for). Must not know
Trading Intelligence services, Wealth Intelligence services, Sentinel Engine,
`bot`, or `dashboard`. Checked in `../tests/test_platform_structure.py`.
