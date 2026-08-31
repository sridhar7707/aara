"""The integration health value types (ADR-061 Sections 2.3 / 2.5).

Product-agnostic, stdlib-only. Imports nothing from any product package,
``sentinel_engine``, ``bot``, ``dashboard``, ``scheduler``, ``database``,
or ``ledger``.

Three types:

* :class:`IntegrationStatus` -- the v1 normative six-state vocabulary. There
  is deliberately NO ``DEGRADED`` member (ADR-061 Section 2.3 and Section 3
  Category B item 8); a stale-but-valid read reports ``HEALTHY``.
* :class:`IntegrationHealth` -- an immutable snapshot of one integration's
  health at a moment in time.
* :class:`ReadResult` -- an immutable envelope pairing an optional value with
  its :class:`IntegrationHealth`, preserving the distinction between a
  genuine-empty result and an unavailable one.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


class IntegrationStatus(Enum):
    """The v1 normative status vocabulary (ADR-061 Section 2.3).

    Exactly six members. ``DEGRADED`` is intentionally absent -- ADR-061
    Section 3 Category B item 8 defers adding any staleness signal to a
    future ADR.
    """

    HEALTHY = "healthy"
    NOT_CONFIGURED = "not_configured"
    AUTH_FAILED = "auth_failed"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    API_ERROR = "api_error"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class IntegrationHealth:
    """One integration's health at ``checked_at`` (ADR-061 Section 2.3).

    Immutable. ``detail`` is short free text for operators; per ADR-061
    Section 2.9 it MUST NEVER contain a credential value, for any status.
    ``retry_after`` (seconds) is only meaningful for
    :attr:`IntegrationStatus.RATE_LIMITED`.
    """

    provider: str
    status: IntegrationStatus
    checked_at: datetime
    detail: str = ""
    retry_after: Optional[int] = None

    @property
    def is_healthy(self) -> bool:
        return self.status is IntegrationStatus.HEALTHY

    @classmethod
    def healthy(
        cls,
        provider: str,
        *,
        detail: str = "",
        checked_at: Optional[datetime] = None,
    ) -> "IntegrationHealth":
        return cls(provider, IntegrationStatus.HEALTHY, checked_at or _utc_now(), detail)

    @classmethod
    def not_configured(
        cls,
        provider: str,
        *,
        detail: str = "",
        checked_at: Optional[datetime] = None,
    ) -> "IntegrationHealth":
        return cls(
            provider, IntegrationStatus.NOT_CONFIGURED, checked_at or _utc_now(), detail
        )

    @classmethod
    def auth_failed(
        cls,
        provider: str,
        *,
        detail: str = "",
        checked_at: Optional[datetime] = None,
    ) -> "IntegrationHealth":
        return cls(
            provider, IntegrationStatus.AUTH_FAILED, checked_at or _utc_now(), detail
        )

    @classmethod
    def rate_limited(
        cls,
        provider: str,
        *,
        retry_after: Optional[int] = None,
        detail: str = "",
        checked_at: Optional[datetime] = None,
    ) -> "IntegrationHealth":
        return cls(
            provider,
            IntegrationStatus.RATE_LIMITED,
            checked_at or _utc_now(),
            detail,
            retry_after,
        )

    @classmethod
    def unavailable(
        cls,
        provider: str,
        *,
        detail: str = "",
        checked_at: Optional[datetime] = None,
    ) -> "IntegrationHealth":
        return cls(
            provider, IntegrationStatus.UNAVAILABLE, checked_at or _utc_now(), detail
        )

    @classmethod
    def api_error(
        cls,
        provider: str,
        *,
        detail: str = "",
        checked_at: Optional[datetime] = None,
    ) -> "IntegrationHealth":
        return cls(
            provider, IntegrationStatus.API_ERROR, checked_at or _utc_now(), detail
        )


@dataclass(frozen=True)
class ReadResult(Generic[T]):
    """An integration read's outcome (ADR-061 Section 2.5).

    Invariant (enforced): when ``health.status`` is not ``HEALTHY``,
    ``value`` MUST be ``None``.

    A ``HEALTHY`` result may carry real data, an empty collection, or
    ``None`` -- the last two both mean "connected, nothing to report", which
    is deliberately distinct from an unavailable read (``value is None`` with
    a non-``HEALTHY`` status).
    """

    value: Optional[T]
    health: IntegrationHealth

    def __post_init__(self) -> None:
        if not self.health.is_healthy and self.value is not None:
            raise ValueError(
                "ReadResult: value must be None when health.status is not HEALTHY "
                "(got status=%s)" % self.health.status.name
            )

    @property
    def is_healthy(self) -> bool:
        return self.health.is_healthy

    @classmethod
    def healthy(
        cls,
        value: Optional[T],
        provider: str,
        *,
        detail: str = "",
        checked_at: Optional[datetime] = None,
    ) -> "ReadResult[T]":
        """A successful read. ``value`` may be real data, an empty
        collection, or ``None`` (a genuine-empty result)."""
        return cls(value, IntegrationHealth.healthy(provider, detail=detail, checked_at=checked_at))

    @classmethod
    def empty(
        cls,
        provider: str,
        *,
        detail: str = "",
        checked_at: Optional[datetime] = None,
    ) -> "ReadResult[T]":
        """A successful read that found nothing -- ``HEALTHY`` with
        ``value is None``. Distinct from :meth:`failed`."""
        return cls(None, IntegrationHealth.healthy(provider, detail=detail, checked_at=checked_at))

    @classmethod
    def failed(cls, health: IntegrationHealth) -> "ReadResult[T]":
        """An unavailable read. ``health`` must carry a non-``HEALTHY``
        status; ``value`` is forced to ``None``."""
        if health.is_healthy:
            raise ValueError("ReadResult.failed() requires a non-HEALTHY IntegrationHealth")
        return cls(None, health)
