"""Tests for bot/core/api_guard.py: retry-with-backoff for 3rd-party API calls."""
from __future__ import annotations

import pytest

from bot.core.api_guard import _is_retryable, call_with_retry


class _StatusError(Exception):
    def __init__(self, msg: str, status_code: int | None = None):
        super().__init__(msg)
        self.status_code = status_code


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    delays = []
    monkeypatch.setattr("bot.core.api_guard.time.sleep", lambda s: delays.append(s))
    return delays


def test_call_with_retry_returns_result_on_first_success():
    assert call_with_retry(lambda: 42) == 42


def test_call_with_retry_does_not_retry_non_retryable_error():
    calls = {"n": 0}
    def _fn():
        calls["n"] += 1
        raise ValueError("invalid symbol")
    with pytest.raises(ValueError):
        call_with_retry(_fn)
    assert calls["n"] == 1


def test_call_with_retry_retries_rate_limit_phrase_then_succeeds():
    calls = {"n": 0}
    def _fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("Too Many Requests")
        return "ok"
    assert call_with_retry(_fn, _max_retries=3) == "ok"
    assert calls["n"] == 3


def test_call_with_retry_retries_status_429():
    calls = {"n": 0}
    def _fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _StatusError("boom", status_code=429)
        return "ok"
    assert call_with_retry(_fn) == "ok"
    assert calls["n"] == 2


def test_call_with_retry_raises_last_exception_after_exhausting_retries():
    def _fn():
        raise RuntimeError("rate limit exceeded")
    with pytest.raises(RuntimeError, match="rate limit exceeded"):
        call_with_retry(_fn, _max_retries=2)


def test_call_with_retry_backoff_doubles_each_attempt(_no_real_sleep):
    def _fn():
        raise RuntimeError("rate limit")
    with pytest.raises(RuntimeError):
        call_with_retry(_fn, _max_retries=3, _base_delay=1.0)
    assert _no_real_sleep == [1.0, 2.0, 4.0]


def test_call_with_retry_passes_args_and_kwargs_through():
    def _fn(a, b, *, c):
        return a + b + c
    assert call_with_retry(_fn, 1, 2, c=3) == 6


def test_is_retryable_rate_limit_only_ignores_502_status():
    exc = _StatusError("boom", status_code=502)
    assert _is_retryable(exc, rate_limit_only=True) is False
    assert _is_retryable(exc, rate_limit_only=False) is True


def test_is_retryable_connection_error_when_not_rate_limit_only():
    exc = ConnectionError("reset")
    assert _is_retryable(exc, rate_limit_only=False) is True
    assert _is_retryable(exc, rate_limit_only=True) is False


def test_is_retryable_exception_class_name_ratelimitexceeded():
    class RateLimitExceeded(Exception):
        pass
    exc = RateLimitExceeded("slow down")
    assert _is_retryable(exc, rate_limit_only=True) is True
