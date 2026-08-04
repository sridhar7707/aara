# AARA Trading Intelligence UI Implementation Plan

**Status:** Location decision — Phase 3F. Documentation only. No UI code was
created. `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`, `database/`,
`ledger/`, `sentinel_engine/` untouched, confirmed via `git status` before and
after.

**Authority:** ADR-002, `AARA_UI_UX_DESIGN_SYSTEM.md`,
`AARA_PLATFORM_USER_EXPERIENCE.md`,
`AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md`,
`TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md` — this document resolves
that last document's open "presentation boundary — not represented in the
skeleton" gap.

---

## Option A: `dashboard/`

- **Architectural fit:** `dashboard/` is the *current*, real, live Trading
  Intelligence UI (per every prior document's "current dashboard reality"
  framing). Putting future UI work here means modifying the existing live app
  directly, not building something new.
- **Ownership:** owned by the live production system, not by
  `applications/trading_intelligence/`. Building here blurs the boundary this
  whole migration has been establishing between the two.
- **Dependency impact:** `dashboard/` already imports `bot` from 33 files
  (`BOT_DEPENDENCY_MAP.md`). Adding a second, `sentinel_engine`-sourced data
  path into the same app blends two different data-source models inside one
  already-coupled surface.
- **Migration risk:** highest of the three. `dashboard/` is explicitly
  protected under ADR-002 — *any* change requires a dedicated ADR meeting its
  full lifting checklist (named modules, isolated branch, workflow updates in
  the same change, full regression, stated rollback plan, both known
  trading-trigger paths verified). This is the heaviest gate of any option
  considered.
- **Rollback strategy:** hard — consistent with every prior assessment of
  `dashboard/` changes in this migration; `dashboard/http_endpoints.py` is also
  part of the live `/run/cron` execution trigger (ADR-002), raising the stakes
  of any change here beyond pure UI concerns.

## Option B: `sentinel/frontend/`

- **Architectural fit:** `sentinel/frontend/` is the existing
  governance/admin-oriented UI surface (`decision_card.py`, `evidence_card.py`,
  `risk_governor_badge.py`, `governance_badge.py`, and the workspace files
  `chain_of_custody.py`, `decision_history.py`, `governance_review.py`, etc.).
  Per the ownership split already established (Sentinel owns decisions,
  evidence, governance, audit; Trading Intelligence owns product views,
  workflows, user-facing interpretation), placing Trading Intelligence's *own*
  UI here would blur that exact boundary.
- **Ownership — a specific finding, not just a general concern:**
  `CODEBASE_MIGRATION_MATRIX.md`'s dashboard-split section names
  `sentinel_engine/admin_ui/` as the Sentinel UI destination — **not**
  `sentinel/frontend/`. `sentinel/frontend/`'s own long-term fate was never
  resolved by any authority document reviewed in this migration: is it the
  thing that eventually becomes `sentinel_engine/admin_ui/`, or a separate,
  pre-existing surface with its own trajectory? Building Trading Intelligence
  UI inside a directory whose own future is unresolved compounds one open
  question with another.
- **Dependency impact:** would invert the established direction — Trading
  Intelligence is supposed to *consume* Sentinel Engine, not live inside a
  Sentinel-owned UI tree.
- **Migration risk:** medium. `sentinel/` is not in the ADR-002 protected list,
  so it isn't blocked by that specific ADR — but committing to it means
  committing to an ambiguous, unresolved long-term location.
- **Rollback strategy:** moderate — would require physically relocating files
  later once `sentinel/frontend/`'s own fate is resolved, a migration this
  document would be creating rather than avoiding.

## Option C: `applications/trading_intelligence/ui/`

- **Architectural fit:** best of the three. Directly extends the skeleton
  already built (`contracts/`, `adapters/`, `projections/`, `services/`),
  consistent with the capability-based naming convention already confirmed
  correct in `TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md` Section 2
  (matching `sentinel_engine`'s own naming pattern). Directly resolves that
  document's Section 6 open item: no presentation/UI subpackage existed
  anywhere in `applications/trading_intelligence/` until this decision.
- **Ownership:** unambiguous — Trading Intelligence owns its own presentation
  layer, exactly matching the ownership split ("Trading Intelligence owns:
  product views... user-facing interpretation") with no directory-naming
  tension like Option B's.
- **Dependency impact:** `ui/` would depend on `services/` (`DecisionQueryService`)
  and, transitively, `contracts/`/`projections/` — entirely within the same
  package. Zero new cross-package coupling; fully consistent with the
  established dependency rule (`trading_intelligence -> sentinel_engine`,
  never `bot`/`dashboard`).
- **Migration risk:** lowest. `applications/trading_intelligence/` is not a
  protected path — every prior implementation milestone in this migration
  (contracts, projections, services, the Sentinel-reading adapter) has already
  proceeded here under the same "design doc, then implementation task"
  cadence, with zero protected-path conflicts across all of them.
- **Rollback strategy:** trivial — consistent with everything already built in
  this package: delete the files. Nothing outside `applications/trading_intelligence/`
  references any of it today.

## Recommendation

**Option C: `applications/trading_intelligence/ui/`.**

This is the only option that simultaneously satisfies all three stated
priorities:

- **Preserves dashboard protection** — zero interaction with `dashboard/`, no
  ADR-002 lifting checklist triggered, no risk to the live `/run/cron`
  execution path.
- **Preserves product separation** — Trading Intelligence's UI lives inside
  Trading Intelligence's own package, not blended into Sentinel's
  governance-oriented admin surface (Option B) or the live product surface of
  a different, undecided ownership (Option A).
- **Supports the future multi-product AARA platform model** — a future Wealth
  Intelligence UI would follow the identical pattern
  (`applications/wealth_intelligence/ui/`), matching
  `AARA_PLATFORM_USER_EXPERIENCE.md`'s shell/product-switcher/workspace model,
  where each product owns its own workspace internals behind a shared shell.

**This decision does not resolve what happens to `dashboard/` itself.**
`DASHBOARD_DEPENDENCY_REDUCTION_PLAN.md`'s three options remain undecided —
Option C here establishes where *new* UI work happens going forward; it does
not schedule retiring or migrating the existing `dashboard/` app.

**No UI was implemented by this document.**

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `dashboard/`, `sentinel/`,
or any protected path was created or modified.
