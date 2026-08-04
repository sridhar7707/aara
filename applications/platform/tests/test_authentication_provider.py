"""Tests for applications.platform.identity.authentication_provider.AuthenticationProvider."""
import pytest

from applications.platform.identity.authentication_provider import AuthenticationProvider
from applications.platform.identity.user import User


class _FakeAuthenticationProvider(AuthenticationProvider):
    """Minimal conforming implementation used only to exercise the interface --
    not a real provider. No OAuth/login flow, per this task's constraints."""

    def __init__(self, current_user=None):
        self._current_user = current_user

    def get_current_user(self):
        return self._current_user


def test_authentication_provider_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        AuthenticationProvider()


def test_fake_provider_returns_none_when_no_user_is_authenticated():
    provider = _FakeAuthenticationProvider()

    assert provider.get_current_user() is None


def test_fake_provider_returns_the_current_user():
    user = User(user_id="user-001", display_name="Jordan Smith")
    provider = _FakeAuthenticationProvider(current_user=user)

    assert provider.get_current_user() == user


def test_incomplete_authentication_provider_subclass_cannot_be_instantiated():
    class _Incomplete(AuthenticationProvider):
        pass  # get_current_user deliberately not implemented

    with pytest.raises(TypeError):
        _Incomplete()
