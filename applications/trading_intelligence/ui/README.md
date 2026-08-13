# Trading Intelligence UI

**Status:** Decision Center (`decision_center/`) is implemented and runnable
-- the only screen built so far, wired to real query services (see
`decision_center/README.md`). Portfolio Intelligence and Risk Intelligence
exist only as non-interactive "Coming Soon" items in the application
shell's navigation bar; neither has a screen, component, or backing code.

## What this is

This UI belongs to the AARA Trading Intelligence product (Product #1), per
`docs/products/AARA_TRADING_INTELLIGENCE_UI_IMPLEMENTATION_PLAN.md`'s decision
to locate Trading Intelligence UI work at
`applications/trading_intelligence/ui/` — not `dashboard/` (the current, live,
protected implementation) and not `sentinel/frontend/` (Sentinel's own
governance-oriented surface).

## Where screens live

Each screen lives under this directory in its own subdirectory. Decision
Center (`decision_center/`, see its own README) is the first, and so far
only, screen built this way, per
`docs/products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md`.
Additional screens named in
`docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` (Morning
Brief, Portfolio Intelligence, Risk Intelligence, Performance & Learning,
Settings) remain undesigned and unbuilt. Portfolio Intelligence and Risk
Intelligence are named today only as "Coming Soon" items in the shell's own
navigation bar (`decision_center/gradio_view.py`'s `_SHELL_NAV_HTML`) --
that is presentation only, not an implemented screen.

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
