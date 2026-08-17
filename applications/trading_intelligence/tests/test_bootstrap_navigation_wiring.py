"""Focused tests for ADR-038: Trading Intelligence EntitlementChecker
implementation and NavigationBuilder composition wiring.

Verifies build_application() constructs exactly one product-local
ProductRegistry/WorkspaceRegistry, registered with only Trading
Intelligence's own already-existing descriptors (Sec 2.2 items 1-2); exactly
one TradingIntelligenceEntitlementChecker (Sec 2.1/Sec 2.2 item 3); and
exactly one NavigationBuilder, given a _ResolvedUserAuthenticationProvider
wrapper rather than the real SupabaseAuthenticationProvider instance
(Sec 2.2 item 4) -- preserving ADR-029 Sec 2.2's "exactly once" call count on
the real provider -- and that the resulting NavigationModel stays local,
never reaching DecisionCenterController/DecisionCenterUI (Sec 2.3).
"""
from applications.platform.identity.supabase_authentication_provider import (
    SupabaseAuthenticationProvider,
)
from applications.platform.identity.user import User
from applications.platform.navigation.navigation_builder import NavigationBuilder
from applications.platform.registry.product_registry import Product
from applications.trading_intelligence.bootstrap import (
    _InMemoryProductRegistry,
    _InMemoryWorkspaceRegistry,
    _ResolvedUserAuthenticationProvider,
    build_application,
)
from applications.trading_intelligence.entitlements import TradingIntelligenceEntitlementChecker
from applications.trading_intelligence.product import TRADING_INTELLIGENCE_PRODUCT
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


def test_build_application_constructs_exactly_one_product_registry(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, _InMemoryProductRegistry)

    build_application()

    assert len(calls) == 1


def test_build_application_product_registry_contains_exactly_trading_intelligence(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, _InMemoryProductRegistry)

    build_application()

    registry = calls[0]["self"]
    products = registry.list_products()
    assert products == [TRADING_INTELLIGENCE_PRODUCT]
    assert all(isinstance(product, Product) for product in products)


def test_build_application_constructs_exactly_one_workspace_registry(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, _InMemoryWorkspaceRegistry)

    build_application()

    assert len(calls) == 1


def test_build_application_constructs_exactly_one_entitlement_checker(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, TradingIntelligenceEntitlementChecker)

    build_application()

    assert len(calls) == 1


def test_build_application_constructs_exactly_one_navigation_builder(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, NavigationBuilder)

    build_application()

    assert len(calls) == 1


def test_build_application_get_current_user_is_called_exactly_once_on_the_real_provider(monkeypatch):
    call_count = {"n": 0}
    original = SupabaseAuthenticationProvider.get_current_user

    def counting_get_current_user(self):
        call_count["n"] += 1
        return original(self)

    monkeypatch.setattr(SupabaseAuthenticationProvider, "get_current_user", counting_get_current_user)

    build_application()

    assert call_count["n"] == 1


def test_resolved_user_authentication_provider_returns_the_captured_none_value():
    provider = _ResolvedUserAuthenticationProvider(None)

    assert provider.get_current_user() is None


def test_resolved_user_authentication_provider_returns_a_captured_user_unchanged():
    user = User(user_id="user-001", display_name="Jordan Smith")
    provider = _ResolvedUserAuthenticationProvider(user)

    assert provider.get_current_user() is user


def test_build_application_does_not_raise_with_navigation_wiring_in_place():
    ui = build_application()

    assert isinstance(ui, DecisionCenterUI)


def test_build_application_does_not_pass_navigation_model_to_the_controller(monkeypatch):
    controller_calls = _track_constructor_calls(monkeypatch, DecisionCenterController)

    build_application()

    assert len(controller_calls) == 1
    args, kwargs = controller_calls[0]["args"], controller_calls[0]["kwargs"]
    assert len(args) == 4
    assert kwargs == {}
