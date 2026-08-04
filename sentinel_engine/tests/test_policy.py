"""Tests for sentinel_engine.governance.policy.Policy."""
import dataclasses

import pytest

from sentinel_engine.governance.policy import Policy


def _make_policy(**overrides):
    defaults = dict(
        policy_id="pol-001",
        name="max_position_size",
        description="Caps single-position exposure as a percent of portfolio value.",
        enabled=True,
    )
    defaults.update(overrides)
    return Policy(**defaults)


def test_policy_can_be_created_with_required_fields():
    policy = _make_policy()
    assert policy.policy_id == "pol-001"
    assert policy.name == "max_position_size"
    assert policy.description == "Caps single-position exposure as a percent of portfolio value."
    assert policy.enabled is True


def test_policy_is_a_dataclass():
    assert dataclasses.is_dataclass(Policy)


def test_policy_is_immutable():
    policy = _make_policy()
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.enabled = False


def test_policy_requires_all_fields():
    with pytest.raises(TypeError):
        Policy(policy_id="pol-001", name="max_position_size")


def test_policy_can_be_disabled():
    policy = _make_policy(enabled=False)
    assert policy.enabled is False
