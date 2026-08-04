# ADR-003: AARA Identity and Product Access Model

**Status:** Accepted Requirement — Implementation Deferred
**Date:** 2026-08-04

## Context

AARA is evolving into a multi-product intelligence platform, per
`AARA_ARCHITECTURE_AUTHORITY.md`'s Product Model and `CODEBASE_MIGRATION_MATRIX.md`:

- **Product #1 — Trading Intelligence**
- **Product #2 — Wealth Intelligence**
- Future products may exist under the AARA platform (per
  `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`'s Long-Term Expansion section:
  Aara CFO, Aara Tax, Aara Estate, Aara Retirement Intelligence).

A multi-product platform needs an eventual answer to "which products can this user
access," but no such model exists today, and none of the current single-user,
single-product implementation work (`sentinel_engine/`, the Trading Intelligence
boundary/event-model docs) has needed one. This ADR captures the requirement now,
while product boundaries are still being defined, so it isn't rediscovered or
redesigned inconsistently later — without building anything.

## Decision

AARA will support product-level access control where users can access one or more
AARA products.

### Initial roles

1. **Trading Intelligence User**
   Access:
   - Trading Intelligence product workspace only
   - Portfolio decision support
   - Risk analysis
   - Trading intelligence features

2. **Wealth Intelligence User**
   Access:
   - Wealth Intelligence product workspace only
   - Personal financial intelligence
   - Asset allocation
   - Wealth insights

3. **AARA Super User / Platform Administrator**
   Access:
   - Trading Intelligence
   - Wealth Intelligence
   - Platform administration capabilities

### Architecture intent

Separate, as distinct concerns:
- Identity
- User roles
- Product entitlements
- Workspace permissions

**Roles are not coupled directly to business logic.** A role determines which
product workspaces and capabilities a user can reach — it does not encode trading
rules, wealth-analysis rules, or any other product-internal logic.

### Future implementation concept

```
User
 |
 Identity
 |
 Product Entitlements
 |
 Workspaces
 |
 Capabilities
```

## Explicitly Not Done By This ADR

- No authentication implementation.
- No authorization middleware.
- No database schema.
- No UI changes.
- Implementation begins only after product boundaries stabilize — i.e., after
  Trading Intelligence and Wealth Intelligence each have a settled architecture of
  their own (Trading Intelligence's is in progress: see
  `TRADING_INTELLIGENCE_BOUNDARY.md`, `TRADING_INTELLIGENCE_EVENT_MODEL.md`; Wealth
  Intelligence's product architecture exists but has no engine wiring yet).

## Consequences

- This is a recorded requirement, not a build order. No code, schema, or
  authentication work should cite this ADR as authorization to implement roles.
- Future work implementing identity/access control should treat this ADR as the
  starting shape (the four-layer concept above) unless a superseding ADR changes it.
- Does not affect `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`,
  `database/`, `ledger/`, or `sentinel_engine/` — all remain governed by ADR-002 and
  ADR-001 respectively, unchanged by this decision.
