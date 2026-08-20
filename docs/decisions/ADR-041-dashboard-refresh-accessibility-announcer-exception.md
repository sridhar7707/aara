# ADR-041: ADR-002 Exception — Dashboard Refresh Accessibility Announcer

**Status:** Accepted
**Date:** 2026-08-20

## Context

The dashboard (`dashboard/app.py`) refreshes two classes of on-screen content:
background timer ticks (`gr.Timer` at 60 s and 300 s, wired in
`dashboard/timers.py`) and user-triggered `.change()`/`.click()` handlers.
Neither class currently produces any signal a screen reader can perceive.
Sighted users see cards, tables, and charts repaint in place; a screen-reader
user gets no indication that background content changed at all — the
dashboard has no `aria-live` region anywhere (confirmed by repo-wide search;
zero matches for `aria-live`, `aria_live`, or `role="status"` under
`dashboard/`).

A prior read-only technical audit traced the refresh architecture
(`dashboard/timers.py`, `dashboard/registry.py`, `dashboard/app.py`,
`dashboard/components/overview.py`, `dashboard/layout.py`) and identified a
minimal, additive seam for a global screen-reader announcement of background
refreshes, without touching any existing render function or the timer/registry
batching mechanism. A governance audit confirmed `dashboard/` is fully frozen
under [ADR-002](ADR-002-bot-runtime-protection.md) ("no file changes of any
kind") and that no existing ADR — including the prior ADR-002 exceptions
([ADR-006](ADR-006-confidence-integrity-phase1-exception.md),
[ADR-017](ADR-017-deploy-analytics-exception.md),
[ADR-018](ADR-018-deploy-analytics-gate-exception.md)) — authorizes this or
any other `dashboard/` source change. No accessibility standard is adopted
anywhere in this repository (`docs/design/AARA_UI_UX_DESIGN_SYSTEM.md` §7
states this explicitly).

A follow-up design investigation resolved two remaining open questions:

1. **ARIA attribute placement.** `gr.HTML` exposes no parameter for arbitrary
   ARIA attributes (verified against the installed Gradio 5.x runtime's
   `gr.HTML.__init__` signature — only `elem_id`, `elem_classes`, `visible`,
   `container`, `padding`, `min_height`, `max_height`, `autoscroll`, `label`,
   `show_label` exist). Placing `aria-live`/`aria-atomic` inside the rendered
   HTML *value* string would fail the verified DOM-persistence seam: Svelte's
   `{@html value}` update path (`HtmlTag.p()`, confirmed from the installed
   `svelte.js` bundle) detaches all old child nodes and inserts brand-new ones
   parsed from the new HTML string on every tick — any element embedded in
   that string, including one carrying `aria-live`, would be destroyed and
   recreated every cycle, which is the specific failure mode the DOM-identity
   verification was run to rule out. The attributes must instead be set on the
   persistent Gradio-generated wrapper itself (the `elem_id="refresh-announcer"`
   node), via JavaScript. This repository already establishes exactly that
   mechanism: `gr.Blocks(js=TAB_FIX_JS)` at `dashboard/app.py:128` runs
   `TAB_FIX_JS` (defined in `dashboard/layout.py:267-347`) once at page load,
   and `TAB_FIX_JS` already does `document.querySelector('#equity-chart ...')`
   against an `elem_id`-tagged Gradio wrapper (`layout.py:304`) — proving both
   that `elem_id` renders as a real DOM `id` in this exact codebase and that a
   one-time JS attribute/DOM operation against such an `id` is an established,
   already-working pattern here, not a new mechanism.
2. **Timer ownership.** The standalone announcer tick belongs on `timer_ui`
   (FAST, 60 s), not `timer_data` (SLOW, 300 s). The FAST group carries the
   large majority of registered `ComponentSpec`s, and the application's own
   sighted-user-facing copy (`HEADER_HTML`/`FOOTER_HTML` in
   `dashboard/layout.py`) already defines "background refresh" as the 60 s
   cadence. Anchoring the announcer to `timer_data` alone would silently skip
   4 of every 5 cycles in which FAST-group content changed — a parity gap
   against what sighted users already experience.

## Decision

Authorize one narrow, additive exception to ADR-002's `dashboard/` freeze:
add a single global, visually-hidden `aria-live` announcer that fires only on
the 60 s background timer refresh, confined to exactly three files, with no
change to any existing render function, the timer batching mechanism, or the
component registry.

## Why This Is a Narrow Exception to ADR-002

ADR-002 exists to protect the two live-trading entry points (the `trade.yml`
CLI path and the `watchdog.yml` → `dashboard/http_endpoints.py`
`GET /run/cron` → `scheduler.dispatcher` → `bot.main.run()` HTTP path) from
incidental breakage during refactors/moves. This change:

- Touches none of `bot/`, `scheduler/`, `database/`, `ledger/`, or
  `dashboard/http_endpoints.py` — the two documented trading entry points are
  structurally unreachable from any of the three authorized edits.
- Adds new code only; it moves, imports, or refactors nothing that exists
  today, which is the specific risk class ADR-002 was written to prevent
  ("no moves, no import changes, no refactors").
- Is purely a presentation-layer accessibility addition — one inert Gradio
  component, one isolated timer callback that writes to that component alone,
  one CSS utility class, and one narrowly-scoped JS attribute-injection
  snippet appended to an already-existing script. It introduces no new
  service, event bus, state-management layer, or architectural abstraction.
- Follows the precedent already established by ADR-006/017/018: a standalone,
  narrowly-scoped ADR that supersedes ADR-002's freeze for an exact, named set
  of files and edits, while leaving every other `dashboard/` protection in
  force unchanged.

## Scope

The following protected path (frozen by
[ADR-002](ADR-002-bot-runtime-protection.md)) is authorized for the
additive-only changes below, and no others:

- `dashboard/app.py`
- `dashboard/timers.py`
- `dashboard/layout.py`

`tests/check_ui.py` is **not** part of this Scope — it is not among ADR-002's
protected paths (`bot/`, `dashboard/`, `.github/workflows/*.yml`,
`scheduler/`, `database/`, top-level `ledger/`) and does not require ADR
reopening. It is listed under Validation below for completeness only.

## Constraints

**Allowed:**

- `dashboard/app.py`:
  - Add exactly one new mounted widget — a dedicated `gr.HTML` component with
    `elem_id="refresh-announcer"`, initial `value=""`, registered via
    `registry.mount("refresh_announcer", ...)`.
  - Place it outside `with gr.Tabs():` (a structural requirement, not
    optional — Gradio hides inactive tab panels via `display:none`, which
    silences `aria-live` regions inside them).
  - No other line in `app.py` is touched, reformatted, or re-commented.

- `dashboard/timers.py`:
  - Add `"refresh_announcer"` to the existing `require_widgets(...)` call.
  - Add exactly one new private helper function (e.g. `_announce_refresh`)
    whose only job is producing the announcement string.
  - Add exactly one new top-level function, e.g. `_register_refresh_announcer(timer: gr.Timer)`,
    that registers exactly one standalone
    `timer.tick(fn=_announce_refresh, outputs=[widget("refresh_announcer")])`
    call.
  - Add exactly one new line inside `register_all_timers()` calling
    `_register_refresh_announcer(timer_ui)` (bound to the FAST/60 s timer,
    per the Timer Ownership finding above).
  - `_register_ui_tick()`'s and `_register_data_tick()`'s existing bodies are
    not edited — the new tick is wired entirely through the new function and
    the one new call in `register_all_timers()`.
  - No other line in `timers.py` is touched, reformatted, or re-commented.

- `dashboard/layout.py`:
  - Add exactly one new CSS rule to `GRADIO_CSS`: a visually-hidden utility
    class (clip/absolute-position pattern — content present in the
    accessibility tree, not `display:none`/`visibility:hidden`) for the live
    region.
  - Append exactly one narrowly-scoped snippet to the existing `TAB_FIX_JS`
    string performing only: locate `#refresh-announcer` (using the same
    load-timing retry pattern `TAB_FIX_JS` already uses for
    `_initEquityPeriod`, since the announcer node may not exist at the instant
    the script first runs) and set `aria-live="polite"` and
    `aria-atomic="true"` on it, once. No other line or existing behavior of
    `TAB_FIX_JS` (tab switching, equity-chart period logic) may be modified.
  - No other line in `layout.py` is touched, reformatted, or re-commented.

- `tests/check_ui.py` (not ADR-gated, listed for completeness):
  - May be updated to assert `#refresh-announcer` exists with
    `aria-live="polite"` and `aria-atomic="true"`, and to verify its DOM node
    identity persists across a value update.

**Forbidden:**

- Any modification to `_batch_tick()`, `RefreshGroup`, `by_group()`,
  `register()`, `mount()`, `widget()`, or any other symbol in
  `dashboard/registry.py`.
- Any modification to `_register_ui_tick()`'s or `_register_data_tick()`'s
  existing bodies, or to either `gr.Timer`'s interval/cadence (`value=60`,
  `value=300`).
