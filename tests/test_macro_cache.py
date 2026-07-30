"""Tests for bot/db/macro_cache.py: TTL-based macro-score DB cache."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import bot._main_db as main_db
import bot.db.macro_cache as macro_cache


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
                         lambda: {"score": 0.7, "cap": 0.5, "halt": True})
    score, cap, halt = macro_cache.get_macro(con)
    assert (score, cap, halt) == (0.7, 0.5, True)
    rows = {r[0]: float(r[1]) for r in con.execute("SELECT key, value FROM macro_cache")}
    assert rows == {"score": 0.7, "cap": 0.5, "halt": 1.0}


def test_get_macro_returns_fresh_cache_without_refetch(con, monkeypatch):
    _seed(con, score=0.3, cap=1.0, halt=False, age_seconds=60)  # well inside 4h TTL

    def _boom():
        raise AssertionError("should not refetch a fresh cache")
    monkeypatch.setattr(macro_cache, "_get_macro_cached", _boom)

    score, cap, halt = macro_cache.get_macro(con)
    assert (score, cap, halt) == (0.3, 1.0, False)


def test_get_macro_refetches_when_cache_expired(con, monkeypatch):
    _seed(con, score=0.3, cap=1.0, halt=False, age_seconds=macro_cache._TTL + 1)
    monkeypatch.setattr(macro_cache, "_get_macro_cached",
                         lambda: {"score": 0.9, "cap": 0.2, "halt": False})
    score, cap, halt = macro_cache.get_macro(con)
    assert (score, cap, halt) == (0.9, 0.2, False)


def test_get_macro_falls_back_to_neutral_defaults_on_fetch_failure(con, monkeypatch):
    def _boom():
        raise RuntimeError("FRED unreachable")
    monkeypatch.setattr(macro_cache, "_get_macro_cached", _boom)
    monkeypatch.setattr(macro_cache.tg, "send", lambda *a, **k: None)

    score, cap, halt = macro_cache.get_macro(con)
    assert (score, cap, halt) == (0.5, 1.0, False)


def test_get_macro_alerts_via_telegram_on_fetch_failure(con, monkeypatch):
    sent = []
    def _boom():
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
                         lambda: {"score": 0.8, "cap": 0.4, "halt": True})

    score, cap, halt = macro_cache.get_macro(con)
    assert (score, cap, halt) == (0.8, 0.4, True)
