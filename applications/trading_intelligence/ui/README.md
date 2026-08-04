# Trading Intelligence UI

**Status:** Ownership boundary only. No screens, components, React files, CSS,
API wiring, or data connections exist yet.

## What this is

This UI belongs to the AARA Trading Intelligence product (Product #1), per
`docs/products/AARA_TRADING_INTELLIGENCE_UI_IMPLEMENTATION_PLAN.md`'s decision
to locate Trading Intelligence UI work at
`applications/trading_intelligence/ui/` — not `dashboard/` (the current, live,
protected implementation) and not `sentinel/frontend/` (Sentinel's own
governance-oriented surface).

## Where future screens live

Future screens live under this directory, one subdirectory per screen. The
first is `decision_center/` (see `decision_center/README.md`), per
`docs/products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md`. Additional
screens (Morning Brief, Portfolio Intelligence, Risk Intelligence, Performance
& Learning, Settings — per `docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`)
are expected to follow the same pattern once designed.

## Dependency rule

**The UI consumes application services, not `bot`/`database` (or anything
else) directly.**

Allowed:

```
ui/ -> services/ (DecisionQueryService, and future services)
```

Forbidden:

```
ui/ -> bot
ui/ -> dashboard
ui/ -> scheduler
ui/ -> sentinel_engine (directly)
```

**Note the last one is stricter than the rest of `applications/trading_intelligence/`:**
`adapters/` is allowed to import `sentinel_engine` (that's its job —
`SentinelProjectionDecisionSource` wraps a `sentinel_engine.repositories.ProjectionRepository`).
The UI layer must not reach past `services/` to import `sentinel_engine`
itself — it goes through `DecisionQueryService`, which already returns
UI-shaped `DecisionView` objects. This keeps the UI layer decoupled from
Sentinel Engine's internal contracts entirely.

This is checked, not just documented — see `tests/test_ui_structure.py`.