- Any modification to any existing `render_fn` in `dashboard/components/`, or
  to any file under `dashboard/components/`.
- Any modification to `dashboard/registry.py`, `dashboard/data.py`,
  `dashboard/charts.py`, `dashboard/builders.py`, `dashboard/prerender.py`,
  `dashboard/http_endpoints.py`, or `dashboard/design_system.py`.
- Any modification to any existing widget's `.change()`/`.click()` outputs in
  `dashboard/app.py` — `refresh_announcer` must never appear in an outputs
  list belonging to a user-triggered handler. This is the mechanism that keeps
  background-refresh announcements isolated from user-triggered updates: the
  announcer has exactly one writer (the new standalone tick on `timer_ui`), by
  construction, permanently.
- Any change to the existing tab-switching or equity-chart-period logic
  already present in `TAB_FIX_JS`.
- Any change to `bot/`, `scheduler/`, `database/`, `ledger/`, or
  `.github/workflows/*.yml`.
- Reopening any part of `dashboard/` beyond the three named files and the
  edits enumerated above. This ADR does not lift ADR-002's freeze on
  `dashboard/` generally.
- Establishing any platform-wide accessibility policy or WCAG conformance
  claim (see "Explicitly Not Established" below).

## Technical Verification Basis

Verified against the actual installed Gradio runtime and the actual running
application, not inferred from general Gradio documentation:

