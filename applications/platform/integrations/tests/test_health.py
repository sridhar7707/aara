"""Tests for applications.platform.integrations.health (ADR-061 Sections 2.3 / 2.5)."""
import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from applications.platform.integrations.health import (
    IntegrationHealth,
    IntegrationStatus,
    ReadResult,
)

_SECRET = "sk-live-ABCDEF1234567890"


# --- IntegrationStatus: exactly the six normative members, no DEGRADED ------

def test_integration_status_has_exactly_the_six_normative_members():
    assert {member.name for member in IntegrationStatus} == {
        "HEALTHY",
        "NOT_CONFIGURED",
        "AUTH_FAILED",
        "RATE_LIMITED",
        "UNAVAILABLE",
        "API_ERROR",
    }


def test_integration_status_has_no_degraded_member():
    assert "DEGRADED" not in IntegrationStatus.__members__
    assert not hasattr(IntegrationStatus, "DEGRADED")


# --- IntegrationHealth: frozen, factories, semantics -----------------------

@pytest.mark.parametrize(
    "factory, expected_status",
    [
        (IntegrationHealth.healthy, IntegrationStatus.HEALTHY),
        (IntegrationHealth.not_configured, IntegrationStatus.NOT_CONFIGURED),
        (IntegrationHealth.auth_failed, IntegrationStatus.AUTH_FAILED),
        (IntegrationHealth.rate_limited, IntegrationStatus.RATE_LIMITED),
        (IntegrationHealth.unavailable, IntegrationStatus.UNAVAILABLE),
        (IntegrationHealth.api_error, IntegrationStatus.API_ERROR),
    ],
)
def test_factory_produces_the_matching_status(factory, expected_status):
    health = factory("alpaca_paper")
    assert health.provider == "alpaca_paper"
    assert health.status is expected_status


def test_is_healthy_is_true_only_for_healthy():
    assert IntegrationHealth.healthy("p").is_healthy is True
    for factory in (
        IntegrationHealth.not_configured,
        IntegrationHealth.auth_failed,
        IntegrationHealth.rate_limited,
        IntegrationHealth.unavailable,
        IntegrationHealth.api_error,
    ):
        assert factory("p").is_healthy is False


def test_integration_health_is_frozen():
    health = IntegrationHealth.healthy("p")
    with pytest.raises(dataclasses.FrozenInstanceError):
        health.status = IntegrationStatus.API_ERROR


def test_checked_at_is_timezone_aware_utc():
    before = datetime.now(timezone.utc)
    health = IntegrationHealth.unavailable("p")
    after = datetime.now(timezone.utc)
    assert health.checked_at.tzinfo is not None
    assert health.checked_at.utcoffset() == timedelta(0)
    assert before <= health.checked_at <= after


def test_checked_at_can_be_supplied_explicitly():
    stamp = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    assert IntegrationHealth.api_error("p", checked_at=stamp).checked_at == stamp


def test_retry_after_defaults_to_none_and_is_carried_for_rate_limited():
    assert IntegrationHealth.healthy("p").retry_after is None
    assert IntegrationHealth.unavailable("p").retry_after is None
    assert IntegrationHealth.rate_limited("p").retry_after is None
    assert IntegrationHealth.rate_limited("p", retry_after=42).retry_after == 42


def test_detail_defaults_to_empty_and_a_supplied_secret_is_the_callers_responsibility():
    # The factory default never contains anything; ADR-061 Section 2.9 puts
    # the no-credential rule on whatever populates `detail`. The value type
    # simply carries the string it is given.
    assert IntegrationHealth.auth_failed("p").detail == ""
    assert _SECRET not in repr(IntegrationHealth.auth_failed("p"))


# --- ReadResult: the genuine-empty vs unavailable distinction -------------

def test_readresult_is_frozen():
    result = ReadResult.healthy("data", "p")
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.value = "other"


def test_healthy_readresult_may_carry_real_data():
    result = ReadResult.healthy(["a", "b"], "p")
    assert result.value == ["a", "b"]
    assert result.is_healthy is True


def test_healthy_readresult_may_be_a_genuine_empty_collection():
    result = ReadResult.healthy((), "p")
    assert result.value == ()
    assert result.is_healthy is True


def test_empty_factory_is_healthy_with_value_none():
    result = ReadResult.empty("p")
    assert result.value is None
    assert result.is_healthy is True
    assert result.health.status is IntegrationStatus.HEALTHY


def test_failed_readresult_forces_value_none_and_keeps_the_reason():
    health = IntegrationHealth.auth_failed("p")
    result = ReadResult.failed(health)
    assert result.value is None
    assert result.is_healthy is False
    assert result.health.status is IntegrationStatus.AUTH_FAILED


def test_non_healthy_readresult_with_a_value_is_rejected():
    with pytest.raises(ValueError):
        ReadResult(value="data", health=IntegrationHealth.unavailable("p"))


def test_failed_requires_a_non_healthy_health():
    with pytest.raises(ValueError):
        ReadResult.failed(IntegrationHealth.healthy("p"))


def test_genuine_empty_and_unavailable_are_distinguishable():
    genuine_empty = ReadResult.empty("p")
    unavailable = ReadResult.failed(IntegrationHealth.unavailable("p"))
    assert genuine_empty.value is None and unavailable.value is None
    assert genuine_empty.is_healthy != unavailable.is_healthy
    assert genuine_empty.health.status is not unavailable.health.status
