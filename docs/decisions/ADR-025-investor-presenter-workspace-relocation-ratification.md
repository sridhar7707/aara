# ADR-025 — Investor Presenter / Investor Workspace Relocation Ratification (Retroactive, Documentation-Only)

**Status:** Accepted — Retroactive Ratification
**Date:** 2026-08-14
**Decision Type:** Architecture — Documentation Correction Only, No Implementation Authorized
**Related ADRs:** ADR-015 (module classification, unamended), ADR-024 (superseded narrowly — §3 only), ADR-022 (cited as governing precedent)

---

## 1. Context

Commit `81e071b` ("refactor: relocate Wealth Intelligence workspace modules",
2026-08-14 16:48:46) moved `investor_presenter.py` and `investor_workspace.py`
from `sentinel_engine/presentation/` and `sentinel_engine/application/` to
`applications/wealth_intelligence/presentation/` and
`applications/wealth_intelligence/application/` respectively, updating their
sole import site (`applications/wealth_intelligence/bootstrap.py`) and the
two files' own test locations.

This commit landed **after** `ADR-024`'s acceptance commit (`4282ea7`), which
had stated (§3): *"Any file move, rename, or refactor — `investor_presenter.py`,
`investor_workspace.py`... all remain physically exactly where they are
today."* No ADR authorized this specific move at the time it happened.

`docs/platform/WEALTH_INTELLIGENCE_BOUNDARY.md` was subsequently written in
commit `09843fa` (17:01:25) — **after** the relocation — but describes the
**pre-relocation** state: it states both modules are "physically still in
`sentinel_engine/presentation/`/`sentinel_engine/application/` today" and
that "no move [is] authorized by this document or by `ADR-024` itself." Both
statements are now factually incorrect. `sentinel_engine/presentation/` and
`sentinel_engine/application/` are confirmed empty except for `__init__.py`.

Verification performed this session: `python -m pytest sentinel_engine/tests
applications/wealth_intelligence -q` — 250 passed, 0 failed, against the
current (post-relocation) file locations.

## 2. Governing Authority

Per `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`'s documentation hierarchy,
committed, tested code outranks any document describing it. `ADR-022`
established the exact precedent this ADR follows: when real, tested code has
already resolved a placement question a document had not yet caught up to,
the correction is to record that resolution, not to treat the code as
non-compliant retroactively or to force a revert.

## 3. Decision

The relocation of `investor_presenter.py` and `investor_workspace.py` to
`applications/wealth_intelligence/` is ratified as the accepted, current,
correct state:

- `applications/wealth_intelligence/presentation/investor_presenter.py`
  (formerly `sentinel_engine/presentation/investor_presenter.py`)
- `applications/wealth_intelligence/application/investor_workspace.py`
  (formerly `sentinel_engine/application/investor_workspace.py`)

Both are now Wealth Intelligence product code, physically and directionally,
resolving `ADR-024` §2.1 and §2.4's "when" question for these two modules
only. `ADR-024`'s classification of `morning_brief_query.py` (§2.2,
generalize-in-place) and `decision_center_query.py` (§2.3, duplication
stands) is unaffected — neither module moved, and this ADR does not touch
them.

## 4. Explicit Non-Authorization

This ADR authorizes no new code change of any kind. It does not authorize:

- Deleting the now-empty `sentinel_engine/presentation/` or
  `sentinel_engine/application/` packages — they remain as-is, a separate,
  smaller future cleanup not decided here.
- Any change to `morning_brief_query.py`, `decision_center_query.py`, or any
  other `ADR-015`-classified module.
- Any change to `sentinel_engine/tests/test_package_imports.py` or any other
  existing test (none require modification — verified, §1).
- Any change to `applications/trading_intelligence/`.
- Any resolution of `ADR-004`'s deferred ledger-ownership choice.

## 5. Relationship to ADR-024

`ADR-024`'s classification and direction (§1, §2.1–§2.4, §4–§9) remain valid
and unamended. Only one clause is superseded, narrowly: §3's statement that
`investor_presenter.py`/`investor_workspace.py` "remain physically exactly
where they are today" no longer describes reality and is superseded by this
ADR **for those two files only**. `ADR-024` itself is not edited — per this
repo's own rule that accepted ADRs are amended only by a superseding ADR,
not silently edited — consistent with how `ADR-022` superseded one
destination in `CODEBASE_MIGRATION_MATRIX.md` without editing that document.

## 6. Consequences

**Positive:** Closes the gap between governance documentation and the real,
tested tree; gives `WEALTH_INTELLIGENCE_BOUNDARY.md` a citable basis for its
correction (§3, this document's companion action).

**Negative:** Confirms that a structural move happened without its own
prior authorizing ADR — a process gap, noted here rather than silently
absorbed.

## 7. Acceptance Criteria

- Names the exact commit (`81e071b`) and exact current paths.
- Supersedes only `ADR-024` §3's now-false physical-location clause, for
  exactly two files.
- Does not edit `ADR-024`.
- Does not authorize any further code change.
- Cites the passing test suite as evidence, not as new authorization.

## 8. Status

**Accepted — Retroactive Ratification.**