- **Static verification**: the installed Gradio 5.50.0 client bundle
  (`.venv_playwright`, the only local Gradio 5.x runtime; production is
  pinned to `gradio==5.9.0` per `requirements_space.txt`) compiles `gr.HTML`'s
  `value` rendering via Svelte's `{@html}` mechanism (`HtmlTag` class in the
  shared `svelte.js` chunk). Its update path (`.p()`) removes old child nodes
  and inserts new ones into the same persistent parent element — the parent
  (where `elem_id` lives) is never destroyed or recreated on a value update.
- **Live verification**: `dashboard/app.py` was started unmodified (via
  direct import, on an isolated port, without touching any file) and driven
  with Playwright against a real Gradio update event (`perf_tabs.change` →
  `perf_out` receiving a new value, the same class of "push a new value into
  an existing `gr.HTML` component" event a `timer.tick()` output receives).
  Result: 7 marked container nodes in the visible tabpanel, 0 lost their
  identity markers after the update, 6 of 7 had genuinely different inner
  HTML, and the visible text confirmed changed — i.e., a real update occurred
  and no container node was replaced.
- **`elem_id` → DOM `id` verification**: confirmed already relied upon inside
  this exact codebase — `eq_plot`'s `elem_id="equity-chart"` (`app.py:150`) is
  targeted by `document.querySelector('#equity-chart ...')` inside
  `TAB_FIX_JS` (`layout.py:304`), and `#three_q_out` is targeted by a standing
  CSS rule (`layout.py:45`).

Conclusion: `aria-live`/`aria-atomic`, set once via a small addition to
`TAB_FIX_JS` against `#refresh-announcer`, will remain attached across every
timer-driven value update.

## Explicitly Not Established By This ADR

- No platform-wide accessibility policy is adopted by this ADR.
- No general WCAG conformance claim is made for the dashboard as a whole, or
  for any component other than `refresh-announcer` itself.
- This ADR resolves one specific, narrow gap (background refreshes are
  imperceptible to screen readers) and nothing broader. The open question in
  `docs/design/AARA_UI_UX_DESIGN_SYSTEM.md` §7 ("what accessibility standard
  is adopted platform-wide") remains unresolved and out of scope.

## Rollback Plan

Stated before implementation begins, per ADR-002 item 5:

- **If not yet deployed:** revert the three additive diffs (`app.py` widget
  mount, `timers.py` new function + call + `require_widgets` entry,
  `layout.py` CSS rule + `TAB_FIX_JS` snippet). Each is a pure addition with
  no dependents elsewhere in the codebase, so removal is a clean revert with
  no follow-on edits required.
- **If deployed and the change misbehaves** (e.g., the new tick throws, or
  the announcer interferes with existing layout or with `TAB_FIX_JS`'s
  existing tab-switching/equity-chart logic): revert the same diffs and
  redeploy. No `bot/`, `database/`, or `ledger/` state is touched by this
  change, so rollback carries no risk to trading data or either live-trading
  entry point.
- No `.github/workflows/*.yml` change is required for this ADR (the added
  files are all within `dashboard/`, which `deploy_ui.yml`'s existing
  `copytree` step already ships wholesale), so there is no workflow state to
  unwind.

## Validation / Testing Expectations

Before this ADR's implementation is considered satisfied:

- Full test suite passes before and after (current repo baseline per
  ADR-018: 1483 passed, 2 skipped, 0 failed — to be re-confirmed at
  implementation time, not assumed from this ADR's drafting).
- `tests/check_ui.py` is updated to assert `#refresh-announcer` exists with
  `aria-live="polite"` and `aria-atomic="true"`, and that its DOM node
  identity survives a live-app refresh cycle (per the live verification
  method used to draft this ADR).
- The CLI trading path (`trade.yml` → `bot/main.py --mode paper --loop`) is
  explicitly confirmed unaffected — per ADR-002 criterion 6, stated not
  assumed, though this change adds no code path connecting to it.
- The HTTP live-trading entry path (`watchdog.yml` → `GET /run/cron` →
  `scheduler.dispatcher.main()` → `bot.main.run()`) is explicitly confirmed
  unaffected — this change does not touch `dashboard/http_endpoints.py` or
  any code it imports.
- Per ADR-002 item 2, implementation happens in an isolated branch or
  worktree, not directly on `main`.
- Per ADR-002 item 1: this is not a module *move* (the item-1 criterion
  concerning `BOT_EXTRACTION_CANDIDATES.md` risk tier / coupling count does
  not apply — nothing is relocated, only new code is added).

## Consequences

- Background dashboard refreshes become perceivable to screen-reader users
  for the first time, via one dedicated, isolated announcement channel.
- `dashboard/`'s ADR-002 freeze remains fully in force for every file and
  symbol not explicitly named in this ADR's Scope/Constraints — this ADR does
  not open a general precedent for dashboard UI work.
- Establishes, alongside ADR-006/017/018, a repeatable narrow-exception
  pattern specifically for additive, zero-coupling-to-trading-logic dashboard
  changes, without weakening ADR-002 itself.
- Leaves the platform-wide accessibility-standard question
  (`AARA_UI_UX_DESIGN_SYSTEM.md` §7) open for a future, separate decision.

## Relationship to ADR-002 and Subsequent ADRs

This ADR supersedes ADR-002's freeze *only* for `dashboard/app.py`,
`dashboard/timers.py`, and `dashboard/layout.py`, and only for the exact
additive edits enumerated in Scope/Constraints above. All other ADR-002
protections remain in force, unchanged — including every file under
`dashboard/components/`, `dashboard/registry.py`, and
`dashboard/http_endpoints.py`, and the four files ADR-006 separately reopened
(`ledger/schema.sql`, `ledger/ledger.py`, `bot/trust_ledger/ids.py`,
`.github/workflows/ci.yml`), which this ADR does not touch or extend. This
ADR has no relationship to ADR-017/ADR-018 (`deploy_ui.yml` staging/gate
changes) beyond sharing the same ADR-002 exception lineage, and no
relationship to the Option A/B/C ledger-ownership choice deferred by
[ADR-004](ADR-004-sentinel-ledger-ownership-strategy.md).

Per `docs/AI_AGENT_GUIDELINES.md` §6 ("ADRs define decisions — nothing
overrides them except a superseding ADR") and consistent with how
ADR-006/017/018 each relate to ADR-002, this is issued as a new, standalone
ADR rather than an amendment to ADR-002 or to any other existing ADR.
