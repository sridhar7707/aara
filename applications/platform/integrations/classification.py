"""Normalized classification of integration failures (ADR-061 Section 2.4).

Pure and stdlib-only. Maps an observed condition -- a missing configuration
value, an HTTP status code, or a raised exception -- onto an
:class:`IntegrationStatus`, so no adapter re-implements the mapping.

This module deliberately imports NONE of ``alpaca``, ``yfinance``,
``huggingface_hub``, ``requests``, ``httpx``, or any product package. It
inspects an exception structurally (an HTTP-like status code first, then
stdlib exception types) and only falls back to conservative lowercased
message matching.

Per ADR-061 Section 2.9 the returned ``detail`` MUST NOT contain a
credential value. This module never copies an exception message or a config
value into ``detail`` -- for exceptions it records only the exception's
class name, and for configuration it records only the caller-supplied name
of the missing setting (callers pass a key name, never a value).
"""
import concurrent.futures
import json
import socket
from typing import Optional

from applications.platform.integrations.health import IntegrationHealth, IntegrationStatus

_AUTH_STATUS_CODES = frozenset({401, 403})
_RATE_STATUS_CODES = frozenset({426, 429})
_UNAVAILABLE_STATUS_CODES = frozenset({502, 503, 504})

_AUTH_MESSAGE_HINTS = (
    "unauthorized",
    "forbidden",
    "invalid api key",
    "invalid api-key",
    "invalid apikey",
    "invalid credentials",
    "invalid token",
    "authentication failed",
    "not authorized",
    "permission denied",
    "access denied",
    "signature",
    "401 ",
    "403 ",
)
_RATE_MESSAGE_HINTS = (
    "rate limit",
    "rate-limit",
    "ratelimit",
    "too many requests",
    "quota exceeded",
    "quota exhausted",
    "throttl",
    "429 ",
    "426 ",
)
_UNAVAILABLE_MESSAGE_HINTS = (
    "timed out",
    "timeout",
    "connection refused",
    "connection reset",
    "connection aborted",
    "temporarily unavailable",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
    "name or service not known",
    "failed to resolve",
    "getaddrinfo failed",
    "network is unreachable",
    "no route to host",
    "502 ",
    "503 ",
    "504 ",
)


def classify_missing_config(provider: str, what: str) -> IntegrationHealth:
    """A required credential or configuration value is absent, determined
    before any network call (ADR-061 Section 2.4). ``what`` is the *name* of
    the missing setting, never its value."""
    return IntegrationHealth.not_configured(
        provider, detail="missing required configuration: %s" % what
    )


def classify_http_status(
    provider: str, status_code: int, *, retry_after: Optional[int] = None
) -> IntegrationHealth:
    """Classify an HTTP status code per ADR-061 Section 2.4.

    ``401`` / ``403`` -> ``AUTH_FAILED``; ``429`` / ``426`` ->
    ``RATE_LIMITED``; ``502`` / ``503`` / ``504`` -> ``UNAVAILABLE``;
    ``500`` and every other ``4xx`` / ``5xx`` -> ``API_ERROR``; anything
    below ``400`` -> ``HEALTHY``.
    """
    detail = "HTTP %s" % status_code
    if status_code < 400:
        return IntegrationHealth.healthy(provider, detail=detail)
    if status_code in _AUTH_STATUS_CODES:
        return IntegrationHealth.auth_failed(provider, detail=detail)
    if status_code in _RATE_STATUS_CODES:
        return IntegrationHealth.rate_limited(
            provider, retry_after=retry_after, detail=detail
        )
    if status_code in _UNAVAILABLE_STATUS_CODES:
        return IntegrationHealth.unavailable(provider, detail=detail)
    return IntegrationHealth.api_error(provider, detail=detail)


def classify_exception(provider: str, exc: BaseException) -> IntegrationHealth:
    """Classify a raised exception per ADR-061 Section 2.4.

    Order of inspection: a structural HTTP-like status code first, then
    stdlib exception types, then a conservative lowercased-message check.
    An exception that matches nothing is ``API_ERROR`` ("unknown"). The
    returned ``detail`` is the exception's class name only -- never its
    message -- so no credential value can leak (ADR-061 Section 2.9).
    """
    detail = type(exc).__name__

    status_code = _extract_status_code(exc)
    if status_code is not None:
        health = classify_http_status(
            provider, status_code, retry_after=_extract_retry_after(exc)
        )
        # Keep the exception class name as detail, not "HTTP <code>", so the
        # detail stays a stable, message-free label.
        return _with_detail(health, detail)

    if isinstance(
        exc,
        (
            socket.gaierror,
            socket.timeout,
            TimeoutError,
            concurrent.futures.TimeoutError,
            ConnectionError,
        ),
    ):
        return IntegrationHealth.unavailable(provider, detail=detail)

    if isinstance(exc, (json.JSONDecodeError, KeyError, AttributeError, IndexError)):
        return IntegrationHealth.api_error(provider, detail=detail)

    message = str(exc).lower()
    if any(hint in message for hint in _AUTH_MESSAGE_HINTS):
        return IntegrationHealth.auth_failed(provider, detail=detail)
    if any(hint in message for hint in _RATE_MESSAGE_HINTS):
        return IntegrationHealth.rate_limited(provider, detail=detail)
    if any(hint in message for hint in _UNAVAILABLE_MESSAGE_HINTS):
        return IntegrationHealth.unavailable(provider, detail=detail)

    return IntegrationHealth.api_error(provider, detail=detail)


def _with_detail(health: IntegrationHealth, detail: str) -> IntegrationHealth:
    return IntegrationHealth(
        provider=health.provider,
        status=health.status,
        checked_at=health.checked_at,
        detail=detail,
        retry_after=health.retry_after,
    )


def _extract_status_code(exc: BaseException) -> Optional[int]:
    for attr in ("status_code", "status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and 100 <= value <= 599:
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        value = getattr(response, "status_code", None)
        if isinstance(value, int) and 100 <= value <= 599:
            return value
    return None


def _extract_retry_after(exc: BaseException) -> Optional[int]:
    value = getattr(exc, "retry_after", None)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    raw = None
    try:
        getter = getattr(headers, "get", None)
        if callable(getter):
            raw = getter("Retry-After") or getter("retry-after")
    except Exception:
        return None
    if raw is None:
        return None
    try:
        seconds = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None
