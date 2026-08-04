# Bot Dependency Map

**Purpose:** Read-only import matrix between `bot/`, `sentinel_engine/`, `dashboard/`,
`database/`, and `scheduler/`, to identify coupling before any future extraction
(ADR-001, Phase 2 candidate). No files were changed to produce this document.

**Method:** `grep` for `^import X` / `^from X` at the top of files in each package,
searching for cross-package references in both directions. This finds static
top-level imports; it does not trace dynamic imports, subprocess calls, or runtime
`importlib` usage.

> **Correction (superseded the original version of this document):** the top-level-only
> grep pattern missed **deferred imports inside function bodies** — the exact pattern
> `scheduler/` uses to reach `bot/`. See "What This Means" below; `scheduler/` is not
> zero-coupled to `bot/` as originally reported. Treat any "0 found" in this document
> as "no top-level import found," not "no coupling exists."

---

## Import Matrix

| Importer → Imports | `bot` | `sentinel_engine` | `database` | top-level `ledger` |
|---|---|---|---|---|
| `dashboard/` | **33 files** | 0 | **7 files** | 0 |
| `sentinel_engine/` | **0** | — | 0 | 0 |
| `database/` | **2 files** | 0 | — | 0 |
| `scheduler/` | **3 files (deferred imports — see below)** | 0 | 0 | not checked |
| `bot/` | — | **0** | **4 files** | 1 file (`bot/main.py`) |

## What This Means

**`sentinel_engine/` and `bot/` have zero coupling today, in either direction.**
Neither package imports the other. This is the single most important fact for
Phase 2 planning: extracting `bot/` into `applications/trading_intelligence/` has
**no dependency-map blocker from the `sentinel_engine/` side** — there is no bridge
code to update, because none exists yet. (`sentinel_engine/adapters/decision_adapter.py`
takes a plain `dict`, not a `bot` type, by design — see ADR-001 context — so it isn't a
bridge in the coupling sense, just a boundary waiting to be wired up later.)

**`dashboard/` is the real coupling risk**, not `sentinel_engine/`. 33 files under
`dashboard/components/` and `dashboard/app.py`/`builders.py` import `bot` directly,
and 7 of those also import `database` directly. Any move of `bot/` submodules changes
import paths for a third of the dashboard's component files. This is a much larger
blast radius than the engine-extraction work done so far.

**`database/` has light two-way coupling**: `database/repositories/analytics_repository.py`
and `database/services/analytics_service.py` import `bot`; conversely `bot/_main_cycle.py`,
`bot/_main_db.py`, `bot/_main_positions.py`, and `bot/capital/pool.py` import `database`.
Four files, not a large surface, but not zero.

**`scheduler/` is not unused — it is a second, live, independent trigger path into
`bot/`.** Investigated directly (see `ADR-002` and `TRADING_INTELLIGENCE_BOUNDARY.md`
for full detail): `scheduler/dispatcher.py` is documented in its own docstring as
"the sole cron entry point." It's reached via `dashboard/http_endpoints.py`'s
`GET /run/cron` route, which spawns `scheduler.dispatcher.main()` in a background
thread on *every* request, unconditionally. `watchdog.yml` — named/described as a
health check — actually issues a real `GET` to that endpoint 5×/day, which means
every "health check" is also a real dispatch trigger, not a passive check.
`scheduler.dispatcher.main()` routes (via `market_calendar`/`session_manager`) to
`scheduler/startup_job.py`, `trading_job.py`, or `shutdown_job.py` depending on
market state, each of which locally imports `bot` (`trading_job.py` →
`from bot.main import run as bot_run`; `startup_job.py` →
`from bot.execution.alpaca_client import AlpacaClient`; `shutdown_job.py` →
`from bot.core.recommendation_engine import get_portfolio_health`). None of these
are top-level imports, which is why the grep in this document's first version
missed them.

**Two independent entry points into `bot/` trading logic exist**, not one:
1. `trade.yml` (cron-job.org → `workflow_dispatch`) → subprocess
   `python bot/main.py --mode paper --loop` (the CLI path, `bot/main.py:451`).
2. `watchdog.yml`'s "ping" (and potentially any other request to the public HF
   Space URL) → `dashboard/http_endpoints.py` `/run/cron` → `scheduler.dispatcher.main()`
   → `scheduler/trading_job.py` → `bot.main.run()` (the function path,
   `bot/main.py:109` — a distinct function from the CLI's `__main__` block, not yet
   confirmed whether they share underlying helpers beyond module-level imports).

`scheduler`'s own idempotency guards (`session_manager.mark_initialized` /
`mark_startup_complete` / `mark_shutdown_complete`, applied *before* running each
job) appear designed to make repeated dispatch triggers safe — but this means the
system relies on that idempotency logic to prevent duplicate execution across two
independently-triggered code paths, which is a materially different risk profile
than a single trigger source.

**`bot/main.py` imports the top-level `ledger/` package directly**
(`from ledger.integrity import get_active_pointer`) — not `bot/trust_ledger/`, and not
`sentinel_engine/ledger/`. This is a third, separate ledger dependency to account for
if/when `sentinel_engine/ledger/` becomes the real backend (per `CODEBASE_MIGRATION_MATRIX.md`,
which names the top-level `ledger/` package — not `bot/trust_ledger/` — as the thing
that moves into `sentinel_engine/ledger/`).

## Bridges

**None exist today.** There is no code that currently translates between `bot/` and
`sentinel_engine/` at runtime — the two packages simply don't reference each other.
`sentinel_engine/adapters/decision_adapter.py` is a one-sided boundary (dict → `Decision`)
built in anticipation of future wiring, not an active bridge carrying live traffic.
When Phase 2 wiring begins, this will be the first real bridge, and it should be
built to fail loudly if the input dict shape drifts from what `bot/` actually
produces (it already validates and raises `ValueError` on missing/malformed fields).

## Not Yet Mapped

This analysis covered `bot`, `sentinel_engine`, `dashboard`, `database`, `scheduler`,
and top-level `ledger`. Not covered: `analytics/`, `backtest/`, `applications/`
(currently near-empty per earlier structure scan), `brand/`, `shared/`. If Phase 2
planning needs those, they'd need their own pass.
