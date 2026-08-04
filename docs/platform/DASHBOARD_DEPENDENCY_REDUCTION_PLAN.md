# Dashboard Dependency Reduction Plan

**Status:** Draft — options and sequencing risk documented, no decision made on
which approach to take, no implementation. See ADR-002: `dashboard/` is protected;
this document proposes nothing be changed yet.

## Problem

Per `BOT_DEPENDENCY_MAP.md`: 33 files under `dashboard/` import `bot` directly
(most of `dashboard/components/*`, plus `dashboard/app.py` and `builders.py`), and 7
of those also import `database` directly. `dashboard/http_endpoints.py` additionally
imports `scheduler.dispatcher` (deferred import, inside the `/run/cron` route).

If `bot/` submodules move (Phase 2, per `CODEBASE_MIGRATION_MATRIX.md` and
`BOT_EXTRACTION_CANDIDATES.md`) without first reducing this coupling, roughly a
third of `dashboard/`'s files break on the same day. This is a substantially larger
blast radius than the `sentinel_engine/` extraction work has touched so far (zero
`bot`/`dashboard` coupling there).

## Current Coupling (from BOT_DEPENDENCY_MAP.md)

| Dependency | File count |
|---|---|
| `dashboard/*` → `bot` | 33 |
| `dashboard/*` → `database` | 7 |
| `dashboard/http_endpoints.py` → `scheduler` | 1 (deferred import) |

## Why This Matters More Than It Looks

`dashboard/http_endpoints.py`'s `/run/cron` route is not just a UI concern — it's
part of the live trading trigger path (see `ADR-002`). Any dashboard refactor that
touches `http_endpoints.py` is implicitly touching trading infrastructure, not just
UI code. This blurs the "dashboard is just a UI" assumption that might otherwise
justify treating dashboard decoupling as low-risk, cosmetic work.

## Reduction Options (Documented, No Decision Made)

### Option A — Narrow facade over `bot`

Introduce a single, stable interface (a facade module) that `dashboard/` depends on
instead of reaching into 33 different `bot` submodules directly. `bot/` internals
could then move freely as long as the facade's surface stays stable. Lowest
implementation cost; does not by itself solve the `sentinel_engine` alignment
question — the facade would still point at `bot/`, not the engine.

### Option B — Route dashboard reads through `sentinel_engine` projections

Once `sentinel_engine`'s `DecisionService`/`DecisionProjection` (and a future
trading-equivalent projection) are wired to real data (see
`TRADING_INTELLIGENCE_BOUNDARY.md`'s target interface), `dashboard/` could read from
`sentinel_engine` repositories instead of `bot` internals directly. This fully
decouples `dashboard/` from `bot/`'s internal module layout, but depends on wiring
that doesn't exist yet (`sentinel_engine` currently has zero real data flowing
through it — see `ADR-001`/`ADR-002` context).

### Option C — Do nothing until Phase 2 is scoped

Leave the coupling as-is; treat it as a known, accepted cost that Phase 2 planning
must explicitly budget for (i.e., "moving `bot/strategy/` also means touching N
dashboard files," counted up front rather than discovered mid-move).

## Sequencing Risk

Whichever option is chosen, **coupling reduction has to happen before, not after, any
`bot/` submodule move** — reducing it after a move means dashboard is already broken
in the interim. This is the opposite order from how `sentinel_engine/` extraction
was sequenced (contracts built first, in isolation, with zero `bot` coupling to
break), and is called out here specifically because that clean sequencing worked
precisely because `sentinel_engine/` started with no existing coupling to unwind.
`dashboard/` does not have that advantage.

## Non-Goals

- No option is recommended over another here.
- No file in `dashboard/` was read in enough depth to confirm which specific `bot`
  imports are load-bearing versus incidental — the 33/7 counts are import-statement
  counts, not a usage-depth analysis.
- Does not address `scheduler.dispatcher`'s coupling to `dashboard/http_endpoints.py`
  beyond flagging it — that's a trading-runtime risk (ADR-002), not primarily a
  dashboard-architecture one.
