"""Advisory capability resolver (ADR-061 Sections 2.6 / 2.7).

Derives whether a named capability is currently available from the health
of the integrations it requires.

Strictly advisory / UI-only (ADR-061 Section 2.7): the resolver performs no
I/O, no retry, never raises because a provider is unhealthy or absent, and
never blocks, gates, vetoes, or alters any operation. It returns an
informational :class:`CapabilityAvailability` fact and nothing more.
Promoting this to enforcing behavior is explicitly deferred to a separate
ADR (ADR-061 Section 2.8).

Product-agnostic: capability names and their provider requirements are
supplied by the caller (a product composition root). No Trading
Intelligence / product provider names live in this module.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional, Tuple

from applications.platform.integrations.health import IntegrationHealth, IntegrationStatus


class _Mode(Enum):
    ALL = "all"
    ANY = "any"
    NONE = "none"


@dataclass(frozen=True)
class Requirement:
    """Which integrations a capability needs, and how they combine.

    Build one via :meth:`all`, :meth:`any`, or :meth:`none` -- do not
    construct directly.
    """

    mode: _Mode
    providers: Tuple[str, ...] = ()

    @classmethod
    def all(cls, *providers: str) -> "Requirement":
        """The capability is available only when *every* named provider is
        ``HEALTHY``. ``all()`` with no providers is vacuously available."""
        return cls(_Mode.ALL, tuple(providers))

    @classmethod
    def any(cls, *providers: str) -> "Requirement":
        """The capability is available when *at least one* named provider is
        ``HEALTHY``."""
        if not providers:
            raise ValueError("Requirement.any() needs at least one provider")
        return cls(_Mode.ANY, tuple(providers))

    @classmethod
    def none(cls) -> "Requirement":
        """The capability depends on no integration -- always available."""
        return cls(_Mode.NONE, ())


@dataclass(frozen=True)
class CapabilityAvailability:
    """An informational availability fact for one capability.

    ``available`` is the derived answer. When it is ``False``,
    ``blocking_provider`` names a required provider that is not ``HEALTHY``
    (or, for an ``any`` requirement, the first such provider); its
    ``blocking_status`` is that provider's status, or ``None`` when the
    provider's health was not reported at all.
    """

    capability: str
    available: bool
    blocking_provider: Optional[str] = None
    blocking_status: Optional[IntegrationStatus] = None


class CapabilityResolver:
    """Resolves capability availability from a snapshot of provider health.

    Requirements are injected once at construction. :meth:`availability`
    is a pure function of the requirement and the supplied health map; it
    never performs I/O and never raises for an unhealthy or absent
    provider.
    """

    def __init__(self, requirements: Mapping[str, Requirement]) -> None:
        self._requirements = dict(requirements)

    def capabilities(self) -> Tuple[str, ...]:
        return tuple(self._requirements)

    def availability(
        self,
        capability: str,
        health_by_provider: Mapping[str, IntegrationHealth],
    ) -> CapabilityAvailability:
        requirement = self._requirements.get(capability)
        if requirement is None:
            # Unknown capability: not asserted available; nothing "blocks"
            # it. Purely informational -- the resolver does not raise.
            return CapabilityAvailability(capability, available=False)

        if requirement.mode is _Mode.NONE:
            return CapabilityAvailability(capability, available=True)

        if requirement.mode is _Mode.ALL:
            for provider in requirement.providers:
                status = _status_of(provider, health_by_provider)
                if status is not IntegrationStatus.HEALTHY:
                    return CapabilityAvailability(
                        capability,
                        available=False,
                        blocking_provider=provider,
                        blocking_status=status,
                    )
            return CapabilityAvailability(capability, available=True)

        # _Mode.ANY
        first_block: Optional[Tuple[str, Optional[IntegrationStatus]]] = None
        for provider in requirement.providers:
            status = _status_of(provider, health_by_provider)
            if status is IntegrationStatus.HEALTHY:
                return CapabilityAvailability(capability, available=True)
            if first_block is None:
                first_block = (provider, status)
        assert first_block is not None  # any() guarantees >= 1 provider
        return CapabilityAvailability(
            capability,
            available=False,
            blocking_provider=first_block[0],
            blocking_status=first_block[1],
        )


def _status_of(
    provider: str, health_by_provider: Mapping[str, IntegrationHealth]
) -> Optional[IntegrationStatus]:
    health = health_by_provider.get(provider)
    return health.status if health is not None else None
