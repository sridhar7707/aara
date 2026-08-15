"""Focused tests for ADR-029: Trading Intelligence bootstrap authentication wiring.

Verifies build_application() constructs the existing SupabaseAuthenticationProvider
with a local, no-op placeholder client (ADR-029 Sec 2.1), calls get_current_user()
exactly once (Sec 2.2), that a None result is not an error (Sec 2.3), and that the
resulting Optional[User] never reaches DecisionCenterController, DecisionCenterUI, or
any other collaborator (Sec 2.4) -- no existing production signature changes.
"""
from applications.platform.identity.supabase_authentication_provider import (
    SupabaseAuthenticationProvider,
)
from applications.trading_intelligence.bootstrap import (
    _NoOpSupabaseClient,
    build_application,
)
from applications.trading_intelligence.ui.decision_center.controller import DecisionCenterController
from applications.trading_intelligence.ui.decision_center.gradio_view import DecisionCenterUI


def _track_constructor_calls(monkeypatch, cls):
    calls = []
    original_init = cls.__init__

    def wrapped_init(self, *args, **kwargs):
        calls.append({"self": self, "args": args, "kwargs": kwargs})
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(cls, "__init__", wrapped_init)
    return calls


def test_noop_supabase_client_get_user_always_returns_none():
    client = _NoOpSupabaseClient()

    assert client.get_user() is None
    assert client.get_user(jwt="anything") is None


def test_build_application_constructs_exactly_one_supabase_authentication_provider(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, SupabaseAuthenticationProvider)

    build_application()

    assert len(calls) == 1


def test_build_application_constructs_the_provider_with_a_noop_client(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, SupabaseAuthenticationProvider)

    build_application()

    assert isinstance(calls[0]["args"][0], _NoOpSupabaseClient)


def test_build_application_calls_get_current_user_exactly_once(monkeypatch):
    call_count = {"n": 0}
    original = SupabaseAuthenticationProvider.get_current_user

    def counting_get_current_user(self):
        call_count["n"] += 1
        return original(self)

    monkeypatch.setattr(SupabaseAuthenticationProvider, "get_current_user", counting_get_current_user)

    build_application()

    assert call_count["n"] == 1


def test_build_application_get_current_user_call_returns_none_via_the_noop_client():
    provider = SupabaseAuthenticationProvider(_NoOpSupabaseClient())

    assert provider.get_current_user() is None


def test_build_application_does_not_raise_when_get_current_user_returns_none():
    ui = build_application()

    assert isinstance(ui, DecisionCenterUI)


def test_build_application_does_not_pass_current_user_to_the_controller(monkeypatch):
    controller_calls = _track_constructor_calls(monkeypatch, DecisionCenterController)

    build_application()

    assert len(controller_calls) == 1
    args, kwargs = controller_calls[0]["args"], controller_calls[0]["kwargs"]
    assert len(args) == 4
    assert kwargs == {}
