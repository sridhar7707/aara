"""Tests for applications.platform.identity.principal.Principal/PrincipalRegistry.

Per ADR-031 Sec 4: confirms Principal's shape, get_or_create()'s allocation
via uuid4(), same-key/different-key identity behavior, and that a fresh
registry carries no state from a prior instance -- proving non-durability
explicitly rather than by absence of a store.
"""
from dataclasses import FrozenInstanceError

import pytest

from applications.platform.identity.principal import Principal, PrincipalRegistry


def test_principal_is_a_frozen_dataclass_with_exactly_principal_id():
    principal = Principal(principal_id="abc")

    assert principal.principal_id == "abc"
    assert Principal.__dataclass_fields__.keys() == {"principal_id"}


def test_principal_is_frozen():
    principal = Principal(principal_id="abc")

    with pytest.raises(FrozenInstanceError):
        principal.principal_id = "xyz"


def test_get_or_create_returns_a_principal_with_a_non_empty_principal_id():
    registry = PrincipalRegistry()

    principal = registry.get_or_create("key-1")

    assert isinstance(principal, Principal)
    assert principal.principal_id != ""


def test_get_or_create_returns_the_identical_object_for_the_same_key():
    registry = PrincipalRegistry()

    first = registry.get_or_create("key-1")
    second = registry.get_or_create("key-1")

    assert first is second


def test_get_or_create_returns_different_principal_ids_for_different_keys():
    registry = PrincipalRegistry()

    first = registry.get_or_create("key-1")
    second = registry.get_or_create("key-2")

    assert first.principal_id != second.principal_id


def test_a_fresh_registry_holds_no_state_from_a_prior_instance():
    first_registry = PrincipalRegistry()
    first_principal = first_registry.get_or_create("shared-key")

    second_registry = PrincipalRegistry()
    second_principal = second_registry.get_or_create("shared-key")

    assert second_principal.principal_id != first_principal.principal_id
