"""Focused tests for ADR-033: Wealth Intelligence User-to-Principal bootstrap wiring.

Mirrors applications.trading_intelligence.tests.test_bootstrap_principal_mapping
exactly. Verifies build_application() constructs exactly one PrincipalRegistry
(ADR-033 Sec 2.3), calls get_or_create(current_user.user_id) exactly once only
when current_user is not None (Sec 2.4), that the resulting Principal never
reaches InvestorWorkspaceFacade/InvestorPresenter/InvestorWorkspaceUI (Sec 2.5),
and that the registry's fresh-per-call lifetime provides no cross-call
guarantee (Sec 2.6).
"""
from applications.platform.identity.principal import PrincipalRegistry
from applications.platform.identity.supabase_authentication_provider import (
    SupabaseAuthenticationProvider,
)
from applications.platform.identity.user import User
from applications.wealth_intelligence.application.investor_workspace import InvestorWorkspaceFacade
from applications.wealth_intelligence.bootstrap import build_application
from applications.wealth_intelligence.presentation.investor_presenter import InvestorPresenter


def _track_constructor_calls(monkeypatch, cls):
    calls = []
    original_init = cls.__init__

    def wrapped_init(self, *args, **kwargs):
        calls.append({"self": self, "args": args, "kwargs": kwargs})
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(cls, "__init__", wrapped_init)
    return calls


def test_build_application_constructs_exactly_one_principal_registry(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, PrincipalRegistry)

    build_application()

    assert len(calls) == 1


def test_build_application_does_not_call_get_or_create_when_current_user_is_none(monkeypatch):
    call_count = {"n": 0}
    original = PrincipalRegistry.get_or_create

    def counting_get_or_create(self, key):
        call_count["n"] += 1
        return original(self, key)

    monkeypatch.setattr(PrincipalRegistry, "get_or_create", counting_get_or_create)

    build_application()

    assert call_count["n"] == 0


def test_build_application_calls_get_or_create_once_with_user_id_when_current_user_exists(monkeypatch):
    user = User(user_id="user-001", display_name="Jordan Smith")
    monkeypatch.setattr(SupabaseAuthenticationProvider, "get_current_user", lambda self: user)

    calls = _track_constructor_calls(monkeypatch, PrincipalRegistry)
    original = PrincipalRegistry.get_or_create
    get_or_create_calls = []

    def tracking_get_or_create(self, key):
        get_or_create_calls.append(key)
        return original(self, key)

    monkeypatch.setattr(PrincipalRegistry, "get_or_create", tracking_get_or_create)

    build_application()

    assert len(calls) == 1
    assert get_or_create_calls == ["user-001"]


def test_build_application_does_not_pass_principal_to_the_workspace_facade_or_presenter(monkeypatch):
    user = User(user_id="user-001", display_name="Jordan Smith")
    monkeypatch.setattr(SupabaseAuthenticationProvider, "get_current_user", lambda self: user)

    facade_calls = _track_constructor_calls(monkeypatch, InvestorWorkspaceFacade)
    presenter_calls = _track_constructor_calls(monkeypatch, InvestorPresenter)

    build_application()

    assert len(facade_calls) == 1
    assert facade_calls[0]["kwargs"] == {}
    assert len(facade_calls[0]["args"]) == 3

    assert len(presenter_calls) == 1
    assert presenter_calls[0]["kwargs"] == {}
    assert len(presenter_calls[0]["args"]) == 1


def test_two_build_application_calls_with_the_same_user_id_produce_different_principal_ids(
    monkeypatch,
):
    user = User(user_id="user-001", display_name="Jordan Smith")
    monkeypatch.setattr(SupabaseAuthenticationProvider, "get_current_user", lambda self: user)

    allocated_principals = []
    original = PrincipalRegistry.get_or_create

    def capturing_get_or_create(self, key):
        principal = original(self, key)
        allocated_principals.append(principal)
        return principal

    monkeypatch.setattr(PrincipalRegistry, "get_or_create", capturing_get_or_create)

    build_application()
    build_application()

    assert len(allocated_principals) == 2
    assert allocated_principals[0].principal_id != allocated_principals[1].principal_id
