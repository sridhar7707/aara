"""Tests for applications.platform.identity.supabase_authentication_provider.

Uses lightweight, locally-defined fake objects shaped like supabase_auth's
own UserResponse/User (per its real, installed source: UserResponse.user is
a User with typed id/email fields) -- never a real supabase_auth client,
never a real Supabase session, network call, or credential, per ADR-028
Section 3. This also matches the adapter's own TYPE_CHECKING-only coupling
to supabase_auth (see supabase_authentication_provider.py's own docstring):
these tests never need the real package importable at runtime either.
"""
from applications.platform.identity.authentication_provider import AuthenticationProvider
from applications.platform.identity.supabase_authentication_provider import (
    SupabaseAuthenticationProvider,
)
from applications.platform.identity.user import User


class _FakeSupabaseUser:
    def __init__(self, id, email=None):
        self.id = id
        self.email = email


class _FakeUserResponse:
    def __init__(self, user):
        self.user = user


class _FakeGoTrueClient:
    """Duck-typed stand-in for supabase_auth's SyncGoTrueClient -- only the
    one method SupabaseAuthenticationProvider actually calls."""

    def __init__(self, response=None):
        self._response = response
        self.get_user_calls = 0

    def get_user(self, jwt=None):
        self.get_user_calls += 1
        return self._response


def test_supabase_authentication_provider_is_an_authentication_provider():
    provider = SupabaseAuthenticationProvider(_FakeGoTrueClient())

    assert isinstance(provider, AuthenticationProvider)


def test_returns_none_when_client_has_no_user_response():
    provider = SupabaseAuthenticationProvider(_FakeGoTrueClient(response=None))

    assert provider.get_current_user() is None


def test_translates_supabase_user_into_aara_user_using_email_as_display_name():
    supabase_user = _FakeSupabaseUser(id="supabase-uid-001", email="jordan@example.com")
    client = _FakeGoTrueClient(response=_FakeUserResponse(supabase_user))
    provider = SupabaseAuthenticationProvider(client)

    result = provider.get_current_user()

    assert result == User(user_id="supabase-uid-001", display_name="jordan@example.com")


def test_falls_back_to_id_as_display_name_when_email_is_absent():
    supabase_user = _FakeSupabaseUser(id="supabase-uid-002", email=None)
    client = _FakeGoTrueClient(response=_FakeUserResponse(supabase_user))
    provider = SupabaseAuthenticationProvider(client)

    result = provider.get_current_user()

    assert result == User(user_id="supabase-uid-002", display_name="supabase-uid-002")


def test_delegates_to_the_injected_client_exactly_once_per_call():
    client = _FakeGoTrueClient(response=_FakeUserResponse(_FakeSupabaseUser(id="u1")))
    provider = SupabaseAuthenticationProvider(client)

    provider.get_current_user()

    assert client.get_user_calls == 1
