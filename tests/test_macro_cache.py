"""Tests for bot/db/macro_cache.py: TTL-based macro-score DB cache."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

import bot._main_db as main_db
import bot.db.macro_cache as macro_cache
import bot.strategy.macro as macro_strategy
from bot.strategy.macro import _compute_from_raw


@pytest.fixture
def con():
    c = main_db.init_db(":memory:")
    yield c
    c.close()


def _seed(con, score: float, cap: float, halt: bool, age_seconds: float):
    ts = (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()
    for key, value in (("score", score), ("cap", cap), ("halt", halt)):
        con.execute(
            "INSERT OR REPLACE INTO macro_cache (key, value, cached_at) VALUES (?,?,?)",
            (key, float(value), ts),
        )
    con.commit()


def test_get_macro_fetches_and_persists_on_empty_cache(con, monkeypatch):
    monkeypatch.setattr(macro_cache, "_get_macro_cached",
                         lambda **_: {"score": 0.7, "cap": 0.5, "halt": True})
    score, cap, halt = macro_cache.get_macro(con)
    assert (score, cap, halt) == (0.7, 0.5, True)
    rows = {r[0]: float(r[1]) for r in con.execute("SELECT key, value FROM macro_cache")}
    assert rows == {"score": 0.7, "cap": 0.5, "halt": 1.0}


def test_get_macro_returns_fresh_cache_without_refetch(con, monkeypatch):
    _seed(con, score=0.3, cap=1.0, halt=False, age_seconds=60)  # well inside 4h TTL

    def _boom(**_):
        raise AssertionError("should not refetch a fresh cache")
    monkeypatch.setattr(macro_cache, "_get_macro_cached", _boom)

    score, cap, halt = macro_cache.get_macro(con)
    assert (score, cap, halt) == (0.3, 1.0, False)


def test_get_macro_refetches_when_cache_expired(con, monkeypatch):
    _seed(con, score=0.3, cap=1.0, halt=False, age_seconds=macro_cache._TTL + 1)
    monkeypatch.setattr(macro_cache, "_get_macro_cached",
                         lambda **_: {"score": 0.9, "cap": 0.2, "halt": False})
    score, cap, halt = macro_cache.get_macro(con)
    assert (score, cap, halt) == (0.9, 0.2, False)


def test_get_macro_blocks_buy_when_no_valid_cache_and_fetch_fails(con, monkeypatch):
    # ADR-010: no valid data (cold start, or expired-and-failed-refresh) must
    # be distinguishable from a genuine "calm market" — halt=True is the
    # signal that reaches the existing, unmodified Gate 0 in _main_cycle.py.
    def _boom(**_):
        raise RuntimeError("FRED unreachable")
    monkeypatch.setattr(macro_cache, "_get_macro_cached", _boom)
    monkeypatch.setattr(macro_cache.tg, "send", lambda *a, **k: None)

    score, cap, halt = macro_cache.get_macro(con)
    assert halt is True
    assert (score, cap) == (0.5, 1.0)


def test_get_macro_does_not_persist_failure_state(con, monkeypatch):
    # Writing the failure state to the DB with a fresh cached_at would make
    # the next read treat it as a valid within-TTL cache, masking the
    # outage for up to another 4 hours — the DB-layer analogue of the
    # in-process _MACRO_CACHE guardrail in bot/strategy/macro.py.
    def _boom(**_):
        raise RuntimeError("FRED unreachable")
    monkeypatch.setattr(macro_cache, "_get_macro_cached", _boom)
    monkeypatch.setattr(macro_cache.tg, "send", lambda *a, **k: None)

    macro_cache.get_macro(con)
    rows = list(con.execute("SELECT key, value, cached_at FROM macro_cache"))
    assert rows == []


def test_get_macro_retries_every_call_while_fred_stays_down(con, monkeypatch):
    calls = []

    def _boom(**_):
        calls.append(1)
        raise RuntimeError("FRED unreachable")
    monkeypatch.setattr(macro_cache, "_get_macro_cached", _boom)
    monkeypatch.setattr(macro_cache.tg, "send", lambda *a, **k: None)

    macro_cache.get_macro(con)
    macro_cache.get_macro(con)
    assert len(calls) == 2


def test_get_macro_alerts_via_telegram_on_fetch_failure(con, monkeypatch):
    sent = []
    def _boom(**_):
        raise RuntimeError("FRED unreachable")
    monkeypatch.setattr(macro_cache, "_get_macro_cached", _boom)
    monkeypatch.setattr(macro_cache.tg, "send", lambda msg: sent.append(msg))

    macro_cache.get_macro(con)
    assert len(sent) == 1
    assert "FRED macro data unavailable" in sent[0]


def test_get_macro_ignores_malformed_cached_timestamp(con, monkeypatch):
    con.execute(
        "INSERT OR REPLACE INTO macro_cache (key, value, cached_at) VALUES (?,?,?)",
        ("score", 0.3, "not-a-timestamp"),
    )
    con.execute(
        "INSERT OR REPLACE INTO macro_cache (key, value, cached_at) VALUES (?,?,?)",
        ("cap", 1.0, "not-a-timestamp"),
    )
    con.commit()
    monkeypatch.setattr(macro_cache, "_get_macro_cached",
                         lambda **_: {"score": 0.8, "cap": 0.4, "halt": True})

    score, cap, halt = macro_cache.get_macro(con)
    assert (score, cap, halt) == (0.8, 0.4, True)


# --- SQLite-TTL-authoritative regression (follow-up correction): once
# get_macro() decides a refresh is due, a still-valid in-process
# _MACRO_CACHE must not silently satisfy it without a genuine FRED call ---

def test_get_macro_forces_real_fred_consult_when_sqlite_expired_even_with_valid_inprocess_cache(con, monkeypatch):
    _seed(con, score=0.3, cap=1.0, halt=False, age_seconds=macro_cache._TTL + 1)  # SQLite expired

    monkeypatch.setattr(macro_strategy, "_MACRO_CACHE", {"score": 0.9, "cap": 1.0, "halt": False})
    monkeypatch.setattr(macro_strategy, "_MACRO_TS", time.time())  # still valid per in-process TTL

    calls = []
    def _boom():
        calls.append(1)
        raise RuntimeError("FRED unreachable")
    monkeypatch.setattr(macro_strategy, "_fetch_macro_raw", _boom)
    monkeypatch.setattr(macro_cache.tg, "send", lambda *a, **k: None)

    rows_before = {r[0]: r[2] for r in con.execute("SELECT key, value, cached_at FROM macro_cache")}

    score, cap, halt = macro_cache.get_macro(con)

    assert len(calls) == 1  # FRED was actually consulted, not silently skipped
    assert halt is True     # failed refresh blocks BUY
    rows_after = {r[0]: r[2] for r in con.execute("SELECT key, value, cached_at FROM macro_cache")}
    assert rows_after == rows_before  # DB timestamp not renewed by the failed attempt


def test_get_macro_renews_from_genuinely_fresh_fetch_when_sqlite_expired_even_with_valid_inprocess_cache(con, monkeypatch):
    _seed(con, score=0.3, cap=1.0, halt=False, age_seconds=macro_cache._TTL + 1)  # SQLite expired

    monkeypatch.setattr(macro_strategy, "_MACRO_CACHE", {"score": 0.11, "cap": 1.0, "halt": False})
    monkeypatch.setattr(macro_strategy, "_MACRO_TS", time.time())  # still valid per in-process TTL

    fresh_raw = {"yield_curve": 0.5, "vix": 10.0, "fed_rate": 2.0}
    calls = []
    def _fresh():
        calls.append(1)
        return fresh_raw
    monkeypatch.setattr(macro_strategy, "_fetch_macro_raw", _fresh)

    old_ts = {r[0]: r[2] for r in con.execute("SELECT key, value, cached_at FROM macro_cache")}["score"]
    score, cap, halt = macro_cache.get_macro(con)

    assert len(calls) == 1  # FRED was actually consulted
    expected = _compute_from_raw(fresh_raw)
    assert (score, cap, halt) == (expected["score"], expected["cap"], expected["halt"])
    assert score != 0.11  # not the stale in-process value

    rows = {r[0]: (float(r[1]), r[2]) for r in con.execute("SELECT key, value, cached_at FROM macro_cache")}
    fresh_ts = datetime.fromisoformat(rows["score"][1]).timestamp()
    old_cached_ts = datetime.fromisoformat(old_ts).timestamp()
    assert fresh_ts > old_cached_ts + macro_cache._TTL  # genuinely newer, not the stale expired row
    assert time.time() - fresh_ts < 5  # renewed just now, not merely re-copied
