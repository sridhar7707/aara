# Phase 0 Architecture Validation Report

**Status:** Historical validation record — not a decision document. Introduces no
new architecture decisions; captures the outcome of decisions already made in
[ADR-001](../decisions/ADR-001-sentinel-engine-structure.md) and
[ADR-008](../decisions/ADR-008-sentinel-scaffold-disposition.md).
**Date:** 2026-08-06
**Scope:** Phase 0 — Sentinel scaffold archival and architecture boundary validation.

## 1. Repository Migration Summary

| Change | Commit |
|---|---|
| Sentinel Engine domain vocabulary preserved ahead of archival | `9214cfb` |
| `sentinel/` scaffold relocated to `archive/sentinel_phase2a_scaffold/` | `1fcc77b` |
| `SENTINEL_ENGINE_DOMAIN_VOCABULARY.md` registered in architecture authority table | `2b50209` |
| ADR-001 / ADR-008 test counts and ADR-008 status reconciled with actual state | `b8b483b` |

`sentinel/` no longer exists as an active package path. `git ls-files` and
filesystem search both confirm no `sentinel/` directory remains outside
`archive/`.

## 2. `sentinel_engine/` Authority Confirmation

Per [ADR-001](../decisions/ADR-001-sentinel-engine-structure.md),
`sentinel_engine/` is the package-structure authority for the Sentinel
Intelligence Engine — a separate package independent of `bot/`, `dashboard/`,
and `database/`. It is the **only** active Sentinel Engine implementation:
referenced from `.github/workflows/ci.yml`,
`applications/trading_intelligence/adapters/sentinel_projection_decision_source.py`,
and the full set of `docs/decisions/`, `docs/platform/`, and `docs/products/`
architecture documents. No competing active implementation exists.

## 3. Archive Disposition

Per [ADR-008](../decisions/ADR-008-sentinel-scaffold-disposition.md)
(Status: Accepted — Archive Executed, commit `1fcc77b`): the pre-ADR-001
`sentinel/` scaffold — verified to contain no working logic (every method
raised `NotImplementedError`) and zero external dependents — was archived
rather than deleted, preserving its git history and the one committed copy of
its domain vocabulary. That vocabulary (`GovernanceAction`,
`RiskGovernorState`, `DecisionState`, `SentinelRole`, `OperationalMode`) is
captured in
[`SENTINEL_ENGINE_DOMAIN_VOCABULARY.md`](SENTINEL_ENGINE_DOMAIN_VOCABULARY.md),
which explicitly authorizes no implementation, migration, or package
placement of its own accord.

## 4. Documentation Authority Model

Per [`AARA_ARCHITECTURE_AUTHORITY.md`](AARA_ARCHITECTURE_AUTHORITY.md), the
controlling hierarchy is: committed code > ADRs > `docs/platform/` /
`docs/implementation/` migration docs > gitignored `docs/architecture/`
working drafts. `SENTINEL_ENGINE_DOMAIN_VOCABULARY.md` is registered in the
authority document's "Current document roles" table as reference-only, not
authoritative — its own content does not override ADR-driven decisions,
consistent with that hierarchy.

## 5. Dependency Boundary Validation

- `git grep "from sentinel\."` across the full repository returns matches only
  inside `archive/sentinel_phase2a_scaffold/` — the archived package's own
  internal, self-referential imports. Zero matches reach `sentinel_engine/`,
  `applications/`, `bot/`, `dashboard/`, `scheduler/`, `database/`, or any
  other active path.
- `git grep "import sentinel"` returns zero matches anywhere.
- `sentinel_engine/tests/test_package_imports.py` AST-scans every production
  file under `sentinel_engine/` and asserts zero imports of `bot`,
  `dashboard`, `scheduler`, `ledger`, `database`, or `applications` —
  enforcing the boundary structurally, not just by convention.

## 6. Test Validation

```
$ pytest sentinel_engine/tests
........................................................................ [ 66%]
....................................                                     [100%]
108 passed
```

This count is reflected in both ADR-001 and ADR-008 as of commit `b8b483b`.

## Conclusion

Phase 0 architecture cleanup is complete: the legacy `sentinel/` scaffold is
archived (not deleted), `sentinel_engine/` stands as the sole authoritative
engine implementation with a structurally enforced dependency boundary, its
domain vocabulary is preserved and registered as a non-authoritative reference
document, and all governing ADRs are reconciled with current, verified test
counts. This report records that outcome; it does not alter or supersede any
ADR, boundary, or decision it describes.
