# ADR-006: ADR-002 Exception — Confidence Integrity Phase 1

**Status:** Approved exception
**Date:** 2026-08-05

## Scope

The following protected paths (frozen by
[ADR-002](ADR-002-bot-runtime-protection.md)) are authorized for
additive-only changes:

- `ledger/schema.sql`
- `ledger/ledger.py`
- `bot/trust_ledger/ids.py`
- `.github/workflows/ci.yml`

## Reason

Confidence Integrity Phase 1 requires:

- immutable confidence event storage
- ledger registration
- deterministic event IDs

The CI workflow additionally needs to run the new `sentinel_engine`
boundary-enforcement tests (`sentinel_engine/tests/test_package_imports.py`)
alongside the existing suite.

## Constraints

**Allowed:**

- new table creation
- new registry entries
- new ID generator
- new CI step appended (`Run sentinel_engine boundary tests`)

**Forbidden:**

- existing schema modification
- behavior changes
- refactors
- file movement
- import changes
- modification of any existing CI step
- change to trigger conditions, job matrix, or existing test invocation
- any change to `trade.yml`, `watchdog.yml`, `keepalive.yml`, or other
  workflow files

## Validation

- 1274 tests passed
- no regressions
- append-only guarantees preserved

## Relationship to ADR-002 and ADR-004

This ADR supersedes ADR-002's freeze *only* for the four paths and the
specific additive changes named above. All other ADR-002 protections
(`bot/` more broadly, `dashboard/`, `scheduler/`, `database/`, remaining
`.github/workflows/*.yml` files) remain in force, unchanged. This ADR does
not make the Option A/B/C ledger-ownership choice deferred by
[ADR-004](ADR-004-sentinel-ledger-ownership-strategy.md) — it authorizes
only schema/registry/ID scaffolding, not a backend implementation decision.
