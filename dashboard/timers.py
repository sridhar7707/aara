"""Centralized Gradio timer callback registration (req 7.1).

Two timers keep the UI responsive without hammering external APIs:
  timer_ui   (60 s)  — lightweight DB reads only; no yfinance calls
  timer_data (300 s) — heavy: yfinance (15 s daemon-thread timeout), charts, AI; batched + stateful

Component ownership: each component module registers a ComponentSpec that declares its
RefreshGroup and render function. register_all_timers() discovers specs via by_group()
and builds one batched tick per group — no central mapping required.

Batching all callbacks into a single timer.tick() per timer prevents Gradio 5
from firing N separate sequential SSE events (one per registration), which
causes components to show loading indicators one-by-one and looks like a
continuous page refresh on slow servers.

Each batch runs its unique render functions CONCURRENTLY (not in a sequential
loop). A batch shares one Gradio event, so every one of its outputs sits in a
pending/spinner state for the full duration of the tick — running sequentially
means one slow call (e.g. market_mood's yfinance fetch, up to ~20s) freezes
every other output in the group, including ones that individually take <50ms.
Running concurrently bounds the wait to the slowest single call instead of the
sum of all of them.
"""
from __future__ import annotations

import concurrent.futures as _cf

import gradio as gr
from loguru import logger

from dashboard.registry import RefreshGroup, by_group, widget, require_widgets

require_widgets("sim_sym_dd", "perf_tabs", "perf_out", "symbol_selector", "symbol_detail_out")

_logger = logger

# Shared across both batches — sized for I/O-bound work (DB reads, yfinance,
# news), not CPU-bound, so more workers than cores is fine. One pool for the
# app's lifetime avoids spinning up/tearing down threads every tick.
_TICK_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=12, thread_name_prefix="dash_tick")


def register_all_timers(timer_ui: gr.Timer, timer_data: gr.Timer) -> None:
    """Register batched timer.tick() callbacks using ComponentSpec discovery."""
    _register_ui_tick(timer_ui)
    _register_data_tick(timer_data)


# ── Shared helper ─────────────────────────────────────────────────────────────

def _safe_call(fn) -> str:
    """Run a render_fn, falling back to '' if it raises outside its own @safe_render guard."""
    try:
        return fn()
    except Exception as exc:
        _logger.error(f"tick: {getattr(fn, '__name__', fn)} raised: {exc}")
        return ""


def _batch_tick(timer: gr.Timer, group: RefreshGroup) -> None:
    """Register one batched tick for all specs in *group*.

    Deduplicates calls to the same render_fn within a single tick so widgets
    sharing a function (e.g. pos_brief_out and pos_out both using render_positions)
    only trigger one DB call per cycle. Unique render functions are submitted to
    the shared thread pool and run concurrently — see module docstring for why.
    """
    specs      = by_group(group)
    fns        = [s.render_fn for s in specs]
    outputs    = [s.output    for s in specs]
    unique_fns = list(dict.fromkeys(fns))  # de-dupe, preserve first-seen order

    def _tick():
        futures = {fn: _TICK_EXECUTOR.submit(_safe_call, fn) for fn in unique_fns}
        cache   = {fn: fut.result() for fn, fut in futures.items()}
        return tuple(cache[fn] for fn in fns)

    timer.tick(fn=_tick, outputs=outputs)


# ── Fast (60 s) — DB reads only, no external API calls ────────────────────────

def _register_ui_tick(timer: gr.Timer) -> None:
    """Batched FAST tick, plus a separate choices-update for the sim dropdown."""
    _batch_tick(timer, RefreshGroup.FAST)

    # sim_sym_dd returns gr.update() (not HTML) — kept as a separate tick.
    # symbol_selector is NOT refreshed: writing to a Dropdown with a registered
    # .change() triggers Gradio 5.9's feedback-loop bug.
    def _sim_choices():
        from dashboard.data import get_data as _gd
        choices = sorted(_gd().get("prices", {}).keys()) or []
        return gr.update(choices=choices)

    timer.tick(fn=_sim_choices, outputs=[widget("sim_sym_dd")])


# ── Slow (300 s) — yfinance (15 s timeout) + charts + AI ──────────────────────

def _register_data_tick(timer: gr.Timer) -> None:
    """Batched SLOW tick, plus stateful callbacks for perf and symbol detail."""
    _batch_tick(timer, RefreshGroup.SLOW)

    # perf_out and symbol_detail_out are NOT refreshed here on purpose. Both
    # take "which thing is currently selected" as an argument (period label /
    # symbol), and each has its own .change() handler in app.py writing to the
    # same output this tick would target. Two independent writers on one
    # output race — whichever response completes last wins, not whichever
    # user action was most recent. If this tick's response lands after a
    # user's own .change() response, it silently overwrites the correct
    # just-selected period/symbol with the previous selection's stale render
    # (confirmed bug: dropdown showing SNOW, panel showing GOOGL's AI
    # analysis). perf_tabs has the identical shape (a stale response could
    # show the wrong period's chart under a label that says otherwise) and is
    # fixed the same way. Leaving each .change() handler as the sole writer
    # removes the race entirely — auto-refreshing an already-open detail view
    # every few minutes is not worth reintroducing a bug that shows the wrong
    # thing under the right label.
