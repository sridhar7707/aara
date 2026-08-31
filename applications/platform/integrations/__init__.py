"""Platform-level, product-agnostic integration health contract (ADR-061).

Owned by ``applications/platform/`` per ADR-061 Section 2.1. Defines the
normalized six-state status vocabulary every external integration reports
(:class:`IntegrationStatus`), the immutable value that carries it
(:class:`IntegrationHealth`), a :class:`ReadResult` envelope that keeps a
genuine-empty result distinct from an unavailable one, a shared failure
:mod:`~applications.platform.integrations.classification` helper, and an
advisory :class:`CapabilityResolver`.

Stdlib-only. Imports nothing from any product package
(``trading_intelligence`` / ``wealth_intelligence``), ``sentinel_engine``,
``bot``, ``dashboard``, ``scheduler``, ``database``, or ``ledger``.
"""
from applications.platform.integrations.capability import (
    CapabilityAvailability,
    CapabilityResolver,
    Requirement,
)
from applications.platform.integrations.classification import (
    classify_exception,
    classify_http_status,
    classify_missing_config,
)
from applications.platform.integrations.health import (
    IntegrationHealth,
    IntegrationStatus,
    ReadResult,
)

__all__ = [
    "IntegrationStatus",
    "IntegrationHealth",
    "ReadResult",
    "classify_missing_config",
    "classify_http_status",
    "classify_exception",
    "Requirement",
    "CapabilityAvailability",
    "CapabilityResolver",
]
