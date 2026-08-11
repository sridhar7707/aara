"""Tests for bot/strategy/macro.py pure functions."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import time
import pytest
from unittest.mock import patch
from bot.strategy import macro as macro_mod
from bot.strategy.macro import _sigmoid, _compute_from_raw


# --- _sigmoid ---

def test_sigmoid_center_is_0_5():
    # At x == center, output should be exactly 0.5
    assert _sigmoid(20.0, center=20.0, scale=5.0) == pytest.approx(0.5, abs=1e-6)


def test_sigmoid_approaches_1_above_center():
    # Far above center → approaches 1.0
    result = _sigmoid(100.0, center=20.0, scale=5.0)
    assert result > 0.99


def test_sigmoid_approaches_0_below_center():
    # Far below center → approaches 0.0
    result = _sigmoid(-100.0, center=20.0, scale=5.0)
    assert result < 0.01


def test_sigmoid_monotonic():
    vals = [_sigmoid(x, center=0.0, scale=1.0) for x in range(-10, 11)]
    assert all(vals[i] < vals[i + 1] for i in range(len(vals) - 1))


# --- _compute_from_raw ---

def test_compute_from_raw_returns_expected_keys():
    raw = {"yield_curve": 0.5, "vix": 15.0, "fed_rate": 2.0}
    result = _compute_from_raw(raw)
    assert {"score", "cap", "halt"} <= set(result.keys())


def test_compute_from_raw_score_bounded():
    raw = {"yield_curve": 0.5, "vix": 15.0, "fed_rate": 2.0}
    result = _compute_from_raw(raw)
    assert 0.0 <= result["score"] <= 1.0


def test_compute_from_raw_bullish_conditions():
    # Low VIX, positive yield curve, low fed rate → high score
    raw = {"yield_curve": 1.0, "vix": 10.0, "fed_rate": 1.0}
    result = _compute_from_raw(raw)
    assert result["score"] > 0.6
    assert result["halt"] is False
    assert result["cap"] == 1.0


def test_compute_from_raw_bearish_conditions():
    # High VIX, inverted yield curve, high fed rate → low score
    raw = {"yield_curve": -0.5, "vix": 35.0, "fed_rate": 6.0}
    result = _compute_from_raw(raw)
    assert result["score"] < 0.4


def test_compute_from_raw_cap_reduced_when_vix_high():
    raw = {"yield_curve": 0.5, "vix": 31.0, "fed_rate": 2.0}
    result = _compute_from_raw(raw)
    assert result["cap"] == 0.5


def test_compute_from_raw_cap_reduced_when_yield_curve_inverted():
    raw = {"yield_curve": -0.1, "vix": 18.0, "fed_rate": 2.0}
    result = _compute_from_raw(raw)
    assert result["cap"] == 0.5


def test_compute_from_raw_cap_full_when_normal():
    raw = {"yield_curve": 0.3, "vix": 20.0, "fed_rate": 3.0}
    result = _compute_from_raw(raw)
    assert result["cap"] == 1.0


def test_compute_from_raw_halt_at_macro_halt_vix():
    from config import MACRO_HALT_VIX
    raw = {"yield_curve": 0.5, "vix": float(MACRO_HALT_VIX), "fed_rate": 2.0}
    result = _compute_from_raw(raw)
    assert result["halt"] is True


def test_compute_from_raw_no_halt_below_threshold():
    from config import MACRO_HALT_VIX
    raw = {"yield_curve": 0.5, "vix": float(MACRO_HALT_VIX) - 1.0, "fed_rate": 2.0}
    result = _compute_from_raw(raw)
    assert result["halt"] is False


def test_compute_from_raw_score_not_nan():
    raw = {"yield_curve": 0.0, "vix": 20.0, "fed_rate": 3.5}
    result = _compute_from_raw(raw)
    assert not math.isnan(result["score"])


# --- _get_cached() failure-state semantics (ADR-010) ---

def _reset_macro_cache(monkeypatch):
    monkeypatch.setattr(macro_mod, "_MACRO_CACHE", {})
    monkeypatch.setattr(macro_mod, "_MACRO_TS", 0.0)


def test_get_cached_fresh_successful_fetch_is_used(monkeypatch):
    _reset_macro_cache(monkeypatch)
    monkeypatch.setattr(
        macro_mod, "_fetch_macro_raw",
        lambda: {"yield_curve": 0.5, "vix": 10.0, "fed_rate": 2.0},
    )
    result = macro_mod._get_cached()
    assert result["halt"] is False
    assert 0.0 <= result["score"] <= 1.0


def test_get_cached_uses_still_valid_cache_without_refetching(monkeypatch):
    monkeypatch.setattr(macro_mod, "_MACRO_CACHE", {"score": 0.42, "cap": 1.0, "halt": False})
    monkeypatch.setattr(macro_mod, "_MACRO_TS", time.time())  # just cached — well within TTL

    def _boom():
        raise AssertionError("must not fetch when the cache is still within TTL")
    monkeypatch.setattr(macro_mod, "_fetch_macro_raw", _boom)

    result = macro_mod._get_cached()
    assert result == {"score": 0.42, "cap": 1.0, "halt": False}


def test_get_cached_raises_on_cold_start_fetch_failure(monkeypatch):
    _reset_macro_cache(monkeypatch)

    def _boom():
        raise RuntimeError("FRED unreachable")
    monkeypatch.setattr(macro_mod, "_fetch_macro_raw", _boom)

    with pytest.raises(RuntimeError):
        macro_mod._get_cached()


def test_get_cached_raises_when_expired_even_with_stale_value_present(monkeypatch):
    # Guardrail (ADR-010): a present-but-expired in-process value must not
    # mask TTL expiration just because it still exists.
    monkeypatch.setattr(macro_mod, "_MACRO_CACHE", {"score": 0.9, "cap": 1.0, "halt": False})
    monkeypatch.setattr(macro_mod, "_MACRO_TS", time.time() - macro_mod._MACRO_TTL - 1)

    def _boom():
        raise RuntimeError("FRED unreachable")
    monkeypatch.setattr(macro_mod, "_fetch_macro_raw", _boom)

    with pytest.raises(RuntimeError):
        macro_mod._get_cached()


def test_get_cached_does_not_advance_ts_on_failed_refresh(monkeypatch):
    # A failed refresh must not reset the TTL clock — otherwise a process
    # stuck failing forever would look "fresh" on every subsequent call.
    _reset_macro_cache(monkeypatch)
    calls = []

    def _boom():
        calls.append(1)
        raise RuntimeError("FRED unreachable")
    monkeypatch.setattr(macro_mod, "_fetch_macro_raw", _boom)

    with pytest.raises(RuntimeError):
        macro_mod._get_cached()
    with pytest.raises(RuntimeError):
        macro_mod._get_cached()

    assert len(calls) == 2  # both calls actually attempted a fetch


# --- force_refresh: lets an authoritative external TTL (macro_cache.py's
# SQLite clock) demand a genuine fetch, bypassing this module's own
# opportunistic "still valid in-process" shortcut ---

def test_get_cached_force_refresh_fetches_even_when_in_process_cache_valid(monkeypatch):
    monkeypatch.setattr(macro_mod, "_MACRO_CACHE", {"score": 0.11, "cap": 1.0, "halt": False})
    monkeypatch.setattr(macro_mod, "_MACRO_TS", time.time())  # still well within TTL

    calls = []
    def _fresh():
        calls.append(1)
        return {"yield_curve": 0.5, "vix": 10.0, "fed_rate": 2.0}
    monkeypatch.setattr(macro_mod, "_fetch_macro_raw", _fresh)

    result = macro_mod._get_cached(force_refresh=True)

    assert len(calls) == 1          # FRED was actually consulted
    assert result["score"] != 0.11  # the fresh result is used, not the stale one


def test_get_cached_force_refresh_raises_on_failure_even_when_in_process_cache_valid(monkeypatch):
    monkeypatch.setattr(macro_mod, "_MACRO_CACHE", {"score": 0.9, "cap": 1.0, "halt": False})
    monkeypatch.setattr(macro_mod, "_MACRO_TS", time.time())  # still well within TTL

    def _boom():
        raise RuntimeError("FRED unreachable")
    monkeypatch.setattr(macro_mod, "_fetch_macro_raw", _boom)

    with pytest.raises(RuntimeError):
        macro_mod._get_cached(force_refresh=True)
