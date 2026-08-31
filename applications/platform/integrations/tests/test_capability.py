"""Tests for applications.platform.integrations.capability (ADR-061 Sections 2.6 / 2.7)."""
import ast
import pathlib

import pytest

from applications.platform.integrations.capability import (
    CapabilityAvailability,
    CapabilityResolver,
    Requirement,
)
from applications.platform.integrations.health import IntegrationHealth, IntegrationStatus


def _healthy(provider):
    return IntegrationHealth.healthy(provider)


def _resolver():
    return CapabilityResolver(
        {
            "cap_all": Requirement.all("a", "b"),
            "cap_any": Requirement.any("a", "b"),
            "cap_none": Requirement.none(),
        }
    )


# --- Requirement construction -------------------------------------------

def test_requirement_all_any_none_construct():
    assert Requirement.all("a", "b").providers == ("a", "b")
    assert Requirement.any("a").providers == ("a",)
    assert Requirement.none().providers == ()


def test_requirement_any_needs_at_least_one_provider():
    with pytest.raises(ValueError):
        Requirement.any()


def test_requirement_all_with_no_providers_is_vacuously_available():
    resolver = CapabilityResolver({"cap": Requirement.all()})
    assert resolver.availability("cap", {}).available is True


# --- all healthy -------------------------------------------------------

def test_all_providers_healthy_makes_every_capability_available():
    resolver = _resolver()
    health = {"a": _healthy("a"), "b": _healthy("b")}
    for capability in ("cap_all", "cap_any", "cap_none"):
        result = resolver.availability(capability, health)
        assert result.available is True
        assert result.blocking_provider is None
        assert result.blocking_status is None


def test_none_requirement_is_available_even_with_no_health_reported():
    assert _resolver().availability("cap_none", {}).available is True


# --- one provider not configured ------------------------------------

def test_not_configured_provider_blocks_all_but_not_any_when_another_is_healthy():
    resolver = _resolver()
    health = {"a": IntegrationHealth.not_configured("a"), "b": _healthy("b")}

    cap_all = resolver.availability("cap_all", health)
    assert cap_all.available is False
    assert cap_all.blocking_provider == "a"
    assert cap_all.blocking_status is IntegrationStatus.NOT_CONFIGURED

    assert resolver.availability("cap_any", health).available is True
    assert resolver.availability("cap_none", health).available is True


# --- auth failed / unavailable ------------------------------------

def test_auth_failed_and_unavailable_block_all_and_any():
    resolver = _resolver()
    health = {
        "a": IntegrationHealth.auth_failed("a"),
        "b": IntegrationHealth.unavailable("b"),
    }

    cap_all = resolver.availability("cap_all", health)
    assert cap_all.available is False
    assert cap_all.blocking_provider == "a"
    assert cap_all.blocking_status is IntegrationStatus.AUTH_FAILED

    cap_any = resolver.availability("cap_any", health)
    assert cap_any.available is False
    # "any" reports the first non-healthy provider it saw
    assert cap_any.blocking_provider == "a"
    assert cap_any.blocking_status is IntegrationStatus.AUTH_FAILED


# --- provider missing from the health map -------------------------

def test_required_provider_absent_from_health_map_blocks_with_unknown_status():
    resolver = _resolver()
    result = resolver.availability("cap_all", {"b": _healthy("b")})
    assert result.available is False
    assert result.blocking_provider == "a"
    assert result.blocking_status is None


# --- unknown capability -----------------------------------------

def test_unknown_capability_is_not_available_and_does_not_raise():
    result = _resolver().availability("no_such_capability", {})
    assert isinstance(result, CapabilityAvailability)
    assert result.available is False
    assert result.blocking_provider is None
    assert result.blocking_status is None


# --- unaffected capabilities -----------------------------------

def test_an_unhealthy_provider_does_not_affect_a_capability_that_does_not_require_it():
    resolver = CapabilityResolver(
        {
            "needs_a": Requirement.all("a"),
            "needs_b": Requirement.all("b"),
        }
    )
    health = {"a": IntegrationHealth.unavailable("a"), "b": _healthy("b")}
    assert resolver.availability("needs_a", health).available is False
    assert resolver.availability("needs_b", health).available is True


# --- advisory only: never raises, no I/O ----------------------

def test_resolver_never_raises_for_unhealthy_or_absent_providers():
    resolver = _resolver()
    tricky = {
        "a": IntegrationHealth.api_error("a"),
        # "b" deliberately absent
    }
    for capability in ("cap_all", "cap_any", "cap_none", "unknown"):
        # must simply return a fact
        result = resolver.availability(capability, tricky)
        assert isinstance(result, CapabilityAvailability)


def test_capabilities_lists_the_injected_capability_names():
    assert set(_resolver().capabilities()) == {"cap_all", "cap_any", "cap_none"}


# --- no product imports -------------------------------------

def test_capability_module_imports_nothing_product_specific():
    forbidden_roots = (
        "applications.trading_intelligence",
        "applications.wealth_intelligence",
        "sentinel_engine",
        "bot",
        "dashboard",
        "scheduler",
        "database",
        "ledger",
    )
    path = pathlib.Path(__file__).resolve().parent.parent / "capability.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    for name in imported:
        assert not any(
            name == root or name.startswith(root + ".") for root in forbidden_roots
        ), "capability.py imports %r" % name
