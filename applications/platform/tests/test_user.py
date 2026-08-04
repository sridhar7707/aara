"""Tests for applications.platform.identity.user.User."""
import dataclasses

import pytest

from applications.platform.identity.user import User


def _make_user(**overrides):
    defaults = dict(user_id="user-001", display_name="Jordan Smith")
    defaults.update(overrides)
    return User(**defaults)


def test_user_can_be_created_with_required_fields():
    user = _make_user()

    assert user.user_id == "user-001"
    assert user.display_name == "Jordan Smith"


def test_user_is_a_dataclass():
    assert dataclasses.is_dataclass(User)


def test_user_is_immutable():
    user = _make_user()
    with pytest.raises(dataclasses.FrozenInstanceError):
        user.display_name = "Someone Else"


def test_user_requires_all_fields():
    with pytest.raises(TypeError):
        User(user_id="user-001")
