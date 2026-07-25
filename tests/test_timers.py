"""Tests for dashboard/timers.py batch-tick behavior: dedup, concurrency, error isolation."""
from __future__ import annotations

import time
from types import SimpleNamespace

import dashboard.timers as timers


class _FakeTimer:
    """Captures the fn passed to .tick() so the test can invoke it directly."""

    def __init__(self):
        self.registered: list[tuple] = []

    def tick(self, fn, outputs=None, inputs=None):
        self.registered.append((fn, outputs, inputs))


def _spec(key: str, render_fn, output=None):
    return SimpleNamespace(key=key, render_fn=render_fn, output=output or object())


def test_batch_tick_preserves_output_order(monkeypatch):
    calls = []

    def fn_a():
        calls.append("a")
        return "A"

    def fn_b():
        calls.append("b")
        return "B"

    specs = [_spec("out_a", fn_a), _spec("out_b", fn_b)]
    monkeypatch.setattr(timers, "by_group", lambda group: specs)

    ft = _FakeTimer()
    timers._batch_tick(ft, timers.RefreshGroup.FAST)
    tick_fn, outputs, _ = ft.registered[0]
    assert outputs == [specs[0].output, specs[1].output]

    result = tick_fn()
    assert result == ("A", "B")


def test_batch_tick_dedupes_shared_render_fn(monkeypatch):
    call_count = {"n": 0}

    def shared_fn():
        call_count["n"] += 1
        return "shared-result"

    specs = [_spec("out_1", shared_fn), _spec("out_2", shared_fn)]
    monkeypatch.setattr(timers, "by_group", lambda group: specs)

    ft = _FakeTimer()
    timers._batch_tick(ft, timers.RefreshGroup.SLOW)
    tick_fn, _, _ = ft.registered[0]

    result = tick_fn()
    assert result == ("shared-result", "shared-result")
    assert call_count["n"] == 1  # only one real call despite two outputs


def test_batch_tick_runs_unique_fns_concurrently(monkeypatch):
    """Two 0.3s calls should complete in ~0.3s total, not ~0.6s, if truly concurrent."""
    def slow_a():
        time.sleep(0.3)
        return "A"

    def slow_b():
        time.sleep(0.3)
        return "B"

    specs = [_spec("out_a", slow_a), _spec("out_b", slow_b)]
    monkeypatch.setattr(timers, "by_group", lambda group: specs)

    ft = _FakeTimer()
    timers._batch_tick(ft, timers.RefreshGroup.SLOW)
    tick_fn, _, _ = ft.registered[0]

    start = time.monotonic()
    result = tick_fn()
    elapsed = time.monotonic() - start

    assert result == ("A", "B")
    assert elapsed < 0.5, f"expected concurrent execution (~0.3s), took {elapsed:.2f}s"


def test_batch_tick_isolates_a_raising_render_fn(monkeypatch):
    def broken():
        raise RuntimeError("boom")

    def healthy():
        return "ok"

    specs = [_spec("out_broken", broken), _spec("out_healthy", healthy)]
    monkeypatch.setattr(timers, "by_group", lambda group: specs)

    ft = _FakeTimer()
    timers._batch_tick(ft, timers.RefreshGroup.SLOW)
    tick_fn, _, _ = ft.registered[0]

    result = tick_fn()
    assert result == ("", "ok")  # broken fn falls back to "", healthy fn unaffected
