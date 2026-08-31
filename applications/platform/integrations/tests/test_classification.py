"""Tests for applications.platform.integrations.classification (ADR-061 Section 2.4)."""
import ast
import concurrent.futures
import json
import pathlib
import socket

import pytest

from applications.platform.integrations.classification import (
    classify_exception,
    classify_http_status,
    classify_missing_config,
)
from applications.platform.integrations.health import IntegrationStatus

_SECRET = "SUPERSECRET-key-9f8e7d6c"

_INTEGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent
_FORBIDDEN_IMPORT_ROOTS = (
    "applications.trading_intelligence",
    "applications.wealth_intelligence",
    "sentinel_engine",
    "bot",
    "dashboard",
    "scheduler",
    "database",
    "ledger",
    "alpaca",
    "yfinance",
    "huggingface_hub",
    "requests",
    "httpx",
)


# --- missing configuration -----------------------------------------------

def test_missing_config_is_not_configured_and_names_the_setting_not_a_value():
    health = classify_missing_config("alpaca_paper", "ALPACA_KEY")
    assert health.status is IntegrationStatus.NOT_CONFIGURED
    assert "ALPACA_KEY" in health.detail


# --- HTTP status codes --------------------------------------------------

@pytest.mark.parametrize(
    "code, expected",
    [
        (401, IntegrationStatus.AUTH_FAILED),
        (403, IntegrationStatus.AUTH_FAILED),
        (426, IntegrationStatus.RATE_LIMITED),
        (429, IntegrationStatus.RATE_LIMITED),
        (500, IntegrationStatus.API_ERROR),
        (502, IntegrationStatus.UNAVAILABLE),
        (503, IntegrationStatus.UNAVAILABLE),
        (504, IntegrationStatus.UNAVAILABLE),
        (404, IntegrationStatus.API_ERROR),
        (418, IntegrationStatus.API_ERROR),
        (200, IntegrationStatus.HEALTHY),
        (204, IntegrationStatus.HEALTHY),
    ],
)
def test_classify_http_status(code, expected):
    assert classify_http_status("p", code).status is expected


def test_classify_http_status_carries_retry_after_for_rate_limited():
    health = classify_http_status("p", 429, retry_after=30)
    assert health.status is IntegrationStatus.RATE_LIMITED
    assert health.retry_after == 30


# --- exception: stdlib types ------------------------------------------

@pytest.mark.parametrize(
    "exc, expected",
    [
        (socket.gaierror("name or service not known"), IntegrationStatus.UNAVAILABLE),
        (TimeoutError("timed out"), IntegrationStatus.UNAVAILABLE),
        (concurrent.futures.TimeoutError(), IntegrationStatus.UNAVAILABLE),
        (ConnectionError("connection refused"), IntegrationStatus.UNAVAILABLE),
        (ConnectionRefusedError(), IntegrationStatus.UNAVAILABLE),
        (json.JSONDecodeError("Expecting value", "", 0), IntegrationStatus.API_ERROR),
        (KeyError("news"), IntegrationStatus.API_ERROR),
        (AttributeError("'NoneType' object has no attribute 'data'"), IntegrationStatus.API_ERROR),
    ],
)
def test_classify_exception_stdlib_types(exc, expected):
    assert classify_exception("p", exc).status is expected


def test_unknown_exception_is_api_error():
    class _Weird(Exception):
        pass

    assert classify_exception("p", _Weird("???")).status is IntegrationStatus.API_ERROR


# --- exception: structural HTTP code first --------------------------

class _HttpishError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def test_structural_status_code_wins_over_message():
    # message says "unauthorized" but the structural code is 503
    exc = _HttpishError("unauthorized-sounding text", 503)
    assert classify_exception("p", exc).status is IntegrationStatus.UNAVAILABLE


def test_structural_status_code_maps_401_to_auth_failed():
    assert classify_exception("p", _HttpishError("nope", 401)).status is IntegrationStatus.AUTH_FAILED


class _RetryAfterHeaders:
    def __init__(self, value):
        self._value = value

    def get(self, key, default=None):
        if key.lower() == "retry-after":
            return self._value
        return default


class _RateLimitError(Exception):
    def __init__(self):
        super().__init__("429 Too Many Requests")

        class _Resp:
            status_code = 429
            headers = _RetryAfterHeaders("15")

        self.response = _Resp()


def test_structural_429_with_retry_after_header():
    health = classify_exception("p", _RateLimitError())
    assert health.status is IntegrationStatus.RATE_LIMITED
    assert health.retry_after == 15


# --- exception: conservative message fallback ----------------------

@pytest.mark.parametrize(
    "message, expected",
    [
        ("HTTP 401: Unauthorized", IntegrationStatus.AUTH_FAILED),
        ("Access denied for this API key", IntegrationStatus.AUTH_FAILED),
        ("You have exceeded your rate limit", IntegrationStatus.RATE_LIMITED),
        ("Too Many Requests", IntegrationStatus.RATE_LIMITED),
        ("Service Unavailable, try later", IntegrationStatus.UNAVAILABLE),
        ("connection reset by peer", IntegrationStatus.UNAVAILABLE),
        ("something entirely unexpected happened", IntegrationStatus.API_ERROR),
    ],
)
def test_message_based_fallback(message, expected):
    assert classify_exception("p", Exception(message)).status is expected


# --- ADR-061 Section 2.9: no credential value in detail / repr ------

@pytest.mark.parametrize(
    "exc",
    [
        Exception("401 unauthorized: rejected api_key=%s" % _SECRET),
        ConnectionError("connect failed with token=%s" % _SECRET),
        _HttpishError("bad request, key=%s in url" % _SECRET, 400),
        RuntimeError("unexpected: bearer %s leaked here" % _SECRET),
    ],
)
def test_exception_message_secret_never_leaks_into_detail_or_repr(exc):
    health = classify_exception("alpaca_paper", exc)
    assert _SECRET not in health.detail
    assert _SECRET not in repr(health)
    # detail is the exception's class name only -- never its message
    assert health.detail == type(exc).__name__


def test_message_hints_still_classify_even_though_the_message_is_discarded():
    health = classify_exception("p", Exception("401 unauthorized: rejected api_key=%s" % _SECRET))
    assert health.status is IntegrationStatus.AUTH_FAILED


def test_http_detail_is_a_bare_label():
    assert classify_http_status("p", 503).detail == "HTTP 503"


# --- module purity ------------------------------------------------

def test_integration_modules_import_no_product_or_http_client_packages():
    offenders = []
    for path in sorted(_INTEGRATIONS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                if any(
                    name == root or name.startswith(root + ".")
                    for root in _FORBIDDEN_IMPORT_ROOTS
                ):
                    offenders.append("%s -> %s" % (path.name, name))
    assert offenders == []
